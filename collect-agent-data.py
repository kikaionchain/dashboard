#!/usr/bin/env python3
"""
collect-agent-data.py
Collects real-time agent status from disk + SSH and writes data.json.
Run before every deploy.
"""

import json, os, re, subprocess, time
from pathlib import Path
from datetime import datetime, timezone

NOW_MS = int(time.time() * 1000)
CLAWD = Path("/Users/kikai/clawd")
OPENCLAW = Path(os.path.expanduser("~/.openclaw"))

# ── Helpers ─────────────────────────────────────────────────────────────────

def time_ago(ms):
    if not ms: return "never"
    diff = (NOW_MS - ms) / 1000
    if diff < 60: return f"{int(diff)}s ago"
    if diff < 3600: return f"{int(diff/60)}m ago"
    if diff < 86400: return f"{int(diff/3600)}h ago"
    return f"{int(diff/86400)}d ago"

def parse_active_task(md_path):
    """Parse ACTIVE-TASK.md into structured data."""
    default = {"name": "Idle", "status": "IDLE", "progress_percent": 0,
               "checklist_total": 0, "checklist_done": 0}
    try:
        text = Path(md_path).read_text()
    except:
        return default

    # Title
    title_m = re.search(r'^# ACTIVE TASK[:\s-]+(.+)', text, re.M)
    name = title_m.group(1).strip() if title_m else "Unknown Task"

    # Status
    status = "IDLE"
    if re.search(r'Status.*IN.PROGRESS', text, re.I): status = "IN_PROGRESS"
    elif re.search(r'Status.*COMPLETE', text, re.I): status = "COMPLETE"
    elif re.search(r'Status.*BLOCKED', text, re.I): status = "BLOCKED"

    # Checklist
    done_boxes = len(re.findall(r'- \[x\]', text, re.I))
    total_boxes = len(re.findall(r'- \[[x ]\]', text, re.I))
    pct = int((done_boxes / total_boxes * 100)) if total_boxes else 0

    # Stale check - if deadline is past, mark stale
    deadline_m = re.search(r'Deadline.*?(\w+ \d+, \d{4}|\d{4}-\d{2}-\d{2})', text)
    stale = False
    if deadline_m:
        try:
            dl_str = deadline_m.group(1)
            from datetime import datetime
            dl = datetime.strptime(dl_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if dl.timestamp() * 1000 < NOW_MS:
                stale = True
                status = "STALE"
        except: pass

    return {
        "name": name, "status": status,
        "progress_percent": pct,
        "checklist_total": total_boxes, "checklist_done": done_boxes,
        "stale": stale
    }

def get_kikai_session_status():
    """Check if Kikai has an active session (lock file present = working)."""
    sessions_dir = OPENCLAW / "agents" / "main" / "sessions"
    try:
        locks = list(sessions_dir.glob("*.lock"))
        if not locks:
            return "idle", None
        # Get most recent lock
        latest = max(locks, key=lambda f: f.stat().st_mtime)
        mtime_ms = int(latest.stat().st_mtime * 1000)
        # If lock is <5 min old = actively working
        age_min = (NOW_MS - mtime_ms) / 60000
        if age_min < 5:
            return "working", mtime_ms
        elif age_min < 30:
            return "recent", mtime_ms
        return "idle", mtime_ms
    except:
        return "idle", None

def get_kikai_last_active():
    """Get timestamp of most recent session file modification."""
    sessions_dir = OPENCLAW / "agents" / "main" / "sessions"
    try:
        sessions = list(sessions_dir.glob("*.jsonl"))
        if not sessions:
            return None
        latest = max(sessions, key=lambda f: f.stat().st_mtime)
        return int(latest.stat().st_mtime * 1000)
    except:
        return None

def get_cron_data():
    """Pull cron job health from jobs.json."""
    try:
        cron_path = OPENCLAW / "cron" / "jobs.json"
        data = json.loads(cron_path.read_text())
        jobs = data.get("jobs", [])
        healthy, erroring, stale_jobs = 0, 0, []
        job_list = []
        for j in jobs:
            state = j.get("state", {})
            sched = j.get("schedule", {})
            last_run = state.get("lastRunAtMs")
            errors = state.get("consecutiveErrors", 0)
            status = state.get("lastStatus")
            enabled = j.get("enabled", False)
            if not enabled:
                continue
            # Detect stale: last run >26h ago and job should run more often
            every_ms = sched.get("everyMs", 0)
            is_stale = False
            if every_ms and last_run:
                expected_interval = every_ms * 1.5  # 50% grace window
                if (NOW_MS - last_run) > expected_interval:
                    is_stale = True
            health = "ok"
            if errors > 0: health = "error"; erroring += 1
            elif is_stale: health = "stale"
            else: healthy += 1
            job_list.append({
                "name": j.get("name", "?"),
                "health": health,
                "lastRunMs": last_run,
                "lastRunAgo": time_ago(last_run),
                "errors": errors,
                "stale": is_stale
            })
        return {
            "healthy": healthy, "erroring": erroring,
            "total": len(job_list), "jobs": job_list
        }
    except Exception as e:
        return {"healthy": 0, "erroring": 0, "total": 0, "jobs": [], "error": str(e)}

def get_yama_status():
    """SSH to Yama and pull status data."""
    try:
        # Get last active from file timestamps
        result = subprocess.run(
            ["ssh", "yama",
             "stat -f '%m' ~/.openclaw/agents/main/sessions/*.jsonl 2>/dev/null | sort -n | tail -1 ; "
             "ls ~/.openclaw/agents/main/sessions/*.lock 2>/dev/null | wc -l ; "
             "cat ~/clawd/ops/ACTIVE-TASK.md 2>/dev/null | head -20 ; "
             "echo '---CRON---' ; "
             "python3 -c \""
             "import json; d=json.load(open(\\\"$HOME/.openclaw/cron/jobs.json\\\")); "
             "jobs=d.get('jobs',[]); "
             "[print(j.get('name','?'),'|',j.get('enabled'),'|',j.get('state',{}).get('lastStatus'),'|',j.get('state',{}).get('consecutiveErrors',0)) for j in jobs]"
             "\" 2>/dev/null"],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout.strip()
        lines = output.split('\n')

        # Parse last active timestamp
        last_active_ms = None
        try:
            ts = int(lines[0].strip()) if lines[0].strip().isdigit() else None
            if ts: last_active_ms = ts * 1000
        except: pass

        # Parse lock count (working indicator)
        lock_count = 0
        try:
            lock_count = int(lines[1].strip()) if len(lines) > 1 else 0
        except: pass

        # Parse ACTIVE-TASK.md content (lines 2 onwards until ---CRON---)
        task_lines = []
        cron_lines = []
        in_cron = False
        for line in lines[2:]:
            if line == '---CRON---':
                in_cron = True
                continue
            if in_cron:
                cron_lines.append(line)
            else:
                task_lines.append(line)

        # Parse task
        task_text = '\n'.join(task_lines)
        task = {"name": "Idle", "status": "IDLE", "progress_percent": 0,
                "checklist_total": 0, "checklist_done": 0}
        if task_text.strip():
            title_m = re.search(r'^# ACTIVE TASK[:\s-]+(.+)', task_text, re.M)
            if title_m: task["name"] = title_m.group(1).strip()
            if re.search(r'Status.*IN.PROGRESS', task_text, re.I): task["status"] = "IN_PROGRESS"
            elif re.search(r'Status.*COMPLETE', task_text, re.I): task["status"] = "COMPLETE"
            # Stale check - handle multiple date formats
            dl_m = (re.search(r'Deadline.*?(\d{4}-\d{2}-\d{2})', task_text) or
                    re.search(r'Deadline.*?(\w+ \d+, \d{4})', task_text) or
                    re.search(r'Deadline.*?([A-Z][a-z]+ \d+, \d{4})', task_text))
            if dl_m:
                try:
                    from datetime import datetime
                    dl_str = dl_m.group(1)
                    try: dl = datetime.strptime(dl_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    except: dl = datetime.strptime(dl_str, "%B %d, %Y").replace(tzinfo=timezone.utc)
                    if dl.timestamp() * 1000 < NOW_MS:
                        task["status"] = "STALE"
                        task["stale"] = True
                except: pass
            done_boxes = len(re.findall(r'- \[x\]', task_text, re.I))
            total_boxes = len(re.findall(r'- \[[x ]\]', task_text, re.I))
            task["checklist_done"] = done_boxes
            task["checklist_total"] = total_boxes
            task["progress_percent"] = int(done_boxes/total_boxes*100) if total_boxes else 0

        # Parse cron
        yama_cron = {"healthy": 0, "erroring": 0, "total": 0, "jobs": []}
        for line in cron_lines:
            if '|' in line:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 4:
                    name, enabled, status, errors_str = parts[0], parts[1], parts[2], parts[3]
                    try: errors = int(errors_str.split()[0])
                    except: errors = 0
                    if enabled == 'True':
                        yama_cron["total"] += 1
                        health = "error" if errors > 0 else "ok"
                        if errors > 0: yama_cron["erroring"] += 1
                        else: yama_cron["healthy"] += 1
                        yama_cron["jobs"].append({"name": name, "health": health, "errors": errors})

        # Determine status
        age_min = (NOW_MS - last_active_ms) / 60000 if last_active_ms else 99999
        if lock_count > 0 and age_min < 5:
            status = "working"
        elif last_active_ms and age_min < 60:
            status = "recent"
        elif last_active_ms and age_min < 1440:
            status = "idle"
        else:
            status = "offline"

        return {
            "status": status,
            "last_active_ms": last_active_ms,
            "last_active_ago": time_ago(last_active_ms),
            "active_task": task,
            "cron": yama_cron,
            "backlog": [
                {"title": "For Crypto REST API work", "tag": "for-crypto"},
                {"title": "PR #7 features review", "tag": "for-crypto"},
            ],
            "done": ["Phase 1 builds", "PR #7 backed up", "Production audit"]
        }
    except Exception as e:
        return {
            "status": "offline",
            "last_active_ms": None,
            "last_active_ago": "unknown",
            "active_task": {"name": "Unreachable", "status": "OFFLINE",
                           "progress_percent": 0, "checklist_total": 0, "checklist_done": 0},
            "cron": {"healthy": 0, "erroring": 0, "total": 0, "jobs": []},
            "backlog": [], "done": [],
            "error": str(e)
        }

def get_needs_wjp():
    """Parse NEEDS-WJP.md into structured data."""
    try:
        text = (CLAWD / "ops" / "NEEDS-WJP.md").read_text()
        items = []
        blocking = re.search(r'## 🔴 Blocking Active Work([\s\S]*?)(?=## 🟠|## 🟡|## ✅|\Z)', text)
        enabling = re.search(r'## 🟠 Enabling Capabilities([\s\S]*?)(?=## 🟡|## ✅|\Z)', text)
        signals  = re.search(r'## 🟡 Signals Needed([\s\S]*?)(?=## ✅|\Z)', text)
        resolved_m = re.search(r'## ✅ Resolved.*?\n([\s\S]*?)(?=## How|\Z)', text)

        def parse_section(section, priority):
            if not section: return
            blocks = re.split(r'(?=### \d+\.)', section.group(1))
            for block in blocks:
                title = re.search(r'### \d+\.\s*(.+)', block)
                ask   = re.search(r'\*\*Ask:\*\*\s*(.+)', block)
                why   = re.search(r'\*\*Why it matters:\*\*\s*(.+)', block)
                if title:
                    items.append({
                        'priority': priority,
                        'title': title.group(1).strip(),
                        'ask': ask.group(1).strip() if ask else '',
                        'impact': why.group(1).strip() if why else '',
                        'tag': priority
                    })

        parse_section(blocking, 'blocking')
        parse_section(enabling, 'enabling')
        parse_section(signals, 'signal')

        # Parse resolved table
        resolved = []
        if resolved_m:
            for row in re.finditer(r'\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|', resolved_m.group(1)):
                title, resolution, date = [c.strip() for c in row.groups()]
                if title and title not in ('Item', '---'):
                    resolved.append({'title': title, 'resolution': resolution})

        from_kikai = [i for i in items if i['priority'] in ('blocking', 'signal')]
        from_yama  = [i for i in items if i['priority'] == 'enabling']

        return {'from_kikai': from_kikai, 'from_yama': from_yama, 'resolved': resolved[-5:]}
    except Exception as e:
        return {'from_kikai': [], 'from_yama': [], 'resolved': [], 'error': str(e)}

# ── Main ─────────────────────────────────────────────────────────────────────

kikai_status, kikai_last_active_ms = get_kikai_session_status()
if not kikai_last_active_ms:
    kikai_last_active_ms = get_kikai_last_active()

kikai_task = parse_active_task(CLAWD / "ops" / "ACTIVE-TASK.md")
kikai_cron = get_cron_data()
yama = get_yama_status()
wjp = get_needs_wjp()

# Build your_move from highest priority WJP item
your_move = {"priority": "signal", "title": "All clear - no blockers", "ask": ""}
all_items = wjp['from_kikai'] + wjp['from_yama']
blocking_items = [i for i in all_items if i['priority'] == 'blocking']
if blocking_items:
    your_move = {"priority": "blocking", "title": blocking_items[0]['title'], "ask": blocking_items[0].get('ask', '')}
elif all_items:
    your_move = {"priority": "signal", "title": all_items[0]['title'], "ask": all_items[0].get('ask', '')}

# Cron error alerts
cron_errors = [j for j in kikai_cron['jobs'] if j['health'] == 'error']
cron_stale = [j for j in kikai_cron['jobs'] if j.get('stale')]

data = {
    "timestamp_ms": NOW_MS,
    "collected_at": datetime.now(timezone.utc).isoformat(),
    "your_move": your_move,
    "kikai": {
        "status": kikai_status,
        "last_active_ms": kikai_last_active_ms,
        "last_active_ago": time_ago(kikai_last_active_ms),
        "active_task": kikai_task,
        "cron": kikai_cron,
        "cron_alerts": [{"name": j["name"], "errors": j["errors"]} for j in cron_errors],
        "backlog": [
            {"title": "Review PR #7 - merge decision", "tag": "needs-you"},
            {"title": "Content strategy review + re-enable 67 posts", "tag": "deep-work"},
        ],
        "done": [
            "OS Overhaul complete",
            "Dashboard rebuilt",
            "50+ OpenClaw tips absorbed",
            "For Crypto REST API verified live",
        ]
    },
    "yama": yama,
    "wjp": wjp,
}

out_path = Path("/Users/kikai/clawd/dashboard/data.json")
out_path.write_text(json.dumps(data, indent=2))
print(f"✅ data.json written ({len(data['kikai']['cron']['jobs'])} cron jobs, kikai={kikai_status}, yama={yama['status']})")
if cron_errors:
    print(f"⚠️  Cron errors: {[j['name'] for j in cron_errors]}")
if cron_stale:
    print(f"⚠️  Stale crons: {[j['name'] for j in cron_stale]}")
