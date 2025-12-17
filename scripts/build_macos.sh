#!/usr/bin/env bash
set -euo pipefail

# Build MANIC on macOS - unsigned DMG distribution

APP_NAME="MANIC"
VERSION="4.0.01"
DIST_DIR="dist"
DMG_NAME="${APP_NAME}-${VERSION}.dmg"

echo "======================================"
echo "Building ${APP_NAME} for macOS"
echo "======================================"

# Check for uv, fallback to pip
if command -v uv &> /dev/null; then
    echo "Detected uv; using uv for build"
    uv venv .venv || exit 1
    uv sync || exit 1
    uv pip install -U pyinstaller pyinstaller-hooks-contrib pyside6 || exit 1
    UV_RUN="uv run"
else
    echo "uv not found; falling back to pip"
    if [ ! -d .venv ]; then
        python3 -m venv .venv || exit 1
    fi
    source .venv/bin/activate || exit 1
    pip install --upgrade pip || exit 1
    pip install -U pyinstaller pyinstaller-hooks-contrib pyside6 || exit 1
    UV_RUN=""
fi

echo ""
echo "Step 1: Cleaning previous build..."
rm -rf "${DIST_DIR}/${APP_NAME}.app" "${DIST_DIR}/${APP_NAME}" build *.spec.lock || true

echo ""
echo "Step 2: Building .app bundle with PyInstaller..."
$UV_RUN pyinstaller -y --clean MANIC-mac.spec || exit 1

APP_PATH="${DIST_DIR}/${APP_NAME}.app"

if [ ! -d "$APP_PATH" ]; then
    echo "Error: ${APP_PATH} not found after build"
    exit 1
fi

echo ""
echo "Built app at ${APP_PATH}"
echo ""

# Check if create-dmg is installed
if command -v create-dmg &> /dev/null; then
    echo "Step 3: Creating DMG installer..."
    
    # Remove old DMG if exists
    [ -f "${DIST_DIR}/${DMG_NAME}" ] && rm "${DIST_DIR}/${DMG_NAME}"
    
    # Create DMG with drag-to-Applications layout
    create-dmg \
        --volname "${APP_NAME}" \
        --background "installer/dmg-background.png" \
        --window-pos 200 120 \
        --window-size 800 500 \
        --icon-size 128 \
        --icon "${APP_NAME}.app" 200 240 \
        --hide-extension "${APP_NAME}.app" \
        --app-drop-link 600 240 \
        --text-size 14 \
        "${DIST_DIR}/${DMG_NAME}" \
        "${APP_PATH}" || exit 1
    
    echo ""
    echo "======================================"
    echo "Build complete!"
    echo "======================================"
    echo "DMG: ${DIST_DIR}/${DMG_NAME}"
    echo ""
    echo "NOTE: This is an unsigned build."
    echo "Users will need to right-click → Open"
    echo "to bypass Gatekeeper on first launch."
    echo "======================================"
else
    echo ""
    echo "======================================"
    echo "Build complete!"
    echo "======================================"
    echo "App bundle: ${APP_PATH}"
    echo ""
    echo "NOTE: create-dmg not found."
    echo "Install with: brew install create-dmg"
    echo "Or distribute the .app directly (zip it)."
    echo "======================================"
fi
