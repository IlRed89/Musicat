#!/usr/bin/env bash
# ==============================================================================
# MUSICAT macOS LAUNCH DIAGNOSTICS & VERBOSE TERMINAL WRAPPER
# Repository: https://github.com/IlRed89/Musicat
#
# Launches Musicat with full stdout/stderr capture, early bootstrap tracing,
# and simultaneous multi-target logging for immediate issue analysis on macOS.
# ==============================================================================

# Move to script's directory (repository root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Destination log targets
DESKTOP_LOG="$HOME/Desktop/musicat_terminal.log"
DEBUG_LOG="$HOME/Desktop/musicat_debug.log"
BOOT_LOG="$HOME/Library/Application Support/Musicat/logs/musicat_boot.log"

mkdir -p "$HOME/Library/Application Support/Musicat/logs"
mkdir -p "$HOME/Desktop" 2>/dev/null || true

# Flag parsing and mode setup
USE_QT_DEBUG=0
LAUNCH_BUNDLE=0
PASSTHROUGH_ARGS=()

for arg in "$@"; do
    case "$arg" in
        --qt-debug|-d)
            USE_QT_DEBUG=1
            ;;
        --app)
            LAUNCH_BUNDLE=1
            ;;
        *)
            PASSTHROUGH_ARGS+=("$arg")
            ;;
    esac
done

if [ "$USE_QT_DEBUG" -eq 1 ]; then
    export QT_DEBUG_PLUGINS=1
    export QT_MAC_WANTS_LAYER=1
    export QT_LOGGING_RULES="qt.qpa.*=true;qt.core.*=true"
fi

# Detect Python interpreter
PYTHON_BIN=""
if [ -x "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/venv/bin/python"
elif [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
fi

# macOS Architecture & Rosetta 2 Inspection
OS_NAME="$(uname -s)"
ARCH_NAME="$(uname -m)"
ROSETTA_STATUS="Native"
if [ "$OS_NAME" = "Darwin" ]; then
    IS_TRANSLATED="$(sysctl -in sysctl.proc_translated 2>/dev/null || echo 0)"
    if [ "$IS_TRANSLATED" = "1" ]; then
        ROSETTA_STATUS="Rosetta 2 (x86_64 translated on Apple Silicon)"
    elif [ "$ARCH_NAME" = "arm64" ]; then
        ROSETTA_STATUS="Apple Silicon (Native ARM64)"
    else
        ROSETTA_STATUS="Intel Mac (x86_64)"
    fi
fi

echo "================================================================================"
echo "          MUSICAT macOS DIAGNOSTIC LAUNCHER & EARLY TRACING SUITE               "
echo "================================================================================"
echo " Operating System: $OS_NAME $(sw_vers -productVersion 2>/dev/null || echo '')"
echo " Architecture:     $ARCH_NAME ($ROSETTA_STATUS)"
echo " Root Directory:   $SCRIPT_DIR"
if [ "$LAUNCH_BUNDLE" -eq 1 ]; then
    echo " Launch Mode:      macOS .app Bundle"
else
    echo " Python Binary:    $PYTHON_BIN ($($PYTHON_BIN --version 2>&1 || echo 'unknown'))"
fi
echo " Qt Plugin Debug:  $([ "$USE_QT_DEBUG" -eq 1 ] && echo 'ENABLED' || echo 'DISABLED (use --qt-debug to enable)')"
echo "--------------------------------------------------------------------------------"
echo " Output Log Targets:"
echo "   1. Terminal Live Log:  $DESKTOP_LOG"
echo "   2. Desktop Debug Log:  $DEBUG_LOG"
echo "   3. Boot System Log:    $BOOT_LOG"
echo "================================================================================"
echo ""

# Execution
EXIT_CODE=0

if [ "$LAUNCH_BUNDLE" -eq 1 ]; then
    BUNDLE_EXEC=""
    if [ -x "$SCRIPT_DIR/dist/Musicat.app/Contents/MacOS/Musicat" ]; then
        BUNDLE_EXEC="$SCRIPT_DIR/dist/Musicat.app/Contents/MacOS/Musicat"
    elif [ -x "/Applications/Musicat.app/Contents/MacOS/Musicat" ]; then
        BUNDLE_EXEC="/Applications/Musicat.app/Contents/MacOS/Musicat"
    fi

    if [ -n "$BUNDLE_EXEC" ]; then
        echo "[*] Launching compiled bundle: $BUNDLE_EXEC"
        "$BUNDLE_EXEC" "${PASSTHROUGH_ARGS[@]}" 2>&1 | tee "$DESKTOP_LOG"
        EXIT_CODE=${PIPESTATUS[0]}
    else
        echo "[!] Compiled Musicat.app bundle not found in ./dist/ or /Applications/."
        echo "[*] Falling back to Python source execution..."
        "$PYTHON_BIN" main.py "${PASSTHROUGH_ARGS[@]}" 2>&1 | tee "$DESKTOP_LOG"
        EXIT_CODE=${PIPESTATUS[0]}
    fi
else
    if [ -z "$PYTHON_BIN" ]; then
        echo "[ERROR] Python 3 executable not found! Please install Python or set up a venv." >&2
        exit 1
    fi
    "$PYTHON_BIN" main.py "${PASSTHROUGH_ARGS[@]}" 2>&1 | tee "$DESKTOP_LOG"
    EXIT_CODE=${PIPESTATUS[0]}
fi

echo ""
echo "================================================================================"
echo "          MUSICAT EXECUTION FINISHED (EXIT CODE: $EXIT_CODE)                    "
echo "================================================================================"
echo " Diagnostic logs generated:"
[ -f "$DESKTOP_LOG" ] && echo "  [✓] $DESKTOP_LOG ($(wc -l < "$DESKTOP_LOG" 2>/dev/null || echo 0) lines)"
[ -f "$DEBUG_LOG" ] && echo "  [✓] $DEBUG_LOG"
[ -f "$BOOT_LOG" ] && echo "  [✓] $BOOT_LOG"
echo "================================================================================"

exit $EXIT_CODE
