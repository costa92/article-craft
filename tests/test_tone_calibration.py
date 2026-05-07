"""Tests for tone-calibration JSONL writer."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main, mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.review_selfcheck import check_rule_17


class ToneCalibrationTests(TestCase):
    def test_calibration_jsonl_written_when_enabled(self):
        with tempfile.TemporaryDirectory() as td:
            cache_dir = Path(td)
            article = (
                "---\nwriting_style: A\ntone: neutral\n---\n\n# T\n\n"
                + "技术内容描述。" * 100
            )
            with mock.patch.dict(
                os.environ,
                {"ARTICLE_CRAFT_CACHE_DIR": str(cache_dir),
                 "ARTICLE_CRAFT_TONE_CALIBRATION": "true"},
            ):
                check_rule_17(article, article.split("\n"))
            jsonl_path = cache_dir / "tone-calibration.jsonl"
            self.assertTrue(jsonl_path.exists())
            line = jsonl_path.read_text(encoding="utf-8").strip().split("\n")[-1]
            data = json.loads(line)
            self.assertEqual(data["tone_resolved"], "neutral")
            self.assertEqual(data["writing_style"], "A")
            self.assertIn("metrics", data)
            self.assertIn("first_person_per_800w", data["metrics"])

    def test_calibration_jsonl_not_written_when_disabled(self):
        with tempfile.TemporaryDirectory() as td:
            cache_dir = Path(td)
            article = (
                "---\nwriting_style: A\ntone: neutral\n---\n\n# T\n\n"
                + "技术内容描述。" * 100
            )
            with mock.patch.dict(
                os.environ,
                {"ARTICLE_CRAFT_CACHE_DIR": str(cache_dir),
                 "ARTICLE_CRAFT_TONE_CALIBRATION": "false"},
            ):
                check_rule_17(article, article.split("\n"))
            self.assertFalse((cache_dir / "tone-calibration.jsonl").exists())


if __name__ == "__main__":
    main()
