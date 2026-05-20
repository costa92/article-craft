#!/usr/bin/env python3
"""Scope-aware ASCII diagram gate.

Re-uses the logic from `review_selfcheck.check_rule_14`: only flags ASCII
box/arrow characters that appear *inside non-executable code blocks*. Prose
uses of `→` ("leads to") and similar are intentionally ignored.

Thresholds (mirror Rule 14):
    box_count >= 5  OR  (box_count >= 2 AND arrow_count >= 2)

Exit codes:
    0 — clean (no violations)
    1 — violations found (printed as `file:line` to stdout)
    2 — file does not exist

Usage:
    python3 ascii_gate.py /abs/path/to/article.md
"""

import os
import sys
from pathlib import Path

# Make this script work both as a direct invocation and as a module.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from review_selfcheck import (  # noqa: E402
    _BOX_CHARS,
    _ARROW_CHARS,
    _EXECUTABLE_LANGS,
)


def find_violations(content: str):
    """Return a list of (line_number, language, preview) violations.

    Line number is 1-indexed and points at the opening ``` fence of the
    offending block.
    """
    lines = content.split("\n")
    violations = []
    in_code = False
    code_start = 0
    code_lang = ""
    code_lines = []

    for i, line in enumerate(lines):
        stripped = line.rstrip()
        if stripped.startswith("```"):
            if in_code:
                # End of block — evaluate
                block_content = "".join(code_lines)
                box_count = sum(1 for c in block_content if c in _BOX_CHARS)
                arrow_count = sum(1 for c in block_content if c in _ARROW_CHARS)
                if box_count >= 5 or (box_count >= 2 and arrow_count >= 2):
                    if code_lang.lower() not in _EXECUTABLE_LANGS:
                        preview = block_content.replace("\n", " | ")[:80]
                        violations.append((code_start + 1, code_lang, preview))
                in_code = False
                code_lines = []
            else:
                in_code = True
                code_start = i
                code_lang = stripped[3:].strip()
                code_lines = []
        elif in_code:
            code_lines.append(line)

    return violations


def main():
    if len(sys.argv) != 2:
        print("Usage: ascii_gate.py <article.md>", file=sys.stderr)
        sys.exit(2)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"ascii_gate: file not found: {path}", file=sys.stderr)
        sys.exit(2)

    content = path.read_text(encoding="utf-8")
    violations = find_violations(content)

    if not violations:
        print(f"ascii_gate: PASS ({path})")
        sys.exit(0)

    print(
        f"ascii_gate: FAIL — {len(violations)} ASCII-diagram block(s) found in "
        f"non-executable code blocks. Convert each to a <!-- IMAGE: --> placeholder.",
        file=sys.stderr,
    )
    for line_no, lang, preview in violations:
        lang_label = lang or "(no-lang)"
        print(f"{path}:{line_no}: ```{lang_label}  {preview}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
