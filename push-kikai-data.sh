#!/bin/bash
# push-kikai-data.sh — Collect Kikai status via SSH, push to dashboard repo.
set -e

REPO_DIR="$HOME/clawd/mission-control"
cd "$REPO_DIR"

git pull --quiet --rebase origin main 2>/dev/null || true

python3 "$REPO_DIR/collect-remote-agent.py" kikai kikai

# Sync kikai agent card into data.json
python3 -c "
import json
from pathlib import Path

agent = json.loads(Path('data/kikai.json').read_text())
data_path = Path('data.json')
data = json.loads(data_path.read_text()) if data_path.exists() else {}

agents = data.setdefault('agents', {})
a = agents.setdefault('kikai', {})

task = agent.get('activeTask', {})
task_name = task.get('name', 'idle') if isinstance(task, dict) else str(task)
a['workingOn'] = task_name
a['status'] = agent.get('status', 'idle')

data['updatedAt'] = agent.get('updatedAt', '')
data_path.write_text(json.dumps(data, indent=2))
"

if git diff --quiet data/kikai.json data.json 2>/dev/null; then
  echo "[OK] data/kikai.json unchanged"
else
  git add data/kikai.json data.json
  git commit -m "kikai: status update $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  git push origin main
  echo "[OK] data/kikai.json pushed"
fi
