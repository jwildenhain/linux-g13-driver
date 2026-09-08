#!/usr/bin/python3
"""Fetch/convert the complete cheshire137 G13 XML library into local atlas data."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from g13_config import atomic_write
from g13_profiles import key_codes, validate_sequence

REPO = 'cheshire137/logitech-g13-profiles'
SOURCE = 'cheshire137-games'
# Logitech XML labels are not driver property indices. Translate at the boundary.
# G25 is the separate TOP control, which the current editor does not expose.
AUXILIARY_LABELS = {'G23':'LEFT', 'G24':'DOWN', 'G25':'TOP',
                    'G26':'STICK_UP', 'G27':'STICK_RIGHT',
                    'G28':'STICK_DOWN', 'G29':'STICK_LEFT'}
ALIASES = {'ESCAPE':'ESC','SPACEBAR':'SPACE','LCTRL':'LEFTCTRL','RCTRL':'RIGHTCTRL',
           'LSHIFT':'LEFTSHIFT','RSHIFT':'RIGHTSHIFT','LALT':'LEFTALT','RALT':'RIGHTALT',
           'LBRACKET':'LEFTBRACE','RBRACKET':'RIGHTBRACE','EQUAL':'EQUAL',
           'QUOTE':'APOSTROPHE','TILDE':'GRAVE','PERIOD':'DOT'}


def tag(element): return element.tag.rsplit('}',1)[-1]


def parse_macro(macro, codes):
    def number(value): return codes['KEY_' + ALIASES.get(value,value)]
    try:
        payload = list(macro)[0]
        kind = tag(payload)
        if kind == 'keystroke':
            keys = [number(e.get('value')) for e in payload if tag(e)=='key']
            modifiers = [number(e.get('value')) for e in payload if tag(e)=='modifier']
            if len(keys)!=1: raise ValueError('Keystroke must contain one key')
            if not modifiers: return 'key',str(keys[0])
            numbers=modifiers+keys
            sequence=','.join([f'kd.{n}' for n in numbers]+['d.20']+[f'ku.{n}' for n in reversed(numbers)])
        elif kind == 'multikey':
            tokens=[]
            for e in payload:
                if tag(e)=='key' and e.get('direction') in ('down','up'):
                    tokens.append(('kd.' if e.get('direction')=='down' else 'ku.')+str(number(e.get('value'))))
                elif tag(e)=='delay': tokens.append('d.'+str(int(e.get('milliseconds'))))
                else: raise ValueError('Unsupported macro event')
            sequence=','.join(tokens)
        elif kind=='hotkeys':
            task=payload.find('./{*}do').get('task')
            key={'copy':'C','paste':'V','cut':'X','undo':'Z','selectall':'A'}[task]
            numbers=[number('LCTRL'),number(key)]
            sequence=','.join([f'kd.{n}' for n in numbers]+['d.20']+[f'ku.{n}' for n in reversed(numbers)])
        else: return 'unsupported',kind
        validate_sequence(sequence)
        return 'sequence',sequence
    except (KeyError, ValueError, IndexError, AttributeError, TypeError):
        return 'unsupported','Unconvertible '+macro.get('name','macro')


def import_collection(directory):
    codes=key_codes()
    if not codes: raise ValueError('Linux input-event-codes.h is required for conversion')
    result={'sources':[{'id':SOURCE,'slug':SOURCE,'repo':REPO,'url':'https://github.com/'+REPO,
                        'license':'No licence declared; locally imported','format':'logitech-xml'}],
            'profiles':[],'macros':[]}
    files=sorted(Path(directory).rglob('*.xml'))
    if not files: raise ValueError('No XML profiles found')
    for path in files:
        root=ET.parse(path).getroot()
        for index,p in enumerate(root.findall('./{*}profile')):
            profile_id=f'{SOURCE}:{path.stem}:{index}'
            commands={}
            for macro in p.findall('./{*}macros/{*}macro'):
                kind,value=parse_macro(macro,codes)
                guid=macro.get('guid')
                if kind=='sequence':
                    ident=profile_id+':'+guid
                    result['macros'].append({'source_id':SOURCE,'macro_id':ident,'name':macro.get('name','Macro'),'sequence':value})
                    kind,value='macro',ident
                commands[guid]=(kind,value,macro.get('name',''))
            modes={}
            for group in p.findall('./{*}assignments'):
                if group.get('devicecategory')!='Logitech.Gaming.LeftHandedController': continue
                for assignment in group:
                    if assignment.get('backup')=='true': continue
                    state=assignment.get('shiftstate','1')
                    xml_key=assignment.get('contextid','')
                    key=AUXILIARY_LABELS.get(xml_key,xml_key)
                    kind,value,label=commands.get(assignment.get('macroguid'),('unsupported','Missing command','Missing command'))
                    modes.setdefault(state,{})[key]={'key_label':key,'source_key_label':xml_key,'action_type':kind,'action_value':value,'action_label':label}
            if not modes: modes={'1':{}}
            for state,bindings in sorted(modes.items()):
                notes=[] if bindings else ['This XML contains no G13 assignments; configure buttons manually.']
                result['profiles'].append({'id':profile_id+':'+state,'source_id':SOURCE,
                    'name':p.get('name',path.stem)+(f' · source M{state}' if len(modes)>1 else ''),
                    'origin':str(path.relative_to(directory)),'format':'properties',
                    'bindings':list(bindings.values()),'notes':notes})
    result['xml_files']=len(files)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout',type=Path,help='Use an existing local clone instead of downloading')
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'data/g13-games.json')
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='g13-games-') as temporary:
        directory=args.checkout or Path(temporary)/'repository'
        if args.checkout is None:
            subprocess.run(['git','clone','--depth','1','https://github.com/'+REPO+'.git',str(directory)],check=True,timeout=120)
        result=import_collection(directory)
        result['revision']=subprocess.check_output(['git','-C',str(directory),'rev-parse','HEAD'],text=True).strip()
        atomic_write(args.output,json.dumps(result,indent=2)+'\n')
        print(f'Imported {result["xml_files"]} XML files, {len(result["profiles"])} mode profiles from {REPO}.')

if __name__=='__main__': main()
