#!/usr/bin/env python3
"""Build a SQLite database of Logitech G13 keymaps gathered from public repos.

Normalises four incompatible on-disk formats into one schema:

  * Java .properties  (this driver / Lordbooker)  G<enum>=p,k.<linuxcode>
  * g13d .bind        (ecraven, brittyazel)       bind G1 KEY_7
  * JSON profiles     (RunicLuke)                 {"bindings": {"G1": "ESC"}}

Physical button placement comes from the arrangement map in
src/java/com/gupta/g13/Key.java, so the viewer lines up with g13.gif.
"""

import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --------------------------------------------------------------------------
# reference tables parsed out of the driver sources
# --------------------------------------------------------------------------

def parse_key_enum(path):
    """Constants.h enum G13_KEYS -> {code: canonical label}."""
    text = open(path).read()
    body = re.search(r"enum G13_KEYS \{(.*?)\n\};", text, re.S).group(1)
    labels, code = {}, 0
    for raw in body.split(","):
        line = re.sub(r"/\*.*?\*/", "", raw, flags=re.S).strip()
        if not line:
            continue
        m = re.match(r"G13_KEY_(\w+)\s*(?:=\s*(\d+))?$", line)
        if not m:
            continue
        if m.group(2) is not None:
            code = int(m.group(2))
        labels[code] = m.group(1)
        code += 1
    return labels


def parse_linux_keycodes(path):
    """JavaToLinuxKeymapping.java -> {linux code: human name}."""
    out = {}
    for name, code in re.findall(r'\{"([^"]*)",\s*(\d+),', open(path).read()):
        out[int(code)] = name
    return out


def parse_arrangement(path):
    """Key.java -> ordered list of {code, points} polygons (g13.gif space)."""
    text = open(path).read()
    block = re.search(r"items = \{(.*?)\n\t\};", text, re.S).group(1)
    shapes = []
    for line in block.splitlines():
        line = line.split("//")[0].strip()
        if not line.startswith("{{"):
            continue
        nums = re.findall(r"\{\s*(-?\d+)\s*(?:,\s*(-?\d+)\s*)?\}", line)
        code = int(nums[0][0])
        pts = [(int(x), int(y)) for x, y in nums[1:] if y != ""]
        if pts:
            shapes.append({"code": code, "points": pts})
    return shapes


# --------------------------------------------------------------------------
# canonical naming
# --------------------------------------------------------------------------

def canonical_label(code, enum_labels):
    """Enum index -> the label a user recognises (code 0 is the G1 key).

    Codes 36-39 carry leftover enum names (UNDEF3/LIGHT/LIGHT2/MISC_TOGGLE) but
    are the four joystick directions everywhere they are actually used - the
    stock bindings map them to W/A/D/S. Report the direction, not the leftover.
    """
    if code is None:
        return None
    if code in ARROW_ALIASES:
        return ARROW_ALIASES[code]
    if 0 <= code <= 21:
        return "G%d" % (code + 1)
    return enum_labels.get(code, "CODE_%d" % code)


# Joystick arrows reuse spare enum slots in the GUI's arrangement map.
ARROW_ALIASES = {36: "STICK_UP", 37: "STICK_LEFT", 38: "STICK_RIGHT", 39: "STICK_DOWN"}

LABEL_TO_CODE = {}


def build_label_index(enum_labels):
    for code in list(enum_labels) + list(range(22)):
        LABEL_TO_CODE[canonical_label(code, enum_labels)] = code
    # .bind files may still spell these the old way, so accept both.
    for code, name in enum_labels.items():
        LABEL_TO_CODE.setdefault(name, code)
    for code, alias in ARROW_ALIASES.items():
        LABEL_TO_CODE[alias] = code


def normalise_keyname(name, linux_names):
    """KEY_LEFTSHIFT / 'ESC' / 'A' -> the driver GUI's display name."""
    if name is None:
        return None
    raw = name.strip()
    bare = raw[4:] if raw.upper().startswith("KEY_") else raw
    folded = {v.upper().replace(" ", ""): v for v in linux_names.values() if v}
    hit = folded.get(bare.upper().replace(" ", "").replace("_", ""))
    return hit or bare


# --------------------------------------------------------------------------
# per-format parsers
# --------------------------------------------------------------------------

def read_properties(path):
    props = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            props[k.strip()] = v.strip()
    return props


