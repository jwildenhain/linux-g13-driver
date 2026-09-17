"""DDC/CI monitor module: LCD pages and key actions for a DDC display.

Optional. Everything degrades to a clear message when no DDC/CI display is
present, so the tray and driver work unchanged on machines without one.

Two rendering paths, because they have different limits:

* ``text_lines()`` feeds the normal tray provider pipeline, which sanitises to
  ASCII and caps at 26 columns by 5 rows. Bars are drawn with '#' and '-'.
* ``render_pbm()`` returns a 160x43 ASCII PBM for use as an
  ``lcd_logiframe_pageN_cmd`` via the "Keep existing command" screen source.
  This bypasses the tray's text pipeline and gives real graphical bars.

Monitors are addressed by EDID serial number (``ddcutil --sn``), never by I2C
bus number: bus numbering is not stable across reboots or driver reloads.
"""

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

CACHE = Path(os.environ.get('XDG_CACHE_HOME', Path.home()/'.cache'))/'g13'
DETECT_CACHE = CACHE/'ddc.json'
DETECT_MAX_AGE = 24 * 3600

BRIGHTNESS, CONTRAST, VOLUME, POWER, SENSOR = 0x10, 0x12, 0x62, 0xD6, 0x66
INPUT = 0x60

# Dell offsets the standard MCCS ambient-light-sensor values by 0x80.
# Plain MCCS uses 0x01/0x02; accept both when deciding whether it is on.
SENSOR_OFF, SENSOR_ON = 0x81, 0x82
SENSOR_ON_VALUES = (0x02, 0x82)

BARS = [('BRI', BRIGHTNESS), ('CON', CONTRAST), ('VOL', VOLUME)]

DDCUTIL_CANDIDATES = ['ddcutil', '/usr/local/bin/ddcutil', '/usr/bin/ddcutil']


class NoDisplay(RuntimeError):
    """No DDC/CI capable display is available."""


def ddcutil_path():
    """Locate ddcutil. ``G13_DDCUTIL`` wins, for local builds that are not
    installed on PATH; put it in ~/.config/g13/g13-driver.env so the driver's
    page commands inherit it."""
    override = os.environ.get('G13_DDCUTIL')
    if override and os.access(override, os.X_OK):
        return override
    for cand in DDCUTIL_CANDIDATES:
        found = shutil.which(cand) if '/' not in cand else (
            cand if os.access(cand, os.X_OK) else None)
        if found:
            return found
    return None


