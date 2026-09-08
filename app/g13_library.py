"""Group source modes and compare assignments without relying on profile names."""
import re
from g13_profiles import convert_profile


def action_identity(value, imported):
    if value.startswith('import:'):
        return ('macro', imported[value]['sequence'])
    return ('binding', value)


def analyse_profile(profile, atlas):
    mapping, imported, warnings = convert_profile(profile, atlas)
    editable = {key:action_identity(value, imported) for key,value in mapping.items()}
    full = {}
    for binding in profile['bindings']:
        # Normalise every source key through the same converter, retaining its
        # physical label. Unsupported actions remain distinct from missing keys.
        one = dict(profile, bindings=[dict(binding, key_label='G1')], notes=[])
        converted, macros, _ = convert_profile(one, atlas)
        full[binding['key_label']] = (action_identity(converted['G0'],macros) if 'G0' in converted
                                      else ('unsupported',binding['action_type'],str(binding.get('action_value',''))))
    return {'profile':profile, 'mapping':mapping, 'imported':imported, 'warnings':warnings,
            'editable':editable, 'full':full}


def compare_profiles(a,b):
    common=set(a['editable']) & set(b['editable'])
    equal=sum(a['editable'][key]==b['editable'][key] for key in common)
    return {'exact':bool(a['full']) and a['full']==b['full'],
            'same_editable':bool(a['editable']) and a['editable']==b['editable'],
            'equal':equal, 'shared':len(common),
            'only_a':len(set(a['editable'])-set(b['editable'])),
            'only_b':len(set(b['editable'])-set(a['editable']))}


def group_library(atlas):
    sources={s['id']:s for s in atlas['sources']}
    grouped={}
    for profile in atlas['profiles']:
        source=sources[profile['source_id']]
        origin=profile.get('origin',str(profile['id']))
        name=re.sub(r' · source M\d+$','',profile['name'])
        if re.search(r'bindings-\d+\.properties$',origin):
            origin=re.sub(r'bindings-\d+\.properties$','bindings.properties',origin)
            name='Imported local snapshots' if source.get('slug')=='local' else source['repo'].split('/')[-1]+' profiles'
        elif origin=='config.json':
            name=source['repo'].split('/')[-1]+' presets'
        key=(str(profile['source_id']),origin)
        group=grouped.setdefault(key,{'id':'group:'+str(len(grouped)), 'name':name, 'source':source, 'modes':[]})
        match=re.search(r'(?:source M|\(M)(\d+)',profile['name'])
        if match: number=int(match[1])
        elif re.search(r'bindings-(\d+)\.properties$',profile.get('origin','')):
            number=int(re.search(r'bindings-(\d+)\.properties$',profile['origin'])[1])+1
        else: number=1
        mode=analyse_profile(profile,atlas)
        mode.update(number=number,label=f'Source M{number}',id=str(profile['id']))
        group['modes'].append(mode)
    all_modes=[m for g in grouped.values() for m in g['modes']]
    for group in grouped.values():
        group['modes'].sort(key=lambda m:(m['number'],m['profile']['name']))
        for mode in group['modes']:
            mode['matches']=[]
            mode['similar']=[]
            for other in all_modes:
                if mode is other: continue
                result=compare_profiles(mode,other)
                if result['exact'] or result['same_editable']:
                    mode['matches'].append((other['profile']['name'],result))
                elif result['shared']>=8 and result['equal']/result['shared']>=.8:
                    mode['similar'].append((other['profile']['name'],result))
            mode['similar'].sort(key=lambda p:(-p[1]['equal'],p[0]))
        badges=[f'{len(group["modes"])} modes' if len(group['modes'])>1 else 'Single mode']
        if not any(m['mapping'] for m in group['modes']): badges.append('No usable assignments')
        if any(m['matches'] for m in group['modes']): badges.append('Matching assignments')
        if any(any('cannot import' in w for w in m['warnings']) for m in group['modes']): badges.append('Unsupported actions')
        if any(compare_profiles(a,b)['exact'] for i,a in enumerate(group['modes']) for b in group['modes'][i+1:]):
            badges.append('Identical modes')
        group['badges']=badges
    return sorted(grouped.values(),key=lambda g:(g['name'].casefold(),g['source']['repo']))


def audit_markdown(groups):
    modes=[m for g in groups for m in g['modes']]
    lines=['# Profile library audit','',f'{len(groups)} grouped entries; {len(modes)} source modes.',
           '', 'Exact matches compare all source assignments, including non-G keys and unsupported actions.',
           'Editable matches compare only successfully converted G-keys, thumb buttons and joystick directions; these are not necessarily interchangeable full profiles.',
           'Partial overlaps require at least eight shared supported G-keys and 80% agreement. Missing keys are not treated as disabled.',
           '', '## Multiple source modes','']
    for g in groups:
        if len(g['modes'])>1: lines.append(f'- {g["name"]} ({g["source"]["repo"]}): '+', '.join(m['label'] for m in g['modes']))
    lines+=['','## Matching assignments','']
    seen=set();count=0
    for i,a in enumerate(modes):
        for b in modes[i+1:]:
            r=compare_profiles(a,b)
            if r['exact'] or r['same_editable']:
                kind='Exact source match' if r['exact'] else 'Same supported control assignments; other source details differ'
                lines.append(f'- {a["profile"]["name"]} ↔ {b["profile"]["name"]}: {kind}.')
                count+=1
    if not count: lines.append('No identical non-empty assignment sets found.')
    lines+=['','## Closest partial overlaps (not duplicates)','']
    for a in modes:
        if a['similar']:
            name,r=a['similar'][0]
            pair=tuple(sorted([a['profile']['name'],name]))
            if pair in seen:continue
            seen.add(pair)
            lines.append(f'- {a["profile"]["name"]} ↔ {name}: {r["equal"]}/{r["shared"]} shared keys match; {r["only_a"]}/{r["only_b"]} keys present only on each side.')
    lines+=['','## Empty or unsupported modes','']
    for a in modes:
        bad=sum('cannot import' in w for w in a['warnings'])
        if bad or not a['mapping']: lines.append(f'- {a["profile"]["name"]}: {len(a["mapping"])} usable controls; {bad} unsupported control actions.')
    return '\n'.join(lines)+'\n'
