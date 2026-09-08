"""Native keypad popup and per-service credential dialogs."""
import copy
from pathlib import Path
import threading
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Pango
from g13_profiles import load_atlas, convert_profile
from g13_config import DEFAULT_CODES, INPUT_LABELS, INPUT_ALIASES, STICK_INPUTS
from g13_providers import render


class KeypadWindow(Gtk.Window):
    def __init__(self, tray, config):
        super().__init__(title='G13 game and mode assignments')
        from g13_library import group_library
        self.tray, self.config = tray, config
        self.atlas = load_atlas()
        self.groups = group_library(self.atlas)
        self.groups.insert(0, {'id':'saved', 'name':'Currently saved on G13',
            'source':{'repo':'Your saved settings'}, 'badges':['M1 · M2 · M3 · M4'],
            'modes':[{'id':f'saved:{i}', 'number':i+1, 'label':f'Currently saved on M{i+1}',
                      'mapping':self.saved_mapping(i), 'imported':{}, 'warnings':[], 'matches':[], 'similar':[]}
                     for i in range(4)]})
        self.refresh_saved_comparisons()
        self.states = {}
        self.group = self.groups[0]
        self.selected_mode = 0
        self.selected_key = 'G0'
        self.updating = False
        self.set_default_size(1180, 790)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=14)
        self.add(root)
        title=Gtk.Label(xalign=0)
        title.set_markup('<big><b>Game and mode assignments</b></big>')
        root.pack_start(title,False,False,0)
        root.pack_start(Gtk.Label(label='Choose a game, route its source modes, then review changes. M1 system stats and all screen colours are preserved.',xalign=0),False,False,0)
        body=Gtk.Box(spacing=14)
        root.pack_start(body,True,True,0)
        sidebar=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8)
        sidebar.set_size_request(245,-1)
        body.pack_start(sidebar,False,False,0)
        self.search=Gtk.SearchEntry(placeholder_text='Search games or repositories')
        sidebar.pack_start(self.search,False,False,0)
        self.games=Gtk.ListBox()
        self.games.set_selection_mode(Gtk.SelectionMode.SINGLE)
        scroll=Gtk.ScrolledWindow();scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.games);sidebar.pack_start(scroll,True,True,0)
        self.game_rows={}
        for group in self.groups:
            row=Gtk.ListBoxRow();row.group=group
            label=Gtk.Label(label=group['name']+'\n'+' · '.join(group['badges']),xalign=0,margin=7)
            label.set_line_wrap(True);label.set_max_width_chars(26)
            row.add(label);row.set_tooltip_text(group['source']['repo'])
            self.games.add(row);self.game_rows[group['id']]=row
        self.games.set_filter_func(lambda row: self.search.get_text().casefold() in (row.group['name']+' '+row.group['source']['repo']).casefold())
        self.search.connect('search-changed',lambda *_:self.games.invalidate_filter())
        self.games.connect('row-selected',self.choose_group)
        middle=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8)
        body.pack_start(middle,False,False,0)
        labels_row=Gtk.Box(spacing=10)
        labels_row.pack_start(Gtk.Label(label='Show assigned keys',xalign=0),True,True,0)
        self.show_assignments=Gtk.Switch()
        self.show_assignments.set_tooltip_text('Switch between physical button names and proposed assignments. Full assignments are shown in tooltips.')
        labels_row.pack_start(self.show_assignments,False,False,0)
        middle.pack_start(labels_row,False,False,0)
        self.show_assignments.connect('notify::active',lambda *_:self.update_preview())
        self.mode_heading=Gtk.Label(label='Select a source mode',xalign=0)
        middle.pack_start(self.mode_heading,False,False,0)
        fixed=Gtk.Fixed();fixed.set_size_request(314,455)
        middle.pack_start(fixed,False,False,0)
        image=Path(__file__).parent/'g13.gif'
        if not image.exists(): image=Path(__file__).resolve().parents[1]/'src/java/com/gupta/g13/images/g13.gif'
        if image.exists():
            from gi.repository import GdkPixbuf
            fixed.put(Gtk.Image.new_from_pixbuf(GdkPixbuf.Pixbuf.new_from_file_at_scale(str(image),314,455,False)),0,0)
        self.buttons={}
        for i in range(22):
            label=f'G{i+1}'
            geo=next((k for k in self.atlas['keys'] if k['key_label']==label),None)
            if geo:
                xs,ys=zip(*geo['polygon']);x,y=int(min(xs)*.64),int(min(ys)*.64)
            else:
                row,col=(0,i) if i<7 else (1,i-7) if i<14 else (2,i-14) if i<19 else (3,i-19)
                x,y=5+col*42+row*10,150+row*47
            button=Gtk.Button(label=label)
            button.set_size_request(38,30)
            # Compact labels fit the physical key geometry.
            css=Gtk.CssProvider();css.load_from_data(b'button {padding: 2px; min-width: 24px; min-height: 22px; font-size: 11px;}')
            button.get_style_context().add_provider(css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            button.connect('clicked',self.select_key,f'G{i}')
            fixed.put(button,x,y);self.buttons[f'G{i}']=button
        # Physical joystick and the thumb buttons to its left and below.
        auxiliary = {'G33':('T1',211,281,28,35), 'G34':('T2',263,325,42,28),
                     'G36':('↑',265,243,26,26), 'G37':('←',239,270,26,26),
                     'G38':('→',287,270,26,26), 'G39':('↓',265,297,26,26)}
        self.physical_labels={key:label for key,label in INPUT_LABELS.items()}
        for key,(label,x,y,width,height) in auxiliary.items():
            button=Gtk.Button(label=label);button.set_size_request(width,height)
            css=Gtk.CssProvider();css.load_from_data(b'button {padding: 1px; min-width: 18px; min-height: 18px; font-size: 10px;}')
            button.get_style_context().add_provider(css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            button.connect('clicked',self.select_key,key)
            fixed.put(button,x,y);self.buttons[key]=button;self.physical_labels[key]=label
        for button in self.buttons.values():
            label=button.get_child()
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.set_max_width_chars(4)
        self.key_label=Gtk.Label(xalign=0)
        middle.pack_start(self.key_label,False,False,0)
        self.assignment=Gtk.ComboBoxText();self.assignment.append('','Disabled')
        self.names={'':'Disabled'}
        for code,name in tray.key_names():
            value=f'p,k.{code}';self.assignment.append(value,name);self.names[value]=name
        for ident,name in tray.macros():
            value=f'm,{ident},1';self.assignment.append(value,'Macro: '+name);self.names[value]='Macro: '+name
        self.known=set(self.names)
        self.assignment.connect('changed',self.change_assignment)
        middle.pack_start(self.assignment,False,False,0)
        middle.pack_start(Gtk.Label(label='Highlighted keys change on the destination.\nUnlisted keys retain their saved assignment.',xalign=0),False,False,0)
        right=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10)
        body.pack_start(right,True,True,0)
        self.source_info=Gtk.Label(xalign=0);self.source_info.set_line_wrap(True)
        right.pack_start(self.source_info,False,False,0)
        self.cards=Gtk.Box(spacing=6);right.pack_start(self.cards,False,False,0)
        notebook=Gtk.Notebook();right.pack_start(notebook,True,True,0)
        self.preview=self.text_panel(notebook,'Current → proposed')
        self.notes=self.text_panel(notebook,'Duplicates & import notes')
        self.summary=Gtk.Label(xalign=0);self.summary.set_line_wrap(True)
        root.pack_start(self.summary,False,False,0)
        bottom=Gtk.Box(spacing=12)
        root.pack_start(bottom,False,False,0)
        self.apply_button=Gtk.Button(label='Review & apply assignments…')
        self.apply_button.connect('clicked',self.review)
        bottom.pack_start(self.apply_button,False,False,0)
        self.status=Gtk.Label(xalign=0);self.status.set_line_wrap(True)
        bottom.pack_start(self.status,True,True,0)
        self.games.select_row(self.game_rows['saved'])
        self.show_all()

    def refresh_saved_comparisons(self):
        from g13_library import compare_profiles
        group=self.groups[0]
        for mode in group['modes']:
            mode['mapping']=self.saved_mapping(mode['number']-1)
            mode['editable']={key:self.identity(value,mode) for key,value in mode['mapping'].items()}
            # We compare the editable keys here, not an entire imported source.
            mode['full']={}
        for mode in group['modes']:
            mode['matches']=[]
            for other_group in self.groups:
                for other in other_group['modes']:
                    if mode is other:continue
                    result=compare_profiles(mode,other)
                    if result['same_editable']:
                        name=other.get('profile',{}).get('name',other['label'])
                        mode['matches'].append((name,result))
        group['badges']=['M1 · M2 · M3 · M4']
        if any(m['matches'] for m in group['modes']):group['badges'].append('Matching control assignments')

    def text_panel(self, notebook, title):
        view=Gtk.TextView(editable=False,cursor_visible=False)
        view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        view.set_left_margin(8);view.set_right_margin(8)
        scroll=Gtk.ScrolledWindow();scroll.set_min_content_width(430)
        scroll.add(view);notebook.append_page(scroll,Gtk.Label(label=title))
        return view

    def saved_mapping(self, mode):
        result={}
        for key in INPUT_LABELS:
            i=int(key[1:])
            default=f'p,k.{DEFAULT_CODES[i]}' if i<22 else 'none'
            value=self.config.raw[mode].get(key,self.config.raw[mode].get(INPUT_ALIASES.get(key,''),default))
            if value.startswith('p,') and not value.startswith('p,k.'):value='p,k.'+value[2:]
            result[key]='' if value=='none' else value
        return result

    def choose_group(self, _, row):
        if row is None:return
        self.group=row.group
        if self.group['id'] not in self.states:
            self.states[self.group['id']]=[{'mode':m,'mapping':dict(m['mapping']),'imported':dict(m['imported']),
                'target':m['number']-1 if m['mapping'] and 1<=m['number']<=4 else -1,'edited':False} for m in self.group['modes']]
        self.selected_mode=0
        self.source_info.set_text(self.group['name']+'\n'+self.group['source']['repo']+'\n'+' · '.join(self.group['badges']))
        self.updating=True
        for child in self.cards.get_children():child.destroy()
        self.destinations=[]
        for index,state in enumerate(self.current_states()):
            card=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5)
            label='M'+str(state['mode']['number'])
            button=Gtk.Button(label='Edit '+label)
            button.connect('clicked',lambda _,index=index:self.edit_mode(index))
            card.pack_start(button,False,False,0)
            combo=Gtk.ComboBoxText();combo.append('-1','Skip')
            for i in range(4):combo.append(str(i),f'→ M{i+1}')
            combo.set_active_id(str(state['target']))
            combo.connect('changed',self.route_mode,index)
            card.pack_start(combo,False,False,0)
            count=Gtk.Label(label=f'{len(state["mapping"])} controls')
            card.pack_start(count,False,False,0)
            self.cards.pack_start(card,True,True,0);self.destinations.append(combo)
        self.cards.show_all();self.updating=False
        self.edit_mode(0)

    def current_states(self):return self.states[self.group['id']]

    def state(self):return self.current_states()[self.selected_mode]

    def edit_mode(self,index):
        self.selected_mode=index
        self.mode_heading.set_text(self.state()['mode']['label'])
        self.select_key(None,self.selected_key)

    def route_mode(self,combo,index):
        if self.updating:return
        self.current_states()[index]['target']=int(combo.get_active_id())
        self.select_key(None,self.selected_key)

    def identity(self,value,state):
        from g13_library import action_identity
        if value.startswith('m,'):
            from g13_config import properties
            parts=value.split(',')
            macro=properties(self.config.bindings/f'macro-{parts[1]}.properties')
            if len(parts)==3 and parts[2]=='1' and macro.get('sequence'):
                return ('macro',macro['sequence'])
        return action_identity(value,state['imported'])

    def changes(self,state):
        if state['target']<0:return {}
        saved=self.saved_mapping(state['target'])
        analog=self.config.raw[state['target']].get('stick_mode','keys') in ('absolute','1')
        return {k:v for k,v in state['mapping'].items()
                if self.identity(v,state)!=self.identity(saved[k],state)
                or (analog and k in STICK_INPUTS and (k in state.get('touched',set()) or self.group['id']!='saved'))}

    def description(self,value,state):
        return self.names.get(value,state['imported'].get(value,{}).get('name',value))

    def select_key(self,_,key):
        self.selected_key=key
        state=self.state();target=state['target']
        self.key_label.set_text(f'{INPUT_LABELS[key]} proposed assignment'+(' · skipped mode' if target<0 else f' → M{target+1}'))
        value=state['mapping'].get(key,self.saved_mapping(max(target,0))[key])
        if value not in self.known:
            self.assignment.append(value,self.description(value,state));self.known.add(value)
        self.updating=True;self.assignment.set_active_id(value);self.updating=False
        self.update_preview()

    def change_assignment(self,*_):
        if self.updating:return
        value=self.assignment.get_active_id()
        if value is None:return
        self.state()['mapping'][self.selected_key]=value;self.state()['edited']=True
        self.state().setdefault('touched',set()).add(self.selected_key)
        self.update_preview()

    def update_preview(self):
        state=self.state();target=state['target'];changes=self.changes(state)
        saved=self.saved_mapping(max(target,0))
        lines=['Choose a destination to compare this skipped mode.' if target<0 else f'Currently saved on M{target+1} → proposed {state["mode"]["label"]}','']
        for key,physical_label in INPUT_LABELS.items():
            old=self.description(saved[key],state)
            new=self.description(state['mapping'].get(key,saved[key]),state)
            marker='CHANGED' if key in changes else 'retained' if key not in state['mapping'] else 'same'
            lines.append(f'{physical_label}: {old} → {new}  [{marker}]')
            context=self.buttons[key].get_style_context()
            context.remove_class('suggested-action');context.remove_class('destructive-action')
            if key==self.selected_key:context.add_class('suggested-action')
            elif key in changes:context.add_class('destructive-action')
            self.buttons[key].set_tooltip_text(f'{physical_label}: {old} → {new}')
            compact={'Disabled':'—','Leftctrl':'Ctrl','Rightctrl':'RCtrl','Leftshift':'Shift','Rightshift':'RShift','Leftalt':'Alt','Rightalt':'RAlt','Space':'Space'}.get(new,new)
            self.buttons[key].get_child().set_text(compact if self.show_assignments.get_active() else self.physical_labels[key])
        self.preview.get_buffer().set_text('\n'.join(lines))
        mode=state['mode']
        notes=['Saved G-key comparisons:' if self.group['id']=='saved' else 'Source-library comparisons (before any edits):']
        for name,result in mode['matches']:
            notes.append(('Exact source match: ' if result['exact'] else 'Same supported controls only: ')+name)
        for name,r in mode['similar']:
            notes.append(f'Partial overlap: {name}: {r["equal"]}/{r["shared"]} shared keys match; {r["only_a"]}/{r["only_b"]} unique keys. Not a duplicate.')
        if not mode['matches'] and not mode['similar']:notes.append('No matching or closely overlapping source profiles found.')
        if state['edited']:notes.append('This draft has manual edits; source comparisons above do not describe the edited draft.')
        notes+=['','Import notes (unsupported and unlisted keys retain the destination):']+mode['warnings']
        self.notes.get_buffer().set_text('\n'.join(notes))
        try:
            plans,summary=self.make_plan()
            self.summary.set_text(summary);self.apply_button.set_sensitive(bool(plans))
        except ValueError as error:
            self.summary.set_text(str(error));self.apply_button.set_sensitive(False)

    def make_plan(self):
        selected=[s for s in self.current_states() if s['target']>=0]
        targets=[s['target'] for s in selected]
        if len(set(targets))!=len(targets):raise ValueError('Destination conflict: choose a different M-mode or Skip for each source mode.')
        plans=[];lines=[]
        for state in selected:
            changes=self.changes(state)
            lines.append(f'{state["mode"]["label"]} → M{state["target"]+1}: {len(changes)} keys change')
            if STICK_INPUTS.intersection(changes):
                lines.append(f'M{state["target"]+1}: joystick uses keyboard bindings (analogue mode off).')
            if changes:plans.append((state['target'],changes,state['imported']))
        lines.append('One backup for all affected modes. Screen content and colours are preserved.')
        if not selected:lines.insert(0,'All source modes are skipped.')
        elif not plans:lines.insert(0,'No assignment changes to apply.')
        return plans,'\n'.join(lines)

    def review(self,*_):
        try:
            plans,summary=self.make_plan()
            if not plans:return
            warnings=sum(len(s['mode']['warnings']) for s in self.current_states() if s['target']>=0)
            dialog=Gtk.MessageDialog(transient_for=self,modal=True,message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.NONE,text='Apply these mode assignments?')
            dialog.format_secondary_text(summary+f'\n\n{warnings} source import notes are listed in the preview. Unsupported assignments retain the destination values.')
            dialog.add_button('Cancel',Gtk.ResponseType.CANCEL);dialog.add_button('Apply assignments',Gtk.ResponseType.OK)
            response=dialog.run();dialog.destroy()
            if response==Gtk.ResponseType.OK:self.apply_plans(plans)
        except Exception as error:self.status.set_text('Not applied: '+str(error))

    def apply_plans(self,plans):
        backup,patches=self.config.save_targets(plans)
        for target,mapping in patches.items():
            for key,value in mapping.items():
                combo=self.tray.keymaps[target].get(key)
                if combo is not None and not combo.set_active_id(value):combo.append(value,value);combo.set_active_id(value)
            for state in self.current_states():
                if state['target']==target:state['mapping'].update(mapping)
        self.refresh_saved_comparisons()
        saved_row=self.game_rows['saved']
        saved_row.get_child().set_text(self.groups[0]['name']+'\n'+' · '.join(self.groups[0]['badges']))
        self.status.set_text('Applied. Backup: '+str(backup))
        self.tray.service('restart')
        self.select_key(None,self.selected_key)


