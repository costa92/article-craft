#!/usr/bin/env python3
"""
lint_article.py — lightweight auto-fix for mechanical article style issues.

Focus:
- Remove roadmap filler such as "本文将..." / "接下来我们将..."
- Remove empty judgement wrappers such as "可以看到，" / "本质上，"
- Strip repetitive paragraph starters such as "首先，" / "其次，" / "另外，"
- Replace high-confidence red-flag words such as "赋能" / "一站式" / "链路"
- Split overlong hook paragraphs into two shorter paragraphs
- Remove engagement-style forbidden closings
- Delete standalone trailing reference sections

This script is intentionally conservative:
- Never edits code blocks
- Never edits HTML comment placeholders
- Never edits Markdown headings or image/link syntax lines
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Set, Tuple

from scripts.config import (
    TONE_REGISTER_LEVELS,
    TONE_LEXICAL_REWRITES,
    get_rewrites_for_tone,
    parse_tone_regions,
    resolve_tone,
)

# ---------------------------------------------------------------------------
# Test seam: tests inject synthetic rewrites via _set_test_rewrites_hook()
# ---------------------------------------------------------------------------
_TEST_REWRITES_HOOK = None  # callable(tone) -> list of (pattern, repl, severity, rule_id)


def _set_test_rewrites_hook(hook):
    """Test seam: when set, replaces get_rewrites_for_tone in auto_fix_text.

    Tests pass either a callable taking *tone* or ``None`` to clear.
    """
    global _TEST_REWRITES_HOOK
    _TEST_REWRITES_HOOK = hook


class FixReport:
    """Result object returned by :func:`auto_fix`.

    Attributes:
        passes: Number of fix passes applied (always 1 for now).
        warnings: Structural warnings, e.g. unmatched lint:disable markers.
        status: Summary status string ("clean").
    """

    def __init__(
        self,
        passes: int = 1,
        warnings: Optional[List[str]] = None,
        status: str = "clean",
    ) -> None:
        self.passes = passes
        self.warnings: List[str] = warnings if warnings is not None else []
        self.status = status

    def __repr__(self) -> str:  # pragma: no cover
        return f"FixReport(passes={self.passes!r}, warnings={self.warnings!r}, status={self.status!r})"


SEVERITY_RANK = {"info": 0, "warning": 1, "error": 2}

# ─── Inline lint:disable / lint:enable region parser ─────────────────────────
DISABLE_PATTERN = re.compile(r"<!--\s*lint:disable\s+([^\-]+?)\s*-->")
ENABLE_PATTERN = re.compile(r"<!--\s*lint:enable\s+([^\-]+?)\s*-->")


def _has_unmatched_disable_at_eof(text: str) -> bool:
    """Return True if <!-- lint:disable --> markers exceed <!-- lint:enable --> markers."""
    disable_count = len(DISABLE_PATTERN.findall(text))
    enable_count = len(ENABLE_PATTERN.findall(text))
    return disable_count > enable_count

ROADMAP_LINE_PATTERNS = [
    re.compile(r"^\s*本文将(?:从.+)?(?:展开|介绍|说明|拆解|讲清楚)[。；;!！]?\s*$"),
    re.compile(r"^\s*接下来我们将(?:逐一)?(?:来看|介绍|展开)[。；;!！]?\s*$"),
    re.compile(r"^\s*下面(?:分别)?(?:来看|介绍|展开)[。；;!！]?\s*$"),
]

OPENING_FILLERS = [
    (re.compile(r"^\s*可以看到[，,:： ]*"), ""),
    (re.compile(r"^\s*本质上[，,:： ]*"), ""),
    (re.compile(r"^\s*从这个角度看[，,:： ]*"), ""),
    (re.compile(r"^\s*某种意义上[，,:： ]*"), ""),
    (re.compile(r"^\s*回到问题本身[，,:： ]*"), ""),
]

PARAGRAPH_STARTERS = [
    re.compile(r"^\s*首先[，,:： ]*"),
    re.compile(r"^\s*其次[，,:： ]*"),
    re.compile(r"^\s*最后[，,:： ]*"),
    re.compile(r"^\s*另外[，,:： ]*"),
    re.compile(r"^\s*此外[，,:： ]*"),
    re.compile(r"^\s*同时[，,:： ]*"),
]

FORBIDDEN_CLOSING_PATTERNS = [
    re.compile(r"希望本文对你有帮助"),
    re.compile(r"如果有问题欢迎留言"),
    re.compile(r"欢迎在评论区分享"),
    re.compile(r"点个在看"),
    re.compile(r"转发给朋友"),
    re.compile(r"你的点赞是我最大的动力"),
    re.compile(r"如果这篇文章对你有帮助"),
]

REFERENCE_SECTION_HEADING = re.compile(r"^##\s*(参考资料|参考链接|References|参考文献)\s*$", re.IGNORECASE)
HOOK_MAX_CHARS = 100
TRANSITION_OPENERS = re.compile(r'^(此外|另外|同时|值得注意的是|除此之外)')
SEQUENCE_OPENERS = re.compile(r'^(首先|其次|最后|先说结论|回到问题本身)')
SUMMARY_TONE_PHRASES = [
    r'可以看到',
    r'本质上',
    r'从这个角度看',
    r'某种意义上',
    r'回到问题本身',
    r'核心问题在于',
    r'更重要的是',
    r'说到底',
    r'归根结底',
    r'关键在于',
    r'问题不在于',
    r'真正的问题是',
]


def _protected_line(stripped: str) -> bool:
    return (
        not stripped
        or stripped.startswith("```")
        or stripped.startswith("<!--")
        or stripped.startswith("#")
        or stripped.startswith(">")
        or stripped.startswith("![")
        or stripped.startswith("|")
    )


def _count_chinese(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def _is_content_paragraph(lines: list[str]) -> bool:
    if not lines:
        return False
    first = lines[0].strip()
    return not (
        not first
        or first.startswith("#")
        or first.startswith(">")
        or first.startswith("![")
        or first.startswith("<!--")
        or first.startswith("|")
        or first.startswith("```")
        or first.startswith("---")
    )


def _split_overlong_hook(text: str) -> tuple[str, bool]:
    chunks = text.split("\n\n")
    for i, chunk in enumerate(chunks):
        para_lines = [line for line in chunk.splitlines() if line.strip()]
        if not _is_content_paragraph(para_lines):
            continue
        para = "\n".join(para_lines).strip()
        if _count_chinese(para) <= HOOK_MAX_CHARS:
            return text, False

        split_match = re.search(r"[。！？]\s*", para)
        if split_match:
            cut = split_match.end()
        else:
            cut = len(para) // 2

        first = para[:cut].strip()
        second = para[cut:].strip()
        if not second:
            return text, False
        chunks[i] = first + "\n\n" + second
        return "\n\n".join(chunks), True
    return text, False


def _replace_forbidden_closing(line: str) -> tuple[str, int]:
    fixed = line
    removed = 0
    for pattern in FORBIDDEN_CLOSING_PATTERNS:
        updated, n = pattern.subn("", fixed)
        if n:
            fixed = updated
            removed += n
    if removed == 0:
        return line, 0

    fixed = re.sub(r"[，,、；;。！？!\? ]+$", "", fixed).strip()
    if fixed:
        fixed = fixed + "。"
    else:
        fixed = "下一步，先把文中的命令跑一遍，再根据输出结果决定是否继续扩展。"
    return fixed, removed


def _get_body(text: str) -> str:
    match = re.match(r'^---\n.*?\n---(\n|$)', text, re.DOTALL)
    if not match:
        return text
    return text[match.end():]


def _parse_frontmatter_simple(text: str) -> dict[str, str]:
    """Extract key: value pairs from a YAML-style frontmatter block.

    Only handles simple scalar string values — no YAML library dependency.
    Returns an empty dict if there is no frontmatter or the block is malformed.
    """
    match = re.match(r'^---\n(.*?)\n---(?:\n|$)', text, re.DOTALL)
    if not match:
        return {}
    result: dict[str, str] = {}
    for line in match.group(1).splitlines():
        kv = re.match(r'^([A-Za-z0-9_]+)\s*:\s*(.*)', line)
        if kv:
            result[kv.group(1).strip()] = kv.group(2).strip()
    return result


def _strip_code_blocks(text: str) -> str:
    return re.sub(r'```.*?```', '', text, flags=re.DOTALL)


def _get_paragraphs(text: str) -> list[str]:
    stripped = _strip_code_blocks(text)
    return [p.strip() for p in stripped.split('\n\n') if p.strip() and len(p.strip()) > 5]


def _get_sections(body: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_heading = ""
    current_content: list[str] = []
    for line in body.split('\n'):
        if line.startswith('## '):
            if current_heading or current_content:
                sections.append((current_heading, '\n'.join(current_content)))
            current_heading = line
            current_content = []
        else:
            current_content.append(line)
    if current_heading or current_content:
        sections.append((current_heading, '\n'.join(current_content)))
    return sections


def _split_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    in_code = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            current.append(line)
            continue
        if not in_code and not stripped:
            if current:
                blocks.append("\n".join(current).strip())
                current = []
            continue
        current.append(line)
    if current:
        blocks.append("\n".join(current).strip())
    return [block for block in blocks if block]


def _section_label(heading: str) -> str:
    heading = heading.strip()
    if not heading:
        return "导言 / 未命名段落"
    return heading.lstrip("#").strip()


def _has_concrete_anchor(paragraph: str) -> bool:
    return (
        re.search(r'`[^`]+`', paragraph) is not None or
        re.search(r'\b(v?\d+(?:\.\d+){1,3})\b', paragraph) is not None or
        re.search(r'(/[A-Za-z0-9_.-]+){2,}', paragraph) is not None or
        re.search(r'(报错|错误|error|exception|warning|404|500|ms|MB|GB|%)', paragraph, re.IGNORECASE) is not None
    )


def _is_summary_tone_paragraph(paragraph: str) -> bool:
    return any(re.search(pattern, paragraph) for pattern in SUMMARY_TONE_PHRASES)


def _is_structural_anchor_block(block: str) -> bool:
    stripped = block.strip()
    lines = stripped.splitlines()
    first = lines[0].strip() if lines else ""
    return (
        stripped.startswith("```")
        or first.startswith("![")
        or first.startswith("|")
        or first.startswith(">")
        or first.startswith("<!--")
    )


def analyze_high_risk_sections(text: str) -> list[str]:
    body = _get_body(text)
    sections = _get_sections(body)
    findings: list[str] = []

    for heading, section_content in sections:
        blocks = _split_blocks(section_content)
        if not blocks:
            continue
        label = _section_label(heading)
        run: list[str] = []
        for block in blocks + ["```reset```"]:
            if _is_structural_anchor_block(block):
                if len(run) >= 3:
                    anchors = [_has_concrete_anchor(p) for p in run]
                    for idx in range(max(0, len(run) - 2)):
                        window = anchors[idx:idx + 3]
                        if len(window) == 3 and not any(window):
                            findings.append(f"{label}: 连续 3 段缺少具体锚点")
                            break

                if len(run) >= 2:
                    anchors = [_has_concrete_anchor(p) for p in run]
                    summaries = [_is_summary_tone_paragraph(p) for p in run]
                    for idx in range(max(0, len(run) - 1)):
                        if len(summaries[idx:idx + 2]) == 2 and all(summaries[idx:idx + 2]) and not any(anchors[idx:idx + 2]):
                            findings.append(f"{label}: 连续 2 段总结腔且缺少锚点")
                            break

                    prev_opener = None
                    for p in run:
                        first_line = p.split('\n')[0]
                        opener = None
                        if TRANSITION_OPENERS.match(first_line):
                            opener = "transition"
                        elif SEQUENCE_OPENERS.match(first_line):
                            opener = "sequence"
                        if opener and prev_opener == opener:
                            findings.append(f"{label}: 连续段落使用同类段首节奏")
                            break
                        prev_opener = opener

                run = []
                continue

            run.append(block)

    return findings


def _fix_line(
    line: str,
    rewrites: list | None = None,
    disabled: frozenset | None = None,
) -> tuple[str, list[str]]:
    stripped = line.strip()
    if _protected_line(stripped):
        return line, []

    changes: list[str] = []
    fixed = line
    if disabled is None:
        disabled = frozenset()

    for pattern in ROADMAP_LINE_PATTERNS:
        if pattern.match(fixed):
            return "", ["removed_roadmap_line"]

    # Tone-tier rewrites run FIRST so higher-tier replacements (e.g. casual
    # "可以看到 → 能看出") are applied before the legacy OPENING_FILLERS
    # constant would delete the same phrase outright.
    if rewrites is None:
        rewrites = []
    for pattern, repl, rule_id in rewrites:
        if "all" in disabled or rule_id in disabled:
            continue
        updated, n = pattern.subn(repl, fixed)
        if n:
            fixed = updated
            changes.append("rewrote_red_flag")

    for pattern, repl in OPENING_FILLERS:
        updated, n = pattern.subn(repl, fixed, count=1)
        if n:
            fixed = updated
            changes.append("removed_empty_judgement")

    for pattern in PARAGRAPH_STARTERS:
        updated, n = pattern.subn("", fixed, count=1)
        if n:
            fixed = updated
            changes.append("removed_paragraph_starter")
            break

    fixed, removed = _replace_forbidden_closing(fixed)
    if removed:
        changes.append("removed_forbidden_closing")
        changes.append("added_concrete_closing")

    if fixed.strip() in {"。", "！", "?", "？"}:
        fixed = ""

    return fixed, changes


def _build_line_disabled_sets(text: str) -> list[frozenset]:
    """For each line in *text*, compute the set of disabled rule_ids at that line.

    Lines that are part of (i.e. between) a <!-- lint:disable X --> and its
    matching <!-- lint:enable X --> carry X in their disabled set.  The marker
    lines themselves are HTML comments and are skipped by _protected_line, so
    they don't need special treatment here.
    """
    lines = text.splitlines()
    result: list[frozenset] = []
    active: set[str] = set()
    for line in lines:
        stripped = line.strip()
        # .search (not .match): a marker is honored anywhere on the line, so a
        # trailing inline `... <!-- lint:disable X -->` opens the region too —
        # matching what _has_unmatched_disable_at_eof counts (findall).
        dm = DISABLE_PATTERN.search(stripped)
        em = ENABLE_PATTERN.search(stripped)
        if dm:
            rules = set(dm.group(1).split())
            active.update(rules)
            result.append(frozenset(active))
        elif em:
            rules = set(em.group(1).split())
            active.difference_update(rules)
            result.append(frozenset(active))
        else:
            result.append(frozenset(active))
    return result


def _atomic_write(path: Path, data: str) -> None:
    """Write *data* to *path* atomically (temp file in the same dir + os.replace),
    so an interrupted write never leaves the author's article half-truncated.
    Mirrors pipeline_state._atomic_write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".lint.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def auto_fix_text(
    text: str,
    tone: Optional[str] = None,
    min_severity: str = "warning",
    apply_info: bool = False,
    test_rewrites_hook=None,
) -> tuple[str, dict[str, int], list[str]]:
    """Apply all mechanical style fixes to *text*.

    *tone* selects the lexical-rewrite tier (neutral / casual / opinionated).
    When None, the function uses the neutral tier.

    *min_severity* sets the minimum severity rank required for a rewrite to be
    applied.  Accepted values: ``"info"``, ``"warning"`` (default), ``"error"``.
    *apply_info* is a convenience flag: when True it overrides *min_severity*
    and sets the effective threshold to ``"info"``, ensuring all rewrites run.

    *test_rewrites_hook* is a test seam: when not None it must be a callable
    ``hook(tone) -> list`` that returns 4-tuples ``(pattern, repl, severity,
    rule_id)`` and completely replaces ``get_rewrites_for_tone``.

    Returns ``(fixed_text, stats, warnings)`` where *warnings* is a list of
    strings describing any structural problems found (e.g. unmatched
    lint:disable markers).
    """
    resolved = tone if tone in TONE_REGISTER_LEVELS else "neutral"
    # Rank-based filter: apply_info widens the gate to include info-severity entries.
    effective_min = "info" if apply_info else min_severity
    threshold_rank = SEVERITY_RANK[effective_min]

    def _build_rewrites_for(t: str) -> list:
        raw = test_rewrites_hook(t) if test_rewrites_hook is not None else get_rewrites_for_tone(t)
        # 4-tuple entries: (pattern, repl, severity, rule_id) — keep rule_id for disable check.
        return [
            (pattern, repl, rule_id)
            for (pattern, repl, sev, rule_id) in raw
            if SEVERITY_RANK[sev] >= threshold_rank
        ]

    # B10: per-section tone via <!-- tone:X --> ... <!-- /tone --> regions.
    # Build a rewrite table for every tier upfront, then resolve per-line.
    # When no override markers appear, every line resolves to ``resolved``
    # and behavior is identical to the pre-B10 single-tone flow.
    rewrites_by_tone: dict[str, list] = {t: _build_rewrites_for(t) for t in TONE_REGISTER_LEVELS}
    rewrites = rewrites_by_tone[resolved]  # kept for legacy callers / fallback

    tone_spans = parse_tone_regions(text, resolved)
    line_tone: dict[int, str] = {}
    for start, end, t in tone_spans:
        for i in range(start, end):
            line_tone[i] = t

    # Build per-line disabled-rule sets from inline lint:disable/enable markers.
    line_disabled = _build_line_disabled_sets(text)

    # Collect structural warnings.
    fix_warnings: list[str] = []
    if _has_unmatched_disable_at_eof(text):
        fix_warnings.append("unmatched <!-- lint:disable --> at end of file")
    if ENABLE_PATTERN.findall(text) and not DISABLE_PATTERN.findall(text):
        fix_warnings.append("unmatched <!-- lint:enable --> tag (no preceding disable)")

    lines = text.splitlines()
    out: list[str] = []
    stats = {
        "removed_roadmap_line": 0,
        "removed_empty_judgement": 0,
        "removed_paragraph_starter": 0,
        "rewrote_red_flag": 0,
        "removed_forbidden_closing": 0,
        "added_concrete_closing": 0,
        "split_hook_paragraph": 0,
        "removed_reference_section": 0,
    }

    in_code = False
    skip_reference_section = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            out.append(line)
            continue

        if in_code:
            out.append(line)
            continue

        if REFERENCE_SECTION_HEADING.match(stripped):
            skip_reference_section = True
            stats["removed_reference_section"] += 1
            continue

        if skip_reference_section:
            if idx == len(lines) - 1:
                continue
            if stripped.startswith("## "):
                skip_reference_section = False
            else:
                continue

        disabled = line_disabled[idx] if idx < len(line_disabled) else frozenset()
        # Use per-line tone resolution (falls back to article tone outside regions).
        effective_rewrites = rewrites_by_tone.get(line_tone.get(idx, resolved), rewrites)
        fixed, changes = _fix_line(line, effective_rewrites, disabled)
        for change in changes:
            stats[change] += 1
        out.append(fixed)

    fixed_text = "\n".join(out)
    fixed_text = re.sub(r"\n{3,}", "\n\n", fixed_text).rstrip() + "\n"
    fixed_text, hook_split = _split_overlong_hook(fixed_text)
    if hook_split:
        stats["split_hook_paragraph"] += 1
    return fixed_text, stats, fix_warnings


