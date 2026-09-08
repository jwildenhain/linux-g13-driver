#!/usr/bin/python3
"""Native GTK configuration window with an Ayatana system tray indicator."""
import copy
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import threading

from g13_config import Config, SOURCES, DEFAULT_CODES, atomic_write
from g13_providers import render


def main(on_ready=None):
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('AyatanaAppIndicator3', '0.1')
    from gi.repository import Gtk, Gdk, GLib, AyatanaAppIndicator3 as Indicator

    config = Config()
    config.cache.mkdir(parents=True, exist_ok=True)
    lock = (config.cache / 'tray.lock').open('w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print('G13 tray is already running; open Settings from the panel icon.')
        return

    class Tray:
        def __init__(self):
            self.busy = False
            self.keypad = None
            self.active_data = copy.deepcopy(config.data)
            self.window = Gtk.Window(title='G13 Control')
            self.window.set_default_size(780, 690)
            self.window.connect('delete-event', self.hide)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=18)
            self.window.add(box)
            title = Gtk.Label(xalign=0)
            title.set_markup('<big><b>G13 Control</b></big>  •  Profiles, lighting and live screens')
            box.pack_start(title, False, False, 0)
            note = Gtk.Label(label='M buttons select key modes; L1–L4 select screens within each mode. M1/L1 keeps system stats. M4 uses MR.', xalign=0)
            note.set_line_wrap(True)
            box.pack_start(note, False, False, 0)
            notebook = Gtk.Notebook()
            box.pack_start(notebook, True, True, 0)
            self.controls = []
            self.page_controls = []
            self.keymaps = []
            for i in range(4):
                page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=12)
                notebook.append_page(page, Gtk.Label(label=f'M{i+1}' + (' · System' if i == 0 else '')))
                if i == 0:
                    for name, label in [('stats_poll_seconds', 'Sample every (seconds)'), ('stats_average_seconds', 'Rolling average (seconds)')]:
                        setting_row = Gtk.Box(spacing=10)
                        setting_row.pack_start(Gtk.Label(label=label, xalign=0), True, True, 0)
                        spinner = Gtk.SpinButton.new_with_range(1, 60, 1)
                        spinner.set_value(config.data[name])
                        setattr(self, name, spinner)
                        setting_row.pack_start(spinner, False, False, 0)
                        page.pack_start(setting_row, False, False, 0)
                screen_tabs = Gtk.Notebook()
                page.pack_start(screen_tabs, False, False, 0)
                mode_controls = []
                for screen_index in range(4):
                    screen_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin=8)
                    screen_tabs.append_page(screen_box, Gtk.Label(label=f'L{screen_index+1}'))
                    screen = config.data['screen_pages'][i][screen_index]
                    row = Gtk.Box(spacing=10)
                    source = Gtk.ComboBoxText()
                    choices = SOURCES
                    for item in choices: source.append_text(item)
                    source.set_active(choices.index(screen['source']))
                    source.set_sensitive(not (i == 0 and screen_index == 0))
                    row.pack_start(Gtk.Label(label='Screen'), False, False, 0)
                    row.pack_start(source, True, True, 0)
                    color = Gtk.ColorButton()
                    rgba = Gdk.RGBA()
                    rgba.red, rgba.green, rgba.blue = [int(v)/255 for v in screen['color'].split(',')]
                    rgba.alpha = 1
                    color.set_rgba(rgba)
                    color.set_title(f'M{i+1} / L{screen_index+1} backlight colour')
                    row.pack_start(color, False, False, 0)
                    screen_box.pack_start(row, False, False, 0)
                    text = Gtk.Entry(text=screen.get('text','').replace('\n', ' | '))
                    text.set_placeholder_text('Custom screen: separate up to five lines with |')
                    file = Gtk.Entry(text=screen.get('file',''))
                    file.set_placeholder_text('Path to Antigravity / other tool text export')
                    screen_box.pack_start(text, False, False, 0)
                    screen_box.pack_start(file, False, False, 0)
                    def source_changed(combo, text=text, file=file):
                        text.set_sensitive(combo.get_active_text() == 'Custom text')
                        file.set_sensitive(combo.get_active_text() == 'Antigravity / text file')
                    source.connect('changed', source_changed)
                    source_changed(source)
                    mode_controls.append((source, color, text, file))
                self.page_controls.append(mode_controls)
                self.controls.append(mode_controls[0])
                page.pack_start(Gtk.Label(label='G-key bindings  ·  choose a key, existing macro, or disable', xalign=0), False, False, 0)
                scroll = Gtk.ScrolledWindow()
                scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
                page.pack_start(scroll, True, True, 0)
                grid = Gtk.Grid(column_spacing=12, row_spacing=8, margin=4)
                scroll.add(grid)
                mapping = {}
                key_names = self.key_names()
                macros = self.macros()
                for key in range(22):
                    label = Gtk.Label(label=f'G{key+1}', xalign=0)
                    combo = Gtk.ComboBoxText()
                    combo.append('', 'Disabled')
                    for code, name in key_names:
                        combo.append(f'p,k.{code}', name)
                    for ident, name in macros:
                        combo.append(f'm,{ident},1', 'Macro: ' + name)
                    value = config.raw[i].get(f'G{key}', f'p,k.{DEFAULT_CODES[key]}')
                    if value.startswith('p,') and not value.startswith('p,k.'):
                        value = 'p,k.' + value[2:]
                    if value == 'none': value = ''
                    if not combo.set_active_id(value):
                        combo.append(value, 'Existing: ' + value)
                        combo.set_active_id(value)
                    col, r = (key % 2)*2, key//2
                    grid.attach(label, col, r, 1, 1)
                    grid.attach(combo, col+1, r, 1, 1)
                    mapping[f'G{key}'] = combo
                self.keymaps.append(mapping)
            connections = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=12)
            notebook.append_page(connections, Gtk.Label(label='Connections'))
            info = Gtk.Label(label='Read-only stats, refreshed every 60 seconds. API keys are stored locally in a file readable only by you.\nClaude/OpenAI API totals are organisation usage, not your personal subscription allowance.\nDiscord requires your bot to be a member of the selected server.\nCodex local reads the latest session’s token counters without an API key.\nAntigravity: select a local text export; no verified public quota endpoint.', xalign=0)
            info.set_line_wrap(True)
            connections.pack_start(info, False, False, 0)
            self.credentials = {}
            for name, label in [('STEAM_API_KEY','Steam Web API key'), ('STEAM_ID','Steam ID (64-bit)'), ('DISCORD_BOT_TOKEN','Discord bot token'), ('DISCORD_GUILD_ID','Discord server ID'), ('OPENAI_ADMIN_KEY','OpenAI organisation admin key'), ('ANTHROPIC_ADMIN_KEY','Claude organisation admin key'), ('ANTIGRAVITY_API_KEY','Antigravity API key (stored only)')]:
                row = Gtk.Box(spacing=12)
                lab = Gtk.Label(label=label, xalign=0, width_chars=28)
                entry = Gtk.Entry(text=config.data['credentials'].get(name,''))
                entry.set_visibility(name.endswith('_ID'))
                row.pack_start(lab, False, False, 0)
                row.pack_start(entry, True, True, 0)
                connections.pack_start(row, False, False, 0)
                self.credentials[name] = entry
            self.preview = Gtk.Label(label='Save & apply to activate screen changes.', xalign=0, selectable=True)
            self.preview.set_line_wrap(True)
            preview_scroll = Gtk.ScrolledWindow()
            preview_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            preview_scroll.set_min_content_height(80)
            preview_scroll.add(self.preview)
            connections.pack_start(preview_scroll, True, True, 0)
            brightness_note = Gtk.Label(label='Hold the round left LCD button to sweep brightness up/down; release to keep it.', xalign=0)
            brightness_note.set_line_wrap(True)
            box.pack_start(brightness_note, False, False, 0)
            self.status = Gtk.Label(label='Ready · Existing settings are preserved until you save.', xalign=0)
            self.status.set_line_wrap(True)
            box.pack_start(self.status, False, False, 0)
            actions = Gtk.Box(spacing=10)
            box.pack_start(actions, False, False, 0)
            for label, callback in [('Configure buttons…', self.open_keypad), ('Save & apply', self.save), ('Refresh stats', self.refresh), ('Hide to tray', lambda *_: self.window.hide())]:
                button = Gtk.Button(label=label)
                button.connect('clicked', callback)
                actions.pack_start(button, False, False, 0)
            self.indicator = Indicator.Indicator.new('g13-control', 'input-gaming', Indicator.IndicatorCategory.HARDWARE)
            self.indicator.set_status(Indicator.IndicatorStatus.ACTIVE)
            self.indicator.set_label('G13', 'G13')
            menu = Gtk.Menu()
            for label, callback in [('Configure G13 buttons…', self.open_keypad), ('G13 settings', lambda *_: self.window.present()), ('Refresh display stats', self.refresh), ('Start driver', lambda *_: self.service('start')), ('Stop driver', lambda *_: self.service('stop')), ('Quit tray', lambda *_: Gtk.main_quit())]:
                item = Gtk.MenuItem(label=label)
                item.connect('activate', callback)
                menu.append(item)
            from g13_dialogs import CONNECTIONS, credentials_dialog
            credentials_menu = Gtk.Menu()
            for source in CONNECTIONS:
                item = Gtk.MenuItem(label=source + ' credentials…')
                item.connect('activate', lambda _, source=source: credentials_dialog(self, config, source))
                credentials_menu.append(item)
            item = Gtk.MenuItem(label='Credentials')
            item.set_submenu(credentials_menu)
            menu.prepend(item)
            menu.show_all()
            self.indicator.set_menu(menu)
            self.window.show_all()
            if '--background' in sys.argv: self.window.hide()
            self.refresh()
            GLib.timeout_add_seconds(60, self.refresh)

        def open_keypad(self, *_):
            from g13_dialogs import KeypadWindow
            if self.keypad is None:
                self.keypad = KeypadWindow(self, config)
                self.keypad.connect('destroy', lambda *_: setattr(self, 'keypad', None))
            self.keypad.present()

        def key_names(self):
            import re
            header = Path('/usr/include/linux/input-event-codes.h')
            if header.exists():
                keys = [(int(code), name.replace('KEY_', '').replace('_',' ').title()) for name, code in re.findall(r'^#define\s+(KEY_\w+)\s+(\d+)\b', header.read_text(), re.M) if 1 <= int(code) <= 255]
                return sorted(keys, key=lambda item:item[1])
            return [(i, f'Linux keycode {i}') for i in range(1,256)]

        def macros(self):
            from g13_config import properties
            return [(p.stem[6:], properties(p).get('name', p.stem)) for p in sorted(config.bindings.glob('macro-*.properties'))]

        def hide(self, *_):
            self.window.hide()
            return True

        def service(self, action):
            def work():
                try:
                    result = subprocess.run(['systemctl','--user',action,'g13-driver.service'], capture_output=True, text=True, timeout=20)
                    message = f'Driver: {action} succeeded.' if result.returncode == 0 else 'Driver action failed: ' + result.stderr[:240]
                except Exception as e:
                    message = 'Driver action failed: ' + type(e).__name__
                GLib.idle_add(self.status.set_text, message)
            threading.Thread(target=work, daemon=True).start()

        def save(self, *_):
            try:
                for i, mode_controls in enumerate(self.page_controls):
                    for page, (source, color, text, file) in enumerate(mode_controls):
                        rgba = color.get_rgba()
                        old = config.data['screen_pages'][i][page]
                        config.data['screen_pages'][i][page] = dict(old, source=source.get_active_text(), color=','.join(str(round(v*255)) for v in [rgba.red,rgba.green,rgba.blue]), text=text.get_text().replace('|','\n'), file=file.get_text())
                config.data['stats_poll_seconds'] = self.stats_poll_seconds.get_value_as_int()
                config.data['stats_average_seconds'] = self.stats_average_seconds.get_value_as_int()
                config.data['credentials'] = {name:entry.get_text().strip() for name,entry in self.credentials.items()}
                backup = config.save([{key:combo.get_active_id() for key,combo in mapping.items()} for mapping in self.keymaps])
                self.active_data = copy.deepcopy(config.data)
                # Provide an immediate valid display, even before network results.
                for i, pages in enumerate(self.active_data['screen_pages']):
                    for page, screen in enumerate(pages):
                        if screen['source'] not in ('Keep existing command', 'System stats'):
                            atomic_write(config.cache / f'page-{i}-{page}.txt', screen['source'] + '\nRefreshing...\n')
                self.status.set_text('Saved. Backup: ' + str(backup))
                self.refresh()
                self.service('restart')
            except Exception as e:
                self.status.set_text('Not applied: ' + str(e))

        def refresh(self, *_):
            if self.busy: return True
            self.busy = True
            snapshot = copy.deepcopy(self.active_data)
            def work():
                previews = []
                try:
                    rendered = {}
                    for i, pages in enumerate(snapshot['screen_pages']):
                        for page, screen in enumerate(pages):
                            if screen['source'] in ('Keep existing command', 'System stats'): continue
                            identity = (screen['source'], screen.get('text',''), screen.get('file',''))
                            if identity not in rendered: rendered[identity] = render(screen, snapshot['credentials'])
                            result = rendered[identity]
                            if snapshot == self.active_data:
                                atomic_write(config.cache / f'page-{i}-{page}.txt', result)
                                # Keep 1.2.0 cache paths alive until Save & apply migrates the driver.
                                if page == 0 and i: atomic_write(config.cache / f'page-{i}.txt', result)
                            previews.append(f'M{i+1}/L{page+1}: ' + result.replace('\n', '  ').strip())
                    GLib.idle_add(self.preview.set_text, '\n\n'.join(previews) or 'Existing commands are managed by the driver.')
                finally:
                    self.busy = False
            threading.Thread(target=work, daemon=True).start()
            return True

    tray = Tray()
    if on_ready is not None:
        GLib.idle_add(on_ready, tray, config)
    if '--keypad-smoke' in sys.argv:
        tray.open_keypad()
    if '--smoke-test' in sys.argv:
        def finish_smoke():
            capture = tray.keypad or tray.window
            window = capture.get_window()
            if window:
                width, height = capture.get_size()
                picture = Gdk.pixbuf_get_from_window(window, 0, 0, width, height)
                if picture: picture.savev('/tmp/g13-tray-preview.png', 'png', [], [])
            Gtk.main_quit()
            return False
        GLib.timeout_add(1500, finish_smoke)
    Gtk.main()


if __name__ == '__main__':
    main()
