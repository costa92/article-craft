import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class PublishPlanTests(unittest.TestCase):
    def _run(self, *args: str):
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            ["python3", str(repo_root / "scripts" / "publish_plan.py"), *args],
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout, result.stderr

    def test_explicit_output_dir_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            article = root / "draft.md"
            out_dir = root / "published"
            out_dir.mkdir()
            article.write_text("---\ntitle: Demo\n---\n\nbody\n", encoding="utf-8")

            code, stdout, stderr = self._run(
                "--article",
                str(article),
                "--output-dir",
                str(out_dir),
                "--dry-run",
            )
            self.assertEqual(code, 0, msg=stderr)
            payload = json.loads(stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["details"]["target_dir"], str(out_dir.resolve()))
            self.assertEqual(payload["details"]["target_file"], str((out_dir / "draft.md").resolve()))
            self.assertEqual(payload["details"]["mode"], "explicit_output")

    def test_style_h_sidecars_are_planned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            article_dir = root / "incoming"
            kb_root = root / "kb"
            target_dir = kb_root / "02-技术" / "AI-生态" / "Claude-Code"
            article_dir.mkdir(parents=True)
            target_dir.mkdir(parents=True)
            article = article_dir / "style-h.md"
            article.write_text("---\ntitle: Claude Code 爆料\n---\n\nbody\n", encoding="utf-8")
            (article_dir / "_evidence.json").write_text("{}", encoding="utf-8")
            (article_dir / "_harvest_menu.md").write_text("# menu\n", encoding="utf-8")

            code, stdout, stderr = self._run(
                "--article",
                str(article),
                "--output-dir",
                str(target_dir),
                "--dry-run",
            )
            self.assertEqual(code, 0, msg=stderr)
            payload = json.loads(stdout)
            self.assertEqual(
                sorted(payload["details"]["sidecars"]),
                ["_evidence.json", "_harvest_menu.md"],
            )

    def test_collision_with_different_content_gets_timestamped_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            article = root / "draft.md"
            out_dir = root / "published"
            out_dir.mkdir()
            article.write_text("---\ntitle: Demo\n---\n\nnew body\n", encoding="utf-8")
            (out_dir / "draft.md").write_text("---\ntitle: Demo\n---\n\nold body\n", encoding="utf-8")

            code, stdout, stderr = self._run(
                "--article",
                str(article),
                "--output-dir",
                str(out_dir),
                "--dry-run",
            )
            self.assertEqual(code, 0, msg=stderr)
            payload = json.loads(stdout)
            self.assertEqual(payload["details"]["collision"]["status"], "rename")
            self.assertNotEqual(payload["details"]["target_file"], str((out_dir / "draft.md").resolve()))

    def test_apply_copies_article_and_sidecars(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            article_dir = root / "incoming"
            out_dir = root / "published"
            article_dir.mkdir(parents=True)
            out_dir.mkdir()
            article = article_dir / "draft.md"
            article.write_text("---\ntitle: Demo\n---\n\nbody\n", encoding="utf-8")
            (article_dir / "_evidence.json").write_text("{}", encoding="utf-8")

            code, stdout, stderr = self._run(
                "--article",
                str(article),
                "--output-dir",
                str(out_dir),
            )
            self.assertEqual(code, 0, msg=stderr)
            payload = json.loads(stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue((out_dir / "draft.md").exists())
            self.assertTrue((out_dir / "_evidence.json").exists())

    def test_auto_mode_uses_kb_directory_matcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            article = root / "draft.md"
            article.write_text("---\ntitle: Claude Code Tips\n---\n\nbody\n", encoding="utf-8")
            kb_root = root / "kb"
            (kb_root / "02-技术" / "AI-生态" / "Claude-Code").mkdir(parents=True)

            code, stdout, stderr = self._run(
                "--article",
                str(article),
                "--kb-root",
                str(kb_root),
                "--dry-run",
            )
            self.assertEqual(code, 0, msg=stderr)
            payload = json.loads(stdout)
            self.assertEqual(payload["details"]["mode"], "auto")
            self.assertEqual(
                payload["details"]["target_dir"],
                str((kb_root / "02-技术" / "AI-生态" / "Claude-Code").resolve()),
            )

    def test_dry_run_does_not_create_directories(self):
        """A --dry-run plan must leave the filesystem untouched, even when the
        auto-placement strategy resolves to a not-yet-existing fallback dir."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            article = root / "draft.md"
            article.write_text("---\ntitle: Totally Unmatched Topic\n---\n\nbody\n", encoding="utf-8")
            kb_root = root / "kb"
            kb_root.mkdir()

            code, stdout, stderr = self._run(
                "--article",
                str(article),
                "--kb-root",
                str(kb_root),
                "--dry-run",
            )
            self.assertEqual(code, 0, msg=stderr)
            payload = json.loads(stdout)
            target_dir = Path(payload["details"]["target_dir"])
            # The plan proposed a directory ...
            self.assertTrue(str(target_dir).startswith(str(kb_root.resolve())))
            # ... but dry-run must not have created it (nor the category root).
            self.assertFalse(target_dir.exists(), "dry-run created the target directory")
            self.assertFalse((kb_root / "02-技术").exists(), "dry-run created the category root")

    def test_apply_creates_missing_target_directory(self):
        """Without --dry-run, apply is responsible for creating the target dir."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            article = root / "draft.md"
            article.write_text("---\ntitle: Unmatched\n---\n\nbody\n", encoding="utf-8")
            kb_root = root / "kb"
            kb_root.mkdir()

            code, stdout, stderr = self._run(
                "--article",
                str(article),
                "--kb-root",
                str(kb_root),
            )
            self.assertEqual(code, 0, msg=stderr)
            payload = json.loads(stdout)
            target_file = Path(payload["details"]["target_file"])
            self.assertTrue(target_file.exists(), "apply did not create the published file")


if __name__ == "__main__":
    unittest.main()
