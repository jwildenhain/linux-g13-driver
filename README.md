# Linux G13 Driver

Version: **1.1.0**. See [release notes](CHANGELOG.md) and the
[follow-up plan awaiting approval](TODO.md). M2–M4 currently have a reported
scrambled-character issue; M1 system stats are confirmed working.

This repository is a maintained fork of the original G13 Linux driver with an updated structure for Git and a small set of practical improvements, including live LCD system stats on supported firmware.

## Desktop tray app

G13 Control provides four hardware mode profiles (M1/M2/M3/MR), per-screen
colours, G1–G22 key/macro selection, and cached service statistics. M1 keeps the
built-in system display. See [installation, integrations and usage](docs/TRAY.md).

## Notes

- Originally based on the Google Code project layout.
- The driver runs as a userspace process and sends input events via `uinput`.
- LCD-capable builds write live status to the G13 display: CPU, memory, GPU, network and disk usage.
- In LogiFrame mode, `G26`..`G29` are page selectors.
- The joystick is currently mapped as directional keys in this branch.

## Ubuntu 22.04 (and Ubuntu-like) setup

### Requirements

- `libusb-1.0` development package
- `ant` (for GUI jar build)
- Java runtime/JDK (JDK 8+; on Ubuntu 22.04 `default-jdk`/`default-jre` is fine)

Install dependencies:

```bash
sudo apt update
sudo apt install -y git build-essential ant default-jdk default-jre libusb-1.0-0-dev
```

## Build

### 1) Build the C++ driver (required)

From the repository root:

```bash
./build_driver.sh --force
```

This builds `src/Linux-G13-Driver`.

### 2) Build the Java GUI (optional, for editing bindings/macros)

From the repository root:

```bash
cd src
ant
```

The GUI jar is produced in the deploy folder, for example:

- `deploy/Linux-G13_v1.0-r<revision>/Linux-G13-GUI.jar`

## Running

### 1) Generate/update config (`.properties`) files

Run the config tool:

```bash
java -jar deploy/Linux-G13_v1.0-r<revision>/Linux-G13-GUI.jar
```

The GUI creates and saves the config files on first run at:

- `~/.g13/bindings-0.properties` ... `~/.g13/bindings-3.properties`
- `~/.g13/macro-0.properties` and additional macro files as needed

You can also create them manually. Required format is Java properties text:

