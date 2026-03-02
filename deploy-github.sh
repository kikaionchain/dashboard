#!/bin/bash
# Deploy Mission Control to GitHub Pages
# No build step - just push updated files to kikaionchain/mission-control
# GitHub Pages serves them instantly from main branch

set -e

WORKSPACE="/Users/kikai/clawd"
MC_DIR="$WORKSPACE/mission-control"
REPO_DIR="$HOME/.mc-deploy"
REPO_URL="https://github.com/kikaionchain/mission-control.git"

# Clone or update the repo
if [ ! -d "$REPO_DIR/.git" ]; then
  rm -rf "$REPO_DIR"
  git clone "$REPO_URL" "$REPO_DIR" 2>/dev/null
fi

cd "$REPO_DIR"
git fetch origin main -q 2>/dev/null
git reset --hard origin/main -q 2>/dev/null

# Copy updated files
cp "$MC_DIR/data.json" "$REPO_DIR/data.json"
cp "$MC_DIR/index.html" "$REPO_DIR/index.html"

# Copy intel.json if it exists
if [ -f "$MC_DIR/intel.json" ]; then
  cp "$MC_DIR/intel.json" "$REPO_DIR/intel.json"
fi

# Check if anything changed
if git diff --quiet && git diff --cached --quiet; then
  echo "MC GitHub: no changes"
  exit 0
fi

# Commit and push
git add data.json index.html intel.json 2>/dev/null || git add data.json index.html
git commit -m "data refresh $(date '+%H:%M')" -q
git push origin main -q 2>&1

echo "MC deployed to GitHub Pages: https://kikaionchain.github.io/mission-control/"
