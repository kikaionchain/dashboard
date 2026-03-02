# Mission Control

Shared task board for WJP, Kikai, and Yama.

## How It Works

1. **Create a task** — Drop a `.md` file in `tasks/backlog/`
2. **Pick up a task** — Move it to `tasks/in-progress/` and start working
3. **Submit for review** — Move to `tasks/review/`
4. **Mark done** — Move to `tasks/done/`

## Task File Format

```markdown
# Task: [Title]
- **ID:** task-XXX
- **Priority:** low | medium | high | critical
- **Assigned:** kikai | yama | unassigned
- **Created:** YYYY-MM-DD
- **Due:** YYYY-MM-DD (optional)
- **Tags:** [comma-separated]

## Description
What needs to be done.

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Notes
Any additional context.
```

## Rules
- Anyone can create tasks
- Only pick up tasks assigned to you (or unassigned)
- Update the task file with progress notes as you work
- Move to `review/` when done — WJP reviews
- Move to `done/` after approval
- No cross-agent communication. Period.

## Viewing the Board
Run `show board` or check the Canvas dashboard.
