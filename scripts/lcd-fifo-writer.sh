#!/usr/bin/env bash
set -euo pipefail

# Example FIFO publisher for Linux G13 LCD input.
# It writes 5-line updates repeatedly from an arbitrary command.
#
# Usage:
#   scripts/lcd-fifo-writer.sh                     # periodic status demo
#   scripts/lcd-fifo-writer.sh "jgtans" "idle"    # start with initial lines
#
# Environment:
#   LCD_FIFO     FIFO path (default /tmp/g13_lcd_fifo)
#   LCD_INTERVAL update interval in seconds (default 1)

FIFO="${LCD_FIFO:-/tmp/g13_lcd_fifo}"
INTERVAL="${LCD_INTERVAL:-1}"

# Ensure FIFO exists (non-destructive: don't replace existing non-FIFO file).
if [[ -p "$FIFO" ]]; then
  :
elif [[ -e "$FIFO" ]]; then
  echo "Refusing to continue: $FIFO exists and is not a FIFO" >&2
  exit 1
else
  mkdir -p "$(dirname "$FIFO")"
  mkfifo "$FIFO"
fi

# Optional CLI seed values for first render
line1="${1:-jgtans}"
line2="${2:-applet active}"
line3="${3:-$(date '+%Y-%m-%d')}"
line4="${4:-$(date '+%H:%M:%S')}"
line5="${5:-}"

render_once() {
  {
    printf '%s\n' "$line1"
    printf '%s\n' "$line2"
    printf '%s\n' "$line3"
    printf '%s\n' "$line4"
    printf '%s\n' "$line5"
  } > "$FIFO"
}

cleanup() {
  :
}
trap cleanup INT TERM

render_once

# Replace this loop with your DBus subscriber and map events to lines 1-5.
while true; do
  line1="jgtans"
  line2="status: ok"
  line3="cpu: $(awk '{print int($1)}' /proc/loadavg 2>/dev/null || echo n/a)"
  line4="mem: $(free -m | awk 'NR==2{print $3"/"$2"MB"}' 2>/dev/null || echo n/a)"
  line5="time: $(date '+%H:%M:%S')"
  render_once
  sleep "$INTERVAL"

done