def parse_properties_profile(path, enum_labels, linux_names):
    props = read_properties(path)
    bindings, meta = [], {}
    for key, value in props.items():
        m = re.fullmatch(r"G(\d+)", key)
        if not m:
            # keep only harmless metadata; LCD page commands are deliberately
            # skipped so no shell (or anyone's API keys) lands in the database.
            if key in ("color", "lcd_mode", "mod", "stickmode"):
                meta[key] = value
            continue
        code = int(m.group(1))
        parts = [p.strip() for p in value.split(",")]
        kind = parts[0] if parts else ""
        if kind == "p" and len(parts) > 1:
            tok = parts[1]
            lcode = int(tok[2:]) if tok.startswith("k.") else int(tok or 0)
            # Code 0 is the blank row in JavaToLinuxKeymapping: no key assigned.
            bindings.append({
                "code": code,
                "label": canonical_label(code, enum_labels),
                "action_type": "none" if lcode == 0 else "key",
                "action_value": str(lcode),
                "display": "unbound" if lcode == 0 else (linux_names.get(lcode) or "code %d" % lcode),
                "raw": value,
            })
        elif kind == "m" and len(parts) > 1:
            bindings.append({
                "code": code,
                "label": canonical_label(code, enum_labels),
                "action_type": "macro",
                "action_value": parts[1],
                "display": "Macro %s" % parts[1],
                "raw": value,
            })
    return bindings, meta


