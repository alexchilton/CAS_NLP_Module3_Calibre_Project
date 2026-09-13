#!/bin/bash
# Build CalibreDaily.app - the menu bar item for the daily enrich sweep.
#
# Hand-assembled bundle rather than an Xcode project: it is one Swift file with
# no dependencies, and a 30-line build script is easier to read than a .pbxproj.
#
#   ./build.sh          build and install to ~/Applications
#   ./build.sh --run    build, install, and launch it

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$HOME/Applications/CalibreDaily.app"

echo "building..."
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# -swift-version 5: the Swift 6 language mode rejects the shared mutable state
# a single-file AppKit app is built on. Nothing here needs strict concurrency.
swiftc -O -swift-version 5 \
    -o "$APP/Contents/MacOS/CalibreDaily" \
    "$HERE/main.swift"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key><string>CalibreDaily</string>
    <key>CFBundleDisplayName</key><string>Calibre Daily</string>
    <key>CFBundleIdentifier</key><string>com.alexchilton.calibre-daily-menubar</string>
    <key>CFBundleExecutable</key><string>CalibreDaily</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleShortVersionString</key><string>1.0</string>
    <key>LSMinimumSystemVersion</key><string>13.0</string>
    <!-- Menu bar only: no dock tile, no window, no app switcher entry. -->
    <key>LSUIElement</key><true/>
</dict>
PLIST
echo '</plist>' >> "$APP/Contents/Info.plist"

chmod +x "$HERE/run_daily_interactive.command" "$HERE/watch_log.command"

# Ad-hoc signature. Without one macOS re-prompts for permissions on every
# rebuild, because an unsigned binary gets a new identity each time.
codesign --force --sign - "$APP" 2>/dev/null || echo "  (codesign skipped)"

echo "installed: $APP"

if [ "${1:-}" = "--run" ]; then
    pkill -f "CalibreDaily" 2>/dev/null || true
    sleep 0.5
    open "$APP"
    echo "running - look for the books icon in the menu bar"
fi