"""Configuration shared by the tray and its tests; no desktop dependencies."""
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import tempfile
from datetime import datetime

SOURCES = ['System stats', 'Steam', 'Discord', 'Codex local', 'OpenAI API', 'Claude API', 'Antigravity / text file', 'Custom text', 'Keep existing command']
DEFAULT_CODES = [3,4,5,6,7,8,9,16,17,18,19,20,21,22,30,31,32,33,34,44,45,46]


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def properties(path):
    return {k.strip(): v.strip() for line in path.read_text().splitlines()
            if not line.lstrip().startswith(('#', '!')) and '=' in line
            for k, v in [line.split('=', 1)]} if path.exists() else {}


def update_properties(path, changes):
    lines = path.read_text().splitlines() if path.exists() else []
    result = []
    for line in lines:
        key = line.split('=', 1)[0].strip()
        if key not in changes or line.lstrip().startswith(('#', '!')):
            result.append(line)
    result += [f'{k}={v}' for k, v in changes.items()]
    atomic_write(path, '\n'.join(result) + '\n')


def validate_binding(value):
    if value == '':
        return
    if re.fullmatch(r'p,k\.\d+', value) and 1 <= int(value[4:]) <= 255:
        return
    if re.fullmatch(r'm,\d+,\d+', value):
        return
    raise ValueError('Use p,k.<Linux keycode 1–255> or m,<macro ID>,<repeat count>.')


class Config:
    def __init__(self, home=None):
        self.home = Path(home or Path.home())
        self.directory = self.home / '.config/g13'
        self.path = self.directory / 'tray.json'
        self.cache = self.home / '.cache/g13-tray'
        self.bindings = self.home / '.g13'
        self.raw = [properties(self.bindings / f'bindings-{i}.properties') for i in range(4)]
        self.original = [(self.bindings / f'bindings-{i}.properties').read_bytes()
                         if (self.bindings / f'bindings-{i}.properties').exists() else None for i in range(4)]
        if self.path.exists():
            self.data = json.loads(self.path.read_text())
        else:
            self.data = {'credentials': {}, 'screens': [
                {'source': 'System stats' if i == 0 else 'Keep existing command',
                 'color': self.raw[0].get(f'lcd_logiframe_page{i+1}_color', ['0,128,255','255,153,0','0,200,64','255,64,64'][i]),
                 'text': '', 'file': ''} for i in range(4)]}
        self.data['screens'][0]['source'] = 'System stats'

    def save(self, keymaps):
        for mapping in keymaps:
            for value in mapping.values():
                validate_binding(value)
                if value.startswith('m,') and not (self.bindings / ('macro-' + value.split(',')[1] + '.properties')).exists():
                    raise ValueError('Macro ' + value.split(',')[1] + ' does not exist. Create it with the macro editor first.')
        for i in range(4):
            p = self.bindings / f'bindings-{i}.properties'
            if (p.read_bytes() if p.exists() else None) != self.original[i]:
                raise ValueError('Bindings changed outside this app. Close and reopen before saving.')
        for screen in self.data['screens']:
            rgb = screen['color'].split(',')
            if len(rgb) != 3 or not all(x.isdigit() and 0 <= int(x) <= 255 for x in rgb):
                raise ValueError('Invalid RGB colour')
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        backup = self.bindings / 'backups' / stamp
        backup.mkdir(parents=True, exist_ok=True)
        changes = {'mode_profiles': '1', 'lcd_mode': 'logiframe', 'lcd_logiframe_page_count': '4', 'lcd_logiframe_page1_cmd': ''}
        for i, screen in enumerate(self.data['screens']):
            changes[f'lcd_logiframe_page{i+1}_color'] = screen['color']
            if i and screen['source'] != 'Keep existing command':
                changes[f'lcd_logiframe_page{i+1}_cmd'] = 'cat -- ' + shlex.quote(str(self.cache / f'page-{i}.txt'))
        # Existing page commands are in profile zero in the legacy page mode.
        for i in range(1,4):
            if self.data['screens'][i]['source'] == 'Keep existing command':
                key = f'lcd_logiframe_page{i+1}_cmd'
                changes[key] = self.raw[0].get(key, '')
        for i, mapping in enumerate(keymaps):
            path = self.bindings / f'bindings-{i}.properties'
            if path.exists():
                shutil.copy2(path, backup / path.name)
            patch = dict(changes, **mapping, mod=str(1 << i))
            # Empty bindings explicitly disable a key in the driver's parser.
            patch.update({k: 'none' for k, v in mapping.items() if not v})
            update_properties(path, patch)
            self.original[i] = path.read_bytes()
            self.raw[i] = properties(path)
        atomic_write(self.path, json.dumps(self.data, indent=2) + '\n')
        return backup
