"""Shared interpreter for CLI subprocess tests.

Always use ``sys.executable`` (the same interpreter running pytest), never a
literal ``"python3"`` on PATH. Skills and docs still say ``python3`` for
humans; doctor probes PATH ``python3`` separately. Tests must not depend on
whatever broken/incomplete Homebrew binary happens to win on PATH.

Historical failure (v1.10.0 dogfood): PATH ``python3`` was Homebrew 3.14 with
a broken libexpat and no PyYAML; pytest ran under 3.13 with deps installed.
Hardcoded ``["python3", script, ...]`` made CLI tests fail while in-process
imports passed.
"""

from __future__ import annotations

import sys

# Prefer the pytest process interpreter for every CLI spawn in tests.
PYTHON = sys.executable
