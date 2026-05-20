"""Tests for scripts/utils.py: PlaceholderManager + SmartDirectoryMatcher (B9).

SmartDirectoryMatcher is the publish-skill auto-placement engine —
silently picking the wrong KB folder is the kind of bug that wouldn't
surface for releases. PlaceholderManager backs image-prompt suggestion
history. Both classes had zero test coverage before this.
"""

import importlib.util
import sys
import tempfile
from pathlib import Path

import pytest


def _load():
    p = Path(__file__).resolve().parents[1] / "scripts" / "utils.py"
    if str(p.parent) not in sys.path:
        sys.path.insert(0, str(p.parent))
    spec = importlib.util.spec_from_file_location("utils_test_mod", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["utils_test_mod"] = mod
    spec.loader.exec_module(mod)
    return mod


utils = _load()


# --- SmartDirectoryMatcher ---


def _fresh_matcher(tmp_path: Path):
    """Build a matcher rooted in an isolated tmp dir so test runs don't
    pollute each other's `.article-gen-dir-rules.json`."""
    return utils.SmartDirectoryMatcher(kb_root=str(tmp_path))


def test_fresh_matcher_returns_none(tmp_path):
    """No rules learned → no match."""
    m = _fresh_matcher(tmp_path)
    assert m.match_directory("Some Random Article") is None


def test_keyword_rule_matches(tmp_path):
    m = _fresh_matcher(tmp_path)
    m.add_keyword_rule("docker", "02-技术/基础设施/Docker")
    assert m.match_directory("Docker 入门教程") == "02-技术/基础设施/Docker"


def test_keyword_rule_is_case_insensitive(tmp_path):
    m = _fresh_matcher(tmp_path)
    m.add_keyword_rule("DOCKER", "02-技术/基础设施/Docker")
    assert m.match_directory("docker compose 实战") == "02-技术/基础设施/Docker"


def test_pattern_rule_matches(tmp_path):
    m = _fresh_matcher(tmp_path)
    m.add_pattern_rule(r"Go\s+\d+\.\d+", "02-技术/基础设施/Go/版本特性")
    assert m.match_directory("Go 1.22 新特性") == "02-技术/基础设施/Go/版本特性"


def test_pattern_rule_invalid_regex_does_not_crash(tmp_path):
    """A user-supplied bad regex should be skipped, not raise."""
    m = _fresh_matcher(tmp_path)
    m.add_pattern_rule(r"[invalid", "02-技术/some")
    # No crash, no rule added → no match
    assert m.match_directory("anything") is None


def test_learn_feedback_then_match(tmp_path):
    """Confirmed feedback teaches keywords from the title."""
    m = _fresh_matcher(tmp_path)
    m.learn_feedback("Claude Code 高级用法", "02-技术/AI-生态/Claude-Code", is_correct=True)
    # The token 'claude' should now map to the directory.
    assert m.match_directory("Claude Code Skills 实战") == "02-技术/AI-生态/Claude-Code"


def test_history_persists_across_instances(tmp_path):
    """Rules survive matcher reconstruction (write to disk)."""
    m1 = _fresh_matcher(tmp_path)
    m1.add_keyword_rule("kubernetes", "02-技术/基础设施/K8s")
    m2 = _fresh_matcher(tmp_path)  # new instance, same kb_root
    assert m2.match_directory("Kubernetes Pod 调度") == "02-技术/基础设施/K8s"


def test_clear_rules_removes_everything(tmp_path):
    m = _fresh_matcher(tmp_path)
    m.add_keyword_rule("docker", "02-技术/基础设施/Docker")
    assert m.match_directory("Docker 教程") is not None
    m.clear_rules()
    assert m.match_directory("Docker 教程") is None


def test_get_rules_returns_copy(tmp_path):
    """Mutating the returned dict must not affect the matcher's state."""
    m = _fresh_matcher(tmp_path)
    m.add_keyword_rule("k8s", "02-技术/K8s")
    rules = m.get_rules()
    rules["keywords"].clear()
    # Internal state still has the rule
    assert m.match_directory("k8s tutorial") == "02-技术/K8s"


# --- PlaceholderManager ---


def test_placeholder_manager_construction():
    """Bare-bones — can we construct it and call basic methods."""
    pm = utils.PlaceholderManager()
    # No prompts learned yet → suggest returns None
    assert pm.suggest_prompt("cover") is None


def test_placeholder_manager_learn_and_suggest():
    pm = utils.PlaceholderManager()
    pm.learn_from_image("architecture", "技术架构图，蓝色调，扁平设计")
    # After learning, suggest_prompt for the same image_type should return something
    result = pm.suggest_prompt("architecture")
    assert result is not None
    assert "架构" in result or "扁平" in result


def test_placeholder_manager_recent_prompts_limit():
    pm = utils.PlaceholderManager()
    for i in range(10):
        pm.learn_from_image("cover", f"prompt v{i}")
    recent = pm.get_recent_prompts(limit=3)
    assert len(recent) <= 3


def test_placeholder_manager_clear_history():
    pm = utils.PlaceholderManager()
    pm.learn_from_image("cover", "test prompt")
    pm.clear_history()
    assert pm.suggest_prompt("cover") is None


# --- singletons ---


def test_get_directory_matcher_singleton(tmp_path):
    """Repeated calls return the same instance for the same kb_root."""
    # Reset singleton state for test isolation
    utils._directory_matcher = None
    a = utils.get_directory_matcher(kb_root=str(tmp_path))
    b = utils.get_directory_matcher(kb_root=str(tmp_path))
    assert a is b


def test_get_placeholder_manager_singleton():
    utils._placeholder_manager = None
    a = utils.get_placeholder_manager()
    b = utils.get_placeholder_manager()
    assert a is b
