#!/bin/bash
# article-craft SessionStart hook
# Checks that shared Python scripts and required skills are available

SCRIPTS_DIR="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/article-craft}/scripts"

# Check shared Python scripts
for f in nanobanana.py generate_and_upload_images.py config.py utils.py; do
  [ -f "$SCRIPTS_DIR/$f" ] || echo "WARNING: article-craft missing shared script: $SCRIPTS_DIR/$f"
done

# Check required skill dependencies
if ! ls "$HOME/.claude/skills/content-reviewer/SKILL.md" >/dev/null 2>&1; then
  echo "WARNING: article-craft requires /content-reviewer skill (not found at ~/.claude/skills/content-reviewer/)"
fi
