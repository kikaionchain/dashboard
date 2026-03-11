#!/bin/bash
# push-kodo-data.sh
# Collect Kodo status, push kodo-data.json to dashboard repo.
# Runs every 30min via OpenClaw cron.

set -e

REPO_DIR="$HOME/clawd/dashboard"
cd "$REPO_DIR"

# Pull latest first (avoid conflicts)
git pull --quiet --rebase origin main 2>/dev/null || true

# Collect Kodo data
python3 "$REPO_DIR/collect-kodo-data.py"

# Commit + push if changed
if git diff --quiet data/kodo.json 2>/dev/null; then
  echo "[OK] data/kodo.json unchanged, no push needed"
else
  git add data/kodo.json
  git commit -m "kodo: status update $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  git push origin main
  echo "[OK] data/kodo.json pushed"
fi