def auto_fix(
    article_path: Path,
    tone: Optional[str] = None,
    min_severity: str = "warning",
    apply_info: bool = False,
    max_passes: int = 3,
) -> FixReport:
    """Public entry point: read *article_path*, apply fixes in-place, return FixReport.

    *tone* precedence: explicit argument > frontmatter ``tone:`` field >
    frontmatter ``writing_style:`` default > "neutral".

    *min_severity* / *apply_info* are forwarded to :func:`auto_fix_text`
    unchanged; see that function's docstring for semantics.

    *max_passes* caps the number of fix iterations.  The function iterates
    until the text stabilises (``status="clean"``), oscillation is detected
    (same ``(before, after)`` pair repeated — ``status="oscillating"``), or the
    cap is hit (``status="incomplete"``).
    """
    text = article_path.read_text(encoding="utf-8")
    fm = _parse_frontmatter_simple(text)
    resolved = resolve_tone(
        cli_tone=tone,
        frontmatter_tone=fm.get("tone"),
        writing_style=fm.get("writing_style"),
    )

    # Use the module-level test hook if set.
    hook = _TEST_REWRITES_HOOK
    all_warnings: List[str] = []
    seen_signatures: set = set()
    dirty = False  # has any pass actually mutated the article?

    for pass_num in range(1, max_passes + 1):
        fixed, _stats, pass_warnings = auto_fix_text(
            text,
            tone=resolved,
            min_severity=min_severity,
            apply_info=apply_info,
            test_rewrites_hook=hook,
        )
        all_warnings.extend(pass_warnings)

        if fixed == text:
            # Text did not change this pass — fully converged. Only write if a
            # prior pass mutated the article; a clean no-op lint must not
            # truncate-rewrite the file (and risk corruption) for zero benefit.
            if dirty:
                _atomic_write(article_path, text)
            return FixReport(passes=pass_num - 1, warnings=all_warnings, status="clean")

        # Oscillation detection: if this exact (before, after) pair has been
        # seen in any previous pass, we are cycling with no net progress.
        sig = (text, fixed)
        if sig in seen_signatures:
            _atomic_write(article_path, fixed)
            return FixReport(passes=pass_num, warnings=all_warnings, status="oscillating")
        seen_signatures.add(sig)
        text = fixed
        dirty = True

    # Exhausted max_passes without converging.
    _atomic_write(article_path, text)
    return FixReport(passes=max_passes, warnings=all_warnings, status="incomplete")


