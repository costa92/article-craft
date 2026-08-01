import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from py_exe import PYTHON


class PipelineE2ETests(unittest.TestCase):
    def _run(self, *args: str):
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [PYTHON, str(repo_root / "scripts" / "pipeline_state.py"), *args],
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout, result.stderr

    def test_init_complete_and_stage_summary_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp) / "article.md"
            article.write_text("---\ntitle: demo\n---\n", encoding="utf-8")

            code, _, stderr = self._run(
                "init",
                "--article",
                str(article),
                "--mode",
                "standard",
                "--writing-style",
                "A",
            )
            self.assertEqual(code, 0, msg=stderr)

            code, _, stderr = self._run(
                "start",
                "--article",
                str(article),
                "--stage",
                "write",
            )
            self.assertEqual(code, 0, msg=stderr)

            code, _, stderr = self._run(
                "complete",
                "--article",
                str(article),
                "--stage",
                "write",
                "--result",
                '{"article_path":"article.md","word_count":123}',
            )
            self.assertEqual(code, 0, msg=stderr)

            code, stdout, stderr = self._run(
                "stage-summary",
                "--article",
                str(article),
            )
            self.assertEqual(code, 0, msg=stderr)
            payload = json.loads(stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["details"]["counts"]["completed"], 1)
            self.assertEqual(payload["details"]["counts"]["running"], 0)
            self.assertEqual(payload["details"]["mode"], "standard")

    def test_publish_ready_and_missing_stages_payloads_share_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp) / "article.md"
            article.write_text(
                "---\nwriting_style: A\n---\n\n# Title\n\n<!-- IMAGE: cover - test (16:9) -->\n",
                encoding="utf-8",
            )

            code, stdout, stderr = self._run(
                "check-publish-ready",
                "--article",
                str(article),
            )
            self.assertEqual(code, 1)
            publish_payload = json.loads(stdout)
            self.assertIn("ok", publish_payload)
            self.assertIn("message", publish_payload)
            self.assertIn("details", publish_payload)
            self.assertFalse(publish_payload["ok"])
            self.assertIn("BLOCK publish", stderr)

            code, stdout, stderr = self._run(
                "missing-stages",
                "--article",
                str(article),
                "--mode",
                "standard",
            )
            self.assertEqual(code, 0, msg=stderr)
            missing_payload = json.loads(stdout)
            self.assertIn("ok", missing_payload)
            self.assertIn("message", missing_payload)
            self.assertIn("details", missing_payload)


if __name__ == "__main__":
    unittest.main()
