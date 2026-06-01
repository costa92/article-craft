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

    def test_extract_tool_strips_env_var_assignment_prefix(self):
        # `FOO=bar mytool` — the leading VAR=value assignment must be stripped so
        # the real tool (mytool) is still extracted and PATH-checked.
        self.assertEqual(verify_claims._extract_tool("FOO=bar mytool run"), "mytool")
        self.assertEqual(verify_claims._extract_tool("DEBUG=1 NODE_ENV=prod mytool"), "mytool")

    def test_extract_tool_handles_pathspec_separator(self):
        # `git -- file.txt` uses `--` as the pathspec separator; the tool is git,
        # not a prose help-description. Must not be dropped.
        self.assertEqual(verify_claims._extract_tool("git -- file.txt"), "git")
        self.assertEqual(verify_claims._extract_tool("mytool -- input.txt"), "mytool")

    def test_extract_tool_still_skips_prose_description(self):
        # Typographic dash help text ("mempalace — a searchable palace") is prose,
        # not a command — still skipped.
        self.assertIsNone(verify_claims._extract_tool("mempalace — a searchable palace"))
        self.assertIsNone(verify_claims._extract_tool("a searchable drawer"))


# ─── B8 Phase 1: flag validation ─────────────────────────────────────────


class FlagValidationTests(unittest.TestCase):
    def test_extract_tool_and_flags_picks_long_flags_only(self):
        tool, flags = verify_claims._extract_tool_and_flags(
            "git commit -m 'msg' --no-edit --amend -v"
        )
        self.assertEqual(tool, "git")
        # Long flags only — short flags filtered out per Phase 1 scope.
        self.assertEqual(flags, ["--no-edit", "--amend"])

    def test_extract_flags_handles_equals_value_form(self):
        tool, flags = verify_claims._extract_tool_and_flags(
            "docker build --tag=myimage --no-cache --file=Dockerfile.prod"
        )
        self.assertEqual(tool, "docker")
        self.assertEqual(flags, ["--tag", "--no-cache", "--file"])

    def test_extract_flags_strips_trailing_punctuation(self):
        tool, flags = verify_claims._extract_tool_and_flags(
            "curl --help. https://example.com"
        )
        self.assertEqual(tool, "curl")
        self.assertIn("--help", flags)

    def test_extract_flags_after_sudo_attribution(self):
        tool, flags = verify_claims._extract_tool_and_flags(
            "sudo docker run --rm --detach nginx"
        )
        self.assertEqual(tool, "docker")
        self.assertEqual(flags, ["--rm", "--detach"])

    def test_check_flags_returns_empty_for_unknown_tool(self):
        unknown = verify_claims._check_flags(
            "my-custom-cli", ["--foo", "--bar"]
        )
        self.assertEqual(unknown, [])

    def test_check_flags_returns_unknown_subset_for_known_tool(self):
        # `--mesage` is the textbook typo we want to catch on git.
        unknown = verify_claims._check_flags(
            "git", ["--message", "--mesage", "--amend"]
        )
        self.assertEqual(unknown, ["--mesage"])

    def test_check_flags_dedupes(self):
        unknown = verify_claims._check_flags(
            "git", ["--made-up", "--made-up", "--also-made-up"]
        )
        self.assertEqual(unknown, ["--made-up", "--also-made-up"])

    def test_scan_emits_flag_warnings_for_git_typo(self):
        article = """```bash
git push --force --mesage "typo here"
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "article.md"
            path.write_text(article, encoding="utf-8")
            report = verify_claims.scan_article(path)

        self.assertEqual(len(report["flag_warnings"]), 1)
        w = report["flag_warnings"][0]
        self.assertEqual(w["tool"], "git")
        self.assertEqual(w["flag"], "--mesage")
        self.assertIn("--mesage", w["fragment"])

    def test_scan_emits_no_flag_warning_for_valid_flags(self):
        article = """```bash
git commit -m "fix" --amend --no-edit
docker run --rm --detach nginx
kubectl get pods --all-namespaces --output json
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "article.md"
            path.write_text(article, encoding="utf-8")
            report = verify_claims.scan_article(path)

        self.assertEqual(report["flag_warnings"], [])

    def test_scan_emits_flag_warnings_across_multiple_tools(self):
        article = """```bash
git push --foo
docker run --bar nginx
kubectl get --baz pods
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "article.md"
            path.write_text(article, encoding="utf-8")
            report = verify_claims.scan_article(path)

        # Sorted alphabetically by tool — docker, git, kubectl
        tools_seen = [w["tool"] for w in report["flag_warnings"]]
        self.assertEqual(tools_seen, ["docker", "git", "kubectl"])

    def test_scan_skips_flag_check_for_tools_not_in_schema(self):
        article = """```bash
some-random-tool --made-up-flag --another-bad-flag
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "article.md"
            path.write_text(article, encoding="utf-8")
            report = verify_claims.scan_article(path)

        # The tool isn't in the schema — no flag warnings even though
        # the flags are nonsense.
        self.assertEqual(report["flag_warnings"], [])

    def test_scan_keeps_exit_code_unchanged_with_only_flag_warnings(self):
        """Flag warnings are informational — they don't fail the exit code.

        Phase 1 scope: introduce the signal, don't gate on it. This pins
        the contract so a later phase that DOES gate is an explicit
        behaviour change.
        """
        article = """```bash
git push --mesage "typo"
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "article.md"
            path.write_text(article, encoding="utf-8")
            report = verify_claims.scan_article(path)

        # Has flag warnings but no missing tools.
        self.assertTrue(report["flag_warnings"])
        self.assertEqual(report["missing"], [])

    def test_schema_includes_top_seven_tools(self):
        """Pin the curated tool list. Adding a new tool here is a
        conscious schema-expansion decision, not an accident."""
        expected = {"git", "docker", "kubectl", "uv", "npm", "curl", "python3"}
        self.assertEqual(set(verify_claims.TOOL_FLAG_SCHEMA.keys()), expected)


if __name__ == "__main__":
    unittest.main()
