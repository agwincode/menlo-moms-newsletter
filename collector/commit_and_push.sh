#!/usr/bin/env bash
# Commit whatever a workflow produced and push, retrying if another run pushed first.
set -euo pipefail
msg="$1"; shift
git config user.name "menlo-moms-bot"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
paths=(); for p in "$@"; do [ -e "$p" ] && paths+=("$p"); done
[ ${#paths[@]} -eq 0 ] && { echo "Nothing to commit"; exit 0; }
git add -A "${paths[@]}"
if git diff --cached --quiet; then echo "Nothing to commit"; exit 0; fi
git commit -q -m "$msg"
for i in 1 2 3 4 5; do
  git pull -q --rebase origin "${GITHUB_REF_NAME:-main}" && git push -q origin HEAD && exit 0
  sleep $((i * 5))
done
echo "Push failed after retries" >&2; exit 1