```properties
# ~/.g13/bindings-0.properties
color=255,255,255
lcd_mode=logiframe
lcd_logiframe_page_count=4
lcd_logiframe_page1_cmd=
lcd_logiframe_page2_cmd=if [ -z "$STEAM_API_KEY" ] || ( [ -z "$STEAM_ID" ] && [ -z "$STEAM_STEAMID" ] ); then printf 'Steam Friends\\nSet STEAM_API_KEY and STEAM_ID/STEAM_STEAMID env vars\\n'; exit 0; fi; if ! command -v curl >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; then printf 'Steam Friends\\nInstall curl and jq\\n'; exit 0; fi; steam_id="${STEAM_ID:-${STEAM_STEAMID:-}}"; friend_ids=$(curl -sf "https://api.steampowered.com/ISteamUser/GetFriendList/v0001/?key=$STEAM_API_KEY&steamid=$steam_id&relationship=friend" | jq -r '.friendslist.friends[]? | .steamid' | tr '\\n' ',' | sed 's/,$//'); if [ -z "$friend_ids" ]; then printf 'Steam Friends\\nNo friends found\\n'; exit 0; fi; online=$(curl -sf "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key=$STEAM_API_KEY&steamids=$friend_ids" | jq -r '.response.players[]? | select((.personastate // 0) > 0) | .personaname' ); count=$(printf '%s\\n' "$online" | sed '/^$/d' | awk 'END {print NR}'); printf 'Steam Friends\\n'; if [ "$count" -eq 0 ]; then printf 'No friends online\\n'; exit 0; fi; printf 'Online: %s\\n' "$count"; printf '%s\\n' "$online" | head -n 3;
lcd_logiframe_page3_cmd=if ! command -v curl >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; then printf 'Token Usage\\nInstall curl and jq\\n'; exit 0; fi; today=$(date +%F); AG_USED=n/a; AG_LIMIT=n/a; if [ -n "$ANTIGRAVITY_USAGE_URL" ] && [ -n "$ANTIGRAVITY_API_KEY" ]; then ag=$(curl -sf --max-time 8 -H "Authorization: Bearer $ANTIGRAVITY_API_KEY" "$ANTIGRAVITY_USAGE_URL"); if [ -n "$ag" ]; then AG_USED=$(printf '%s' "$ag" | jq -r '.used // .tokens_used // .usage // "n/a"'); AG_LIMIT=$(printf '%s' "$ag" | jq -r '.daily_limit // .limit // "n/a"'); fi; fi; GEM_USED=n/a; GEM_LIMIT=n/a; if [ -n "$GEMINI_USAGE_URL" ] && [ -n "$GEMINI_API_KEY" ]; then gem=$(curl -sf --max-time 8 -H "x-goog-api-key: $GEMINI_API_KEY" "$GEMINI_USAGE_URL"); if [ -n "$gem" ]; then GEM_USED=$(printf '%s' "$gem" | jq -r '.used // .tokens_used // .usage // .total_tokens // "n/a"'); GEM_LIMIT=$(printf '%s' "$gem" | jq -r '.daily_limit // .limit // "n/a"'); fi; fi; CX_USED=n/a; CX_LIMIT=n/a; if [ -n "$OPENAI_API_KEY" ]; then openai_usage=$(curl -sf --max-time 8 -H "Authorization: Bearer $OPENAI_API_KEY" "https://api.openai.com/v1/dashboard/billing/usage?start_date=$today&end_date=$today"); openai_sub=$(curl -sf --max-time 8 -H "Authorization: Bearer $OPENAI_API_KEY" "https://api.openai.com/v1/dashboard/billing/subscription"); if [ -n "$openai_usage" ]; then CX_USED=$(printf '%s' "$openai_usage" | jq -r '.total_usage // .total_tokens // .usage.total_tokens // "n/a"'); fi; if [ -n "$openai_sub" ]; then CX_LIMIT=$(printf '%s' "$openai_sub" | jq -r '.hard_limit_usd // "n/a"'); fi; fi; printf 'Token Usage\\n'; printf 'Antigravity: %s/%s\\n' "$AG_USED" "$AG_LIMIT"; printf 'Gemini: %s/%s\\n' "$GEM_USED" "$GEM_LIMIT"; printf 'Codex/GPT: %s/%s\\n' "$CX_USED" "$CX_LIMIT";
lcd_logiframe_page4_cmd=
lcd_logiframe_page1_color=0,128,255
lcd_logiframe_page2_color=255,153,0
lcd_logiframe_page3_color=0,200,64
lcd_logiframe_page4_color=255,64,64
G1=p,k.3
G2=p,k.4
...
G22=m,0,1
```

- `p,k.<linux_keycode>` = pass-through keycode
- `m,<macro_id>,<repeat_count>` = macro sequence playback

`macro-*.properties` examples use:

```properties
name=ALT-TAB
sequence=kd.56,kd.15,d.20,ku.15,ku.56
id=0
```

### 2) Start driver

The supported way to run the driver is as a systemd **user** service, managed
with `scripts/g13ctl`. This runs the driver as you (not root), so it reads
`~/.g13`, and it starts again automatically at login and after a replug.

Install device permissions once (needs root). This re-emits the udev `add`
events itself, so a physical replug is usually not needed, and it reports
whether you actually gained access:

```bash
sudo ./scripts/g13ctl udev-install
```

Install and start the service:

```bash
./scripts/g13ctl install
```

Day to day:

```bash
g13ctl start
```

```bash
g13ctl stop
```

```bash
g13ctl status
```

```bash
g13ctl logs -f
```

`g13ctl status` reports the unit state, whether the G13 is attached, whether the
USB and `uinput` nodes are writable, and which binary and bindings are in use.
`g13ctl doctor` adds troubleshooting hints. Full command list: `g13ctl help`.

#### Manual foreground run

Useful for debugging; not needed if the service is installed:

```bash
sudo -E ./src/Linux-G13-Driver
```

`-E` preserves your environment so the driver reads `~/.g13` for your user.

### 3) Config changes while running

The driver reloads only on top-row bindings change keys (when supported by your build flow). For reliable results after edits, restart the driver.

### Mode-key LEDs (M1-M4 / MR)

Mode keys are controlled by the `mod` property in `bindings-*.properties`.

- `mod=1` enables M1
- `mod=2` enables M2
- `mod=4` enables M3
- `mod=8` enables M4

