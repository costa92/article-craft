import importlib.util
import tempfile
import unittest
from pathlib import Path


def load_verify_claims_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "verify_claims.py"
    spec = importlib.util.spec_from_file_location("verify_claims", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


verify_claims = load_verify_claims_module()


class VerifyClaimsTests(unittest.TestCase):
    def test_scan_skips_builtins_and_ubiquitous_tools(self):
        article = """```bash
cd /tmp && ls && curl https://example.com && python3 -V
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "article.md"
            path.write_text(article, encoding="utf-8")

            report = verify_claims.scan_article(path)

            self.assertEqual(report["checked"], [])
            self.assertCountEqual(report["skipped_ubiquitous"], ["curl", "ls", "python3"])
            self.assertEqual(report["missing"], [])

    def test_scan_reports_missing_tools(self):
        article = """```bash
mycustomtool --version
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "article.md"
            path.write_text(article, encoding="utf-8")

            report = verify_claims.scan_article(path)

            self.assertEqual([entry["tool"] for entry in report["checked"]], ["mycustomtool"])
            self.assertEqual(report["missing"], ["mycustomtool"])

    def test_iter_shell_blocks_ignores_non_shell_fences(self):
        text = """```python
print("hello")
```
```bash
echo ok
```
"""
        blocks = list(verify_claims._iter_shell_blocks(text))

        self.assertEqual(len(blocks), 1)
        self.assertIn("echo ok", blocks[0])

    def test_iter_shell_blocks_supports_fence_attributes(self):
        text = """```bash title="example"
echo ok
```
"""
        blocks = list(verify_claims._iter_shell_blocks(text))

        self.assertEqual(len(blocks), 1)
        self.assertIn("echo ok", blocks[0])

    def test_extract_tool_strips_env_and_sudo(self):
        self.assertEqual(verify_claims._extract_tool("sudo env mytool --help"), "mytool")


if __name__ == "__main__":
    unittest.main()
