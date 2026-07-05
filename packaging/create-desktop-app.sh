#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$SRC_DIR/venv/bin/python"
APP="$HOME/Desktop/Murmur.app"

if [[ ! -x "$VENV_PY" ]]; then
    echo "Error: $VENV_PY not found. Run from a project with venv installed." >&2
    exit 1
fi

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>Murmur</string>
    <key>CFBundleDisplayName</key>
    <string>Murmur</string>
    <key>CFBundleIdentifier</key>
    <string>com.murmur.app</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleExecutable</key>
    <string>Murmur</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSUIElement</key>
    <true/>
    <key>LSMinimumSystemVersion</key>
    <string>13.0</string>
    <key>NSMicrophoneUsageDescription</key>
    <string>Murmur transcribes your voice into text.</string>
    <key>NSAppleEventsUsageDescription</key>
    <string>Murmur pastes transcribed text into the active app.</string>
</dict>
</plist>
EOF

cat > "$APP/Contents/MacOS/Murmur" <<EOF
#!/usr/bin/env bash
LOG_DIR="\$HOME/Library/Logs/Murmur"
mkdir -p "\$LOG_DIR"
exec "$VENV_PY" -m murmur >> "\$LOG_DIR/launch.log" 2>&1
EOF
chmod +x "$APP/Contents/MacOS/Murmur"

touch "$APP"

echo "✓ Created $APP"
echo "  Double-click the Murmur icon on your Desktop to start it."
echo "  The first launch will prompt for Mic / Accessibility / Input Monitoring permissions."
