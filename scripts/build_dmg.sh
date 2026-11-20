#!/usr/bin/env bash
# macOS Application Bundle (.app) & DMG Installer Builder for JARVIS Mark-LVII
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR"

BUILD_DIR="$DIR/build"
APP_DIR="$BUILD_DIR/Jarvis.app"
DMG_ROOT="$BUILD_DIR/dmg_root"
OUTPUT_DMG="$HOME/Desktop/Jarvis-Mark-LVII.dmg"

echo "=========================================="
echo "📦 Building JARVIS macOS App & DMG Installer"
echo "=========================================="

rm -rf "$BUILD_DIR"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"
mkdir -p "$DMG_ROOT"

# Create Info.plist
cat <<EOF > "$APP_DIR/Contents/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>Jarvis</string>
    <key>CFBundleIdentifier</key>
    <string>com.fatihmakes.jarvis</string>
    <key>CFBundleName</key>
    <string>JARVIS</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>57.0</string>
    <key>CFBundleVersion</key>
    <string>57.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSMicrophoneUsageDescription</key>
    <string>JARVIS needs microphone access for voice control and live speech processing.</string>
    <key>NSCameraUsageDescription</key>
    <string>JARVIS needs camera access for visual perception and image analysis.</string>
</dict>
</plist>
EOF

# Create Launcher executable inside Contents/MacOS/Jarvis
cat <<'EOF' > "$APP_DIR/Contents/MacOS/Jarvis"
#!/usr/bin/env bash
APP_BUNDLE="$( cd "$( dirname "${BASH_SOURCE[0]}" )/../../.." && pwd )"
REPO_DIR="$HOME/Downloads/Jarvise"

if [ ! -d "$REPO_DIR" ]; then
    REPO_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/../../../.." && pwd )"
fi

cd "$REPO_DIR"

if [ -f "$REPO_DIR/.venv/bin/python" ]; then
    exec "$REPO_DIR/.venv/bin/python" main.py
else
    exec python3 main.py
fi
EOF

chmod +x "$APP_DIR/Contents/MacOS/Jarvis"

# Copy App to DMG root
cp -R "$APP_DIR" "$DMG_ROOT/"

# Create symlink to /Applications inside DMG for drag-and-drop install
ln -s /Applications "$DMG_ROOT/Applications"

echo "💿 Creating DMG Disk Image at: $OUTPUT_DMG..."
hdiutil create -volname "JARVIS Mark-LVII" -srcfolder "$DMG_ROOT" -ov -format UDZO "$OUTPUT_DMG"

echo "✅ DMG Installer successfully generated at: $OUTPUT_DMG"
echo "You can double click '$OUTPUT_DMG' and drag JARVIS into Applications to install!"
