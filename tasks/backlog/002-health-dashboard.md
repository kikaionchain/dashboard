# Task: System Health Dashboard

**Priority:** MEDIUM
**Status:** OPEN
**Category:** Operations

## Description
Create a single HTML dashboard (like dashboard but for system health) showing:
- Cron job status (last run, next run, success/fail)
- Token usage trends
- Agent uptime (Kikai + Yama)
- Memory file sizes and growth
- Active tasks

Could be generated as a static HTML file by a cron, saved to ops/output/.

## Success Criteria
- [ ] Dashboard HTML generated
- [ ] Shows real cron status
- [ ] Updated automatically (daily cron)
