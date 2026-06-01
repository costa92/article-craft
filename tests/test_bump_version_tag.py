"""Regression test: bump_version.create_git_tag must tag a commit that
contains the version bump.

Bug: create_git_tag did `git add` then `git tag -a` with no `git commit` in
between (a comment even claimed it would amend/commit, but it never did). The
tag pointed at the pre-bump HEAD and the bumped files sat uncommitted, so
`git show vX.Y.Z:.claude-plugin/plugin.json` showed the OLD version.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


def _load():
    p = Path(__file__).resolve().parents[1] / "scripts" / "bump_version.py"
    if str(p.parent) not in sys.path:
        sys.path.insert(0, str(p.parent))
    spec = importlib.util.spec_from_file_location("bump_version_tag_test", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bv = _load()


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A throwaway git repo seeded with an OLD-version plugin.json committed."""
    (tmp_path / ".claude-plugin").mkdir()
    plugin = tmp_path / ".claude-plugin" / "plugin.json"
    marketplace = tmp_path / ".claude-plugin" / "marketplace.json"
    plugin.write_text(json.dumps({"version": "1.0.0"}), encoding="utf-8")
    marketplace.write_text(json.dumps({"version": "1.0.0"}), encoding="utf-8")
    skills = tmp_path / "skills"
    skill = skills / "demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: demo\nversion: 1.0.0\n---\n", encoding="utf-8")

    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@t.com")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "initial")

    # Point the module's path constants at the temp repo.
    monkeypatch.setattr(bv, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(bv, "PLUGIN_JSON", plugin)
    monkeypatch.setattr(bv, "MARKETPLACE_JSON", marketplace)
    monkeypatch.setattr(bv, "SKILLS_DIR", skills)
    return tmp_path


def test_tag_points_at_commit_containing_bump(repo):
    # Simulate what main() does before tagging: write the new version on disk
    # (uncommitted), exactly as update_* helpers would.
    plugin = repo / ".claude-plugin" / "plugin.json"
    plugin.write_text(json.dumps({"version": "1.1.0"}), encoding="utf-8")

    bv.create_git_tag("1.1.0")

    # The tag must resolve and its tree must contain the NEW version.
    tagged = subprocess.run(
        ["git", "-C", str(repo), "show", "v1.1.0:.claude-plugin/plugin.json"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert json.loads(tagged)["version"] == "1.1.0"

    # And no bump should be left uncommitted.
    porcelain = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert porcelain == "", f"bump left uncommitted: {porcelain!r}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
