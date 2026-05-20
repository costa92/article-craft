"""Tests for B16 — scripts/ascii_gate.py is scope-aware: it only fires on
ASCII box/arrow characters that appear inside non-executable code blocks.
Prose use of `→` (e.g., "需要更强推理 → 上 Pro") should pass.

Mirrors the rule_14 thresholds in review_selfcheck.py:
    box_count >= 5  OR  (box_count >= 2 AND arrow_count >= 2)
"""

import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ascii_gate.py"


def _run(article_text: str) -> subprocess.CompletedProcess:
    """Write article_text to a temp file and run ascii_gate.py against it."""
    with TemporaryDirectory() as td:
        path = Path(td) / "article.md"
        path.write_text(article_text, encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(path)],
            capture_output=True,
            text=True,
        )


class AsciiGateTests(unittest.TestCase):
    def test_inline_arrow_in_prose_passes(self):
        """Rhetorical `→` in prose is NOT inside a code block — exit 0."""
        article = (
            "---\ntitle: demo\n---\n\n"
            "# 标题\n\n"
            "需要更强推理 → 上 Pro；只要补全 → Haiku 就够。\n\n"
            "另一段：A → B → C 是常见的因果链。\n"
        )
        result = _run(article)
        self.assertEqual(
            result.returncode,
            0,
            f"prose arrows should pass; stderr={result.stderr}",
        )

    def test_box_chars_in_non_executable_code_block_fails(self):
        """6+ box chars in a `text` code block → exit 1."""
        article = (
            "---\ntitle: demo\n---\n\n"
            "# 标题\n\n"
            "```text\n"
            "┌─────┐\n"
            "│ A   │\n"
            "│ B   │\n"
            "└─────┘\n"
            "```\n"
        )
        result = _run(article)
        self.assertEqual(
            result.returncode,
            1,
            f"text-language block with ASCII diagram should fail; "
            f"stdout={result.stdout} stderr={result.stderr}",
        )
        self.assertIn("FAIL", result.stderr)

    def test_box_chars_in_bash_code_block_passes(self):
        """Same 6+ box chars but in a `bash` block → exit 0 (executable, skipped).

        Note: real bash never contains `│ └ ┌`, but the gate skips by language
        tag, not by content shape, so this is the correct behavior.
        """
        article = (
            "---\ntitle: demo\n---\n\n"
            "# 标题\n\n"
            "```bash\n"
            "echo '┌─────┐'\n"
            "echo '│ A   │'\n"
            "echo '│ B   │'\n"
            "echo '└─────┘'\n"
            "```\n"
        )
        result = _run(article)
        self.assertEqual(
            result.returncode,
            0,
            f"bash-tagged block should be skipped; "
            f"stdout={result.stdout} stderr={result.stderr}",
        )

    def test_no_ascii_chars_passes(self):
        article = (
            "---\ntitle: demo\n---\n\n"
            "# 标题\n\n"
            "这是一篇纯文字的文章，没有任何 ASCII 框线或箭头字符。\n"
        )
        result = _run(article)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_file_exits_two(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "/nonexistent/path/article.md"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)

    def test_box_and_arrow_combo_in_text_block_fails(self):
        """box_count >= 2 AND arrow_count >= 2 → fail."""
        article = (
            "---\ntitle: demo\n---\n\n"
            "# 标题\n\n"
            "```text\n"
            "Pod A │ → │ Pod B\n"
            "      ↓    ↓\n"
            "```\n"
        )
        result = _run(article)
        self.assertEqual(result.returncode, 1, result.stderr)

    def test_few_box_chars_below_threshold_passes(self):
        """Single `│` in a text block — below the 5-box / (2+2) thresholds."""
        article = (
            "---\ntitle: demo\n---\n\n"
            "# 标题\n\n"
            "```text\n"
            "A │ B\n"
            "```\n"
        )
        result = _run(article)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_arg_usage(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Usage", result.stderr)


if __name__ == "__main__":
    unittest.main()
