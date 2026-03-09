#!/usr/bin/env python3
"""
collect-kodo-data.py
Collects Kodo's real-time status from disk and writes kodo-data.json.
Run every 30min via cron.
"""

import json, os, re, time, subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

NOW_MS = int(time.time() * 1000)
NOW_ISO = datetime.now(timezone.utc).isoformat()
WORKSPACE = Path("/Users/kodo/.openclaw/workspace")
OPENCLAW = Path(os.path.expanduser("~/.openclaw"))
OUTPUT_DIR = Path("/Users/kodo/clawd/ops/output")
ACTIVE_TASK_PATH = WORKSPACE / "ops" / "ACTIVE-TASK.md"


def time_ago(ms):
    if not ms:
        return "never"
    diff = (NOW_MS - ms) / 1000
    if diff < 60: return f"{int(diff)}s ago"
    if diff < 3600: return f"{int(diff/60)}m ago"
    if diff < 86400: return f"{int(diff/3600)}h ago"
    return f"{int(diff/86400)}d ago"


def parse_active_task(path):
    default = {"name": "Available", "status": "IDLE", "progress_percent": 0,
               "checklist_total": 0, "checklist_done": 0, "startedAt": None, "blockedOn": None}
    try:
        text = Path(path).read_text()
    except:
        return default

    title_m = re.search(r'^# ACTIVE TASK[:\s-]+(.+)', text, re.M)
    name = title_m.group(1).strip() if title_m else "Unknown Task"

    status = "IN_PROGRESS"
    if re.search(r'\*\*Status:\*\*\s*COMPLETE', text, re.I): status = "COMPLETE"
    elif re.search(r'\*\*Status:\*\*\s*BLOCKED', text, re.I): status = "BLOCKED"
    elif re.search(r'\*\*Status:\*\*\s*IDLE', text, re.I): status = "IDLE"

    done_boxes = len(re.findall(r'- \[x\]', text, re.I))
    total_boxes = len(re.findall(r'- \[[x ]\]', text, re.I))
    pct = int((done_boxes / total_boxes * 100)) if total_boxes else 0

    started_m = re.search(r'\*\*Started:\*\*\s*(.+)', text)
    started = started_m.group(1).strip() if started_m else None

    blocked_m = re.search(r'blocked[:\s]+(.+)', text, re.I)
    blocked = blocked_m.group(1).strip() if blocked_m and status == "BLOCKED" else None

    return {
        "name": name, "status": status,
        "progress_percent": pct,
        "checklist_total": total_boxes,
        "checklist_done": done_boxes,
        "startedAt": started,
        "blockedOn": blocked
    }


def get_recent_outputs(days=7, limit=20):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    outputs = []
    try:
        for f in sorted(OUTPUT_DIR.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
            if not f.is_file(): continue
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff: continue
            outputs.append({
                "filename": f.name,
                "createdAt": mtime.isoformat(),
                "size": f.stat().st_size,
                "agent": "kodo"
            })
            if len(outputs) >= limit: break
    except:
        pass
    return outputs


def get_cron_jobs():
    try:
        cron_path = OPENCLAW / "cron" / "jobs.json"
        data = json.loads(cron_path.read_text())
        jobs = data.get("jobs", [])
        result = []
        for j in jobs:
            if not j.get("enabled", False): continue
            state = j.get("state", {})
            sched = j.get("schedule", {})
            last_run_ms = state.get("lastRunAtMs")
            errors = state.get("consecutiveErrors", 0)
            every_ms = sched.get("everyMs")
            next_run_ms = None
            if last_run_ms and every_ms:
                next_run_ms = last_run_ms + every_ms

            status = "ok"
            if errors > 0: status = "error"
            elif last_run_ms and every_ms:
                grace = every_ms * 1.5
                if (NOW_MS - last_run_ms) > grace: status = "stale"

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
                "nextRunMs": next_run_ms,
                "status": status,
                "errors": errors
            })
        return result
    except Exception as e:
        return []


def get_skills():
    """Read skills from ~/skills/ directory."""
    skills_dir = Path.home() / "skills"
    skills = []
    # Known skill metadata — status and use counts tracked manually
    SKILL_META = {
        "site-audit":           {"status": "LIVE",    "uses": 5, "triggerScore": 10},
        "code-review-quality":  {"status": "LIVE",    "uses": 3, "triggerScore": 9},
        "bug-fix-workflow":     {"status": "LIVE",    "uses": 3, "triggerScore": 9},
        "ship-flow":            {"status": "PARKED",  "uses": 0, "triggerScore": 0},
        "agent-orchestration":  {"status": "PARKED",  "uses": 0, "triggerScore": 0},
    }
    try:
        if skills_dir.exists():
            for skill_dir in sorted(skills_dir.iterdir()):
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    meta = SKILL_META.get(skill_dir.name, {"status": "BUILDING", "uses": 0, "triggerScore": 0})
                    skills.append({"name": skill_dir.name, **meta})
    except Exception:
        pass
    return skills


def get_session_status():
    """Check if Kodo has an active OpenClaw session."""
    sessions_dir = OPENCLAW / "agents" / "main" / "sessions"
    try:
        locks = list(sessions_dir.glob("*.lock"))
        if not locks:
            return "idle", None
        latest = max(locks, key=lambda f: f.stat().st_mtime)
        mtime_ms = int(latest.stat().st_mtime * 1000)
        age_min = (NOW_MS - mtime_ms) / 60000
        if age_min < 5: return "active", mtime_ms
        elif age_min < 30: return "recent", mtime_ms
        return "idle", mtime_ms
    except:
        return "idle", None


def main():
    active_task = parse_active_task(ACTIVE_TASK_PATH)
    recent_outputs = get_recent_outputs()
    cron_jobs = get_cron_jobs()
    session_status, last_active_ms = get_session_status()
    skills = get_skills()

    data = {
        "updatedAt": NOW_ISO,
        "agent": "kodo",
        "status": session_status,
        "activeTask": active_task,
        "recentOutputs": recent_outputs,
        "cronJobs": cron_jobs,
        "skills": skills,
        "lastActiveMs": last_active_ms,
        "lastActiveAgo": time_ago(last_active_ms)
    }

    out_path = Path(__file__).parent / "data" / "kodo.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2))
    print(f"[OK] kodo-data.json written — {len(recent_outputs)} outputs, {len(cron_jobs)} jobs, task: {active_task['name']}")


if __name__ == "__main__":
    main()
