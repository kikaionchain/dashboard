#!/usr/bin/env bash
# push-kodo-usage.sh — Update Kodo's usage in data/usage.json and push
#
# Usage:
#   bash push-kodo-usage.sh <allModels%> <sonnet%> <opus%>
#   bash push-kodo-usage.sh 97 97 3
#
# Any arg can be "null" to clear that field.
# Called by cron agent after parsing session_status / rate limit info.

set -euo pipefail
cd "$(dirname "$0")"

ALL="${1:-null}"
SONNET="${2:-null}"
OPUS="${3:-null}"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Calculate next Friday 7PM PDT (02:00 UTC Saturday) as reset time
# Python one-liner for reliable date math
RESET=$(python3 -c "
from datetime import datetime, timedelta
now = datetime.utcnow()
days_until_friday = (4 - now.weekday()) % 7
if days_until_friday == 0 and now.hour >= 2:
    days_until_friday = 7
target = now.replace(hour=2, minute=0, second=0, microsecond=0) + timedelta(days=days_until_friday)
print(target.strftime('%Y-%m-%dT%H:%M:%SZ'))
")

USAGE_FILE="data/usage.json"

# Create file if missing
if [ ! -f "$USAGE_FILE" ]; then
  cat > "$USAGE_FILE" <<EOF
{
  "updatedAt": "$NOW",
  "weekResets": "$RESET",
  "agents": {
    "kodo": { "allModels": null, "sonnet": null, "opus": null, "updatedAt": null },
    "kikai": { "allModels": null, "sonnet": null, "opus": null, "updatedAt": null },
    "yama": { "allModels": null, "sonnet": null, "opus": null, "updatedAt": null }
  }
}
EOF
fi

# Convert "null" string to jq null, numbers stay as numbers
jq_val() {
  if [ "$1" = "null" ]; then echo "null"; else echo "$1"; fi
}

# Update Kodo's entry + top-level timestamps
jq \
  --argjson all "$(jq_val "$ALL")" \
  --argjson son "$(jq_val "$SONNET")" \
  --argjson opus "$(jq_val "$OPUS")" \
  --arg now "$NOW" \
  --arg reset "$RESET" \
  '.updatedAt = $now |
   .weekResets = $reset |
   .agents.kodo.allModels = $all |
   .agents.kodo.sonnet = $son |
   .agents.kodo.opus = $opus |
   .agents.kodo.updatedAt = $now' \
  "$USAGE_FILE" > "${USAGE_FILE}.tmp" && mv "${USAGE_FILE}.tmp" "$USAGE_FILE"

echo "[OK] usage.json updated — kodo: all=$ALL sonnet=$SONNET opus=$OPUS"

# Commit + push
git add "$USAGE_FILE"
if git diff --cached --quiet; then
  echo "[SKIP] No changes to push"
else
  git commit -m "usage: kodo all=${ALL} sonnet=${SONNET} opus=${OPUS}"
  git push
  echo "[OK] Pushed"
fi
