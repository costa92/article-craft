import importlib.util
import tempfile
import unittest
from pathlib import Path


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

    def test_scan_article_tone_field_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp) / "article.md"
            article_text = "---\nwriting_style: D\n---\n\n# T\n\nbody."
            article.write_text(article_text, encoding="utf-8")

            scan = pipeline_state._scan_article(article)
            self.assertIsNone(scan.tone)


if __name__ == "__main__":
    unittest.main()