def _run(args, timeout=30):
    """ddcutil, decoded leniently: some monitors emit invalid UTF-8 in their
    capabilities string (Dell packs multi-byte vendor values), which would
    otherwise raise UnicodeDecodeError."""
    try:
        proc = subprocess.run(args, capture_output=True, text=True,
                              errors='replace', timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout if proc.returncode == 0 or proc.stdout else None


def detect(refresh=False):
    """Return {'serial','model','bus'} for the first DDC/CI display, or None.

    Cached: `ddcutil detect` takes one to two seconds, far too slow for an LCD
    page that refreshes every second.
    """
    if not refresh and DETECT_CACHE.is_file():
        try:
            cached = json.loads(DETECT_CACHE.read_text())
            if time.time() - cached.get('at', 0) < DETECT_MAX_AGE:
                return cached.get('display')
        except (OSError, ValueError):
            pass

    binary = ddcutil_path()
    display = None
    if binary:
        out = _run([binary, 'detect']) or ''
        cur = {}
        for line in out.splitlines():
            if re.match(r'^Display \d+', line):
                cur = {}
            m = re.match(r'\s+(Model|Serial number|I2C bus):\s+(.*?)\s*$', line)
            if m:
                key, val = m.group(1), m.group(2)
                cur['model' if key == 'Model' else
                    'serial' if key == 'Serial number' else 'bus'] = (
                        val.replace('/dev/i2c-', ''))
                if cur.get('serial') and cur.get('model'):
                    display = cur
                    break

    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        DETECT_CACHE.write_text(json.dumps(
            {'at': time.time(), 'display': display}))
    except OSError:
        pass
    return display


def available():
    return detect() is not None


class Backend:
    """Talks to the monitor, preferring a ddcmond session daemon when present.

    DDC/CI writes take around 50ms and concurrent access can wedge a panel
    until it is power cycled, so if something already owns the bus we go
    through it rather than competing with it.
    """

    DBUS_NAME = 'org.ddcmon.Daemon1'
    DBUS_PATH = '/org/ddcmon/Daemon1'

    def __init__(self):
        self._bus = None
        self._display = detect()
        if self._display is None:
            raise NoDisplay('no DDC/CI display detected')
        self._binary = ddcutil_path()
        self._connect_dbus()

    def _connect_dbus(self):
        try:
            import gi
            gi.require_version('Gio', '2.0')
            from gi.repository import Gio, GLib
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            names = bus.call_sync(
                'org.freedesktop.DBus', '/org/freedesktop/DBus',
                'org.freedesktop.DBus', 'ListNames', None, None,
                Gio.DBusCallFlags.NONE, 2000, None).unpack()[0]
            if self.DBUS_NAME in names:
                self._bus, self._glib = bus, GLib
        except Exception:
            self._bus = None

    def get(self, code):
        """Return (value, maximum) or None."""
        if self._bus is not None:
            try:
                res = self._bus.call_sync(
                    self.DBUS_NAME, self.DBUS_PATH, self.DBUS_NAME,
                    'GetFeature', self._glib.Variant('(u)', (code,)), None,
                    0, 4000, None)
                got = json.loads(res.unpack()[0])
                if got.get('ok'):
                    return got['value'], got.get('max') or 100
                return None
            except Exception:
                self._bus = None       # fall through to ddcutil

        out = _run([self._binary, '--sn', self._display['serial'],
                    '--brief', 'getvcp', f'{code:02X}'])
        if not out:
            return None
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[0] == 'VCP':
                try:
                    if parts[2] == 'C':
                        value, maximum = int(parts[3]), int(parts[4])
                        # Vendor features can report an impossible ceiling
                        # (Dell's volume reads back 0xFF64); treat as 0-100.
                        if maximum <= 0 or maximum > 255:
                            maximum = 100
                        return value, maximum
                    if parts[2] in ('SNC', 'CNC'):
                        return int(parts[3].lstrip('xX'), 16), 255
                except (ValueError, IndexError):
                    return None
        return None

    def set(self, code, value):
        if self._bus is not None:
            try:
                self._bus.call_sync(
                    self.DBUS_NAME, self.DBUS_PATH, self.DBUS_NAME,
                    'SetFeature', self._glib.Variant('(uu)', (code, value)),
                    None, 0, 4000, None)
                return True
            except Exception:
                self._bus = None

        return _run([self._binary, '--sn', self._display['serial'],
                     'setvcp', f'{code:02X}', str(value)]) is not None

    @property
    def display(self):
        return self._display


def read_state(backend=None, allow_asleep=False):
    """Return {code: (value, max)} for the bar features plus the sensor.

    Returns {} when the display is asleep unless `allow_asleep` is set. A DDC
    read can wake this panel, so a page refreshing on a timer would otherwise
    hold the monitor awake, or bounce it between sleeping and waking.
    """
    if not allow_asleep and asleep():
        return {}
    backend = backend or Backend()
    state = {}
    for code in [c for _, c in BARS] + [SENSOR]:
        got = backend.get(code)
        if got:
            state[code] = got
    return state


def _percent(got):
    if not got:
        return 0
    value, maximum = got
    return 0 if maximum <= 0 else max(0, min(100, round(value * 100 / maximum)))


def text_lines(state=None, display=None):
    """ASCII bars for the tray pipeline (26 columns, 5 rows maximum)."""
    if state is None:
        try:
            backend = Backend()
            state, display = read_state(backend), backend.display
        except NoDisplay:
            return ['DDC monitor', 'No DDC/CI display found',
                    'Check ddcutil detect', 'and i2c group membership']
        if not state:
            return ['DDC monitor', f'Display {display_state().lower()}',
                    'Not polling while asleep']
    width = 14
    lines = []
    for label, code in BARS:
        pct = _percent(state.get(code))
        filled = round(width * pct / 100)
        lines.append(f'{label} [{"#" * filled}{"-" * (width - filled)}]{pct:4d}')
    sensor = state.get(SENSOR)
    auto = 'ON' if sensor and sensor[0] in SENSOR_ON_VALUES else 'OFF'
    model = (display or {}).get('model', 'Monitor')
    lines.append(f'{model[:17]:<17} AUTO {auto}')
    return lines


def render_pbm(state=None, display=None, width=160, height=43):
    """160x43 ASCII PBM with graphical bars, for lcd_logiframe_pageN_cmd.

    The driver's parser reads one whitespace-separated token per pixel, so
    pixels are emitted spaced, not packed into solid rows.
    """
    from PIL import Image, ImageDraw, ImageFont

    if state is None:
        backend = Backend()
        state, display = read_state(backend), backend.display
    if not state:
        # Nothing was read (asleep, or unreachable). Draw a static page rather
        # than three empty bars, which would misreport the monitor as at zero.
        img = Image.new('1', (width, height), 0)
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        draw.text((0, 8), f'Display {display_state().lower()}', fill=1,
                  font=font)
        draw.text((0, 22), 'not polling while asleep', fill=1, font=font)
        px = img.load()
        rows = [' '.join('1' if px[x, y] else '0' for x in range(width))
                for y in range(height)]
        return f'P1\n{width} {height}\n' + '\n'.join(rows) + '\n'

    img = Image.new('1', (width, height), 0)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    bar_x0, bar_x1 = 26, width - 34

    for i, (label, code) in enumerate(BARS):
        y = i * 11 + 1
        draw.text((0, y), label, fill=1, font=font)
        pct = _percent(state.get(code))
        draw.rectangle([bar_x0, y, bar_x1, y + 7], outline=1, fill=0)
        span = bar_x1 - bar_x0 - 2
        filled = round(span * pct / 100)
        if filled > 0:
            draw.rectangle([bar_x0 + 1, y + 2, bar_x0 + 1 + filled, y + 5],
                           outline=1, fill=1)
        draw.text((bar_x1 + 5, y), f'{pct:3d}', fill=1, font=font)

    sensor = state.get(SENSOR)
    auto = 'ON' if sensor and sensor[0] in SENSOR_ON_VALUES else 'OFF'
    model = (display or {}).get('model', 'Monitor')
    draw.text((0, height - 11), f'{model[:16]:<16} AUTO {auto}', fill=1,
              font=font)

    px = img.load()
    rows = [' '.join('1' if px[x, y] else '0' for x in range(width))
            for y in range(height)]
    return f'P1\n{width} {height}\n' + '\n'.join(rows) + '\n'


def display_state():
    """Return 'On', 'Off', 'Standby', 'Suspend' or 'Unknown'.

    Uses `xset q`, not /sys/class/drm/*/dpms: under the nvidia proprietary
    driver the sysfs property reports Off while the display is plainly awake,
    because modesetting does not go through DRM there.
    """
    out = _run(['xset', 'q'], timeout=5) or ''
    for line in out.splitlines():
        low = line.strip().lower()
        if low.startswith('monitor is'):
            word = low.replace('monitor is', '').strip().strip('.')
            if word.startswith('in '):
                word = word[3:]
            return word.capitalize() or 'Unknown'
    return 'Unknown'


def asleep():
    return display_state() not in ('On', 'Unknown')


def _x(args):
    """Run an X client command, ignoring failures (there may be no display)."""
    if not os.environ.get('DISPLAY'):
        return False
    try:
        return subprocess.run(args, capture_output=True,
                              timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def connected_outputs():
    out = _run(['xrandr', '--query'], timeout=10) or ''
    return [line.split()[0] for line in out.splitlines()
            if ' connected' in line]


def wake(backend=None, hard=False):
    """Bring the display back from sleep.

    Order matters. A blanked output usually means the graphics driver has
    dropped the link, and with DisplayPort the DDC/CI AUX channel goes with it
    -- so a VCP power-on cannot be delivered until the link is back. Restore
    the output first, then nudge the panel over DDC.

    `hard` additionally cycles the output off and on, which forces link
    retraining for a monitor that stays asleep even once the signal returns.
    """
    steps = []
    if _x(['xset', 'dpms', 'force', 'on']):
        steps.append('dpms-on')

    if hard:
        for output in connected_outputs():
            if _x(['xrandr', '--output', output, '--off']):
                time.sleep(1.0)
            for attempt in range(3):
                if _x(['xrandr', '--output', output, '--auto']):
                    steps.append(f'recycled {output}')
                    break
                time.sleep(1.0)
            else:
                steps.append(f'FAILED to restore {output}')

    try:
        backend = backend or Backend()
        if backend.set(POWER, 0x01):
            steps.append('vcp-d6-01')
    except (NoDisplay, Exception):
        steps.append('ddc-unreachable')

    return 'wake: ' + (', '.join(steps) or 'nothing to do')


def act(action, delta=5, backend=None):
    """Perform a key action. Returns a short status string."""
    backend = backend or Backend()

    if action in ('wake', 'wake-hard'):
        return wake(backend, hard=action == 'wake-hard')

    if action == 'auto':
        got = backend.get(SENSOR)
        on = bool(got and got[0] in SENSOR_ON_VALUES)
        backend.set(SENSOR, SENSOR_OFF if on else SENSOR_ON)
        return f'auto {"off" if on else "on"}'

    if action == 'input':
        # `delta` carries the input value here (e.g. 0x19). Switching inputs is
        # reversible over DDC -- the panel keeps answering on the AUX channel
        # while displaying another source -- but if the monitor's USB hub
        # follows the input, the keyboard driving this command moves with it.
        backend.set(INPUT, delta)
        return f'input 0x{delta:02X}'

    codes = {'brightness': BRIGHTNESS, 'contrast': CONTRAST, 'volume': VOLUME}
    if action not in codes:
        raise ValueError(f'unknown action {action!r}')
    code = codes[action]

    # With the monitor's own ambient light sensor active it overrides a manual
    # brightness change within seconds, which makes the keys appear broken.
    if code == BRIGHTNESS:
        got = backend.get(SENSOR)
        if got and got[0] in SENSOR_ON_VALUES:
            backend.set(SENSOR, SENSOR_OFF)

    got = backend.get(code)
    if not got:
        raise RuntimeError(f'cannot read {action}')
    value = max(0, min(got[1], got[0] + delta))
    backend.set(code, value)
    return f'{action} {value}'


def log_action(message):
    """Append a timestamped line to the action log.

    Key actions run from a desktop hotkey with no terminal attached, so this is
    the only way to tell a binding that never fired from one that fired and
    failed.
    """
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        with (CACHE/'ddc-key.log').open('a') as fh:
            fh.write(f'{time.strftime("%F %T")}  {message}\n')
    except OSError:
        pass
