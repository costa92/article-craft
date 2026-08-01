import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from py_exe import PYTHON


class SeriesStateTests(unittest.TestCase):
    def _run(self, *args: str):
        repo_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            [PYTHON, str(repo_root / "scripts" / "series_state.py"), *args],
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout, result.stderr

    def _series_file(self, root: Path) -> Path:
        series_dir = root / "kb" / "02-技术" / "基础设施" / "Go" / "go-tutorial"
        series_dir.mkdir(parents=True)
        series_file = series_dir / "series-go-tutorial.md"
        series_file.write_text(
            "---\n"
            'series_name: "Go 实战教程"\n'
            'series_slug: "go-tutorial"\n'
            'target_audience: "intermediate"\n'
            "total_articles: 2\n"
            'writing_style: "A"\n'
            'status: "in_progress"\n'
            "---\n\n"
            "# 📚 系列：Go 实战教程\n\n"
            "| # | 标题 | 核心内容 | 状态 | 文件路径 |\n"
            "|---|------|---------|------|---------|\n"
            "| 1 | Go 环境搭建 | 安装与初始化 | 💡 planned | — |\n"
            "| 2 | Go 数据结构 | slice/map | 💡 planned | — |\n",
            encoding="utf-8",
        )
        return series_file

    def test_status_reports_next_planned_article(self):
        with tempfile.TemporaryDirectory() as tmp:
            series_file = self._series_file(Path(tmp))
            code, stdout, stderr = self._run("status", "--series", str(series_file))
            self.assertEqual(code, 0, msg=stderr)
            payload = json.loads(stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["details"]["next"]["title"], "Go 环境搭建")
            self.assertEqual(payload["details"]["progress"]["done"], 0)

    def test_next_returns_next_article_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            series_file = self._series_file(Path(tmp))
            code, stdout, stderr = self._run("next", "--series", str(series_file))
            self.assertEqual(code, 0, msg=stderr)
            payload = json.loads(stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["details"]["article"]["title"], "Go 环境搭建")
            self.assertTrue(payload["details"]["article"]["save_path"].endswith("01_go_环境搭建.md"))

    def test_mark_published_updates_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            series_file = self._series_file(Path(tmp))
            code, stdout, stderr = self._run(
                "mark-published",
                "--series",
                str(series_file),
                "--index",
                "1",
                "--path",
                str((series_file.parent / "01_go_environment_setup.md")),
            )
            self.assertEqual(code, 0, msg=stderr)
            payload = json.loads(stdout)
            self.assertTrue(payload["ok"])
            updated = series_file.read_text(encoding="utf-8")
            self.assertIn("✅ published", updated)
            self.assertIn("01_go_environment_setup.md", updated)

    def test_mark_published_fails_loudly_on_unknown_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            series_file = self._series_file(Path(tmp))
            before = series_file.read_text(encoding="utf-8")
            code, stdout, stderr = self._run(
                "mark-published",
                "--series",
                str(series_file),
                "--index",
                "99",
                "--path",
                "/tmp/whatever.md",
            )
            self.assertEqual(code, 1)
            payload = json.loads(stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error_code"], "series_row_not_found")
            # A non-matching index must not silently rewrite the file.
            self.assertEqual(series_file.read_text(encoding="utf-8"), before)

    def test_next_includes_series_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            series_file = self._series_file(Path(tmp))
            code, stdout, stderr = self._run("next", "--series", str(series_file))
            self.assertEqual(code, 0, msg=stderr)
            payload = json.loads(stdout)
            article = payload["details"]["article"]
            self.assertEqual(article["series_order"], 1)
            self.assertEqual(article["series_total"], 2)
            self.assertIsNone(article["prev_title"])
            self.assertEqual(article["next_title"], "Go 数据结构")

    def test_validate_rejects_series_file_without_article_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            series_file = root / "broken-series.md"
            series_file.write_text(
                "---\nseries_name: Broken\nseries_slug: broken\ntotal_articles: 2\n---\n\n# Broken\n",
                encoding="utf-8",
            )
            code, stdout, stderr = self._run("validate", "--series", str(series_file))
            self.assertEqual(code, 1)
            payload = json.loads(stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error_code"], "series_table_missing")


if __name__ == "__main__":
    unittest.main()