def build_change_summary(stats: dict[str, int]) -> list[str]:
    labels = [
        ("removed_roadmap_line", "Removed roadmap filler lines"),
        ("removed_empty_judgement", "Removed empty judgement wrappers"),
        ("removed_paragraph_starter", "Removed mechanical paragraph starters"),
        ("rewrote_red_flag", "Rewrote red-flag words"),
        ("removed_forbidden_closing", "Removed forbidden closings"),
        ("added_concrete_closing", "Added concrete fallback closings"),
        ("split_hook_paragraph", "Split overlong hook paragraphs"),
        ("removed_reference_section", "Removed standalone reference sections"),
    ]
    summary: list[str] = []
    for key, label in labels:
        count = stats.get(key, 0)
        if count:
            summary.append(f"- {label}: {count}")
    return summary


def build_report(original: str, fixed: str, stats: dict[str, int], risk_findings: list[str] | None = None) -> str:
    changed = original != fixed
    lines = [
        "## Lint Auto-Fix",
        "",
        f"- changed: {'yes' if changed else 'no'}",
        f"- roadmap lines removed: {stats['removed_roadmap_line']}",
        f"- empty judgement wrappers removed: {stats['removed_empty_judgement']}",
        f"- paragraph starters removed: {stats['removed_paragraph_starter']}",
        f"- red-flag rewrites: {stats['rewrote_red_flag']}",
        f"- forbidden closings removed: {stats['removed_forbidden_closing']}",
        f"- concrete closings added: {stats['added_concrete_closing']}",
        f"- hook paragraphs split: {stats['split_hook_paragraph']}",
        f"- reference sections removed: {stats['removed_reference_section']}",
    ]
    summary = build_change_summary(stats)
    if summary:
        lines.extend(["", "### Changes by Category", ""])
        lines.extend(summary)
    if risk_findings:
        lines.extend(["", "### High-Risk Sections", ""])
        lines.extend(f"- {item}" for item in risk_findings)
    return "\n".join(lines)


