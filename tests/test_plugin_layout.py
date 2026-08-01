"""Plugin layout smoke tests (B6).

This file is the regression net for the v1.6.2 / v1.6.3 / v1.3.4 class
of bugs — issues that don't break individual scripts but break the
plugin's *layout contract* (command files in wrong place, frontmatter
versions out of lockstep, referenced scripts missing).

Every PR runs `pytest tests/test_plugin_layout.py` via
`.github/workflows/smoke.yml`. The test failures are deliberately
written to point at the fix, not just the symptom.
"""

import json
import re
from pathlib import Path

import pytest
import yaml


REPO = Path(__file__).resolve().parents[1]
COMMANDS_DIR = REPO / "commands"
SKILLS_DIR = REPO / "skills"
PLUGIN_JSON = REPO / ".claude-plugin" / "plugin.json"

# Commands without a backing skill — non-skill wrappers (doctor, upgrade,
# the orchestrator). New additions should be reviewed.
NON_SKILL_COMMANDS = {"doctor", "upgrade", "article-craft"}


def _read_frontmatter(md_path: Path) -> dict:
    """Parse YAML frontmatter from a markdown file. Returns {} if absent."""
    text = md_path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    return yaml.safe_load(m.group(1)) or {}


# --- Layout invariants ---


def test_no_commands_nested_under_article_craft_subdir():
    """v1.6.3 lesson: sub-command files at `commands/article-craft/<name>.md`
    register as `/article-craft:article-craft:<name>` (doubled prefix),
    not `/article-craft:<name>`. Every command must be at the top level
    of `commands/`.
    """
    nested_dir = COMMANDS_DIR / "article-craft"
    if not nested_dir.exists():
        return  # clean — directory shouldn't exist post-v1.6.3
    leftover = list(nested_dir.rglob("*.md"))
    assert not leftover, (
        f"Found {len(leftover)} command file(s) under commands/article-craft/ — "
        f"these resolve as the doubled /article-craft:article-craft:<name>. "
        f"Move to commands/<name>.md so they resolve as single-prefix "
        f"/article-craft:<name>. Files: {[str(p.relative_to(REPO)) for p in leftover]}"
    )


def test_every_skill_has_matching_command():
    """1:1 invariant — every skill (except orchestrator, which has its
    own top-level command file `commands/article-craft.md`) must have a
    matching `commands/<name>.md` so users can invoke it standalone
    via `/article-craft:<name>`.
    """
    skill_names = {
        d.name for d in SKILLS_DIR.iterdir()
        if d.is_dir() and d.name != "orchestrator"
    }
    command_stems = {p.stem for p in COMMANDS_DIR.glob("*.md")}
    missing = skill_names - command_stems
    assert not missing, (
        f"Skills without matching command file: {sorted(missing)}. "
        f"Create commands/<name>.md (top-level) for each."
    )


def test_every_command_either_wraps_a_skill_or_is_in_allowlist():
    """The mirror of the previous test — every command file is either
    backed by a skill OR an explicitly allowed non-skill wrapper
    (doctor.md wraps doctor.py; upgrade.md wraps an orchestrator mode;
    article-craft.md is the orchestrator entry point).

    Adding a new non-skill command requires explicit allowlisting here
    so it goes through code review.
    """
    skill_names = {d.name for d in SKILLS_DIR.iterdir() if d.is_dir()}
    skill_names = {n if n != "orchestrator" else "article-craft" for n in skill_names}
    orphans = []
    for cmd in COMMANDS_DIR.glob("*.md"):
        if cmd.stem in skill_names or cmd.stem in NON_SKILL_COMMANDS:
            continue
        orphans.append(cmd.stem)
    assert not orphans, (
        f"Command files with no matching skill and not in NON_SKILL_COMMANDS "
        f"allowlist: {orphans}. Either create the skill or add to the "
        f"allowlist in tests/test_plugin_layout.py."
    )


# --- Frontmatter invariants ---


def test_all_command_files_have_description_frontmatter():
    for cmd in COMMANDS_DIR.rglob("*.md"):
        fm = _read_frontmatter(cmd)
        assert fm.get("description"), (
            f"{cmd.relative_to(REPO)}: missing or empty `description:` "
            f"frontmatter field (required for Claude Code to display "
            f"the command's purpose)."
        )


def test_all_skill_files_have_required_frontmatter():
    """Per CLAUDE.md convention every skill SKILL.md must declare these
    four fields. All 14 non-orchestrator skills + orchestrator must comply.
    """
    required = {"name", "version", "description", "allowed-tools"}
    for skill in SKILLS_DIR.glob("*/SKILL.md"):
        fm = _read_frontmatter(skill)
        missing = required - set(fm.keys())
        assert not missing, (
            f"{skill.relative_to(REPO)}: missing required frontmatter fields "
            f"{sorted(missing)}."
        )


def test_skill_name_matches_directory():
    """`skills/X/SKILL.md` frontmatter `name:` must be `article-craft:X`
    (or `article-craft` for orchestrator)."""
    for skill in SKILLS_DIR.glob("*/SKILL.md"):
        fm = _read_frontmatter(skill)
        dirname = skill.parent.name
        expected = "article-craft" if dirname == "orchestrator" else f"article-craft:{dirname}"
        assert fm.get("name") == expected, (
            f"{skill.relative_to(REPO)}: name `{fm.get('name')}` != "
            f"expected `{expected}` (must match directory: skills/{dirname}/)"
        )


