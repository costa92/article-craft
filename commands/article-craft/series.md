---
description: Plan, manage, and generate article series — create series, write next article, check progress, validate, audit coverage, or generate collection
argument-hint: [create|next|status|validate|audit|collection] [series-file-path]
---

Read and follow the skill at `${CLAUDE_PLUGIN_ROOT}/skills/series/SKILL.md`.

Series state operations are implemented in `scripts/series_state.py`:
- `status --series FILE`
- `next --series FILE`
- `mark-published --series FILE --index N --path PATH`
- `validate --series FILE`

ARGUMENTS: $ARGUMENTS
