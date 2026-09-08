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
