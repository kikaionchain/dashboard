# Task: Build Browser Fallback Skill
- **ID:** task-003
- **Priority:** high
- **Assigned:** kikai
- **Created:** 2026-02-18
- **Tags:** os, tooling, reliability

## Description
When the browser tool fails (port stuck, process dead), have a self-healing fallback:
1. Kill stuck processes
2. Restart browser
3. Retry the action
4. If all else fails, use web_fetch as degraded mode

Never tell WJP "browser is broken." Fix it.

## Acceptance Criteria
- [ ] Browser self-heals on failure
- [ ] Falls back to web_fetch if needed
- [ ] No user intervention required
