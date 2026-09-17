# LogiFrame + LCD Source Documentation

This repository supports three LCD modes in `bindings-*.properties`:

- `lcd_mode=stats`, `system`, `default`, `sys`
- `lcd_mode=fifo`
- `lcd_mode=logiframe`

Supported keys:

- `lcd_mode` (preferred)
- `lcd_source` (alias)
- `lcd_path` / `lcd_fifo` (FIFO path)
- `lcd_logiframe_page_count` (1..4)
- `lcd_logiframe_page1_cmd` / `lcd_logiframe_page2_cmd` / `lcd_logiframe_page3_cmd` / `lcd_logiframe_page4_cmd`
- `lcd_logiframe_page1_color` .. `lcd_logiframe_page4_color`
- `color` (fallback color)

## LogiFrame mapping

`lcd_mode=logiframe` enables profile buttons as page selectors:

- `G26` -> page 1
- `G27` -> page 2
- `G28` -> page 3
- `G29` -> page 4

Page 1 is the built-in usage view (same data shown in stats mode).

## Default LogiFrame commands and colors

Default generated values now include three ready-made pages (page 1 intentionally blank):

```properties
lcd_mode=logiframe
lcd_logiframe_page_count=4
lcd_logiframe_page1_cmd=
lcd_logiframe_page2_cmd=if [ -z "$STEAM_API_KEY" ] || ( [ -z "$STEAM_ID" ] && [ -z "$STEAM_STEAMID" ] ); then printf 'Steam Friends\\nSet STEAM_API_KEY and STEAM_ID/STEAM_STEAMID env vars\\n'; exit 0; fi; if ! command -v curl >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; then printf 'Steam Friends\\nInstall curl and jq\\n'; exit 0; fi; steam_id="${STEAM_ID:-${STEAM_STEAMID:-}}"; friend_ids=$(curl -sf "https://api.steampowered.com/ISteamUser/GetFriendList/v0001/?key=$STEAM_API_KEY&steamid=$steam_id&relationship=friend" | jq -r '.friendslist.friends[]? | .steamid' | tr '\\n' ',' | sed 's/,$//'); if [ -z "$friend_ids" ]; then printf 'Steam Friends\\nNo friends found\\n'; exit 0; fi; online=$(curl -sf "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key=$STEAM_API_KEY&steamids=$friend_ids" | jq -r '.response.players[]? | select((.personastate // 0) > 0) | .personaname' ); count=$(printf '%s\\n' "$online" | sed '/^$/d' | awk 'END {print NR}'); printf 'Steam Friends\\n'; if [ "$count" -eq 0 ]; then printf 'No friends online\\n'; exit 0; fi; printf 'Online: %s\\n' "$count"; printf '%s\\n' "$online" | head -n 3;
lcd_logiframe_page3_cmd=if ! command -v curl >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; then printf 'Token Usage\\nInstall curl and jq\\n'; exit 0; fi; today=$(date +%F); AG_USED=n/a; AG_LIMIT=n/a; if [ -n "$ANTIGRAVITY_USAGE_URL" ] && [ -n "$ANTIGRAVITY_API_KEY" ]; then ag=$(curl -sf --max-time 8 -H "Authorization: Bearer $ANTIGRAVITY_API_KEY" "$ANTIGRAVITY_USAGE_URL"); if [ -n "$ag" ]; then AG_USED=$(printf '%s' "$ag" | jq -r '.used // .tokens_used // .usage // "n/a"'); AG_LIMIT=$(printf '%s' "$ag" | jq -r '.daily_limit // .limit // "n/a"'); fi; fi; GEM_USED=n/a; GEM_LIMIT=n/a; if [ -n "$GEMINI_USAGE_URL" ] && [ -n "$GEMINI_API_KEY" ]; then gem=$(curl -sf --max-time 8 -H "x-goog-api-key: $GEMINI_API_KEY" "$GEMINI_USAGE_URL"); if [ -n "$gem" ]; then GEM_USED=$(printf '%s' "$gem" | jq -r '.used // .tokens_used // .usage // .total_tokens // "n/a"'); GEM_LIMIT=$(printf '%s' "$gem" | jq -r '.daily_limit // .limit // "n/a"'); fi; fi; CX_USED=n/a; CX_LIMIT=n/a; if [ -n "$OPENAI_API_KEY" ]; then openai_usage=$(curl -sf --max-time 8 -H "Authorization: Bearer $OPENAI_API_KEY" "https://api.openai.com/v1/dashboard/billing/usage?start_date=$today&end_date=$today"); openai_sub=$(curl -sf --max-time 8 -H "Authorization: Bearer $OPENAI_API_KEY" "https://api.openai.com/v1/dashboard/billing/subscription"); if [ -n "$openai_usage" ]; then CX_USED=$(printf '%s' "$openai_usage" | jq -r '.total_usage // .total_tokens // .usage.total_tokens // "n/a"'); fi; if [ -n "$openai_sub" ]; then CX_LIMIT=$(printf '%s' "$openai_sub" | jq -r '.hard_limit_usd // "n/a"'); fi; fi; printf 'Token Usage\\n'; printf 'Antigravity: %s/%s\\n' "$AG_USED" "$AG_LIMIT"; printf 'Gemini: %s/%s\\n' "$GEM_USED" "$GEM_LIMIT"; printf 'Codex/GPT: %s/%s\\n' "$CX_USED" "$CX_LIMIT";
lcd_logiframe_page4_cmd=
lcd_logiframe_page1_color=0,128,255
lcd_logiframe_page2_color=255,153,0
lcd_logiframe_page3_color=0,200,64
lcd_logiframe_page4_color=255,64,64
```

