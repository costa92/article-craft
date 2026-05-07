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
import re
import sys
from pathlib import Path


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

RED_FLAG_REWRITES = [
    (re.compile(r"赋能"), "支持"),
    (re.compile(r"一站式"), "集成的"),
    (re.compile(r"链路"), "调用路径"),
    (re.compile(r"综上所述[，,:： ]*"), ""),
    (re.compile(r"总而言之[，,:： ]*"), ""),
    (re.compile(r"值得注意的是[，,:： ]*"), ""),
    (re.compile(r"实际上[，,:： ]*"), ""),
    (re.compile(r"事实上[，,:： ]*"), ""),
    (re.compile(r"显然[，,:： ]*"), ""),
    (re.compile(r"众所周知[，,:： ]*"), ""),
    (re.compile(r"不难看出[，,:： ]*"), ""),
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


def _fix_line(line: str) -> tuple[str, list[str]]:
    stripped = line.strip()
    if _protected_line(stripped):
        return line, []

    changes: list[str] = []
    fixed = line

    for pattern in ROADMAP_LINE_PATTERNS:
        if pattern.match(fixed):
            return "", ["removed_roadmap_line"]

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

    for pattern, repl in RED_FLAG_REWRITES:
        updated, n = pattern.subn(repl, fixed)
        if n:
            fixed = updated
            changes.append("rewrote_red_flag")

    fixed, removed = _replace_forbidden_closing(fixed)
    if removed:
        changes.append("removed_forbidden_closing")
        changes.append("added_concrete_closing")

    if fixed.strip() in {"。", "！", "?", "？"}:
        fixed = ""

    return fixed, changes


def auto_fix_text(text: str) -> tuple[str, dict[str, int]]:
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

        fixed, changes = _fix_line(line)
        for change in changes:
            stats[change] += 1
        out.append(fixed)

    fixed_text = "\n".join(out)
    fixed_text = re.sub(r"\n{3,}", "\n\n", fixed_text).rstrip() + "\n"
    fixed_text, hook_split = _split_overlong_hook(fixed_text)
    if hook_split:
        stats["split_hook_paragraph"] += 1
    return fixed_text, stats


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Auto-fix mechanical AI-sounding article phrases")
    parser.add_argument("--article", required=True, help="Path to article.md")
    parser.add_argument("--fix", action="store_true", help="Write fixes back to file")
    parser.add_argument("--diff", action="store_true", help="Print unified diff")
    args = parser.parse_args(argv)

    article = Path(args.article).resolve()
    if not article.exists():
        sys.stderr.write(f"error: article not found: {article}\n")
        return 2

    original = article.read_text(encoding="utf-8")
    fixed, stats = auto_fix_text(original)
    risk_findings = analyze_high_risk_sections(fixed)

    print(build_report(original, fixed, stats, risk_findings))

    if args.diff and original != fixed:
        diff = difflib.unified_diff(
            original.splitlines(),
            fixed.splitlines(),
            fromfile=str(article),
            tofile=str(article),
            lineterm="",
        )
        print()
        print("\n".join(diff))

    if args.fix and original != fixed:
        article.write_text(fixed, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
