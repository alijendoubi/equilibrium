#!/usr/bin/env bash
# Shared helpers for scripts/github/*.sh. Source it; do not execute directly.
# shellcheck shell=bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RULESET_FILE="$REPO_ROOT/.github/rulesets/main.json"
# shellcheck disable=SC2034  # consumed by bootstrap-repo.sh
LABELS_FILE="$SCRIPT_DIR/labels.json"
RULESET_NAME="main-protection"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m ok\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mWARN\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31mERROR\033[0m %s\n' "$*" >&2; exit 1; }

require_gh() {
  command -v gh >/dev/null 2>&1 || die "GitHub CLI 'gh' is required: https://cli.github.com"
  gh auth status >/dev/null 2>&1 || die "gh is not authenticated. Run: gh auth login"
}

# Pick a Python interpreter for JSON parsing (jq is not guaranteed on Windows).
python_bin() {
  local candidate
  for candidate in python3 python py; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import json' >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done
  die "python3 (or python) is required to parse JSON"
}

# True when gh error output looks like a plan/permission limitation.
is_plan_limit_error() {
  grep -qiE 'HTTP 403|Upgrade to GitHub Pro|make this repository public|not available' <<<"$1"
}

# Create or update the ruleset named $RULESET_NAME. Never fails on 403 (plan limits).
apply_ruleset() {
  local repo="$1" out existing_id
  [[ -f "$RULESET_FILE" ]] || die "Ruleset file not found: $RULESET_FILE"
  log "Applying ruleset '$RULESET_NAME' to $repo"

  if ! out="$(gh api "repos/$repo/rulesets" --paginate \
      --jq ".[] | select(.name == \"$RULESET_NAME\") | .id" 2>&1)"; then
    if is_plan_limit_error "$out"; then
      warn "Rulesets are not available for $repo on the current plan (private repo on GitHub Free)."
      warn "Re-run after making the repo public: scripts/github/go-public.sh"
      return 0
    fi
    die "Listing rulesets failed: $out"
  fi
  existing_id="$(head -n1 <<<"$out" | tr -d '[:space:]')"

  local method="POST" path="repos/$repo/rulesets"
  if [[ -n "$existing_id" ]]; then
    method="PUT"
    path="repos/$repo/rulesets/$existing_id"
  fi

  if ! out="$(gh api -X "$method" "$path" --input "$RULESET_FILE" 2>&1)"; then
    if is_plan_limit_error "$out"; then
      warn "GitHub refused the ruleset (HTTP 403) - private repos on GitHub Free cannot enforce rulesets."
      warn "Re-run after making the repo public: scripts/github/go-public.sh"
      return 0
    fi
    die "Applying ruleset failed: $out"
  fi
  if [[ "$method" == "PUT" ]]; then ok "Ruleset updated (id $existing_id)"; else ok "Ruleset created"; fi
}