CONNECTIONS = {
    'Antigravity': [('ANTIGRAVITY_API_KEY','API key (stored locally)')],
    'Steam': [('STEAM_API_KEY','Web API key'),('STEAM_ID','SteamID64')],
    'Discord': [('DISCORD_BOT_TOKEN','Bot token'),('DISCORD_GUILD_ID','Server ID')],
    'OpenAI API': [('OPENAI_ADMIN_KEY','Organisation admin key')],
    'Claude API': [('ANTHROPIC_ADMIN_KEY','Organisation admin key')],
}


def credentials_dialog(tray,config,source):
    dialog=Gtk.Dialog(title=source+' credentials', transient_for=tray.window, flags=0)
    dialog.set_default_size(460,260)
    dialog.add_button('Close',Gtk.ResponseType.CLOSE)
    box=dialog.get_content_area();box.set_spacing(10);box.set_border_width(14)
    entries={}
    for key,label in CONNECTIONS[source]:
        box.pack_start(Gtk.Label(label=label,xalign=0),False,False,0)
        entry=Gtk.Entry(text=config.data['credentials'].get(key,''))
        entry.set_visibility(key.endswith('_ID'))
        entries[key]=entry;box.pack_start(entry,False,False,0)
    hint=Gtk.Label(label='API totals describe organisation usage, not personal subscription quota.' if source in ('Claude API','OpenAI API') else 'Discord: the bot must belong to this server.' if source=='Discord' else 'Your Steam friend list must be accessible to the API.',xalign=0)
    if source=='Antigravity':
        hint.set_text('Stores your Antigravity key locally. No supported usage API endpoint has been verified, so this key is not sent or tested. The text-file screen remains available.')
    hint.set_line_wrap(True);box.pack_start(hint,False,False,0)
    status=Gtk.Label(xalign=0);status.set_line_wrap(True)
    row=Gtk.Box(spacing=8);box.pack_start(row,False,False,0)
    box.pack_start(status,False,False,0)
    def persist(remove=False):
        try:
            values={key:'' if remove else entry.get_text().strip() for key,entry in entries.items()}
            config.save_credentials(values)
            tray.active_data['credentials']=copy.deepcopy(config.data['credentials'])
            for key,value in values.items():
                entries[key].set_text(value);tray.credentials[key].set_text(value)
            status.set_text('Credentials removed.' if remove else 'Credentials saved.')
            tray.refresh()
        except Exception:
            status.set_text('Could not save credentials. Check configuration file access.')
    def test(button):
        values={key:entry.get_text().strip() for key,entry in entries.items()}
        button.set_sensitive(False);status.set_text('Checking read-only access…')
        def work():
            result=render({'source':source},values)
            def done():
                if dialog.get_visible(): status.set_text(result);button.set_sensitive(True)
                return False
            GLib.idle_add(done)
        threading.Thread(target=work,daemon=True).start()
    for label,callback in [('Save',lambda *_:persist()),('Remove',lambda *_:persist(True)),('Check connection',test)]:
        button=Gtk.Button(label=label);button.connect('clicked',callback);row.pack_start(button,False,False,0)
        if source=='Antigravity' and label=='Check connection':
            button.set_sensitive(False)
            button.set_tooltip_text('No verified Antigravity usage API endpoint')
    dialog.connect('response',lambda *_:dialog.destroy())
    dialog.show_all()
    return dialog
