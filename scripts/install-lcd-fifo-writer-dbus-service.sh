#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: install-lcd-fifo-writer-dbus-service.sh [--no-enable] [--dry-run] [--help]

Installs the DBus FIFO writer service into user locations:
- copies script to ~/.local/bin
- installs env template to ~/.config/g13
- installs user systemd unit to ~/.config/systemd/user
- updates SCRIPT_PATH in env
- reloads systemd user units
- enables and starts the service (unless --no-enable)

Options:
  --no-enable   Copy files but do not enable/start the user service.
  --dry-run     Print actions without making any filesystem or system changes.
  --help        Show this help.
USAGE
}

SKIP_ENABLE=0
DRY_RUN=0

while [[ ${#} -gt 0 ]]; do
  case "${1}" in
    --no-enable)
      SKIP_ENABLE=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: ${1}" >&2
      usage
      exit 1
      ;;
  esac
done

SCRIPT_NAME="lcd-fifo-writer-dbus.sh"
SERVICE_NAME="lcd-fifo-writer-dbus.service"
ENV_NAME="lcd-fifo-writer-dbus.env"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$REPO_ROOT/.." && pwd)"

SCRIPT_SRC="$REPO_ROOT/scripts/$SCRIPT_NAME"
SERVICE_SRC="$REPO_ROOT/scripts/$SERVICE_NAME"
ENV_SRC="$REPO_ROOT/scripts/${ENV_NAME}.example"

LOCAL_BIN_DIR="$HOME/.local/bin"
CONFIG_DIR="$HOME/.config/g13"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
SCRIPT_DST="$LOCAL_BIN_DIR/$SCRIPT_NAME"
SERVICE_DST="$SYSTEMD_USER_DIR/g13-$SERVICE_NAME"
ENV_DST="$CONFIG_DIR/$ENV_NAME"

if [[ ! -f "$SCRIPT_SRC" || ! -f "$SERVICE_SRC" || ! -f "$ENV_SRC" ]]; then
  echo "Required source files are missing from repo scripts directory." >&2
  exit 1
fi

if [[ "$DRY_RUN" == "1" ]]; then
  echo "DRY RUN enabled"
  echo "Would install script to: $SCRIPT_DST"
  echo "Would install env file to: $ENV_DST"
  echo "Would install systemd unit to: $SERVICE_DST"
  echo "Would set SCRIPT_PATH in env file to: $SCRIPT_DST"
  echo "Would run: systemctl --user daemon-reload"
  if [[ "$SKIP_ENABLE" == "1" ]]; then
    echo "Would skip: systemctl --user enable --now g13-$SERVICE_NAME"
  else
    echo "Would run: systemctl --user enable --now g13-$SERVICE_NAME"
  fi
  exit 0
fi

mkdir -p "$LOCAL_BIN_DIR" "$CONFIG_DIR" "$SYSTEMD_USER_DIR"

install -m 0755 "$SCRIPT_SRC" "$SCRIPT_DST"
cp "$ENV_SRC" "$ENV_DST"
cp "$SERVICE_SRC" "$SERVICE_DST"

if grep -q '^SCRIPT_PATH=' "$ENV_DST"; then
  sed -i "s#^SCRIPT_PATH=.*#SCRIPT_PATH=$SCRIPT_DST#" "$ENV_DST"
else
  printf 'SCRIPT_PATH=%s\n' "$SCRIPT_DST" >> "$ENV_DST"
fi

echo "Installed DBus FIFO writer to:"
echo "  $SCRIPT_DST"
echo "  $ENV_DST"
echo "  $SERVICE_DST"

echo "Reloading user systemd units..."
systemctl --user daemon-reload

echo "SCRIPT_PATH set in env file: $SCRIPT_DST"
echo "To inspect and tune: $ENV_DST"

if [[ "$SKIP_ENABLE" == "0" ]]; then
  echo "Enabling and starting g13-lcd-fifo-writer-dbus.service..."
  systemctl --user enable --now g13-lcd-fifo-writer-dbus.service
  echo "Service status:"
  systemctl --user status --no-pager g13-lcd-fifo-writer-dbus.service
else
  echo "Enable/start skipped. Run when ready: systemctl --user enable --now g13-lcd-fifo-writer-dbus.service"
fi
