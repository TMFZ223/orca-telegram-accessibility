#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

# Orca loads user extensions from the invoking user's data directory,
# not from root's home when this script is run with sudo.
if [ "$(id -u)" -eq 0 ] && [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != root ]; then
    TARGET_USER=$SUDO_USER
    TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)
    if [ -z "$TARGET_HOME" ] || [ ! -d "$TARGET_HOME" ]; then
        printf 'Cannot determine the home directory of %s\n' "$TARGET_USER" >&2
        exit 1
    fi
    DATA_HOME="$TARGET_HOME/.local/share"
else
    TARGET_USER=$(id -un)
    DATA_HOME=${XDG_DATA_HOME:-"$HOME/.local/share"}
fi

EXTENSION_DIR="$DATA_HOME/orca/extensions/telegram_accessibility"

mkdir -p "$EXTENSION_DIR"
install -m 0644 "$SCRIPT_DIR/__init__.py" "$EXTENSION_DIR/__init__.py"
install -m 0644 "$SCRIPT_DIR/links.py" "$EXTENSION_DIR/links.py"
install -m 0644 "$SCRIPT_DIR/reactions.py" "$EXTENSION_DIR/reactions.py"
install -m 0644 "$SCRIPT_DIR/diagnostics.py" "$EXTENSION_DIR/diagnostics.py"

if [ "$(id -u)" -eq 0 ] && [ "$TARGET_USER" != root ]; then
    chown -R "$TARGET_USER:$(id -gn "$TARGET_USER")" "$EXTENSION_DIR"
fi

printf 'Installed extension files to: %s\n' "$EXTENSION_DIR"
printf '\n'
printf 'Run these commands as %s (without sudo):\n' "$TARGET_USER"
printf '  orca --approve-extension telegram_accessibility\n'
printf '  orca --replace\n'
printf '\n'
printf 'Orca requires approval again whenever the extension files change.\n'
