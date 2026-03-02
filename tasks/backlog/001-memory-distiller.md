# Task: Automated Memory Distiller

**Priority:** HIGH
**Status:** OPEN
**Category:** OS Improvement

## Description
Build a skill/cron that automatically distills daily memory files (memory/YYYY-MM-DD.md) into MEMORY.md. Currently this is manual and gets forgotten. The distiller should:
- Run weekly (Sunday night)
- Read all daily files from the past week
- Extract patterns, lessons, decisions, preferences
- Append curated entries to MEMORY.md
- Flag entries that might be obsolete

## Success Criteria
- [ ] Cron job created and tested
- [ ] MEMORY.md grows with useful content weekly
- [ ] Daily files older than 30 days can be safely archived
