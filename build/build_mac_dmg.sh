#!/usr/bin/env bash
# ==============================================================================
# Musicat - macOS DMG Packaging Script
# Generates Musicat-macOS.dmg with Drag-to-Applications layout
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$PROJECT_ROOT/dist"
APP_PATH="$DIST_DIR/Musicat.app"
DMG_PATH="$DIST_DIR/Musicat-macOS.dmg"

echo "=== Building Musicat macOS Disk Image (DMG) ==="

if [ ! -d "$APP_PATH" ]; then
    echo "[ERROR] Musicat.app not found in $DIST_DIR. Run pyinstaller build_mac.spec first."
    exit 1
fi

rm -f "$DMG_PATH"

if command -v create-dmg >/dev/null 2>&1; then
    echo "[INFO] Using create-dmg for styled disk image..."
    create-dmg \
        --volname "Musicat Installer" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "Musicat.app" 175 190 \
        --hide-extension "Musicat.app" \
        --app-drop-link 425 190 \
        "$DMG_PATH" \
        "$APP_PATH"
else
    echo "[INFO] create-dmg not found. Using native macOS hdiutil fallback..."
    TMP_DMG_DIR="$DIST_DIR/dmg_temp"
    rm -rf "$TMP_DMG_DIR"
    mkdir -p "$TMP_DMG_DIR"
    cp -R "$APP_PATH" "$TMP_DMG_DIR/"
    ln -s /Applications "$TMP_DMG_DIR/Applications"
    
    hdiutil create -volname "Musicat" -srcfolder "$TMP_DMG_DIR" -ov -format UDZO "$DMG_PATH"
    rm -rf "$TMP_DMG_DIR"
fi

echo "[SUCCESS] Created macOS DMG at: $DMG_PATH"
ls -lh "$DMG_PATH"
