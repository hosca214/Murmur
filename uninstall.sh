#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="$HOME/.murmur"
PLIST_PATH="$HOME/Library/LaunchAgents/com.murmur.app.plist"
APP_SUPPORT="$HOME/Library/Application Support/Murmur"
LOG_DIR="$HOME/Library/Logs/Murmur"
ENV_FILE="$INSTALL_ROOT/.env"

echo "Uninstalling Murmur…"

if [[ -f "$PLIST_PATH" ]]; then
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    rm -f "$PLIST_PATH"
fi

if [[ -f "$ENV_FILE" ]]; then
    read -p "Remove your saved Gemini API key (.env)? [y/N] " yn
    if [[ "$yn" =~ ^[Yy]$ ]]; then
        rm -f "$ENV_FILE"
    fi
fi

rm -rf "$INSTALL_ROOT/src" "$INSTALL_ROOT/venv"
rm -rf "$APP_SUPPORT"
rm -rf "$LOG_DIR"

if [[ -d "$INSTALL_ROOT" ]] && [[ -z "$(ls -A "$INSTALL_ROOT")" ]]; then
    rmdir "$INSTALL_ROOT"
fi

echo "Done."
