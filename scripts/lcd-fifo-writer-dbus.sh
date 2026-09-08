#!/usr/bin/env bash
set -euo pipefail

# Lordbooker/DBus -> G13 LCD FIFO bridge.
#
# Environment:
#   LCD_FIFO        FIFO path (default: /tmp/g13_lcd_fifo)
#   DBUS_BUS        --session or --system (default: --session)
#   DBUS_INTERFACE  Interface to match (default: com.jgtans.Lordbooker)
#   DBUS_MEMBER     Signal/member name (default: StatusUpdated)
#   DBUS_MATCH      Full dbus-monitor match expression (overrides interface/member)
#
# Default match pattern expects a signal with up to 5 string arguments.
# Replace DBUS_INTERFACE / DBUS_MEMBER for your specific Lordbooker version.

FIFO="${LCD_FIFO:-/tmp/g13_lcd_fifo}"
DBUS_BUS="${DBUS_BUS:---session}"
DBUS_INTERFACE="${DBUS_INTERFACE:-com.jgtans.Lordbooker}"
DBUS_MEMBER="${DBUS_MEMBER:-StatusUpdated}"
DBUS_MATCH="${DBUS_MATCH:-type='signal',interface='${DBUS_INTERFACE}',member='${DBUS_MEMBER}'}"

if [[ "$DBUS_BUS" != "--session" && "$DBUS_BUS" != "--system" ]]; then
  echo "Unsupported DBUS_BUS value: $DBUS_BUS (use --session or --system)" >&2
  exit 1
fi

if [[ -p "$FIFO" ]]; then
  :
elif [[ -e "$FIFO" ]]; then
  echo "Refusing to continue: $FIFO exists and is not a FIFO" >&2
  exit 1
else
  mkdir -p "$(dirname "$FIFO")"
  mkfifo "$FIFO"
fi

if ! command -v dbus-monitor >/dev/null 2>&1; then
  echo "dbus-monitor not found; install dbus package" >&2
  exit 1
fi

write_lcd() {
  {
    printf '%s\n' "${1:-}"
    printf '%s\n' "${2:-}"
    printf '%s\n' "${3:-}"
    printf '%s\n' "${4:-}"
    printf '%s\n' "${5:-}"
  } > "$FIFO"
}

handle_payload() {
  local -a lines=("${payload[@]}")
  if (( ${#lines[@]} == 0 )); then
    return
  fi

  # keep up to 5 lines for LCD rendering
  write_lcd "${lines[0]:-}" "${lines[1]:-}" "${lines[2]:-}" "${lines[3]:-}" "${lines[4]:-}"
}

parse_string_line() {
  local input="$1"
  if [[ "$input" =~ ^[[:space:]]*string[[:space:]]"(.*)"$ ]]; then
    printf '%s\n' "${BASH_REMATCH[1]}"
    return 0
  fi
  return 1
}

in_message=0
payload=()

trap 'exit 0' INT TERM

while IFS= read -r line; do
  if (( in_message == 0 )); then
    if [[ "$line" == *"interface='$DBUS_INTERFACE'"* && "$line" == *"member='$DBUS_MEMBER'"* ]]; then
      in_message=1
      payload=()
    fi
    continue
  fi

  if [[ -z "$line" ]]; then
    handle_payload
    in_message=0
    payload=()
    continue
  fi

  if [[ "$line" == *"string"* ]]; then
    value="$(parse_string_line "$line" || true)"
    if [[ -n "$value" ]]; then
      payload+=("$value")
    fi
  fi
done < <(dbus-monitor "$DBUS_BUS" "$DBUS_MATCH")

# flush any final payload when stream closes
test -n "${payload[*]-}" && handle_payload
