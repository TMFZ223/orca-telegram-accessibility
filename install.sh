#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DATA_HOME=${XDG_DATA_HOME:-"$HOME/.local/share"}
EXTENSION_DIR="$DATA_HOME/orca/extensions/telegram_accessibility"

mkdir -p "$EXTENSION_DIR"
install -m 0644 "$SCRIPT_DIR/__init__.py" "$EXTENSION_DIR/__init__.py"
install -m 0644 "$SCRIPT_DIR/links.py" "$EXTENSION_DIR/links.py"

printf 'Installed extension files to: %s\n' "$EXTENSION_DIR"
printf '\n'
printf 'Approve the extension, then restart Orca:\n'
printf '  orca --approve-extension telegram_accessibility\n'
printf '  orca --replace\n'
printf '\n'
printf 'Orca requires approval again whenever the extension files change.\n'
