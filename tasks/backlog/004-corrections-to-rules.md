# Task: Convert Corrections to Automated Guardrails

**Priority:** MEDIUM
**Status:** OPEN
**Category:** OS Improvement

## Description
CORRECTIONS.md has 14 rules but they only work if read. Convert the most critical ones into automated checks:
- Pre-flight check before external API calls (verify auth exists)
- Channel routing validation (content goes to right channel)
- Context threshold alerts (auto-warn at 60%)

These could be shell scripts, cron checks, or skill enhancements.

## Success Criteria
- [ ] Top 3 corrections converted to automated checks
- [ ] Checks run automatically (cron or pre-task)
- [ ] False positive rate < 10%
