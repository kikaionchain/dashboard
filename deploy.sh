#!/bin/bash
# Deploy Mission Control (Next.js) to Netlify
# JSON files go to public/ so Next.js bakes them into the build automatically
set -e

export NETLIFY_AUTH_TOKEN="nfp_84AEp7PQBm7kiZ1EsWr7nkw1GCFpBZiA32a1"
export NETLIFY_SITE_ID="e09bbb98-5154-4736-b1b9-3bf99b4290bc"

DASHBOARD_DIR="/Users/kikai/clawd/mission-control/dashboard"
MC_DIR="/Users/kikai/clawd/mission-control"
CLAWD_DIR="/Users/kikai/clawd"
PUBLIC_DIR="$DASHBOARD_DIR/public"

# 1. Collect live agent data (replaces manual data.json editing)
python3 "$MC_DIR/collect-agent-data.py"

# 2. Copy data.json to public/
cp "$MC_DIR/data.json" "$PUBLIC_DIR/data.json"

# 3. Generate cron-snapshot.json (for legacy compatibility)
python3 -c "
import json
with open('/Users/kikai/.openclaw/cron/jobs.json') as f:
    cron_data = json.load(f)
jobs = cron_data.get('jobs', [])
snapshot = []
for j in jobs:
    state = j.get('state', {})
    sched = j.get('schedule', {})
    sched_str = sched.get('expr', '') or f\"every {sched.get('everyMs',0)//60000}min\"
    model = j.get('payload', {}).get('model', 'anthropic/claude-sonnet-4-6')
    model_short = model.split('/')[-1].replace('claude-','').replace('-20251001','')
    snapshot.append({
        'name': j.get('name',''),
        'enabled': j.get('enabled', False),
        'schedule': sched_str,
        'lastStatus': state.get('lastStatus'),
        'lastRunMs': state.get('lastRunAtMs'),
        'model': model_short,
    })
with open('$PUBLIC_DIR/cron-snapshot.json', 'w') as f:
    json.dump(snapshot, f, indent=2)
print(f'cron-snapshot: {len(snapshot)} jobs')
"

# 4. Generate needs-wjp.json (for legacy compatibility)
python3 -c "
import json, re
try:
    with open('/Users/kikai/clawd/ops/NEEDS-WJP.md') as f:
        content = f.read()
except:
    content = ''
items = []
blocking = re.search(r'## 🔴 Blocking Active Work([\s\S]*?)(?=## 🟠|## 🟡|## ✅|\Z)', content)
enabling = re.search(r'## 🟠 Enabling Capabilities([\s\S]*?)(?=## 🟡|## ✅|\Z)', content)
signals  = re.search(r'## 🟡 Signals Needed([\s\S]*?)(?=## ✅|\Z)', content)
def parse_section(section, priority):
    if not section: return
    blocks = re.split(r'(?=### \d+\.)', section.group(1))
    for block in blocks:
        title = re.search(r'### \d+\.\s*(.+)', block)
        ask   = re.search(r'\*\*Ask:\*\*\s*(.+)', block)
        if title:
            items.append({'priority': priority, 'title': title.group(1).strip(), 'ask': ask.group(1).strip() if ask else ''})
parse_section(blocking, 'blocking')
parse_section(enabling, 'enabling')
parse_section(signals, 'signal')
with open('$PUBLIC_DIR/needs-wjp.json', 'w') as f:
    json.dump({'items': items}, f, indent=2)
print(f'needs-wjp: {len(items)} items')
"

# 4. Build Next.js (public/ files are automatically included in out/)
cd "$DASHBOARD_DIR"
npx next build 2>&1 | grep -E "✓|error|Error" | head -10

# 5. Deploy out/ to Netlify
netlify deploy --prod --dir=out 2>&1 | grep -E "URL:|prod|Deployed" | head -5
echo "✅ Mission Control deployed"
