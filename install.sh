#!/usr/bin/env bash
#
# claude-content-engine installer
# Install, update, or uninstall claude-content-engine for Claude Code.
#
# Uses the `claude plugin` CLI so the marketplace and plugin are registered
# through Claude Code itself - no hand-editing of config files.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/quionie/claude-content-engine/main/install.sh | bash
#   ./install.sh --update
#   ./install.sh --uninstall
#

set -euo pipefail

# --- Configuration ---
MARKETPLACE_REPO="quionie/claude-content-engine"
MARKETPLACE_NAME="claude-content-engine"
PLUGIN_ID="claude-content-engine@claude-content-engine"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# --- Helpers ---
info()    { printf "${BLUE}[info]${NC}  %s\n" "$1"; }
success() { printf "${GREEN}[ok]${NC}    %s\n" "$1"; }
warn()    { printf "${YELLOW}[warn]${NC}  %s\n" "$1"; }
error()   { printf "${RED}[error]${NC} %s\n" "$1" >&2; }

# --- Pre-flight checks ---
preflight() {
    if ! command -v claude &> /dev/null; then
        error "The 'claude' CLI is required but was not found."
        error "Install Claude Code first: https://claude.com/claude-code"
        exit 1
    fi

    if ! command -v python3 &> /dev/null; then
        warn "python3 not found. The skills will work, but the quality gate"
        warn "hooks (AI slop detector) need python3 to run."
    fi
}

# --- Install ---
do_install() {
    info "Adding the ${MARKETPLACE_NAME} marketplace..."
    if ! claude plugin marketplace add "${MARKETPLACE_REPO}" 2>/dev/null; then
        info "Marketplace already added - refreshing it instead."
        claude plugin marketplace update "${MARKETPLACE_NAME}"
    fi

    info "Installing the plugin..."
    claude plugin install "${PLUGIN_ID}"

    printf "\n"
    success "claude-content-engine installed!"
    printf "\n"
    info "Run ${BOLD}/reload-plugins${NC} in an open Claude Code session (or restart) to activate."
    info "To update later: ${BOLD}./install.sh --update${NC}"
    info "To uninstall:    ${BOLD}./install.sh --uninstall${NC}"
}

# --- Update ---
do_update() {
    info "Refreshing the marketplace..."
    claude plugin marketplace update "${MARKETPLACE_NAME}"

    info "Reinstalling the plugin at the latest version..."
    claude plugin install "${PLUGIN_ID}"

    printf "\n"
    success "claude-content-engine is up to date."
    info "Run ${BOLD}/reload-plugins${NC} in an open session (or restart) to pick up changes."
}

# --- Uninstall ---
do_uninstall() {
    info "Uninstalling the plugin..."
    claude plugin uninstall "${PLUGIN_ID}" || warn "Plugin was not installed."

    info "Removing the marketplace..."
    claude plugin marketplace remove "${MARKETPLACE_NAME}" || warn "Marketplace was not registered."

    printf "\n"
    success "claude-content-engine has been uninstalled."
    info "Your content memory at ~/.claude-content-engine/ was left in place."
    info "Remove it with: ${BOLD}rm -rf ~/.claude-content-engine${NC}"
}

# --- Main ---
main() {
    printf "\n"
    printf "${BOLD}  claude-content-engine${NC} installer\n"
    printf "  ─────────────────────────────\n"
    printf "\n"

    preflight

    case "${1:-}" in
        --update|-u)
            do_update
            ;;
        --uninstall|--remove|-r)
            do_uninstall
            ;;
        --help|-h)
            printf "Usage: install.sh [OPTIONS]\n\n"
            printf "Options:\n"
            printf "  (none)        Install claude-content-engine\n"
            printf "  --update      Update to the latest version\n"
            printf "  --uninstall   Remove claude-content-engine\n"
            printf "  --help        Show this help message\n"
            ;;
        "")
            do_install
            ;;
        *)
            error "Unknown option: $1"
            printf "Run with --help for usage information.\n"
            exit 1
            ;;
    esac
}

main "$@"