You can combine values by adding them together (for example, `mod=13` lights M1, M3 and M4).

Example:
```properties
# enable only M1 and M3
mod=5
```

This does not control LCD color; it controls the per-mode-button background LEDs used for profile mode indicators.

## Service management

The service is a systemd **user** unit, `g13-driver.service`. User scope is
deliberate: the driver reads bindings from `$HOME/.g13`, and LCD LogiFrame page
commands run as you.

### What `g13ctl install` puts where

| Path | Purpose |
| --- | --- |
| `~/.local/bin/g13ctl` | The control script itself |
| `~/.config/systemd/user/g13-driver.service` | The unit |
| `~/.config/g13/g13-driver.env` | Driver path and page-command environment |
| `/etc/udev/rules.d/91-g13.rules` | Device access (installed by `udev-install`) |

`G13_DRIVER_BIN` in the env file points at your build tree, so a rebuild is
picked up by `g13ctl restart` with no reinstall.

### Environment for LCD page commands

A user service does not inherit your interactive shell, so exports in
`.bashrc` are not visible to `lcd_logiframe_pageN_cmd`. Put anything those
commands need into `~/.config/g13/g13-driver.env`:

```ini
STEAM_API_KEY=xxxxxxxx
STEAM_ID=7656119xxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxx
```

The file is `systemd` syntax, not shell: no `export`, no `$VAR` expansion, and
quote values containing spaces. `g13ctl install` creates it mode `0600`.
Apply changes with `g13ctl restart`.

### Behaviour

- **Device not plugged in, or not writable yet:** `g13ctl run` waits and polls
  rather than exiting, so neither an absent G13 nor a pending permission fix
  becomes a restart loop in the journal. The reason is logged once, and the
  driver starts on its own within a couple of seconds of the device becoming
  usable — no `g13ctl restart` needed after a replug.
- **Device unplugged while running:** the driver exits on the USB read error,
  and systemd restarts the unit after `RestartSec=5`, which returns it to the
  wait loop until you plug back in.
- **Stop:** systemd sends `SIGTERM`; the driver clears its run flag, unwinds the
  read loop, resets the LED and releases the USB interface.

### Removing it

```bash
g13ctl uninstall
```

This stops, disables and removes the unit. The env file, `~/.local/bin/g13ctl`
and the udev rule are left in place; delete them by hand if you want them gone.

## Keymap database and atlas

`data/g13-keymaps.db` is a SQLite database of published G13 keymaps collected
from public repositories, normalised into one schema. `data/g13-keymap-atlas.html`
is a self-contained viewer: pick a keymap from the dropdown and see each binding
drawn on the button it belongs to.

### Rebuilding

```bash
python3 tools/build_keymap_db.py <downloaded-keymaps-dir>
```

```bash
python3 tools/build_keymap_viewer.py
```

### What is in it

| Source | Format | Profiles |
| --- | --- | --- |
| `Lordbooker/linux-g13-driver` | `.properties` | 4 |
| `ecraven/g13` | g13d `.bind` | 5 game profiles |
| `brittyazel/g13d` | g13d `.bind` | 1 default |
| `RunicLuke/logitech-g13` | JSON | 3 |
| your own `~/.g13` | `.properties` | 4 |

Three incompatible formats are mapped onto one set of canonical button labels
(`G1`..`G22`, `M1`..`MR`, `L1`..`L4`, `STICK_UP`..`STICK_DOWN`), so the same
button means the same thing regardless of which project a keymap came from.

Button geometry comes from the arrangement map in
`src/java/com/gupta/g13/Key.java`, which is why the overlay lines up with
`g13.gif`. Two quirks are preserved and flagged rather than silently fixed:

- `Key.java` lists key code 25 twice (the under-screen `L1` and the right-hand
  round button), so Java's `getKeyFor()` can never return the second shape. The
  viewer draws it dashed and marks it as a duplicate.
- Codes 36-39 carry leftover enum names (`UNDEF3`, `LIGHT`, `LIGHT2`,
  `MISC_TOGGLE`) but are the four joystick directions in practice - the stock
  bindings map them to W/A/D/S. They are reported as `STICK_*`.

LCD page commands are deliberately **not** imported, so no shell (or anyone's
API keys) ends up in the database.

### Licensing

`brittyazel/g13d` and `RunicLuke/logitech-g13` are MIT. `Lordbooker/linux-g13-driver`
and `ecraven/g13` declare no licence, which means all rights reserved by default -
fine to read locally, but do not redistribute those keymaps without asking.

