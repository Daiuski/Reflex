#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Reflex — macOS build & package script
# Run from the project root:  bash build.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="Reflex"
VERSION="1.0.0"
DMG_NAME="${APP_NAME}-${VERSION}.dmg"
ENTITLEMENTS="${PROJECT_ROOT}/entitlements.plist"

cd "$PROJECT_ROOT"

echo "▶ Checking dependencies…"

# Locate Homebrew (Apple Silicon: /opt/homebrew, Intel: /usr/local)
if command -v brew &>/dev/null; then
    BREW=brew
elif [ -x /opt/homebrew/bin/brew ]; then
    BREW=/opt/homebrew/bin/brew
    eval "$($BREW shellenv)"
elif [ -x /usr/local/bin/brew ]; then
    BREW=/usr/local/bin/brew
else
    echo "✖ Homebrew not found. Install it from https://brew.sh then re-run."
    exit 1
fi

python3 -c "import py2app" 2>/dev/null || {
    echo "  Installing py2app…"
    pip3 install py2app
}
command -v create-dmg &>/dev/null || {
    echo "  Installing create-dmg via Homebrew…"
    "$BREW" install create-dmg
}

echo "▶ Cleaning previous build…"
rm -rf build dist

echo "▶ Building .app bundle with py2app…"
python3 setup.py py2app 2>&1

APP_PATH="${PROJECT_ROOT}/dist/${APP_NAME}.app"

if [ ! -d "$APP_PATH" ]; then
    echo "✖ Build failed — ${APP_PATH} not found."
    exit 1
fi

# ── Code signing (ad-hoc if no Developer ID available) ───────────────────────
echo "▶ Code signing…"
if security find-identity -v -p codesigning | grep -q "Developer ID Application"; then
    IDENTITY=$(security find-identity -v -p codesigning | grep "Developer ID Application" | head -1 | awk '{print $2}')
    echo "  Signing with Developer ID: ${IDENTITY}"
    codesign --deep --force --options runtime \
        --entitlements "$ENTITLEMENTS" \
        --sign "$IDENTITY" \
        "$APP_PATH"
else
    echo "  No Developer ID found — using ad-hoc signature (app will work locally)."
    codesign --deep --force --sign - "$APP_PATH"
fi

# ── Create .dmg ───────────────────────────────────────────────────────────────
echo "▶ Creating .dmg…"
rm -f "${PROJECT_ROOT}/dist/${DMG_NAME}"

create-dmg \
    --volname "${APP_NAME}" \
    --volicon "${PROJECT_ROOT}/icon.icns" \
    --window-pos 200 120 \
    --window-size 560 340 \
    --icon-size 128 \
    --icon "${APP_NAME}.app" 140 160 \
    --hide-extension "${APP_NAME}.app" \
    --app-drop-link 420 160 \
    "${PROJECT_ROOT}/dist/${DMG_NAME}" \
    "${PROJECT_ROOT}/dist/${APP_NAME}.app"

echo ""
echo "✔ Done!  →  dist/${DMG_NAME}"
echo ""
echo "Share dist/${DMG_NAME} with users."
echo "They open the .dmg, drag Reflex to Applications, launch it,"
echo "and grant Accessibility permission when prompted — nothing else needed."
