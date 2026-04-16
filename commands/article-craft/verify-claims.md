---
description: Scan an article's body for shell commands and check they exist on PATH. Post-write counterpart to the pre-write verify stage.
argument-hint: <article-path>
---

Read the skill at `${CLAUDE_PLUGIN_ROOT}/skills/verify-claims/SKILL.md` and
follow its Process section. If `$ARGUMENTS` contains an absolute path, use
it as the article argument; otherwise ask the user for the path.

ARGUMENTS: $ARGUMENTS