## Command output rendering

Per page, the parser does:

1. Executes configured command (`sh -c`).
2. If output is ASCII PBM (`P1` header + `160x43`) -> renders pixels.
3. Otherwise splits on lines and renders up to 5 text rows.
4. If empty output, writes diagnostic placeholders naming the property.

## Producer notes (FIFO)

- Use newline-separated text, up to 5 lines.
- Keep line length under LCD width limits (`P1..P5` style rendering is capped in driver).

## UI editing in Java GUI

`LogiFrame / LCD Settings` allows editing:

- `lcd_mode`
- `lcd_path`
- `lcd_logiframe_page_count`
- `lcd_logiframe_page1_cmd` .. `lcd_logiframe_page4_cmd`
- `lcd_logiframe_pageN_color`

Changes are saved back to the active profile (`bindings-0..3`).

## Steam connection plan

1. Start Linux G13 driver with your normal user environment so it can read `~/.g13`.
2. In Steam, ensure the G13 virtual input is detected in Controller/Gamepad settings.
3. For keyboard-style games:
   - Keep key macros/actions in `bindings-*.properties` and disable Steam Input if game expects raw keyboard events.
4. For controller-style games:
   - Enable Steam Input and map keys to actions in a game profile.
5. If G13 is not detected, restart Steam after driver starts and reconnect/reload USB.
6. Keep the LCD source stable while testing (`stats` or FIFO path) to avoid repeated process churn.

## DDC monitor module

Optional module controlling a DDC/CI monitor from the G13: an LCD page with
live bars for brightness, contrast and volume, and keys that adjust them.
Inactive when no DDC/CI display is present — `g13-ddc` exits 3 and the tray
source renders an explanatory page, so nothing breaks on machines without one.

Files: `app/g13_ddc.py` (module), `scripts/g13-ddc` (CLI).

Requires `ddcutil` and membership of the `i2c` group. If ddcutil is a local
build not on `PATH`, set `G13_DDCUTIL` in `~/.config/g13/g13-driver.env` so the
driver's page commands inherit it.

### LCD page

Two paths, with different limits:

- **Graphical bars.** `g13-ddc page` emits a 160x43 ASCII PBM. Wire it as
  `lcd_logiframe_pageN_cmd`, selecting the `Keep existing command` screen
  source in the tray so a save does not overwrite it. Note the driver's PBM
  parser reads one whitespace-separated token per pixel, so pixels must be
  emitted spaced; packed rows are consumed as a single pixel and the page falls
  back to raw text.
- **Text bars.** Screen source `DDC monitor` goes through the normal tray
  provider pipeline, which sanitises to ASCII and caps at 26 columns by 5 rows,
  so bars are drawn with `#` and `-`.