## Linux-G13-Driver display output

The driver renders five lines and refreshes approximately every second:

- `CPU xx% yyC` (highest CPU die/package temperature)
- `MEM xx% NIC yyC` (active Ethernet PHY temperature when exposed by hwmon)
- `GPU xx% yyC` (or `GPU n/a`)
- `NET xx` (throughput in B/s / KB/s / MB/s)
- `ROOT xx% yyC Rxx Wxx` (root filesystem, NVMe temperature and I/O)

Temperature fields are omitted when the corresponding sensor is unavailable;
other unavailable values continue to show `n/a`.

## LCD source modes (stats / fifo / logiframe)

The driver supports:

- `lcd_mode=stats` (default): built-in live usage stats.
- `lcd_mode=fifo` (legacy FIFO path): read lines from `lcd_path`/`lcd_fifo`.
- `lcd_mode=logiframe`: render command output per page and switch with `G26`..`G29`.

For `logiframe` mode, configure:

```properties
lcd_mode=logiframe
lcd_logiframe_page_count=4
lcd_logiframe_page1_cmd=...
lcd_logiframe_page2_cmd=...
lcd_logiframe_page3_cmd=...
lcd_logiframe_page4_cmd=  # optional
lcd_logiframe_page1_color=0,128,255
lcd_logiframe_page2_color=255,153,0
lcd_logiframe_page3_color=0,200,64
lcd_logiframe_page4_color=255,64,64
```

Notes:

- `G26` -> page 1, `G27` -> page 2, `G28` -> page 3, `G29` -> page 4.
- If a logiframe command emits no output, fallback helper lines are shown with the property name.
- Existing FIFO behavior remains unchanged; if FIFO is enabled and no cache is available, stats are shown.

### FIFO update format

```bash
mkdir -p /tmp
mkfifo /tmp/g13_lcd_fifo
echo "TITLE" >> /tmp/g13_lcd_fifo
echo "CPU: 42%" >> /tmp/g13_lcd_fifo
echo "MEM: 66%" >> /tmp/g13_lcd_fifo
echo "NET: 12 MB/s" >> /tmp/g13_lcd_fifo
echo "DSK: 55%" >> /tmp/g13_lcd_fifo
```

### Lordbooker / DBus-pluggable applet integration

A pluggable DBus applet can be adapted by emitting LCD text to the configured FIFO.
Minimal pattern:

```bash
#!/usr/bin/env bash
set -euo pipefail
FIFO="${LCD_FIFO:-/tmp/g13_lcd_fifo}"

# Replace this block with your DBus subscriber/formatter logic.
render_lcd() {
  {
    printf '%s\n' "${1:-jgtans}"
    printf '%s\n' "${2:-status}"
    printf '%s\n' "${3:-active}"
    printf '%s\n' "${4:-$(date +%H:%M:%S)}"
    printf '%s\n' "${5:- }"
  } > "$FIFO"
}

# Example static render
render_lcd "jgtans" "applet" "connected" "$(date +%H:%M:%S)" "  "
```

If your applet updates frequently, rewrite only changed lines and keep writes non-blocking.

For copy-pasteable producer scripts, see:
- `scripts/lcd-fifo-writer.sh`
- `scripts/lcd-fifo-writer-dbus.sh`

## One-command installation of DBus FIFO service

After cloning the repo, run from the repository root:

```bash
./scripts/install-lcd-fifo-writer-dbus-service.sh
```

The installer copies:

- `scripts/lcd-fifo-writer-dbus.sh` -> `~/.local/bin/lcd-fifo-writer-dbus.sh`
- `scripts/lcd-fifo-writer-dbus.env.example` -> `~/.config/g13/lcd-fifo-writer-dbus.env`
- `scripts/lcd-fifo-writer-dbus.service` -> `~/.config/systemd/user/g13-lcd-fifo-writer-dbus.service`

It also sets `SCRIPT_PATH` in the env file and enables/runs the user service.

Optional:
- `--dry-run`: print planned actions without writing files or touching systemd.
- `--no-enable`: install files only and skip auto-start.
- `--help`: show options.


### Quick verification

After install, run:

```bash
systemctl --user status --no-pager g13-lcd-fifo-writer-dbus.service
journalctl --user -u g13-lcd-fifo-writer-dbus.service -f
```
