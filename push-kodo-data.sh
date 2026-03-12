#!/bin/bash
# push-kodo-data.sh
# Collect Kodo status, push kodo-data.json to dashboard repo.
# Also sync kodo agent card in data.json so dashboard shows current task.
# Runs every 30min via OpenClaw cron.

set -e

REPO_DIR="$HOME/clawd/mission-control"
cd "$REPO_DIR"

# Pull latest first (avoid conflicts)
git pull --quiet --rebase origin main 2>/dev/null || true

# Collect Kodo data
python3 "$REPO_DIR/collect-kodo-data.py"

# Sync kodo's activeTask into data.json agent card
python3 -c "
import json
from pathlib import Path

kodo = json.loads(Path('data/kodo.json').read_text())
data_path = Path('data.json')
data = json.loads(data_path.read_text()) if data_path.exists() else {}

agents = data.setdefault('agents', {})
kodo_agent = agents.setdefault('kodo', {})

# Sync task name from activeTask
task = kodo.get('activeTask', {})
task_name = task.get('name', 'idle') if isinstance(task, dict) else str(task)
kodo_agent['workingOn'] = task_name
kodo_agent['status'] = kodo.get('status', 'idle')

# Update timestamp
data['updatedAt'] = kodo.get('updatedAt', '')

data_path.write_text(json.dumps(data, indent=2))
"

# Commit + push if changed
if git diff --quiet data/kodo.json data.json 2>/dev/null; then
  echo "[OK] data/kodo.json unchanged, no push needed"
else
  git add data/kodo.json data.json
  git commit -m "kodo: status update $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  git push origin main
  echo "[OK] data/kodo.json pushed"
fi
