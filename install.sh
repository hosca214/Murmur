#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${MURMUR_REPO:-https://github.com/hosca214/Murmur.git}"
INSTALL_ROOT="$HOME/.murmur"
SRC_DIR="$INSTALL_ROOT/src"
VENV_DIR="$INSTALL_ROOT/venv"
PLIST_PATH="$HOME/Library/LaunchAgents/com.murmur.app.plist"
LOG_DIR="$HOME/Library/Logs/Murmur"

bold() { printf "\033[1m%s\033[0m\n" "$1"; }
err() { printf "\033[31m%s\033[0m\n" "$1" >&2; }

bold "Murmur installer"

if [[ "$(uname)" != "Darwin" ]]; then
    err "Murmur is macOS-only."
    exit 1
fi

OS_MAJOR=$(sw_vers -productVersion | cut -d. -f1)
if (( OS_MAJOR < 13 )); then
    err "Murmur needs macOS 13 (Ventura) or later. You have $(sw_vers -productVersion)."
    exit 1
fi

if ! command -v python3.11 >/dev/null 2>&1; then
    bold "Installing Python 3.11 via Homebrew…"
    if ! command -v brew >/dev/null 2>&1; then
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    brew install python@3.11
    brew install python-tk@3.11
fi

mkdir -p "$INSTALL_ROOT" "$LOG_DIR"

if [[ -d "$SRC_DIR/.git" ]]; then
    bold "Updating Murmur source…"
    git -C "$SRC_DIR" pull --ff-only
else
    bold "Cloning Murmur…"
    git clone "$REPO_URL" "$SRC_DIR"
fi

if [[ ! -d "$VENV_DIR" ]]; then
    bold "Creating venv…"
    python3.11 -m venv "$VENV_DIR"
fi

bold "Installing Python dependencies…"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -e "$SRC_DIR" -r "$SRC_DIR/requirements.txt"

bold "Pre-downloading Whisper model (with retry)…"
ARCH=$(uname -m)
if [[ "$ARCH" == "arm64" ]]; then MODEL="small.en"; else MODEL="base.en"; fi
for ATTEMPT in 1 2 3; do
    if "$VENV_DIR/bin/python" -c "from faster_whisper import WhisperModel; WhisperModel('$MODEL', device='cpu', compute_type='int8')"; then
        break
    fi
    if (( ATTEMPT == 3 )); then
        err "Model download failed after 3 attempts. Resume with:"
        err "  $VENV_DIR/bin/python -c \"from faster_whisper import WhisperModel; WhisperModel('$MODEL', device='cpu', compute_type='int8')\""
        exit 1
    fi
    SLEEP=$(( 2 ** (ATTEMPT + 1) ))
    bold "Retry $ATTEMPT failed, sleeping ${SLEEP}s…"
    sleep "$SLEEP"
done

bold "Installing launchd agent (auto-start at login)…"
mkdir -p "$(dirname "$PLIST_PATH")"
sed \
    -e "s|__VENV_PYTHON__|$VENV_DIR/bin/python|g" \
    -e "s|__SRC_DIR__|$SRC_DIR|g" \
    -e "s|__LOG_OUT__|$LOG_DIR/stdout.log|g" \
    -e "s|__LOG_ERR__|$LOG_DIR/stderr.log|g" \
    "$SRC_DIR/packaging/com.murmur.app.plist" > "$PLIST_PATH"

launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

bold "Launching Murmur…"
"$VENV_DIR/bin/python" -m murmur &

bold "Done. The Murmur menu bar icon should appear shortly."
echo "If the onboarding window doesn't open, run: $VENV_DIR/bin/python -m murmur"