def test_all_skill_versions_match_plugin_json():
    """v1.3.4 lesson: plugin.json + marketplace.json + every SKILL.md
    version frontmatter must move in lockstep. `scripts/bump_version.py`
    enforces this on release; this test catches accidental drift in PRs.
    """
    plugin_v = json.loads(PLUGIN_JSON.read_text())["version"]
    mismatches = []
    for skill in SKILLS_DIR.glob("*/SKILL.md"):
        fm = _read_frontmatter(skill)
        if fm.get("version") != plugin_v:
            mismatches.append(f"{skill.relative_to(REPO)}: {fm.get('version')!r} != {plugin_v!r}")
    assert not mismatches, (
        "SKILL.md version frontmatter out of sync with plugin.json — "
        "run `python3 scripts/bump_version.py patch` (or major/minor/X.Y.Z) "
        "to fix.\n  " + "\n  ".join(mismatches)
    )


# --- Script-reference integrity ---


_SCRIPT_REF = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/scripts/([\w\-]+\.py)")


def test_referenced_scripts_actually_exist():
    """Every `${CLAUDE_PLUGIN_ROOT}/scripts/X.py` mentioned in skill or
    command markdown must resolve to a real file. Catches the case
    where a script gets renamed/removed but a SKILL.md still points at
    the old name.
    """
    missing = []
    md_files = (
        list(SKILLS_DIR.rglob("*.md"))
        + list(COMMANDS_DIR.rglob("*.md"))
        + [REPO / "CLAUDE.md", REPO / "INSTALL.md", REPO / "README.md"]
    )
    for md in md_files:
        if not md.exists():
            continue
        for m in _SCRIPT_REF.finditer(md.read_text(encoding="utf-8")):
            script_name = m.group(1)
            if not (REPO / "scripts" / script_name).exists():
                missing.append(f"{md.relative_to(REPO)}: references missing scripts/{script_name}")
    assert not missing, (
        "Markdown files reference scripts that don't exist:\n  "
        + "\n  ".join(missing)
    )


# --- plugin.json shape ---


def test_plugin_json_has_required_fields():
    data = json.loads(PLUGIN_JSON.read_text())
    for field in ("name", "version", "description"):
        assert field in data, f".claude-plugin/plugin.json missing `{field}`"
    # Version must be semver-shaped
    assert re.match(r"^\d+\.\d+\.\d+$", data["version"]), (
        f"plugin.json version `{data['version']}` is not X.Y.Z semver"
    )


def test_marketplace_json_agrees_with_plugin_json():
    """Already covered by test_bump_version.test_get_current_version_matches_marketplace,
    but pinned here too because this is the v1.3.4-class drift check that
    matters most on PR."""
    plugin = json.loads(PLUGIN_JSON.read_text())
    mp = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text())
    plugin_v = plugin["version"]
    mp_v = mp["plugins"][0]["version"]
    assert plugin_v == mp_v, (
        f"plugin.json={plugin_v} but marketplace.json plugins[0].version={mp_v}. "
        "Run `python3 scripts/bump_version.py <type>` to fix lockstep."
    )


# Literal PATH-python argv is allowed only in these files —
# content fixtures (verify_claims tool names) or TimeoutExpired mock cmd.
_PYTHON3_ARGV_ALLOWLIST = {
    "tests/test_verify_claims.py",
    "tests/test_doctor.py",
    "tests/py_exe.py",
}

# Matches subprocess argv lists that hardcode the PATH binary as first element.
_HARDCODED_PYTHON3_ARGV = re.compile(
    r"""\[\s*["']python3["']\s*,""",
    re.MULTILINE,
)
# Drop comments + triple-quoted strings so docs/examples in this file don't trip.
_CODE_NOISE = re.compile(
    r"('''.*?'''|\"\"\".*?\"\"\"|#.*?$)",
    re.DOTALL | re.MULTILINE,
)


def test_cli_tests_do_not_hardcode_path_python3():
    """v1.10.1: CLI subprocess tests must use sys.executable (via py_exe.PYTHON).

    Hardcoding PATH python3 as the first argv made the suite fail when that
    binary was a broken/incomplete Homebrew install while pytest itself ran
    under a healthy interpreter with deps. Skills still document python3;
    doctor probes PATH separately — tests must not depend on PATH quality.
    """
    offenders: list[str] = []
    for path in (REPO / "tests").glob("test_*.py"):
        rel = str(path.relative_to(REPO))
        if rel in _PYTHON3_ARGV_ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8")
        code_only = _CODE_NOISE.sub("", text)
        if _HARDCODED_PYTHON3_ARGV.search(code_only):
            offenders.append(rel)
    assert not offenders, (
        "CLI tests hardcode PATH python3 as subprocess argv — use "
        "`from py_exe import PYTHON` and [PYTHON, ...] instead "
        f"(see tests/py_exe.py). Offenders: {offenders}"
    )
