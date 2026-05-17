#!/usr/bin/env bash
# bootstrap.sh — Path B installer for claude-obsidian-vault
#
# What this does:
#   1. Checks prerequisites (macOS, Homebrew)
#   2. Installs Obsidian via Homebrew Cask if not present
#   3. Opens Obsidian
#   4. Opens obsidian:// URIs to prompt Smart Connections + Bases install
#   5. Prints next-step instructions (Path A)
#
# Usage:
#   ./scripts/bootstrap.sh              # normal run
#   ./scripts/bootstrap.sh --dry-run    # print what would happen, do nothing
#   GITHUB_TOKEN=<token> ./scripts/bootstrap.sh   # authenticated registry access
#
# Idempotent: safe to run multiple times. Already-installed steps are skipped.

set -euo pipefail

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RESET='\033[0m'

ok()   { echo -e "${GREEN}[ok]${RESET}    $*"; }
warn() { echo -e "${YELLOW}[warn]${RESET}  $*"; }
err()  { echo -e "${RED}[error]${RESET} $*" >&2; }
info() { echo -e "        $*"; }

# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------
DRY_RUN=false

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    *)
      err "Unknown argument: $arg"
      echo "Usage: $0 [--dry-run]"
      exit 1
      ;;
  esac
done

if $DRY_RUN; then
  warn "Dry-run mode — nothing will be installed or opened."
  echo ""
fi

# ---------------------------------------------------------------------------
# Step 0: Require macOS
# ---------------------------------------------------------------------------
if [[ "$(uname -s)" != "Darwin" ]]; then
  err "This script requires macOS. Linux support is tracked but not yet implemented."
  err "For Linux: install Obsidian manually from https://obsidian.md/download, then follow Path A."
  exit 1
fi

ok "macOS detected."

# ---------------------------------------------------------------------------
# Step 1: Require Homebrew
# ---------------------------------------------------------------------------
if ! command -v brew &>/dev/null; then
  err "Homebrew is required but not installed."
  err "Install it from https://brew.sh, then re-run this script."
  exit 1
fi

ok "Homebrew found: $(brew --version | head -1)"

# ---------------------------------------------------------------------------
# Step 2: Install Obsidian via Homebrew Cask (idempotent)
# ---------------------------------------------------------------------------
if brew list --cask obsidian &>/dev/null 2>&1; then
  ok "Obsidian already installed (Homebrew Cask)."
elif [[ -d "/Applications/Obsidian.app" ]]; then
  ok "Obsidian already installed (found at /Applications/Obsidian.app)."
else
  info "Installing Obsidian via Homebrew Cask..."
  if $DRY_RUN; then
    info "[dry-run] Would run: brew install --cask obsidian"
  else
    brew install --cask obsidian
    ok "Obsidian installed."
  fi
fi

# ---------------------------------------------------------------------------
# Step 3: Open Obsidian
# ---------------------------------------------------------------------------
info "Opening Obsidian..."
if $DRY_RUN; then
  info "[dry-run] Would run: open -a Obsidian"
else
  open -a Obsidian || {
    warn "Could not open Obsidian automatically. Please open it manually before continuing."
  }
  # Give Obsidian a moment to launch before opening URIs
  sleep 3
fi

ok "Obsidian opened (or already running)."

# ---------------------------------------------------------------------------
# Step 4: Prompt Smart Connections install via obsidian:// URI
# ---------------------------------------------------------------------------
info ""
info "Next: you need to install Smart Connections in Obsidian."
info "Smart Connections is the semantic retrieval substrate for the cascade."
info ""
info "Opening the plugin page in Obsidian..."

if $DRY_RUN; then
  info "[dry-run] Would run: open 'obsidian://show-plugin?id=smart-connections'"
else
  open "obsidian://show-plugin?id=smart-connections" 2>/dev/null || {
    warn "Could not open obsidian:// URI automatically."
    warn "In Obsidian: Settings → Community plugins → Browse → search 'Smart Connections' → Install → Enable"
  }
fi

echo ""
warn "ACTION REQUIRED: Install and enable Smart Connections in Obsidian."
warn "After enabling, go to Smart Connections settings and click 'Rebuild index'."
echo ""
read -rp "Press Enter when Smart Connections is installed and the index has been rebuilt... "

# ---------------------------------------------------------------------------
# Step 5: Prompt Bases enable via obsidian:// URI
# ---------------------------------------------------------------------------
info ""
info "Next: enable Bases in Obsidian."
info "Bases is a core Obsidian plugin (no install needed — just enable it)."
info ""
info "Opening the core plugins page in Obsidian..."

if $DRY_RUN; then
  info "[dry-run] Would run: open 'obsidian://show-plugin?id=bases'"
else
  open "obsidian://show-plugin?id=bases" 2>/dev/null || {
    warn "Could not open obsidian:// URI automatically."
    warn "In Obsidian: Settings → Core plugins → find 'Bases' → enable it"
  }
fi

echo ""
warn "ACTION REQUIRED: Enable Bases in Obsidian (Settings → Core plugins → Bases)."
echo ""
read -rp "Press Enter when Bases is enabled... "

# ---------------------------------------------------------------------------
# Step 6: Optional — verify GITHUB_TOKEN for authenticated registry access
# ---------------------------------------------------------------------------
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  ok "GITHUB_TOKEN is set — authenticated registry access will be available."
  info "When you run '/plugin marketplace add' in Cowork, the token will be used automatically."
else
  info "No GITHUB_TOKEN set. Unauthenticated registry access (lower rate limits)."
  info "If you hit rate limits: export GITHUB_TOKEN=<your-token> and re-run, or set it before Cowork."
fi

# ---------------------------------------------------------------------------
# Step 7: Print next-step instructions (Path A)
# ---------------------------------------------------------------------------
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
ok "Bootstrap complete. Obsidian is ready with Smart Connections and Bases."
echo ""
info "Next steps (Path A):"
info ""
info "  1. Open Cowork (Claude for Desktop) and select your project folder"
info "     — this is the folder you want to use as your vault root."
info ""
info "  2. In Cowork, run:"
info "       /plugin marketplace add https://github.com/<owner>/claude-obsidian-vault"
info "       /plugin install vault-framework@claude-obsidian-vault"
info ""
info "  3. Run /vault-setup — Claude will ask 3 questions and scaffold your vault."
info ""
info "  4. After setup, verify the baseline:"
info "       python3 plugins/vault-framework/scripts/verify_baseline.py --vault <your-path>"
info ""
info "  See INSTALL.md for full details, troubleshooting, and optional plugins."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
