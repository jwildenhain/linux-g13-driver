"""Run under an isolated HOME on a desktop; never restarts the real driver."""
from pathlib import Path
import sys
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from g13_config import properties
import g13_tray

if __name__ == '__main__':
    failures=[]
    def ready(tray,config):
        from gi.repository import Gtk, GLib
        from g13_dialogs import credentials_dialog
        try:
            assert tray.stats_poll_seconds.get_value_as_int() == 1
            assert tray.stats_average_seconds.get_value_as_int() == 5
            config.save([{k:c.get_active_id() for k,c in mapping.items()} for mapping in tray.keymaps])
            actions=[]
            tray.service=lambda action: actions.append(action)
            tray.open_keypad()
            popup=tray.keypad
            default=next(g for g in popup.groups if g['name']=='Default Profile')
            popup.games.select_row(popup.game_rows[default['id']])
            assert len(popup.destinations)==3
            assert [s['target'] for s in popup.current_states()]==[0,1,2]
            assert 'Identical modes' in default['badges']
            popup.destinations[1].set_active_id('0')
            assert not popup.apply_button.get_sensitive()
            popup.destinations[1].set_active_id('1')
            popup.edit_mode(0);popup.select_key(None,'G0')
            assert popup.assignment.set_active_id('p,k.30')
            popup.edit_mode(1);popup.select_key(None,'G0')
            assert popup.assignment.set_active_id('p,k.31')
            original=(config.bindings/'bindings-3.properties').read_bytes()
            plans,summary=popup.make_plan()
            assert len(plans)==3
            assert 'M3' in summary
            # The review dialog can be cancelled without changing anything.
            def respond(response):
                for window in Gtk.Window.list_toplevels():
                    if isinstance(window,Gtk.MessageDialog):window.response(response)
                return False
            GLib.idle_add(respond,Gtk.ResponseType.CANCEL)
            popup.review()
            assert actions==[]
            GLib.idle_add(respond,Gtk.ResponseType.OK)
            popup.review()
            assert properties(config.bindings/'bindings-0.properties')['G0']=='p,k.30'
            assert properties(config.bindings/'bindings-1.properties')['G0']=='p,k.31'
            assert (config.bindings/'bindings-3.properties').read_bytes()==original
            assert actions==['restart']
            assert not popup.make_plan()[0]
            game=next(g for g in popup.groups if g['name']=='Skyrim')
            popup.games.select_row(popup.game_rows[game['id']])
            assert len(popup.destinations)==1
            popup.destinations[0].set_active_id('3')
            popup.edit_mode(0);popup.select_key(None,'G0')
            popup.assignment.set_active_id('p,k.32')
            plans,_=popup.make_plan();assert len(plans)==1 and plans[0][0]==3
            popup.apply_plans(plans)
            assert properties(config.bindings/'bindings-3.properties')['G0']=='p,k.32'
            popup.show_assignments.set_active(True)
            assert popup.buttons['G0'].get_child().get_text()=='D'
            popup.show_assignments.set_active(False)
            assert popup.buttons['G0'].get_child().get_text()=='G1'
            for key,value in [('G33','p,k.57'),('G34','p,k.28'),('G36','p,k.17'),('G37','p,k.30'),('G38','p,k.32'),('G39','p,k.31')]:
                assert key in popup.buttons
                popup.select_key(None,key)
                popup.assignment.set_active_id(value)
            popup.show_assignments.set_active(True)
            assert popup.buttons['G36'].get_child().get_text()=='W'
            plans,summary=popup.make_plan()
            assert 'joystick uses keyboard bindings' in summary
            popup.apply_plans(plans)
            saved=properties(config.bindings/'bindings-3.properties')
            assert saved['G33']=='p,k.57' and saved['G34']=='p,k.28'
            assert saved['G36']=='p,k.17' and saved['G39']=='p,k.31'
            assert saved['stick_mode']=='keys'

            dialog=credentials_dialog(tray,config,'OpenAI API')
            entries=[];buttons={}
            def walk(widget):
                if isinstance(widget,Gtk.Entry): entries.append(widget)
                if isinstance(widget,Gtk.Button): buttons[widget.get_label()]=widget
                if isinstance(widget,Gtk.Container):
                    for child in widget.get_children(): walk(child)
            walk(dialog)
            assert entries and not entries[0].get_visibility()
            entries[0].set_text('test-only')
            buttons['Save'].clicked()
            assert config.data['credentials']['OPENAI_ADMIN_KEY']=='test-only'
            buttons['Remove'].clicked()
            assert config.data['credentials']['OPENAI_ADMIN_KEY']==''
            dialog.destroy()
            dialog=credentials_dialog(tray,config,'Antigravity')
            entries=[];buttons={}
            walk(dialog)
            assert not entries[0].get_visibility()
            assert not buttons['Check connection'].get_sensitive()
            entries[0].set_text('test-antigravity-only')
            buttons['Save'].clicked()
            assert config.data['credentials']['ANTIGRAVITY_API_KEY']=='test-antigravity-only'
            buttons['Remove'].clicked()
            assert config.data['credentials']['ANTIGRAVITY_API_KEY']==''
            dialog.destroy()
            print('GTK interaction checks passed: profile selection, key edit, target saves, credential save/remove.')
        except Exception:
            failures.append(traceback.format_exc())
        finally: GLib.idle_add(Gtk.main_quit)
        return False
    g13_tray.main(ready)
    if failures: raise AssertionError('\n'.join(failures))
