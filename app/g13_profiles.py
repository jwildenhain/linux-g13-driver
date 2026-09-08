"""Local atlas loading and explicit, validated conversion to driver bindings."""
import json
from pathlib import Path
import re
from g13_config import validate_binding, INPUT_ALIASES


def load_atlas():
    candidates = [Path(__file__).parent / 'g13-keymaps.json',
                  Path(__file__).resolve().parents[1] / 'data/g13-keymaps.json']
    atlas = {'profiles': [], 'sources': [], 'keys': [], 'macros': []}
    for path in candidates:
        if path.exists():
            atlas = json.loads(path.read_text())
            break
    for path in [Path(__file__).parent / 'g13-games.json',
                 Path(__file__).resolve().parents[1] / 'data/g13-games.json']:
        if path.exists():
            games = json.loads(path.read_text())
            for key in ('profiles', 'sources', 'macros'): atlas[key].extend(games[key])
            break
    return atlas


def validate_sequence(sequence):
    held = set()
    if not sequence or len(sequence) > 800:
        raise ValueError('Empty or oversized macro sequence')
    for token in sequence.split(','):
        if not re.fullmatch(r'(kd|ku|d)\.\d+', token):
            raise ValueError('Unsupported macro event')
        kind, number = token.split('.')
        code = int(number)
        if kind == 'd':
            if code > 10000: raise ValueError('Macro delay exceeds 10 seconds')
        else:
            if not 1 <= code <= 255: raise ValueError('Unsupported macro keycode')
            if kind == 'kd': held.add(code)
            else: held.discard(code)
    if held: raise ValueError('Macro leaves keys held down')


def key_codes():
    header = Path('/usr/include/linux/input-event-codes.h')
    if not header.exists(): return {}
    tokens = dict(re.findall(r'^#define\s+(KEY_\w+)\s+(\w+)\b', header.read_text(), re.M))
    result = {}
    for _ in range(8):
        for name, value in tokens.items():
            if value.isdigit(): result[name] = int(value)
            elif value in result: result[name] = result[value]
    return result


def convert_profile(profile, atlas):
    mapping, imported, warnings = {}, {}, list(profile.get('notes', []))
    codes = key_codes()
    for binding in profile['bindings']:
        label = binding.get('key_label', '')
        if label in INPUT_ALIASES.values():
            key = next(key for key, alias in INPUT_ALIASES.items() if alias == label)
        elif re.fullmatch(r'G(?:[1-9]|1[0-9]|2[0-2])', label):
            key = 'G' + str(int(label[1:])-1)
        else:
            warnings.append(label + ': preserved target assignment (reserved or unsupported control)')
            continue
        kind, value = binding['action_type'], str(binding.get('action_value',''))
        try:
            if kind == 'none': converted = ''
            elif kind == 'key':
                if value.startswith('COMBO:'):
                    numbers = [codes['KEY_' + part.removeprefix('KEY_')] for part in value[6:].split('+')]
                    sequence = ','.join([f'kd.{n}' for n in numbers] + ['d.20'] + [f'ku.{n}' for n in reversed(numbers)])
                    validate_sequence(sequence)
                    converted = f'import:{profile["id"]}:{key}'
                    imported[converted] = {'name':value[6:], 'sequence':sequence}
                else:
                    if profile.get('format') != 'properties' or not value.isdigit():
                        value = str(codes['KEY_' + value.removeprefix('KEY_')])
                    converted = 'p,k.' + value
                    validate_binding(converted)
            elif kind == 'macro':
                ident = value.split(',')[0]
                macro = next(m for m in atlas['macros'] if m['source_id'] == profile['source_id'] and str(m['macro_id']) == ident)
                validate_sequence(macro['sequence'])
                converted = f'import:{profile["id"]}:{key}'
                imported[converted] = macro
            else:
                raise ValueError('Unsupported action: ' + kind + ' (' + value + ')')
            mapping[key] = converted
        except (ValueError, StopIteration, KeyError) as e:
            warnings.append(label + ': cannot import ' + (str(e) or 'missing macro') + '; target assignment retained')
    return mapping, imported, warnings