### Keys

Bindings support only `p` (keycode) and `m` (macro) — there is no shell-command
action — so each key emits a keycode that a desktop hotkey turns into a
`g13-ddc key` call. `g13-ddc install-keys` writes the GNOME custom keybindings
and prints the matching `bindings-<mode>.properties` lines; `--dry-run` shows
both without changing anything.

| Device key | File key | Linux keycode | X keysym | Action |
| --- | --- | --- | --- | --- |
| G1  | `G0`  | 148 | `XF86Launch1` | wake the panel |
| G2  | `G1`  | 184 | `XF86Launch5` | brightness +5 |
| G9  | `G8`  | 185 | `XF86Launch6` | brightness -5 |
| G3  | `G2`  | 186 | `XF86Launch7` | contrast +5 |
| G10 | `G9`  | 187 | `XF86Launch8` | contrast -5 |
| G4  | `G3`  | 149 | `XF86Launch2` | volume +5 |
| G11 | `G10` | 202 | `XF86Launch3` | volume -5 |
| G8  | `G7`  | 203 | `XF86Launch4` | auto-brightness toggle |
| G15 | `G14` | 188 | `XF86Launch9` | switch input to `0x19` |
| G16 | `G15` | 204 | `XF86LaunchB` | switch input to `0x0F` |

Two traps worth knowing:

- **Binding keys are zero-indexed.** The key labelled G1 on the device is `G0`
  in the properties file (`INPUT_LABELS` in `app/g13_config.py`).
- **GNOME matches accelerators by keysym, not keycode.** F13-F20 look like the
  natural choice and fail silently: on a default X keymap those keycodes carry
  `XF86Tools`, `XF86Launch5-9` and `XF86AudioMicMute`, and one has no symbol at
  all. Check a candidate with `xmodmap -pke | awk '$2 == <keycode + 8>'`, and
  see what a key really emits with
  `xinput test $(xinput list --id-only G13)`.

### Waking a sleeping display

`g13-ddc key wake` restores the output *before* touching DDC, and the order is
the point. A blanked display usually means the graphics driver dropped the
link; on DisplayPort the DDC/CI AUX channel goes with it, so a `VCP D6 = 01`
power-on cannot be delivered while the panel is asleep. The action therefore
runs `xset dpms force on` first, then sends the VCP write, and reports which
steps succeeded.

`g13-ddc key wake-hard` additionally cycles each connected output off and on
with `xrandr`, forcing link retraining for a panel that stays asleep even once
the signal returns. It retries the restore three times per output and reports a
failure rather than leaving an output off silently.

### Switching inputs

`g13-ddc key input <value>` selects a source, e.g. `input 0x19`. Values are
monitor-specific and often mislabelled by ddcutil -- verify by switching and
looking, rather than trusting the name.

Switching is reversible over DDC: the panel keeps answering on the AUX channel
while displaying another source, so a second `input` command switches back.
**But if the monitor's USB hub follows the display input (a built-in KVM, common
on Dell USB-C panels), every device on that hub moves to the other machine** --
keyboard, mouse, webcam, USB audio and the monitor's own ethernet port.

Whether the switch-back key still works depends on where the G13 is plugged in.
Check with `lsusb -t`: a G13 hanging directly off a root hub keeps talking to
this machine and its keys keep working, while one behind the monitor's hub
travels with everything else and its keys will be delivered to the wrong
computer. In that case use the monitor's buttons, or a DDC tool on the machine
the hub moved to.

### Auto-brightness

`g13-ddc key auto` toggles the monitor's own ambient light sensor (VCP `0x66`)
rather than implementing a schedule. Standard MCCS uses `0x01`/`0x02`; Dell
offsets these by `0x80` to `0x81`/`0x82`, and the module accepts both.

Brightness keys switch the sensor off first: with it active the monitor
overrides a manual change within seconds, which makes the keys appear broken.

### Shared bus access

DDC/CI writes take around 50ms and concurrent access can wedge a panel until it
is power cycled. If a `ddcmond` session daemon owns the bus the module routes
through it over D-Bus; otherwise it calls `ddcutil` directly.