def scan_only(
    article_path: Path,
    tone: Optional[str] = None,
    min_severity: str = "warning",
) -> FixReport:
    """Scan *article_path* for violations and return a FixReport without writing the file.

    Mirrors :func:`auto_fix` but performs a single dry-run pass on an in-memory
    copy of the text — the file on disk is never touched.
    """
    text = article_path.read_text(encoding="utf-8")
    fm = _parse_frontmatter_simple(text)
    resolved = resolve_tone(
        cli_tone=tone,
        frontmatter_tone=fm.get("tone"),
        writing_style=fm.get("writing_style"),
    )
    hook = _TEST_REWRITES_HOOK
    _fixed, _stats, pass_warnings = auto_fix_text(
        text,
        tone=resolved,
        min_severity=min_severity,
        apply_info=(min_severity == "info"),
        test_rewrites_hook=hook,
    )
    status = "clean" if _fixed == text else "has_violations"
    return FixReport(passes=0, warnings=pass_warnings, status=status)


def _format_report(report: FixReport) -> str:
    """Return a human-readable summary of a :class:`FixReport`."""
    lines = [f"status: {report.status}", f"passes: {report.passes}"]
    if report.warnings:
        lines.append("warnings:")
        for w in report.warnings:
            lines.append(f"  - {w}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="article-craft lint with tone awareness")
    p.add_argument("--article", required=True, type=Path)
    p.add_argument(
        "--tone",
        choices=list(TONE_REGISTER_LEVELS),
        default=None,
        help="Override tone (else read from frontmatter or style default)",
    )
    p.add_argument("--fix", action="store_true",
                   help="Apply replacements (default: report-only)")
    p.add_argument("--apply-info", action="store_true",
                   help="Also apply info-severity fixes (default: warning+ only)")
    p.add_argument(
        "--min-severity",
        choices=list(SEVERITY_RANK.keys()),
        default="warning",
        help="Filter reported violations below this severity",
    )
    p.add_argument("--max-passes", type=int, default=3,
                   help="Oscillation guard upper bound")
    p.add_argument("--report-only", action="store_true",
                   help="Run scan without modifying the file")
    args = p.parse_args(argv)

    article = args.article.resolve()
    if not article.exists():
        sys.stderr.write(f"error: article not found: {article}\n")
        return 2

    if args.fix:
        report = auto_fix(
            article,
            tone=args.tone,
            min_severity=args.min_severity,
            apply_info=args.apply_info,
            max_passes=args.max_passes,
        )
        print(_format_report(report))
        if report.status == "oscillating":
            return 2
        if report.status == "incomplete":
            return 1
        return 0
    else:
        # Report-only mode: scan but don't write the file.
        report = scan_only(
            article,
            tone=args.tone,
            min_severity="info" if args.report_only else args.min_severity,
        )
        print(_format_report(report))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
