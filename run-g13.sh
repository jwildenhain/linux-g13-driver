#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRIVER_CMD="$SCRIPT_DIR/src/Linux-G13-Driver"
GUI_JAR="$SCRIPT_DIR/deploy/Linux-G13_v1.0-r36/Linux-G13-GUI.jar"
DRIVER_LOG="${XDG_RUNTIME_DIR:-/tmp}/g13-driver.log"
NO_GUI=0
NO_SUDO=0

usage() {
  cat <<'USAGE'
Usage: ./run-g13.sh [--no-gui] [--no-sudo] [--log PATH]

  --no-gui     Start only the driver (do not launch GUI)
  --no-sudo    Start the driver without sudo. Use this only if /dev/bus/usb
               is already readable/writable for your user (for example via udev rules).
  --log PATH   Write driver output to PATH instead of default
  -h, --help   Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-gui)
      NO_GUI=1
      shift
      ;;
    --no-sudo)
      NO_SUDO=1
      shift
      ;;
    --log)
      if [[ $# -lt 2 ]]; then
        echo "--log requires a path argument"
        usage
        exit 1
      fi
      DRIVER_LOG="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ ! -x "$DRIVER_CMD" ]]; then
  echo "Driver binary not found or not executable: $DRIVER_CMD"
  echo "Run ./build_driver.sh --force from the repo root first."
  exit 1
fi

if [[ ! -f "$GUI_JAR" ]]; then
  echo "GUI jar not found: $GUI_JAR"
  echo "Run ./build_driver.sh --force and cd src && ant first."
  exit 1
fi

if [[ ! -x "$GUI_JAR" ]] && command -v java >/dev/null 2>&1; then
  # jars are usually readable, but this prevents an empty/mispackaged file from still launching.
  echo "GUI jar not executable as a file: $GUI_JAR"
fi

if ! command -v java >/dev/null 2>&1; then
  echo "java not found. Install a JDK/JRE package before continuing."
  exit 1
fi

echo "Stopping any existing G13 driver instances..."
if [[ "$NO_SUDO" -eq 1 ]]; then
  pkill -9 -f 'Linux-G13-Driver' 2>/dev/null || true
else
  if ! sudo pkill -9 -f 'Linux-G13-Driver' 2>/dev/null; then
    # non-fatal if there were none or permissions blocked by sudo config
    true
  fi
fi

if pgrep -f 'Linux-G13-Driver' >/dev/null 2>&1; then
  echo "Could not stop all existing Linux-G13-Driver processes."
  pgrep -af 'Linux-G13-Driver' || true
  if [[ "$NO_SUDO" -eq 0 ]]; then
    echo "You may need to run:"
    echo "  sudo kill -9 <pid>"
  else
    echo "You may need to close existing processes manually."
  fi
fi

echo "Starting Linux-G13-Driver..."
(
  cd "$SCRIPT_DIR/src"
  if [[ "$NO_SUDO" -eq 1 ]]; then
    nohup ./Linux-G13-Driver >"$DRIVER_LOG" 2>&1 &
  else
    if [[ -t 0 ]]; then
      nohup sudo -E ./Linux-G13-Driver >"$DRIVER_LOG" 2>&1 &
    else
      if ! sudo -n true >/dev/null 2>&1; then
        echo "No TTY available for sudo and passwordless sudo is not configured." >&2
        echo "Re-run with --no-sudo after applying USB permissions for your user, or run from a real terminal." >&2
        echo "Example:"
        echo "  ./run-g13.sh --no-gui --no-sudo --log $DRIVER_LOG" >&2
        exit 1
      fi
      nohup sudo -E ./Linux-G13-Driver >"$DRIVER_LOG" 2>&1 &
    fi
  fi
)

echo "Driver log: $DRIVER_LOG"
sleep 1

if ! pgrep -f 'Linux-G13-Driver' >/dev/null; then
  echo "Driver may not have started. Check $DRIVER_LOG"
  exit 1
fi

if [[ "$NO_GUI" -eq 1 ]]; then
  echo "Started in no-gui mode. Driver log: $DRIVER_LOG"
  exit 0
fi

echo "Launching GUI..."
java -jar "$GUI_JAR"
