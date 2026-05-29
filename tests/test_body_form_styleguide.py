"""Structural guard: style-guide.md must document both body forms so the
writer prompt has something to inject (Task 5 depends on these anchors)."""

import sys
from pathlib import Path
from unittest import TestCase, main

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "skills" / "write" / "style-guide.md"


class BodyFormStyleGuideTests(TestCase):
    def setUp(self):
        self.text = GUIDE.read_text(encoding="utf-8")

    def test_has_wechat_native_section(self):
        self.assertIn("## Body Form: wechat-native", self.text)

    def test_documents_callout_ban(self):
        # The native form must explicitly forbid Obsidian callouts.
        self.assertRegex(self.text, r"Body Form: wechat-native[\s\S]*?callout")

    def test_documents_long_form(self):
        self.assertIn("long-form", self.text)


if __name__ == "__main__":
    main()
