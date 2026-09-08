"""Read-only providers. Network access occurs only in the tray worker."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError


def request(url, headers=None, params=None):
    if params:
        url += '?' + urlencode(params)
    req = Request(url, headers=dict({'User-Agent': 'G13-Tray/1.0'}, **(headers or {})))
    with urlopen(req, timeout=8) as response:
        return json.loads(response.read(2_000_000))


class SetupError(ValueError):
    pass


def require(credentials, *names):
    values = [credentials.get(n, '').strip() or os.environ.get(n, '') for n in names]
    if not all(values):
        raise SetupError('Configure connection\nin the tray settings')
    return values


def steam(c):
    key, user = require(c, 'STEAM_API_KEY', 'STEAM_ID')
    friends = request('https://api.steampowered.com/ISteamUser/GetFriendList/v1/', params={'key':key, 'steamid':user, 'relationship':'friend'})['friendslist']['friends']
    online = []
    ids = [f['steamid'] for f in friends]
    for i in range(0, len(ids), 100):
        players = request('https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/', params={'key':key, 'steamids':','.join(ids[i:i+100])})['response']['players']
        online += [p['personaname'] for p in players if p.get('personastate', 0) > 0]
    return ['Steam friends', f'Online: {len(online)}/{len(ids)}'] + online[:3]


def discord(c):
    token, guild = require(c, 'DISCORD_BOT_TOKEN', 'DISCORD_GUILD_ID')
    if not guild.isdigit():
        raise SetupError('Guild ID must be numeric')
    data = request('https://discord.com/api/v10/guilds/' + guild, {'Authorization':'Bot ' + token}, {'with_counts':'true'})
    return ['Discord server', data['name'], 'Members: ' + str(data.get('approximate_member_count','n/a')), 'Online: ' + str(data.get('approximate_presence_count','n/a'))]


def api_usage(c, claude=False):
    key, = require(c, 'ANTHROPIC_ADMIN_KEY' if claude else 'OPENAI_ADMIN_KEY')
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    if claude:
        url = 'https://api.anthropic.com/v1/organizations/usage_report/messages'
        headers = {'x-api-key':key, 'anthropic-version':'2023-06-01'}
        params = {'starting_at':start.isoformat(), 'bucket_width':'1d'}
    else:
        url = 'https://api.openai.com/v1/organization/usage/completions'
        headers = {'Authorization':'Bearer ' + key}
        params = {'start_time':int(start.timestamp()), 'bucket_width':'1d'}
    inp = out = 0
    for _ in range(100):
        data = request(url, headers, params)
        for bucket in data['data']:
            for r in bucket['results']:
                inp += r.get('input_tokens', 0) if not claude else (r.get('uncached_input_tokens',0) + r.get('cache_read_input_tokens',0) + sum((r.get('cache_creation') or {}).values()))
                out += r.get('output_tokens',0)
        if not data.get('has_more'):
            return ['Claude API UTC today' if claude else 'OpenAI API UTC today', f'Input: {inp:,}', f'Output: {out:,}', 'Organisation usage', 'Not subscription quota']
        params['page'] = data['next_page']
    raise SetupError('Too many usage pages')


def codex_local():
    root = Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex'))) / 'sessions'
    paths = list(root.glob('**/*.jsonl'))
    if not paths:
        return ['Codex local session', 'No session logs found']
    latest = max(paths, key=lambda p:p.stat().st_mtime)
    # Inspect a bounded tail, never prompts, auth files or conversation content.
    with latest.open('rb') as f:
        size = f.seek(0, 2)
        f.seek(max(0, size-2_000_000))
        lines = f.read().splitlines()
    for line in reversed(lines):
        try:
            event = json.loads(line)
        except (ValueError, UnicodeError):
            continue
        payload = event.get('payload', {})
        if event.get('type') == 'event_msg' and payload.get('type') == 'token_count':
            usage = (payload.get('info') or {}).get('total_token_usage') or {}
            if usage:
                age = int((time.time()-latest.stat().st_mtime)/60)
                return ['Codex latest session', f"Input: {usage.get('input_tokens',0):,}", f"Output: {usage.get('output_tokens',0):,}", f'Updated {age} min ago', 'Local, not account quota']
    return ['Codex local session', 'No token event in tail']


def render(screen, credentials):
    source = screen['source']
    try:
        if source == 'Steam': lines = steam(credentials)
        elif source == 'Discord': lines = discord(credentials)
        elif source == 'OpenAI API': lines = api_usage(credentials)
        elif source == 'Claude API': lines = api_usage(credentials, True)
        elif source == 'Codex local': lines = codex_local()
        elif source == 'Antigravity / text file':
            if not screen['file']:
                lines = ['Antigravity', 'Quota API unverified', 'Choose a text export', 'or use CLI /usage']
            else:
                p = Path(screen['file']).expanduser()
                if not p.is_file():
                    raise SetupError('Choose a regular text file')
                with p.open() as f:
                    lines = f.read(4096).splitlines()[:4]
                lines += [f'File age: {int((time.time()-p.stat().st_mtime)/60)}m']
        elif source == 'Custom text': lines = screen['text'].splitlines()
        else: lines = [source]
    except HTTPError as e:
        lines = [source, f'API error: HTTP {e.code}', 'Check access / credentials', 'Retry in next refresh']
    except SetupError as e:
        lines = [source] + str(e).splitlines()[:3]
    except Exception:
        lines = [source, 'Unavailable', 'Check network / file access', 'Retry in next refresh']
    return '\n'.join(''.join(ch if 32 <= ord(ch) < 127 else '?' for ch in str(line))[:26] for line in lines[:5]) + '\n'
