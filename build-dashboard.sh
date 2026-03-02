#!/bin/bash
# Reads task markdown files and builds dashboard with injected JSON
MC_DIR="$(cd "$(dirname "$0")" && pwd)"
TASKS_DIR="$MC_DIR/tasks"
OUTPUT="$MC_DIR/index.html"
TEMPLATE="$MC_DIR/dashboard.html"

tasks_json="["
first=true

for status_dir in backlog in-progress review done; do
  dir="$TASKS_DIR/$status_dir"
  [ -d "$dir" ] || continue
  for f in "$dir"/*.md; do
    [ -f "$f" ] || continue
    title=$(grep -m1 '^# Task:' "$f" | sed 's/^# Task: //')
    [ -z "$title" ] && title=$(grep -m1 '^# ' "$f" | sed 's/^# //')
    id=$(grep -m1 'ID:' "$f" | sed 's/.*ID:\*\* *//' | sed 's/\*//g' | xargs)
    priority=$(grep -m1 'Priority:' "$f" | sed 's/.*Priority:\*\* *//' | sed 's/\*//g' | xargs)
    assigned=$(grep -m1 'Assigned:' "$f" | sed 's/.*Assigned:\*\* *//' | sed 's/\*//g' | xargs)
    tags_raw=$(grep -m1 'Tags:' "$f" | sed 's/.*Tags:\*\* *//' | sed 's/\*//g')
    tags_json="[]"
    if [ -n "$tags_raw" ]; then
      tags_json="[$(echo "$tags_raw" | tr ',' '\n' | sed 's/^ *//;s/ *$//' | sed 's/.*/"&"/' | tr '\n' ',' | sed 's/,$//' )]"
    fi
    
    $first || tasks_json="$tasks_json,"
    first=false
    tasks_json="$tasks_json{\"id\":\"$id\",\"title\":\"$title\",\"priority\":\"$priority\",\"assigned\":\"$assigned\",\"status\":\"$status_dir\",\"tags\":$tags_json}"
  done
done

tasks_json="$tasks_json]"

sed "s|__TASKS_JSON__|$tasks_json|" "$TEMPLATE" > "$OUTPUT"
echo "Dashboard built: $OUTPUT"
