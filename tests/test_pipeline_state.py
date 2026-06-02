import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def load_pipeline_state_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "pipeline_state.py"
    spec = importlib.util.spec_from_file_location("pipeline_state", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


pipeline_state = load_pipeline_state_module()


class PipelineStateTests(unittest.TestCase):
    def test_missing_stages_standard_blank_article(self):
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp) / "article.md"
            article.write_text("", encoding="utf-8")

            state = pipeline_state.PipelineState(str(article))
            out = pipeline_state._compute_missing(state, "standard")

            self.assertEqual(
                out["missing"],
                [
                    "requirements",
                    "verify",
                    "write",
                    "screenshot",
                    "share_card",
                    "images",
                    "verify_claims",
                    "review",
                    "publish",
                ],
            )
            self.assertEqual(out["done"], [])
            self.assertEqual(out["stale"], [])
            self.assertEqual(out["skipped"], [])
            self.assertEqual(out["source"], "heuristic")

    def test_missing_stages_honors_completed_verify_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp) / "02-技术" / "article.md"
            article.parent.mkdir(parents=True, exist_ok=True)
            article.write_text("---\ntitle: demo\n---\n", encoding="utf-8")

            state = pipeline_state.PipelineState(str(article))
            state.set_meta("standard", None)
            for stage in [
                "requirements",
                "verify",
                "write",
                "screenshot",
                "share_card",
                "images",
                "verify_claims",
                "review",
                "publish",
            ]:
                state.complete_stage(stage, {"ok": True})
            state.save()

            out = pipeline_state._compute_missing(state, "standard")

            self.assertEqual(out["missing"], [])
            self.assertEqual(
                out["done"],
                [
                    "requirements",
                    "verify",
                    "write",
                    "screenshot",
                    "share_card",
                    "images",
                    "verify_claims",
                    "review",
                    "publish",
                ],
            )
            self.assertEqual(out["source"], "state_file")

    def test_stale_completed_image_stage_is_requeued(self):
        # state says images completed, but the body still has a raw placeholder →
        # the stage must be flagged stale AND re-queued into missing (the core
        # --upgrade safety net). Guards _is_stale's positive path.
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp) / "article.md"
            article.write_text(
                "---\ntitle: demo\n---\n\n# T\n\n<!-- IMAGE: cover - x (16:9) -->\n",
                encoding="utf-8",
            )
            state = pipeline_state.PipelineState(str(article))
            state.set_meta("standard", None)
            for stage in ["requirements", "verify", "write", "screenshot", "share_card", "images"]:
                state.complete_stage(stage, {"ok": True})
            state.save()

            out = pipeline_state._compute_missing(state, "standard")
            self.assertIn("images", out["stale"])
            self.assertIn("images", out["missing"])
            self.assertEqual(out["source"], "hybrid")

    def test_stale_completed_screenshot_stage_is_requeued(self):
        # screenshot completed in state but body still has a SCREENSHOT placeholder.
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp) / "article.md"
            article.write_text(
                "---\ntitle: demo\n---\n\n# T\n\n<!-- SCREENSHOT: https://x.com/a -->\n",
                encoding="utf-8",
            )
            state = pipeline_state.PipelineState(str(article))
            state.set_meta("standard", None)
            for stage in ["requirements", "verify", "write", "screenshot"]:
                state.complete_stage(stage, {"ok": True})
            state.save()

            out = pipeline_state._compute_missing(state, "standard")
            self.assertIn("screenshot", out["stale"])
            self.assertIn("screenshot", out["missing"])

    def test_stale_completed_publish_stage_when_not_in_kb(self):
        # publish completed in state but the article isn't under the KB path.
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp) / "article.md"  # not under /02-技术/
            article.write_text("---\ntitle: demo\n---\n\n# T\n\n正文。\n", encoding="utf-8")
            state = pipeline_state.PipelineState(str(article))
            state.set_meta("standard", None)
            for stage in ["requirements", "verify", "write", "screenshot", "share_card",
                          "images", "verify_claims", "review", "publish"]:
                state.complete_stage(stage, {"ok": True})
            state.save()

            out = pipeline_state._compute_missing(state, "standard")
            self.assertIn("publish", out["stale"])
            self.assertIn("publish", out["missing"])

    def test_missing_stages_draft_skips_evidence_when_not_style_h(self):
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp) / "article.md"
            article.write_text("", encoding="utf-8")

            state = pipeline_state.PipelineState(str(article))
            out = pipeline_state._compute_missing(state, "draft")

            self.assertEqual(out["missing"], ["requirements", "write"])
            self.assertNotIn("evidence", out["missing"])

    def test_unknown_stage_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp) / "article.md"
            article.write_text("", encoding="utf-8")

            self.assertEqual(
                pipeline_state.main([
                    "start",
                    "--article",
                    str(article),
                    "--stage",
                    "unknown",
                ]),
                2,
            )

    def test_scan_article_extracts_tone_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp) / "article.md"
            article_text = "---\nwriting_style: D\ntone: casual\n---\n\n# T\n\nbody."
            article.write_text(article_text, encoding="utf-8")

            scan = pipeline_state._scan_article(article)
            self.assertEqual(scan.tone, "casual")

    def test_scan_in_kb_respects_custom_category_root(self):
        """in_kb must use config.kb_category_root(), not a hardcoded /02-技术/.

        A fork can set kb_category_root in env.json (e.g. "03-Notes"); the
        --upgrade scan must recognize the article as in-KB under that name.
        """
        with tempfile.TemporaryDirectory() as tmp:
            kb_dir = Path(tmp) / "03-Notes"
            kb_dir.mkdir()
            article = kb_dir / "article.md"
            article.write_text("# T\n", encoding="utf-8")
            with mock.patch.object(pipeline_state, "_kb_category_root",
                                   return_value="03-Notes", create=True):
                scan = pipeline_state._scan_article(article)
            self.assertTrue(
                scan.in_kb,
                "in_kb must honor the configured KB category root, not hardcode 02-技术",
            )

    def test_scan_article_tone_field_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp) / "article.md"
            article_text = "---\nwriting_style: D\n---\n\n# T\n\nbody."
            article.write_text(article_text, encoding="utf-8")

            scan = pipeline_state._scan_article(article)
            self.assertIsNone(scan.tone)

    def test_complete_rejects_non_object_result_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp) / "article.md"
            article.write_text("", encoding="utf-8")

            code = pipeline_state.main([
                "complete",
                "--article",
                str(article),
                "--stage",
                "write",
                "--result",
                "[]",
            ])
            self.assertEqual(code, 1)

    def test_validate_state_reports_invalid_stage_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp) / "article.md"
            article.write_text("---\ntitle: demo\n---\n", encoding="utf-8")
            state_path = article.parent / pipeline_state.STATE_FILENAME
            state_path.write_text(
                json.dumps(
                    {
                        "schema_version": pipeline_state.SCHEMA_VERSION,
                        "pipeline_version": "test",
                        "article_path": str(article.resolve()),
                        "mode": "standard",
                        "writing_style": "A",
                        "created_at": 0,
                        "last_updated_at": 0,
                        "stages": {
                            "write": {
                                "status": "broken",
                                "started_at": 0,
                                "completed_at": 0,
                                "result": {},
                            }
                        },
                        "artifacts": {},
                    }
                ),
                encoding="utf-8",
            )

            repo_root = Path(__file__).resolve().parent.parent
            result = subprocess.run(
                [
                    "python3",
                    str(repo_root / "scripts" / "pipeline_state.py"),
                    "validate-state",
                    "--article",
                    str(article),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error_code"], "invalid_stage_status")

    def test_missing_stages_cli_emits_standard_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp) / "article.md"
            article.write_text("", encoding="utf-8")

            repo_root = Path(__file__).resolve().parent.parent
            result = subprocess.run(
                [
                    "python3",
                    str(repo_root / "scripts" / "pipeline_state.py"),
                    "missing-stages",
                    "--article",
                    str(article),
                    "--mode",
                    "standard",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["message"], "computed missing stages")
            self.assertIn("missing", payload["details"])
            self.assertEqual(payload["details"]["source"], "heuristic")


class CheckPublishReadyTests(unittest.TestCase):
    """Pre-publish placeholder gate (`pipeline_state.py check-publish-ready`).

    Catches the silent failure where --no-upload (or upload error) leaves
    <!-- IMAGE/PROMPT/SCREENSHOT/HARVEST: --> placeholders intact and
    publish moves a half-baked file into the knowledge base.
    """

    def _run(self, article_path):
        """Invoke the CLI and return (exit_code, stdout, stderr)."""
        import subprocess
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [
                "python3",
                str(repo_root / "scripts" / "pipeline_state.py"),
                "check-publish-ready",
                "--article", str(article_path),
            ],
            capture_output=True, text=True,
        )
        return result.returncode, result.stdout, result.stderr

    def test_clean_article_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp) / "article.md"
            article.write_text(
                "---\nwriting_style: A\n---\n\n# Title\n\n"
                "Body text. Image already replaced: ![](https://cdn.example.com/img.jpg)\n",
                encoding="utf-8",
            )
            code, stdout, stderr = self._run(article)
            self.assertEqual(code, 0, msg=stderr)
            payload = json.loads(stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["details"]["ready"])

    def test_unresolved_image_placeholder_blocks_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp) / "article.md"
            article.write_text(
                "---\nwriting_style: A\n---\n\n# Title\n\n"
                "Body. <!-- IMAGE: cover - test (16:9) -->\n"
                "<!-- PROMPT: Test prompt. -->\n",
                encoding="utf-8",
            )
            code, stdout, stderr = self._run(article)
            self.assertEqual(code, 1)
            payload = json.loads(stdout)
            self.assertFalse(payload["ok"])
            self.assertFalse(payload["details"]["ready"])
            self.assertIn("BLOCK publish", stderr)
            self.assertIn("IMAGE: 1", stderr)
            self.assertIn("PROMPT: 1", stderr)

    def test_unresolved_screenshot_placeholder_blocks_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp) / "article.md"
            article.write_text(
                "---\nwriting_style: B\n---\n\n# T\n\n"
                "<!-- SCREENSHOT: https://example.com -->\n",
                encoding="utf-8",
            )
            code, stdout, stderr = self._run(article)
            self.assertEqual(code, 1)
            self.assertIn("SCREENSHOT: 1", stderr)

    def test_unresolved_harvest_placeholder_blocks_publish(self):
        # Style H articles use HARVEST placeholders for source-image picking.
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp) / "article.md"
            article.write_text(
                "---\nwriting_style: H\n---\n\n# T\n\n"
                '<!-- HARVEST: https://example.com idx=2 caption="..." -->\n',
                encoding="utf-8",
            )
            code, stdout, stderr = self._run(article)
            self.assertEqual(code, 1)
            self.assertIn("HARVEST: 1", stderr)

    def test_multiple_placeholder_kinds_counted_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp) / "article.md"
            article.write_text(
                "---\nwriting_style: D\n---\n\n# T\n\n"
                "<!-- IMAGE: a - x (16:9) -->\n"
                "<!-- PROMPT: x. -->\n"
                "<!-- IMAGE: b - y (16:9) -->\n"
                "<!-- PROMPT: y. -->\n"
                "<!-- SCREENSHOT: https://example.com -->\n",
                encoding="utf-8",
            )
            code, stdout, stderr = self._run(article)
            self.assertEqual(code, 1)
            self.assertIn("IMAGE: 2", stderr)
            self.assertIn("PROMPT: 2", stderr)
            self.assertIn("SCREENSHOT: 1", stderr)

    def test_nonexistent_article_returns_two(self):
        code, stdout, stderr = self._run("/tmp/definitely-does-not-exist-xyz.md")
        self.assertEqual(code, 2)
        self.assertIn("not found", stderr)


if __name__ == "__main__":
    unittest.main()
