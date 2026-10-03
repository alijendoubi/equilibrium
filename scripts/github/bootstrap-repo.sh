#!/usr/bin/env bash
# Idempotent GitHub repo bootstrap: settings, topics, labels, milestones, ruleset.
# Usage: scripts/github/bootstrap-repo.sh [OWNER/REPO]   (default alijendoubi/equilibrium)
set -euo pipefail

# shellcheck source=lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

REPO="${1:-${REPO:-alijendoubi/equilibrium}}"

TOPICS=(hackathon rare-diseases knowledge-graph openai nextjs fastapi python typescript bioinformatics hack-nation)
DEFAULT_LABELS=(bug documentation duplicate enhancement "good first issue" "help wanted" invalid question wontfix)
MILESTONES=("M1 Repo ready" "M2 Graph slice" "M3 Trust layer" "M4 UI journey" "M5 Submission")

configure_settings() {
  log "Repository settings"
  gh api -X PATCH "repos/$REPO" --silent \
    -F allow_squash_merge=true \
    -F allow_merge_commit=false \
    -F allow_rebase_merge=false \
    -f squash_merge_commit_title=PR_TITLE \
    -f squash_merge_commit_message=PR_BODY \
    -F delete_branch_on_merge=true \
    -F allow_auto_merge=true \
    -F allow_update_branch=true \
    -F has_wiki=false \
    -F has_discussions=true
  ok "squash-only, auto-merge, delete branch on merge, wiki off, discussions on"
}

configure_topics() {
  log "Topics"
  local joined
  joined="$(IFS=,; echo "${TOPICS[*]}")"
  gh repo edit "$REPO" --add-topic "$joined" >/dev/null
  ok "$joined"
}

configure_labels() {
  log "Labels"
  local name
  for name in "${DEFAULT_LABELS[@]}"; do
    if gh label delete "$name" --repo "$REPO" --yes >/dev/null 2>&1; then
      ok "deleted default label '$name'"
    fi
  done

  local py
  py="$(python_bin)"
  # Emit name<TAB>color<TAB>description per label.
  while IFS=$'\t' read -r name color description; do
    [[ -z "$name" ]] && continue
    gh label create "$name" --repo "$REPO" --color "$color" --description "$description" --force >/dev/null
    ok "$name"
  done < <("$py" -c '
import json, sys
for label in json.load(open(sys.argv[1], encoding="utf-8")):
    print("\t".join([label["name"], label["color"], label.get("description", "")]))
' "$LABELS_FILE" | tr -d '\r')
}

configure_milestones() {
  log "Milestones"
  local existing title
  existing="$(gh api "repos/$REPO/milestones?state=all&per_page=100" --paginate --jq '.[].title' | tr -d '\r')"
  for title in "${MILESTONES[@]}"; do
    if grep -qxF "$title" <<<"$existing"; then
      ok "exists: $title"
    else
      gh api -X POST "repos/$REPO/milestones" -f title="$title" --silent
      ok "created: $title"
    fi
  done
}

main() {
  require_gh
  log "Bootstrapping $REPO"
  configure_settings
  configure_topics
  configure_labels
  configure_milestones
  apply_ruleset "$REPO"
  log "Done. Remember to add secrets: VERCEL_TOKEN, VERCEL_ORG_ID, VERCEL_PROJECT_ID, RENDER_DEPLOY_HOOK_URL"
}

main "$@"
