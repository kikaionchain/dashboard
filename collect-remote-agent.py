#!/usr/bin/env python3
"""
collect-remote-agent.py <agent_name> <ssh_host>
SSH into a remote machine, collect OpenClaw agent status, write data/<agent>.json.
Mirrors collect-kodo-data.py but works remotely.
"""

import json, os, sys, subprocess, time, re
from pathlib import Path
from datetime import datetime, timezone, timedelta

if len(sys.argv) < 3:
    print(f"Usage: {sys.argv[0]} <agent_name> <ssh_host>")
    sys.exit(1)

AGENT = sys.argv[1]
SSH_HOST = sys.argv[2]
NOW_MS = int(time.time() * 1000)
NOW_ISO = datetime.now(timezone.utc).isoformat()


def ssh_cmd(cmd, timeout=10):
    """Run a command via SSH and return stdout."""
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", SSH_HOST, cmd],
            capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except:
        return ""


def time_ago(ms):
    if not ms: return "never"
    diff = (NOW_MS - ms) / 1000
    if diff < 60: return f"{int(diff)}s ago"
    if diff < 3600: return f"{int(diff/60)}m ago"
    if diff < 86400: return f"{int(diff/3600)}h ago"
    return f"{int(diff/86400)}d ago"


def get_active_task():
    text = ssh_cmd("cat ~/.openclaw/workspace/ops/ACTIVE-TASK.md 2>/dev/null")
    default = {"name": "Available", "status": "IDLE", "progress_percent": 0,
               "checklist_total": 0, "checklist_done": 0, "startedAt": None, "blockedOn": None}
    if not text:
        return default

    title_m = re.search(r'^# ACTIVE TASK[:\s-]+(.+)', text, re.M)
    name = title_m.group(1).strip() if title_m else "Unknown Task"

    status = "IN_PROGRESS"
    if re.search(r'\*\*Status:\*\*\s*COMPLETE', text, re.I): status = "COMPLETE"
    elif re.search(r'\*\*Status:\*\*\s*BLOCKED', text, re.I): status = "BLOCKED"
    elif re.search(r'\*\*Status:\*\*\s*IDLE', text, re.I): status = "IDLE"

    done = len(re.findall(r'- \[x\]', text, re.I))
    total = len(re.findall(r'- \[[x ]\]', text, re.I))
    pct = int((done / total * 100)) if total else 0

    started_m = re.search(r'\*\*Started:\*\*\s*(.+)', text)
    started = started_m.group(1).strip() if started_m else None
    blocked_m = re.search(r'blocked[:\s]+(.+)', text, re.I)
    blocked = blocked_m.group(1).strip() if blocked_m and status == "BLOCKED" else None

    return {"name": name, "status": status, "progress_percent": pct,
            "checklist_total": total, "checklist_done": done,
            "startedAt": started, "blockedOn": blocked}


def get_cron_jobs():
    raw = ssh_cmd("cat ~/.openclaw/cron/jobs.json 2>/dev/null")
    if not raw: return []
    try:
        data = json.loads(raw)
        jobs = data.get("jobs", [])
        result = []
        for j in jobs:
            if not j.get("enabled", False): continue
            state = j.get("state", {})
            sched = j.get("schedule", {})
            last_run_ms = state.get("lastRunAtMs")
            errors = state.get("consecutiveErrors", 0)
            every_ms = sched.get("everyMs")

            status = "ok"
            if errors > 0: status = "error"
            elif last_run_ms and every_ms:
                if (NOW_MS - last_run_ms) > every_ms * 1.5: status = "stale"

            schedule_str = "—"
            if every_ms:
                mins = every_ms // 60000
                if mins < 60: schedule_str = f"every {mins}m"
                elif mins < 1440: schedule_str = f"every {mins//60}h"
                else: schedule_str = f"every {mins//1440}d"
            elif sched.get("kind") == "cron":
                schedule_str = sched.get("expr", "—")

            result.append({
                "name": j.get("name", "Unnamed"),
                "schedule": schedule_str,
                "lastRunMs": last_run_ms,
                "lastRunAgo": time_ago(last_run_ms),
                "status": status,
                "errors": errors
            })
        return result
    except:
        return []


def get_session_status():
    raw = ssh_cmd("ls -lt ~/.openclaw/agents/main/sessions/*.lock 2>/dev/null | head -1")
    if not raw: return "idle", None
    try:
        # Get mtime of newest lock file
        parts = raw.split()
        # Use stat for accurate mtime
        lock_file = parts[-1] if parts else None
        if not lock_file: return "idle", None
        mtime_raw = ssh_cmd(f"stat -f %m {lock_file} 2>/dev/null || stat -c %Y {lock_file} 2>/dev/null")
        if not mtime_raw: return "idle", None
        mtime_ms = int(float(mtime_raw)) * 1000
        age_min = (NOW_MS - mtime_ms) / 60000
        if age_min < 5: return "active", mtime_ms
        elif age_min < 30: return "recent", mtime_ms
        return "idle", mtime_ms
    except:
        return "idle", None


def get_recent_outputs(limit=10):
    raw = ssh_cmd(f"ls -lt ~/clawd/ops/output/*.md 2>/dev/null | head -{limit}")
    if not raw: return []
    outputs = []
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 9: continue
        filename = Path(parts[-1]).name
        outputs.append({"filename": filename, "agent": AGENT})
    return outputs


def main():
    task = get_active_task()
    cron = get_cron_jobs()
    status, last_ms = get_session_status()
    outputs = get_recent_outputs()

    data = {
        "updatedAt": NOW_ISO,
        "agent": AGENT,
        "status": status,
        "activeTask": task,
        "recentOutputs": outputs,
        "cronJobs": cron,
        "lastActiveMs": last_ms,
        "lastActiveAgo": time_ago(last_ms)
    }

    out_path = Path(__file__).parent / "data" / f"{AGENT}.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2))
    print(f"[OK] {AGENT}-data.json written — {len(outputs)} outputs, {len(cron)} jobs, task: {task['name']}")


if __name__ == "__main__":
    main()