def parse_bind_profile(path, enum_labels, linux_names):
    bindings, meta = [], {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.split("#")[0].strip()
            if not line:
                continue
            parts = line.split()
            head = parts[0].lower()
            if head == "bind" and len(parts) >= 3:
                label = parts[1].upper()
                bindings.append({
                    "code": LABEL_TO_CODE.get(label),
                    "label": label,
                    "action_type": "key",
                    "action_value": parts[2],
                    "display": normalise_keyname(parts[2], linux_names),
                    "raw": line,
                })
            elif head == "rgb" and len(parts) >= 4:
                meta["color"] = ",".join(parts[1:4])
            elif head == "stickmode" and len(parts) >= 2:
                meta["stickmode"] = parts[1]
    return bindings, meta


def parse_json_profiles(path, linux_names):
    data = json.load(open(path, encoding="utf-8"))
    out = []
    for slot, prof in (data.get("profiles") or {}).items():
        bindings = []
        for label, value in (prof.get("bindings") or {}).items():
            label = label.upper()
            bindings.append({
                "code": LABEL_TO_CODE.get(label),
                "label": label,
                "action_type": "key",
                "action_value": str(value),
                "display": normalise_keyname(str(value), linux_names),
                "raw": "%s=%s" % (label, value),
            })
        colour = prof.get("color") or {}
        meta = {}
        if colour:
            meta["color"] = "%s,%s,%s" % (colour.get("r", 0), colour.get("g", 0), colour.get("b", 0))
        out.append((slot, prof.get("name") or slot, bindings, meta))
    return out


def parse_macro(path):
    props = read_properties(path)
    if not props.get("id"):
        return None
    return {
        "macro_id": props.get("id"),
        "name": props.get("name") or "",
        "sequence": props.get("sequence") or "",
    }


# --------------------------------------------------------------------------
# database
# --------------------------------------------------------------------------

SCHEMA = """
DROP TABLE IF EXISTS sources;
DROP TABLE IF EXISTS profiles;
DROP TABLE IF EXISTS bindings;
DROP TABLE IF EXISTS macros;
DROP TABLE IF EXISTS keys;
DROP TABLE IF EXISTS linux_keycodes;

CREATE TABLE sources (
    id       INTEGER PRIMARY KEY,
    slug     TEXT NOT NULL UNIQUE,
    repo     TEXT NOT NULL,
    url      TEXT,
    license  TEXT,
    format   TEXT NOT NULL,
    fetched  TEXT NOT NULL
);

CREATE TABLE profiles (
    id          INTEGER PRIMARY KEY,
    source_id   INTEGER NOT NULL REFERENCES sources(id),
    name        TEXT NOT NULL,
    origin_path TEXT NOT NULL,
    format      TEXT NOT NULL,
    color       TEXT,
    stick_mode  TEXT,
    lcd_mode    TEXT,
    UNIQUE (source_id, origin_path, name)
);

CREATE TABLE bindings (
    id           INTEGER PRIMARY KEY,
    profile_id   INTEGER NOT NULL REFERENCES profiles(id),
    key_code     INTEGER,
    key_label    TEXT NOT NULL,
    action_type  TEXT NOT NULL,
    action_value TEXT,
    action_label TEXT,
    raw          TEXT
);
CREATE INDEX idx_bindings_profile ON bindings(profile_id);
CREATE INDEX idx_bindings_key ON bindings(key_label);

CREATE TABLE macros (
    id          INTEGER PRIMARY KEY,
    source_id   INTEGER NOT NULL REFERENCES sources(id),
    macro_id    TEXT NOT NULL,
    name        TEXT,
    sequence    TEXT,
    origin_path TEXT
);
CREATE INDEX idx_macros_source ON macros(source_id, macro_id);

-- Physical arrangement, straight from Key.java (coordinates in g13.gif space).
CREATE TABLE keys (
    id        INTEGER PRIMARY KEY,
    key_code  INTEGER NOT NULL,
    key_label TEXT NOT NULL,
    key_group TEXT NOT NULL,
    polygon   TEXT NOT NULL,
    anomaly   TEXT
);

CREATE TABLE linux_keycodes (
    code INTEGER PRIMARY KEY,
    name TEXT
);
"""


def key_group(code):
    if 0 <= code <= 21:
        return "gkey"
    if code in (25, 26, 27, 28):
        return "lcd"
    if code == 24:
        return "round"
    if code in (29, 30, 31, 32):
        return "mode"
    if code in (33, 34, 35):
        return "thumb"
    if code in ARROW_ALIASES:
        return "stick"
    return "other"


def main():
    src_root = sys.argv[1] if len(sys.argv) > 1 else None
    if not src_root or not os.path.isdir(src_root):
        sys.exit("usage: build_keymap_db.py <downloaded-keymaps-dir>")

    out_db = os.path.join(REPO, "data", "g13-keymaps.db")
    out_json = os.path.join(REPO, "data", "g13-keymaps.json")

    enum_labels = parse_key_enum(os.path.join(REPO, "src/cpp/Constants.h"))
    linux_names = parse_linux_keycodes(os.path.join(REPO, "src/java/com/gupta/g13/JavaToLinuxKeymapping.java"))
    shapes = parse_arrangement(os.path.join(REPO, "src/java/com/gupta/g13/Key.java"))
    build_label_index(enum_labels)

    conn = sqlite3.connect(out_db)
    conn.executescript(SCHEMA)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # -- arrangement map -----------------------------------------------------
    seen = {}
    for shape in shapes:
        code = shape["code"]
        label = ARROW_ALIASES.get(code) or canonical_label(code, enum_labels)
        anomaly = None
        if code in seen:
            # Key.java lists code 25 twice: the under-screen L1 and the right
            # round button. Java's getKeyFor() returns the first, so the second
            # shape is unreachable in the original GUI. Kept, but flagged.
            anomaly = "duplicate key code %d (first use: %s)" % (code, seen[code])
        seen[code] = label
        conn.execute(
            "INSERT INTO keys (key_code, key_label, key_group, polygon, anomaly) VALUES (?,?,?,?,?)",
            (code, label, key_group(code), json.dumps(shape["points"]), anomaly),
        )

    for code, name in sorted(linux_names.items()):
        conn.execute("INSERT INTO linux_keycodes (code, name) VALUES (?,?)", (code, name))

    # -- sources -------------------------------------------------------------
    catalogue = [
        ("lordbooker", "Lordbooker/linux-g13-driver", "https://github.com/Lordbooker/linux-g13-driver", "NONE (no licence declared)", "properties"),
        ("ecraven", "ecraven/g13", "https://github.com/ecraven/g13", "NONE (no licence declared)", "g13d-bind"),
        ("brittyazel", "brittyazel/g13d", "https://github.com/brittyazel/g13d", "MIT", "g13d-bind"),
        ("runicluke", "RunicLuke/logitech-g13", "https://github.com/RunicLuke/logitech-g13", "MIT", "json"),
        ("local", "this checkout (~/.g13)", None, "local", "properties"),
    ]
    source_ids = {}
    for slug, repo, url, lic, fmt in catalogue:
        cur = conn.execute(
            "INSERT INTO sources (slug, repo, url, license, format, fetched) VALUES (?,?,?,?,?,?)",
            (slug, repo, url, lic, fmt, now),
        )
        source_ids[slug] = cur.lastrowid

    def add_profile(slug, name, origin, fmt, bindings, meta):
        if not bindings:
            return
        cur = conn.execute(
            "INSERT OR IGNORE INTO profiles (source_id, name, origin_path, format, color, stick_mode, lcd_mode)"
            " VALUES (?,?,?,?,?,?,?)",
            (source_ids[slug], name, origin, fmt, meta.get("color"),
             meta.get("stickmode"), meta.get("lcd_mode")),
        )
        if not cur.lastrowid:
            return
        pid = cur.lastrowid
        for b in bindings:
            conn.execute(
                "INSERT INTO bindings (profile_id, key_code, key_label, action_type, action_value, action_label, raw)"
                " VALUES (?,?,?,?,?,?,?)",
                (pid, b["code"], b["label"], b["action_type"], b["action_value"], b["display"], b["raw"]),
            )

    # -- walk the downloaded tree -------------------------------------------
    for slug in ("lordbooker", "ecraven", "brittyazel", "runicluke"):
        folder = os.path.join(src_root, slug)
        if not os.path.isdir(folder):
            continue
        for fname in sorted(os.listdir(folder)):
            path = os.path.join(folder, fname)
            if fname.endswith(".properties"):
                if "macro-" in fname:
                    macro = parse_macro(path)
                    if macro:
                        conn.execute(
                            "INSERT INTO macros (source_id, macro_id, name, sequence, origin_path)"
                            " VALUES (?,?,?,?,?)",
                            (source_ids[slug], macro["macro_id"], macro["name"], macro["sequence"], fname),
                        )
                else:
                    b, meta = parse_properties_profile(path, enum_labels, linux_names)
                    label = re.search(r"bindings-(\d+)", fname)
                    name = "Profile %s" % label.group(1) if label else fname
                    add_profile(slug, name, fname, "properties", b, meta)
            elif fname.endswith(".bind"):
                b, meta = parse_bind_profile(path, enum_labels, linux_names)
                name = re.sub(r"\.bind$", "", fname.split("_")[-1])
                add_profile(slug, name, fname, "g13d-bind", b, meta)
            elif fname.endswith(".json"):
                for slot, name, b, meta in parse_json_profiles(path, linux_names):
                    add_profile(slug, "%s (%s)" % (name, slot), fname, "json", b, meta)

    # -- the user's own bindings --------------------------------------------
    local_dir = os.path.expanduser("~/.g13")
    if os.path.isdir(local_dir):
        for fname in sorted(os.listdir(local_dir)):
            path = os.path.join(local_dir, fname)
            if fname.startswith("bindings-") and fname.endswith(".properties"):
                b, meta = parse_properties_profile(path, enum_labels, linux_names)
                label = re.search(r"bindings-(\d+)", fname)
                add_profile("local", "My profile %s" % label.group(1), fname, "properties", b, meta)
            elif fname.startswith("macro-") and fname.endswith(".properties"):
                macro = parse_macro(path)
                if macro:
                    conn.execute(
                        "INSERT INTO macros (source_id, macro_id, name, sequence, origin_path)"
                        " VALUES (?,?,?,?,?)",
                        (source_ids["local"], macro["macro_id"], macro["name"], macro["sequence"], fname),
                    )

    conn.commit()

    # -- JSON bundle for the viewer -----------------------------------------
    conn.row_factory = sqlite3.Row
    bundle = {
        "generated": now,
        "image": {"width": 491, "height": 710},
        "keys": [dict(r) for r in conn.execute("SELECT key_code, key_label, key_group, polygon, anomaly FROM keys")],
        "sources": [dict(r) for r in conn.execute("SELECT id, slug, repo, url, license, format FROM sources")],
        "profiles": [],
        "macros": [dict(r) for r in conn.execute("SELECT source_id, macro_id, name, sequence FROM macros")],
    }
    for key in bundle["keys"]:
        key["polygon"] = json.loads(key["polygon"])
    for prof in conn.execute("SELECT * FROM profiles ORDER BY source_id, name"):
        rows = conn.execute(
            "SELECT key_code, key_label, action_type, action_value, action_label"
            " FROM bindings WHERE profile_id=?", (prof["id"],)
        ).fetchall()
        bundle["profiles"].append({
            "id": prof["id"], "source_id": prof["source_id"], "name": prof["name"],
            "origin": prof["origin_path"], "format": prof["format"],
            "color": prof["color"], "stick_mode": prof["stick_mode"],
            "bindings": [dict(r) for r in rows],
        })
    with open(out_json, "w") as fh:
        json.dump(bundle, fh, separators=(",", ":"))

    counts = {t: conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
              for t in ("sources", "profiles", "bindings", "macros", "keys", "linux_keycodes")}
    conn.close()
    print("wrote %s" % out_db)
    print("wrote %s (%.1f KB)" % (out_json, os.path.getsize(out_json) / 1024))
    for table, n in counts.items():
        print("  %-16s %d" % (table, n))


if __name__ == "__main__":
    main()
