#!/usr/bin/env bash
set -euo pipefail

ENGRAM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIN_PYTHON_MINOR=10   # require 3.10+

# ── colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BOLD='\033[1m'; RESET='\033[0m'

info()    { printf "${BOLD}  →${RESET} %s\n" "$*"; }
ok()      { printf "${GREEN}  ✓${RESET} %s\n" "$*"; }
warn()    { printf "${YELLOW}  !${RESET} %s\n" "$*"; }
die()     { printf "${RED}  ✗${RESET} %s\n" "$*" >&2; exit 1; }

printf "\n${BOLD}Engram setup${RESET}\n\n"

# ── 1. Find or install Python 3.10+ ──────────────────────────────────────────
find_python() {
    for candidate in python3.12 python3.11 python3.10 python3 python; do
        if command -v "$candidate" &>/dev/null; then
            local ver
            ver=$("$candidate" -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo 0)
            local major
            major=$("$candidate" -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo 0)
            if [[ "$major" -eq 3 && "$ver" -ge "$MIN_PYTHON_MINOR" ]]; then
                echo "$candidate"
                return 0
            fi
        fi
    done
    return 1
}

if PYTHON=$(find_python); then
    ok "Python found: $PYTHON ($($PYTHON --version))"
else
    warn "Python 3.10+ not found — attempting install..."

    OS="$(uname -s)"
    case "$OS" in
        Darwin)
            if command -v brew &>/dev/null; then
                info "Installing python@3.12 via Homebrew..."
                brew install python@3.12
                PYTHON="$(brew --prefix)/bin/python3.12"
            else
                die "Homebrew not found. Install it first: https://brew.sh, then re-run this script."
            fi
            ;;
        Linux)
            if command -v apt-get &>/dev/null; then
                info "Installing python3.12 via apt..."
                sudo apt-get update -q && sudo apt-get install -y python3.12 python3.12-venv python3-pip
                PYTHON="python3.12"
            elif command -v dnf &>/dev/null; then
                info "Installing python3.12 via dnf..."
                sudo dnf install -y python3.12
                PYTHON="python3.12"
            elif command -v pacman &>/dev/null; then
                info "Installing python via pacman..."
                sudo pacman -Sy --noconfirm python
                PYTHON="python3"
            else
                die "Could not detect package manager. Install Python 3.10+ manually and re-run."
            fi
            ;;
        *)
            die "Unsupported OS: $OS. Install Python 3.10+ manually and re-run."
            ;;
    esac

    PYTHON=$(find_python) || die "Python install succeeded but binary not found. Check your PATH."
    ok "Python installed: $PYTHON ($($PYTHON --version))"
fi

# ── 2. Create virtual environment ────────────────────────────────────────────
VENV_DIR="$ENGRAM_DIR/venv"
if [[ -d "$VENV_DIR" ]]; then
    ok "Virtual environment already exists"
else
    info "Creating virtual environment..."
    "$PYTHON" -m venv "$VENV_DIR"
    ok "Virtual environment created at $VENV_DIR"
fi

VENV_PYTHON="$VENV_DIR/bin/python3"
VENV_PIP="$VENV_DIR/bin/pip"

# Upgrade pip quietly
"$VENV_PIP" install --upgrade pip --quiet

# ── 3. Install requirements ───────────────────────────────────────────────────
info "Installing Python dependencies..."
"$VENV_PIP" install -r "$ENGRAM_DIR/requirements.txt" --quiet
ok "Dependencies installed"

# ── 4. Initialise database ────────────────────────────────────────────────────
info "Initialising Engram database..."
"$VENV_PYTHON" "$ENGRAM_DIR/engram_cli.py" init
ok "Database initialised"

# ── 5. Register MCP, skill, and hooks for detected tools ─────────────────────
info "Configuring AI coding tools..."
"$VENV_PYTHON" "$ENGRAM_DIR/engram_cli.py" install
printf "\n"

# ── 6. Shell alias hint ───────────────────────────────────────────────────────
ENGRAM_BIN="$ENGRAM_DIR/engram"
printf "${BOLD}Setup complete.${RESET}\n\n"
printf "Add a shell alias for quick access:\n"
printf "  ${BOLD}echo \"alias engram='$ENGRAM_BIN'\" >> ~/.zshrc && source ~/.zshrc${RESET}\n\n"
printf "Or add $ENGRAM_DIR to your PATH.\n\n"
printf "Restart your IDE to activate MCP + hooks.\n\n"
