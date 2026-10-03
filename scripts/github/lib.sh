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

# True when gh error output contains an HTTP 403.
is_http_403() {
  grep -qE 'HTTP 403' <<<"$1"
}

# Seconds to wait before retry N (1-based) after an HTTP 403. GitHub can return a
# transient 403 right after a visibility change; it usually succeeds on retry.
RULESET_RETRY_DELAYS=(5 10)

# Print the repo visibility (PUBLIC, PRIVATE or INTERNAL), or UNKNOWN on failure.
repo_visibility() {
  local repo="$1" vis
  if vis="$(gh repo view "$repo" --json visibility --jq .visibility 2>/dev/null)" && [[ -n "$vis" ]]; then
    echo "$vis"
  else
    echo "UNKNOWN"
  fi
}

# Run `gh api "$@"`, retrying on HTTP 403 (up to 3 attempts in total).
# Prints the combined output; returns the status of the last attempt.
gh_api_retry_403() {
  local out attempt=1 max_attempts=$(( ${#RULESET_RETRY_DELAYS[@]} + 1 ))
  while true; do
    if out="$(gh api "$@" 2>&1)"; then
      printf '%s
' "$out"
      return 0
    fi
    if ! is_http_403 "$out" || (( attempt >= max_attempts )); then
      printf '%s
' "$out"
      return 1
    fi
    local delay="${RULESET_RETRY_DELAYS[$((attempt - 1))]}"
    warn "HTTP 403 from GitHub (attempt $attempt/$max_attempts); retrying in ${delay}s"
    sleep "$delay"
    attempt=$(( attempt + 1 ))
  done
}

# Handle a failed ruleset API call. Private repo + 403 means the GitHub Free plan
# cannot enforce rulesets: warn and continue. Anything else is a real error.
handle_ruleset_failure() {
  local repo="$1" action="$2" out="$3"
  if is_http_403 "$out" && [[ "$(repo_visibility "$repo")" == "PRIVATE" ]]; then
    warn "GitHub refused the ruleset (HTTP 403) - private repos on GitHub Free cannot enforce rulesets."
    warn "Re-run after making the repo public: scripts/github/go-public.sh"
    return 0
  fi
  die "$action failed: $out"
}

# Create or update the ruleset named $RULESET_NAME. Retries transient 403s; only
# tolerates a persistent 403 when the repo is actually private.
apply_ruleset() {
  local repo="$1" out existing_id
  [[ -f "$RULESET_FILE" ]] || die "Ruleset file not found: $RULESET_FILE"
  log "Applying ruleset '$RULESET_NAME' to $repo"

  if ! out="$(gh_api_retry_403 "repos/$repo/rulesets" --paginate       --jq ".[] | select(.name == \"$RULESET_NAME\") | .id")"; then
    handle_ruleset_failure "$repo" "Listing rulesets" "$out"
    return 0
  fi
  existing_id="$(head -n1 <<<"$out" | tr -d '[:space:]')"

  local method="POST" path="repos/$repo/rulesets"
  if [[ -n "$existing_id" ]]; then
    method="PUT"
    path="repos/$repo/rulesets/$existing_id"
  fi

  if ! out="$(gh_api_retry_403 -X "$method" "$path" --input "$RULESET_FILE")"; then
    handle_ruleset_failure "$repo" "Applying ruleset" "$out"
    return 0
  fi
  if [[ "$method" == "PUT" ]]; then ok "Ruleset updated (id $existing_id)"; else ok "Ruleset created"; fi
}
