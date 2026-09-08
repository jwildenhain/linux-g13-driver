#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DOCS_DIR="docs/screens"
OUT_DIR="screens"
mkdir -p "$DOCS_DIR" "$OUT_DIR"

python3 - <<'PY'
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import re, time

W, H = 160, 43
scale = 4
canvas = (W * scale, H * scale)

font = None
for p in [
    '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf',
    '/usr/share/fonts/truetype/freefont/FreeMono.ttf',
]:
    try:
        font = ImageFont.truetype(p, 10)
        break
    except Exception:
        continue
if font is None:
    font = ImageFont.load_default()


def read_cpu_percent():
    def sample():
        with open('/proc/stat') as f:
            parts = f.readline().split()[1:]
        total = sum(int(v) for v in parts)
        idle = int(parts[3])
        return total, idle

    a_t, a_i = sample()
    time.sleep(0.2)
    b_t, b_i = sample()
    dt = b_t - a_t
    if dt <= 0:
        return None
    return int(((dt - (b_i - a_i)) * 100) / dt)


def read_mem_percent():
    data = {}
    with open('/proc/meminfo') as f:
        for line in f:
            m = re.match(r'^(\w+):\s+(\d+)\s+kB', line)
            if m:
                data[m.group(1)] = int(m.group(2))
    total = data.get('MemTotal', 0)
    avail = data.get('MemAvailable', 0)
    if total <= 0:
        return None
    if avail:
        used = total - avail
    else:
        used = total - (data.get('MemFree', 0) + data.get('Buffers', 0) + data.get('Cached', 0))
    return int((used * 100) / total)


def read_gpu_percent():
    import subprocess
    try:
        v = subprocess.check_output(['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'], stderr=subprocess.DEVNULL, timeout=1)
        return int(float(v.splitlines()[0]))
    except Exception:
        pass
    for p in ['/sys/class/drm/card0/device/gpu_busy_percent', '/sys/class/drm/card1/device/gpu_busy_percent', '/sys/class/drm/card2/device/gpu_busy_percent']:
        try:
            with open(p) as f:
                return int(float(f.read().strip()))
        except Exception:
            pass
    return None


def read_root_disk_usage_percent():
    import os
    st = os.statvfs('/')
    if st.f_blocks <= 0:
        return None
    return int(((st.f_blocks - st.f_bavail) * 100) / st.f_blocks)


def get_root_dev():
    with open('/proc/mounts') as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == '/':
                src = parts[0]
                if not src.startswith('/dev/'):
                    return None
                dev = src.split('/')[-1]
                i = len(dev)
                while i > 0 and dev[i - 1].isdigit():
                    i -= 1
                if i > 0 and dev[i - 1] == 'p':
                    i -= 1
                return dev[:i] if i > 0 else None
    return None


def read_disk_bytes():
    dev = get_root_dev()
    if not dev:
        return None, None
    with open('/proc/diskstats') as f:
        for line in f:
            p = line.split()
            if len(p) < 14:
                continue
            if p[2] == dev:
                return int(p[5]) * 512, int(p[9]) * 512
    return None, None


def format_speed(v):
    if v is None:
        return 'n/a'
    if v >= 1024 ** 3:
        return f"{v / (1024**3):4.1f}GB/s"
    if v >= 1024 ** 2:
        return f"{v / (1024**2):4.1f}MB/s"
    if v >= 1024:
        return f"{v / 1024:4.1f}KB/s"
    return f"{v:4d}B/s"


def read_net_speed():
    def sample():
        rx = tx = 0
        with open('/proc/net/dev') as f:
            for line in f.readlines()[2:]:
                if ':' not in line:
                    continue
                iface, rest = line.split(':', 1)
                iface = iface.strip()
                if iface == 'lo':
                    continue
                cols = rest.split()
                if len(cols) >= 16:
                    rx += int(cols[0])
                    tx += int(cols[8])
        return rx, tx
    a = sample()
    time.sleep(1)
    b = sample()
    return format_speed((b[0] - a[0]) + (b[1] - a[1]))


def read_pages():
    cpu = read_cpu_percent()
    mem = read_mem_percent()
    gpu = read_gpu_percent()
    net = read_net_speed()
    root = read_root_disk_usage_percent()

    rd0, wr0 = read_disk_bytes()
    time.sleep(1)
    rd1, wr1 = read_disk_bytes()

    rd = (rd1 - rd0) if rd0 is not None and rd1 is not None else None
    wr = (wr1 - wr0) if wr0 is not None and wr1 is not None else None

    usage = [
        f"CPU {cpu:3d}%" if cpu is not None else 'CPU  n/a',
        f"MEM {mem:3d}%" if mem is not None else 'MEM  n/a',
        f"GPU {gpu:3d}%" if gpu is not None else 'GPU  n/a',
        f"NET {net}",
        f"ROOT {root:3d}% R {format_speed(rd)} W {format_speed(wr)}" if root is not None else 'ROOT n/a',
    ]

    steam = [
        'Steam Friends',
        'Set STEAM_API_KEY',
        'and STEAM_ID',
        'for live data',
        '',
    ]

    tokens = [
        'Token Usage',
        'Antigravity: n/a/n/a',
        'Gemini: n/a/n/a',
        'Codex/GPT: n/a/n/a',
        'Daily allowance: n/a',
    ]

    custom = [
        'Custom',
        'Place your own',
        'status or',
        'widget here',
        '',
    ]

    return usage, steam, tokens, custom


def draw(path, lines, bg):
    img = Image.new('RGB', canvas, bg)
    d = ImageDraw.Draw(img)
    for i, t in enumerate(lines):
        d.text((2 * scale, i * 8 * scale + 1), t, fill=(220, 220, 220), font=font)
    return img

usage, steam, tokens, custom = read_pages()
pages = [
    ('g13-page1-usage-live.png', usage, (0, 128, 255)),
    ('g13-page2-steam-live.png', steam, (255, 153, 0)),
    ('g13-page3-tokens-live.png', tokens, (0, 200, 64)),
    ('g13-page4-custom-live.png', custom, (255, 64, 64)),
]

for name, lines, bg in pages:
    img = draw(name, lines, bg)
    img.save(name)
PY
