#!/usr/bin/env bash
# Flip the repo to PUBLIC (for hackathon submission) and re-apply the main ruleset.
# Usage: scripts/github/go-public.sh [--yes] [OWNER/REPO]   (default alijendoubi/equilibrium)
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

ASSUME_YES=false
REPO="${REPO:-alijendoubi/equilibrium}"
for arg in "$@"; do
  case "$arg" in
    -y|--yes) ASSUME_YES=true ;;
    -h|--help) sed -n '2,3p' "$0"; exit 0 ;;
    */*) REPO="$arg" ;;
    *) die "Unknown argument: $arg" ;;
  esac
done

require_gh

visibility="$(gh repo view "$REPO" --json visibility --jq .visibility)"
if [[ "$visibility" == "PUBLIC" ]]; then
  ok "$REPO is already public"
else
  warn "This makes $REPO PUBLIC: all code, issues and FULL GIT HISTORY become visible."
  warn "Make sure gitleaks is green and no secrets were ever committed."
  if [[ "$ASSUME_YES" != true ]]; then
    read -r -p "Type the repo name ($REPO) to confirm: " answer
    [[ "$answer" == "$REPO" ]] || die "Confirmation did not match; aborting."
  fi
  log "Changing visibility to public"
  gh repo edit "$REPO" --visibility public --accept-visibility-change-consequences
  ok "$REPO is now public"
fi

apply_ruleset "$REPO"
log "Done. CodeQL code scanning will now work (GitHub Advanced Security is free for public repos)."
