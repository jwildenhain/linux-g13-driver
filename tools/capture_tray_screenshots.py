#!/usr/bin/python3
"""Capture README screenshots on a GTK desktop using a disposable configuration.

Run from any directory after importing the game collection. No real bindings,
credentials, or driver services are modified. Screenshots go to docs/screenshots.
"""
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))


def main():
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, Gdk, GLib
    import g13_tray
    from g13_dialogs import credentials_dialog

    output = ROOT / 'docs/screenshots'
    output.mkdir(parents=True, exist_ok=True)
    errors = []
    with tempfile.TemporaryDirectory(prefix='g13-docs-') as sample_home:
        os.environ['HOME'] = sample_home

        def ready(tray, config):
            tray.service = lambda *_: None
            steps = []

            def game(name, assigned=False):
                tray.window.hide()
                tray.open_keypad()
                popup = tray.keypad
                group = next(g for g in popup.groups if g['name'] == name)
                popup.search.set_text(name)
                popup.games.select_row(popup.game_rows[group['id']])
                popup.show_assignments.set_active(assigned)
                if name == 'Skyrim':
                    popup.destinations[0].set_active_id('3')
                    popup.select_key(None, 'G33')
                popup.present()
                return popup

            def credential():
                tray.keypad.hide()
                dialog = credentials_dialog(tray, config, 'Antigravity')
                dialog.present()
                return dialog

            steps.extend([
                ('settings.png', lambda: tray.window),
                ('game-modes.png', lambda: game('Overwatch 2')),
                ('assigned-controls.png', lambda: game('Skyrim', True)),
                ('credentials.png', credential),
            ])

            def advance():
                if not steps:
                    Gtk.main_quit()
                    return False
                name, setup = steps.pop(0)
                try:
                    window = setup()
                    def capture():
                        try:
                            width, height = window.get_size()
                            pixbuf = Gdk.pixbuf_get_from_window(window.get_window(), 0, 0, width, height)
                            if pixbuf is None:
                                raise RuntimeError('Window capture unavailable')
                            pixbuf.savev(str(output / name), 'png', [], [])
                            print(output / name)
                            advance()
                        except Exception as exc:
                            errors.append(exc)
                            Gtk.main_quit()
                        return False
                    GLib.timeout_add(1500, capture)
                except Exception as exc:
                    errors.append(exc)
                    Gtk.main_quit()
                return False
            GLib.timeout_add(1000, advance)
            return False
        g13_tray.main(on_ready=ready)
    if errors:
        raise errors[0]


if __name__ == '__main__':
    main()
