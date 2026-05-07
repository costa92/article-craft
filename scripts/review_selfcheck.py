#!/usr/bin/env python3
"""
Automated self-check for article review (15 rules).

Validates articles against the self-check rules defined in
references/self-check-rules.md. Can be used standalone or
called by the review skill.

Usage:
    python3 review_selfcheck.py /path/to/article.md          # Text report
    python3 review_selfcheck.py /path/to/article.md --json    # JSON output
    python3 review_selfcheck.py /path/to/article.md --gate-only  # Only Rule 11
"""

import re
import sys
import json
import os
import yaml
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Union
from dataclasses import dataclass, field, asdict
from scripts.config import TONE_THRESHOLDS, resolve_tone, STRONG_OPINION_PATTERNS

# ─── Rule Definitions ───────────────────────────────────────────────

RED_FLAG_WORDS = (
    r'无缝|赋能|一站式|综上所述|总而言之|值得注意的是|不难发现|'
    r'深度解析|全面梳理|链路|闭环|抓手|底层逻辑|方法论|降本增效|'
    r'实际上|事实上|显然|众所周知|不难看出'
)

RED_FLAG_PHRASES = [
    r'颠覆', r'极致', r'完美解决',
    r'在当今快速发展', r'随着.*的不断发展', r'让我们一起探索',
    r'效率提升\s*\d+%',
]

FORBIDDEN_CLOSINGS = [
    r'希望本文对你有帮助', r'如果有问题欢迎留言', r'欢迎在评论区分享',
    r'点个在看', r'转发给朋友', r'你的点赞是我最大的动力',
    r'如果这篇文章对你有帮助',
]

TRANSITION_WORDS = r'^(此外|另外|同时|值得注意的是|除此之外)'
SEQUENCE_OPENERS = r'^(首先|其次|最后|先说结论|回到问题本身)'
EMPTY_JUDGEMENT_PHRASES = [
    r'可以看到',
    r'本质上',
    r'从这个角度看',
    r'某种意义上',
    r'回到问题本身',
]
SUMMARY_TONE_PHRASES = [
    r'核心问题在于',
    r'更重要的是',
    r'说到底',
    r'归根结底',
    r'关键在于',
    r'问题不在于',
    r'真正的问题是',
]
ROADMAP_FILLER_PATTERNS = [
    r'本文将',
    r'接下来我们将',
    r'下面分别',
    r'下面我们',
]


# ─── Data Classes ────────────────────────────────────────────────

@dataclass
class Violation:
    line: int
    text: str
    suggestion: str = ""
    severity: str = "warning"


@dataclass
class CheckResult:
    rule_id: Union[int, str]
    rule_name: str
    passed: bool
    is_gate: bool = False
    violations: List[Violation] = field(default_factory=list)
    details: str = ""
    skipped: bool = False
    skip_reason: str = ""
    meta: Dict = field(default_factory=dict)


# ─── Helper Functions ────────────────────────────────────────────

def parse_frontmatter(content: str) -> Dict:
    """Extract YAML frontmatter using the yaml library (handles multi-line values)."""
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return {}
    try:
        fm = yaml.safe_load(match.group(1))
        return dict(fm) if fm else {}
    except yaml.YAMLError:
        return {}


def get_body(content: str) -> str:
    """Get content after frontmatter — finds closing --- at line start only."""
    match = re.match(r'^---\n.*?\n---(\n|$)', content, re.DOTALL)
    if not match:
        return content
    return content[match.end():]


def strip_code_blocks(text: str) -> str:
    """Remove code blocks from text."""
    return re.sub(r'```.*?```', '', text, flags=re.DOTALL)


def _strip_callout_blocks(text: str) -> str:
    """Remove Obsidian callout blocks (> [!type] ... \n> body) from text.

    Plain blockquotes (lines starting with `>` but no `[!type]` marker)
    are preserved. Implementation: greedy state machine that toggles "inside
    callout" when it sees `> [!...]` and exits on the first non-`>` line.
    """
    lines = text.split("\n")
    out: List[str] = []
    in_callout = False
    for line in lines:
        stripped = line.lstrip()
        if not in_callout:
            if stripped.startswith("> [!") and "]" in stripped:
                in_callout = True
                continue
            out.append(line)
        else:
            if stripped.startswith(">"):
                continue
            in_callout = False
            out.append(line)
    return "\n".join(out)


def _strip_image_lines(text: str) -> str:
    """Drop lines that are *only* a Markdown image (optionally with surrounding whitespace).

    Inline images embedded inside a paragraph are preserved.
    """
    image_only = re.compile(r"^\s*!\[[^\]]*\]\([^)]+\)\s*$")
    return "\n".join(line for line in text.split("\n") if not image_only.match(line))


def get_paragraphs(body: str) -> List[str]:
    """Split body into non-empty paragraphs (excluding code blocks)."""
    text = strip_code_blocks(body)
    return [p.strip() for p in text.split('\n\n') if p.strip() and len(p.strip()) > 5]


def count_chinese(text: str) -> int:
    """Count Chinese characters."""
    return len(re.findall(r'[\u4e00-\u9fff]', text))


def get_sections(body: str) -> List[Tuple[str, str]]:
    """Split body by ## headings. Returns [(heading, content), ...]."""
    sections = []
    current_heading = ""
    current_content = []
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


def _split_blocks(text: str) -> List[str]:
    blocks: List[str] = []
    current: List[str] = []
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


def _has_concrete_anchor(paragraph: str) -> bool:
    return (
        re.search(r'`[^`]+`', paragraph) is not None or
        re.search(r'\b(v?\d+(?:\.\d+){1,3})\b', paragraph) is not None or
        re.search(r'(/[A-Za-z0-9_.-]+){2,}', paragraph) is not None or
        re.search(r'(报错|错误|error|exception|warning|404|500|ms|MB|GB|%)', paragraph, re.IGNORECASE) is not None
    )


def _is_summary_tone_paragraph(paragraph: str) -> bool:
    return any(re.search(pattern, paragraph) for pattern in EMPTY_JUDGEMENT_PHRASES + SUMMARY_TONE_PHRASES)


def _section_label(heading: str) -> str:
    heading = heading.strip()
    if not heading:
        return "导言 / 未命名段落"
    return heading.lstrip("#").strip()


# ─── Rule Implementations ────────────────────────────────────────

def check_rule_1(content: str, lines: List[str]) -> CheckResult:
    """Red-Flag Words: scan for AI-sounding phrases."""
    violations = []
    body = get_body(content)
    body_lines = body.split('\n')

    for i, line in enumerate(body_lines):
        # Skip code blocks
        if line.strip().startswith('```'):
            continue
        # Check main red-flag words
        for m in re.finditer(RED_FLAG_WORDS, line):
            violations.append(Violation(
                line=i + 1, text=m.group(), suggestion=f"替换「{m.group()}」为更自然的表达"
            ))
        # Check red-flag phrases
        for pattern in RED_FLAG_PHRASES:
            for m in re.finditer(pattern, line):
                violations.append(Violation(
                    line=i + 1, text=m.group(), suggestion=f"改写含「{m.group()}」的句子"
                ))

    return CheckResult(
        rule_id=1, rule_name="红旗词汇",
        passed=len(violations) == 0, violations=violations,
        details=f"发现 {len(violations)} 个红旗词"
    )


def check_rule_2(content: str, lines: List[str]) -> CheckResult:
    """Hook Length: first paragraph must be ≤100 Chinese characters."""
    body = get_body(content)
    paragraphs = get_paragraphs(body)

    # Find first real paragraph (not heading, not callout, not image, not placeholder, not separator)
    hook = ""
    for p in paragraphs:
        first_line = p.split('\n')[0].strip()
        if (first_line.startswith('#') or first_line.startswith('>') or
            first_line.startswith('![') or first_line.startswith('<!--') or
            first_line.startswith('---') or first_line.startswith('|') or
            len(first_line) < 5):
            continue
        hook = first_line
        break

    char_count = count_chinese(hook)
    passed = char_count <= 100 and char_count > 0

    violations = []
    if char_count == 0:
        violations.append(Violation(
            line=0, text="未找到有效的 Hook 段落",
            suggestion="确保文章在标题/导航后有一个简短的开头段落"
        ))
    elif not passed:
        violations.append(Violation(
            line=0, text=hook[:80] + "...",
            suggestion=f"Hook 有 {char_count} 个中文字符，需缩减到 100 以内"
        ))

    return CheckResult(
        rule_id=2, rule_name="Hook 长度",
        passed=passed or char_count == 0, violations=violations,
        details=f"{char_count} 字（≤100）" if char_count > 0 else "未检测到（跳过）"
    )


def check_rule_3(content: str, lines: List[str]) -> CheckResult:
    """Closing Paragraph: must not use forbidden closings."""
    body = get_body(content)
    # Find last non-empty, non-callout paragraph
    body_lines = body.strip().split('\n')
    last_lines = []
    for line in reversed(body_lines):
        stripped = line.strip()
        if stripped and not stripped.startswith('>') and not stripped.startswith('---'):
            last_lines.insert(0, stripped)
            if len(last_lines) >= 3:
                break

    last_text = ' '.join(last_lines)
    violations = []
    for pattern in FORBIDDEN_CLOSINGS:
        if re.search(pattern, last_text):
            violations.append(Violation(
                line=len(lines), text=last_text[:60],
                suggestion=f"替换禁用结尾「{pattern}」为具体的下一步操作"
            ))

    return CheckResult(
        rule_id=3, rule_name="结尾禁用词",
        passed=len(violations) == 0, violations=violations,
        details="结尾符合要求" if not violations else f"发现 {len(violations)} 个禁用结尾"
    )


def check_rule_4(content: str, lines: List[str]) -> CheckResult:
    """Description Field: frontmatter must have description ≤120 chars."""
    fm = parse_frontmatter(content)
    desc = fm.get('description', '')

    violations = []
    if not desc:
        violations.append(Violation(
            line=1, text="frontmatter", suggestion="添加 description 字段（≤120 中文字符）"
        ))
    elif count_chinese(desc) > 120:
        violations.append(Violation(
            line=1, text=desc[:60] + "...",
            suggestion=f"Description 有 {count_chinese(desc)} 字，需缩减到 120 以内"
        ))

    return CheckResult(
        rule_id=4, rule_name="Description 字段",
        passed=len(violations) == 0, violations=violations,
        details=f"{count_chinese(desc)} 字" if desc else "缺失"
    )


def check_rule_5(content: str, lines: List[str]) -> CheckResult:
    """Anti-AI Structure: varied paragraphs + personal perspective."""
    body = get_body(content)
    paragraphs = get_paragraphs(body)
    violations = []

    prev_opener = None
    concrete_anchor_hits = 0
    empty_judgement_hits = 0
    roadmap_hits = 0
    anchor_flags: List[bool] = []
    summary_flags: List[bool] = []

    for i, p in enumerate(paragraphs):
        first_line = p.split('\n')[0]
        opener = None
        if re.match(TRANSITION_WORDS, first_line):
            opener = "transition"
        elif re.match(SEQUENCE_OPENERS, first_line):
            opener = "sequence"

        if opener:
            if prev_opener == opener:
                violations.append(Violation(
                    line=0, text=first_line[:50],
                    suggestion="连续两段使用同类段首节奏，改成直接切入内容或换结构"
                ))
            prev_opener = opener
        else:
            prev_opener = None

        if any(re.search(pattern, p) for pattern in ROADMAP_FILLER_PATTERNS):
            roadmap_hits += 1
        if any(re.search(pattern, p) for pattern in EMPTY_JUDGEMENT_PHRASES):
            empty_judgement_hits += 1
        has_anchor = _has_concrete_anchor(p)
        anchor_flags.append(has_anchor)
        summary_flags.append(_is_summary_tone_paragraph(p))
        if has_anchor:
            concrete_anchor_hits += 1

    # Check personal perspective count
    personal_markers = re.findall(
        r'我(?:在|曾|的|会|用|选|踩|测|最后|发现)|踩坑|实测|我的经验|生产环境中.*我',
        body
    )
    if len(personal_markers) < 2:
        violations.append(Violation(
            line=0, text=f"个人视角标记仅 {len(personal_markers)} 处",
            suggestion="增加至少 2 处第一人称经验分享（如踩坑、实测、选型理由）"
        ))

    if roadmap_hits >= 1:
        violations.append(Violation(
            line=0, text=f"模板化路线图语句 {roadmap_hits} 处",
            suggestion="删掉“本文将/接下来/下面分别”式路线图，直接进入问题、证据或结论"
        ))

    if empty_judgement_hits >= 2:
        violations.append(Violation(
            line=0, text=f"空泛判断句 {empty_judgement_hits} 处",
            suggestion="把“可以看到/本质上/从这个角度看”改成具体判断+证据"
        ))

    if concrete_anchor_hits < 2:
        violations.append(Violation(
            line=0, text=f"具体锚点仅 {concrete_anchor_hits} 处",
            suggestion="补 2 处以上具体锚点：数字、版本、命令、路径、报错或实测结果"
        ))

    sections = get_sections(body)
    for heading, section_content in sections:
        section_blocks = _split_blocks(section_content)
        if not section_blocks:
            continue
        label = _section_label(heading)
        run: List[str] = []
        for block in section_blocks + ["```reset```"]:
            if _is_structural_anchor_block(block):
                if len(run) >= 3:
                    anchors = [_has_concrete_anchor(p) for p in run]
                    for idx in range(max(0, len(run) - 2)):
                        window = anchors[idx:idx + 3]
                        if len(window) == 3 and not any(window):
                            preview = run[idx].split('\n')[0][:50]
                            violations.append(Violation(
                                line=0,
                                text=f"章节「{label}」连续 3 段缺少具体锚点，起始段：{preview}",
                                suggestion="每连续 3 段正文里至少放 1 段具体锚点：命令、数字、路径、报错或实测结果"
                            ))
                            break

                if len(run) >= 2:
                    anchors = [_has_concrete_anchor(p) for p in run]
                    summaries = [_is_summary_tone_paragraph(p) for p in run]
                    for idx in range(max(0, len(run) - 1)):
                        if (
                            len(summaries[idx:idx + 2]) == 2 and
                            all(summaries[idx:idx + 2]) and
                            not any(anchors[idx:idx + 2])
                        ):
                            preview = run[idx].split('\n')[0][:50]
                            violations.append(Violation(
                                line=0,
                                text=f"章节「{label}」连续 2 段总结腔且缺少锚点，起始段：{preview}",
                                suggestion="把相邻的总结/判断段改成‘判断 + 命令/数字/报错/反例’组合，不要连续两段纯解释"
                            ))
                            break
                run = []
                continue

            run.append(block)

    return CheckResult(
        rule_id=5, rule_name="反 AI 结构",
        passed=len(violations) == 0, violations=violations,
        details=(
            f"个人视角 {len(personal_markers)} 处，具体锚点 {concrete_anchor_hits} 处，"
            f"路线图语句 {roadmap_hits} 处，空泛判断句 {empty_judgement_hits} 处"
        )
    )


def check_rule_6(content: str, lines: List[str]) -> CheckResult:
    """Chapter Depth: each section needs ≥2 code blocks (intro/motivation chapters need ≥1)."""
    body = get_body(content)
    sections = get_sections(body)
    violations = []

    # Keywords indicating intro/motivation chapters that naturally have fewer code blocks
    intro_keywords = re.compile(r'为什么|挑战|争议|背景|动机|现实|痛点|局限|需要|缺什么|之后')

    for heading, section_content in sections:
        if (
            not heading or
            heading.startswith('## 导言') or
            heading.startswith('## 总结') or
            heading.startswith('## 写在最后') or
            heading.startswith('## 结语') or
            heading.startswith('## 结尾')
        ):
            continue
        code_blocks = re.findall(r'```', section_content)
        code_count = len(code_blocks) // 2

        # Intro/motivation chapters: threshold = 1; other chapters: threshold = 2
        threshold = 1 if intro_keywords.search(heading) else 2

        if code_count < threshold and len(section_content) > 200:
            violations.append(Violation(
                line=0, text=heading[:60],
                suggestion=f"章节「{heading.strip('# ')}」仅有 {code_count} 个代码块，建议补充到 {threshold} 个以上"
            ))

    return CheckResult(
        rule_id=6, rule_name="章节深度",
        passed=len(violations) == 0, violations=violations,
        details=f"{len(violations)} 个浅层章节"
    )


def check_rule_7(content: str, lines: List[str]) -> CheckResult:
    """Duplicate Images: no two images with same purpose in same section."""
    body = get_body(content)
    sections = get_sections(body)
    violations = []

    for heading, section_content in sections:
        images = re.findall(r'!\[(.*?)\]', section_content)
        seen = set()
        for alt in images:
            # Simple similarity: first 10 chars
            key = alt[:10].lower()
            if key in seen:
                violations.append(Violation(
                    line=0, text=f"{heading}: {alt}",
                    suggestion="同一章节中存在相似图片，考虑删除重复"
                ))
            seen.add(key)

    return CheckResult(
        rule_id=7, rule_name="重复图片",
        passed=len(violations) == 0, violations=violations,
        details=f"{len(violations)} 个重复"
    )


def check_rule_8(content: str, lines: List[str]) -> CheckResult:
    """External Links for WeChat: no bare URLs in body text."""
    body = get_body(content)
    # Remove code blocks first
    text = strip_code_blocks(body)
    # Remove markdown image links
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    # Remove markdown links (keep for later, these are OK)
    text = re.sub(r'\[.*?\]\(.*?\)', '', text)
    # Remove callout/blockquote lines that reference links
    text = re.sub(r'^>.*$', '', text, flags=re.MULTILINE)

    # Find bare URLs
    bare_urls = re.findall(r'https?://[^\s)<>]+', text)
    # Filter out CDN image URLs (these are in image tags, OK)
    bare_urls = [u for u in bare_urls if 'cdn.jsdelivr.net' not in u]

    violations = []
    for url in bare_urls:
        violations.append(Violation(
            line=0, text=url[:60],
            suggestion=f"将裸 URL 改为搜索指引：搜索「关键词」"
        ))

    return CheckResult(
        rule_id=8, rule_name="WeChat 外链",
        passed=len(violations) == 0, violations=violations,
        details=f"{len(violations)} 个裸 URL"
    )


def check_rule_9(content: str, lines: List[str]) -> CheckResult:
    """Mermaid Residue: no ```mermaid code blocks."""
    violations = []
    for i, line in enumerate(lines):
        if re.match(r'^\s*```mermaid', line):
            violations.append(Violation(
                line=i + 1, text=line.strip(),
                suggestion="将 Mermaid 代码块转为 <!-- IMAGE --> 占位符"
            ))

    return CheckResult(
        rule_id=9, rule_name="Mermaid 残留",
        passed=len(violations) == 0, violations=violations,
        details=f"{len(violations)} 个 Mermaid 块"
    )


def check_rule_10(content: str, lines: List[str]) -> CheckResult:
    """References Inline: no standalone reference section."""
    violations = []
    for i, line in enumerate(lines):
        if re.match(r'^##\s*(参考资料|参考链接|References|参考文献)', line):
            violations.append(Violation(
                line=i + 1, text=line.strip(),
                suggestion="删除独立参考部分，所有链接应在首次提及处内联"
            ))

    return CheckResult(
        rule_id=10, rule_name="参考资料内联",
        passed=len(violations) == 0, violations=violations,
        details="符合要求" if not violations else "发现独立参考部分"
    )


def check_rule_11(content: str, lines: List[str]) -> CheckResult:
    """Placeholder Residue: CRITICAL GATE — no unprocessed placeholders."""
    violations = []
    for i, line in enumerate(lines):
        # Standard IMAGE/SCREENSHOT comment placeholders
        if re.search(r'<!--\s*IMAGE:', line):
            violations.append(Violation(
                line=i + 1, text=line.strip()[:80],
                suggestion="运行 /article-craft:images 生成缺失的图片"
            ))
        if re.search(r'<!--\s*SCREENSHOT:', line):
            violations.append(Violation(
                line=i + 1, text=line.strip()[:80],
                suggestion="运行 /article-craft:screenshot 处理截图"
            ))
        # Agent-generated placeholder formats (IMAGE_PLACEHOLDER_*)
        if re.search(r'IMAGE_PLACEHOLDER', line, re.IGNORECASE):
            violations.append(Violation(
                line=i + 1, text=line.strip()[:80],
                suggestion="替换 IMAGE_PLACEHOLDER 为标准 <!-- IMAGE: --> 格式或 CDN URL"
            ))
        # Broken local image paths (images/xxx.jpg or placeholder-xxx.jpg that don't exist)
        local_img = re.search(r'!\[.*?\]\(((?:images/|placeholder-)[\w.-]+)\)', line)
        if local_img:
            img_path = local_img.group(1)
            # Check if referenced file exists relative to article
            article_dir = os.path.dirname(os.path.abspath(lines[0])) if lines else '.'
            # Use the article's directory from the content context
            if not os.path.exists(img_path) and 'cdn.' not in img_path and 'http' not in img_path:
                violations.append(Violation(
                    line=i + 1, text=line.strip()[:80],
                    suggestion=f"本地图片 {img_path} 不存在，替换为 CDN URL 或添加 <!-- IMAGE: --> 占位符"
                ))

    return CheckResult(
        rule_id=11, rule_name="占位符残留",
        passed=len(violations) == 0, violations=violations,
        is_gate=True,
        details=f"GATE {'PASSED' if not violations else 'BLOCKED'}: {len(violations)} 个占位符"
    )


# ─── Rule 12 ────────────────────────────────────────────────────

TEMPLATE_SUMMARY_PATTERNS = [
    r'本文从.*出发.*拆解',
    r'本文将.*详细.*介绍',
    r'接下来.*我们将.*逐一',
    r'下面.*章节.*将.*逐一',
    r'本文.*完整.*梳理.*通过.*最后',
    r'本文.*系统.*讲解.*从.*到',
]


def check_rule_12(content: str, lines: List[str]) -> CheckResult:
    """Template Summary Detection: flag AI-style summary paragraphs."""
    body = get_body(content)
    text = strip_code_blocks(body)
    violations = []

    for i, line in enumerate(lines):
        for pattern in TEMPLATE_SUMMARY_PATTERNS:
            if re.search(pattern, line):
                violations.append(Violation(
                    line=i + 1, text=line.strip()[:80],
                    suggestion="改写模板化摘要，用具体问题或个人经历替代概括性描述"
                ))
                break  # One match per line is enough

    return CheckResult(
        rule_id=12, rule_name="模板化摘要",
        passed=len(violations) == 0, violations=violations,
        details=f"{len(violations)} 处模板化表述" if violations else "无模板化摘要"
    )


def check_rule_13(content: str, lines: List[str]) -> CheckResult:
    """Code Block Language Identifier: every opening ``` must have a language tag."""
    violations = []
    in_code = False

    for i, line in enumerate(lines):
        stripped = line.rstrip()
        if stripped.startswith('```'):
            if in_code:
                # Closing fence — should be bare, skip
                in_code = False
            else:
                # Opening fence — must have language identifier
                in_code = True
                lang = stripped[3:].strip()
                if not lang:
                    violations.append(Violation(
                        line=i + 1, text=stripped,
                        suggestion="添加语言标识符，如 ```yaml、```bash、```go、```text"
                    ))

    return CheckResult(
        rule_id=13, rule_name="代码块语言标识",
        passed=len(violations) == 0, violations=violations,
        details=f"{len(violations)} 个代码块缺少语言标识" if violations else "所有代码块已标注语言"
    )


# Non-executable languages that may contain ASCII diagrams
_EXECUTABLE_LANGS = {
    'bash', 'shell', 'sh', 'zsh', 'python', 'go', 'yaml', 'yml', 'json',
    'sql', 'javascript', 'js', 'typescript', 'ts', 'hcl', 'toml', 'dockerfile',
    'diff', 'ini', 'conf', 'nginx', 'lua', 'ruby', 'java', 'c', 'cpp', 'rust',
    'proto', 'protobuf', 'graphql', 'xml', 'html', 'css', 'scss', 'makefile',
    'cmake', 'rego', 'promql', 'markdown', 'md', 'csv', 'plaintext',
}

_BOX_CHARS = set('│├└┌┐─┬┴┤┼╔╗╚╝║═╭╮╯╰')
_ARROW_CHARS = set('▼▶◄◀←→↑↓►')


def check_rule_14(content: str, lines: List[str]) -> CheckResult:
    """ASCII Diagram Detection: flag ASCII diagrams in code blocks."""
    violations = []
    in_code = False
    code_start = 0
    code_lang = ''
    code_lines = []

    for i, line in enumerate(lines):
        stripped = line.rstrip()
        if stripped.startswith('```'):
            if in_code:
                # End of code block — check for ASCII diagram
                block_content = ''.join(code_lines)
                box_count = sum(1 for c in block_content if c in _BOX_CHARS)
                arrow_count = sum(1 for c in block_content if c in _ARROW_CHARS)
                if (box_count >= 5 or (box_count >= 2 and arrow_count >= 2)):
                    if code_lang.lower() not in _EXECUTABLE_LANGS:
                        preview = block_content.replace('\n', ' | ')[:80]
                        violations.append(Violation(
                            line=code_start + 1,
                            text=f"```{code_lang} 块含 ASCII 图: {preview}",
                            suggestion="转换为 <!-- IMAGE: name - desc (ratio) --> 占位符"
                        ))
                in_code = False
                code_lines = []
            else:
                in_code = True
                code_start = i
                code_lang = stripped[3:].strip()
                code_lines = []
        elif in_code:
            code_lines.append(line)

    return CheckResult(
        rule_id=14, rule_name="ASCII 图表残留",
        passed=len(violations) == 0, violations=violations,
        details=f"{len(violations)} 个 ASCII 图表需转换为 IMAGE 占位符" if violations else "无 ASCII 图表残留"
    )


def check_rule_15(content: str, lines: List[str]) -> CheckResult:
    """Orphan PROMPT comments: flag <!-- PROMPT: --> not preceded by <!-- IMAGE: -->."""
    violations = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('<!-- PROMPT:'):
            # Check if previous non-empty line is <!-- IMAGE: -->
            prev_is_image = False
            for j in range(i - 1, max(i - 3, -1), -1):
                prev = lines[j].strip()
                if not prev:
                    continue
                if prev.startswith('<!-- IMAGE:'):
                    prev_is_image = True
                break
            if not prev_is_image:
                violations.append(Violation(
                    line=i + 1, text=stripped[:80],
                    suggestion="删除孤立的 PROMPT 注释（图片已生成后的残片）"
                ))

    return CheckResult(
        rule_id=15, rule_name="孤立 PROMPT 注释",
        passed=len(violations) == 0, violations=violations,
        details=f"{len(violations)} 个孤立 PROMPT 注释" if violations else "无孤立 PROMPT 注释"
    )


def check_rule_16(content: str, lines: List[str]) -> CheckResult:
    """PROMPT 文字渲染风险：PROMPT 里出现 CJK 字符 / 明显的 'render this exact text' 指令。

    Gemini 图像模型无法稳定渲染中文汉字，也渲不好英文长句。一旦 PROMPT 里出现
    中日韩字符或 'text "...", label "...", title "...", headline "..."' 之类直接
    指令，生成出来的图几乎必然文字翻车。这条规则在**write 阶段**就拦截。
    """
    cjk_re = re.compile(r'[一-鿿぀-ヿ가-힯]')
    text_instruction_re = re.compile(
        r'\b(text|title|headline|caption|label|logo|slogan|copy|heading|word|letter|sign|quote|saying)\s*[:=]?\s*["“‘]',
        re.IGNORECASE,
    )
    violations: List[Violation] = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith('<!-- PROMPT:'):
            continue

        # Extract prompt body (strip marker and trailing -->)
        body = stripped
        if body.startswith('<!-- PROMPT:'):
            body = body[len('<!-- PROMPT:'):]
        if body.endswith('-->'):
            body = body[:-3]
        body = body.strip()

        # CJK inside prompt → hard fail (Gemini can't render Chinese text)
        cjk_chars = cjk_re.findall(body)
        if cjk_chars:
            sample = ''.join(cjk_chars[:10])
            violations.append(Violation(
                line=i + 1, text=stripped[:80],
                suggestion=(
                    f"PROMPT 里出现 CJK 字符 ({sample})。Gemini 不能稳定渲染中文。"
                    "改成视觉替代（剪影/色块/图标），并在结尾加 "
                    "'No readable text anywhere, no letters, no numbers, no labels.'"
                )
            ))
            continue

        # English instructions to render specific text strings → warn
        if text_instruction_re.search(body):
            # Allow if prompt explicitly says 'no text' or similar
            if re.search(r'no\s+(readable\s+)?(text|letters|words|labels|captions|logos)', body, re.IGNORECASE):
                continue
            violations.append(Violation(
                line=i + 1, text=stripped[:80],
                suggestion=(
                    "PROMPT 指示 Gemini 渲染具体文字（text/title/label/...）。"
                    "改用图标或剪影替代，或在末尾加硬约束 "
                    "'No readable text anywhere, no letters, no numbers, no labels.'"
                )
            ))

    return CheckResult(
        rule_id=16, rule_name="PROMPT 文字渲染风险",
        passed=len(violations) == 0, violations=violations,
        details=(
            f"{len(violations)} 处 PROMPT 里包含文字渲染风险（CJK 或 'render text X' 指令）"
            if violations else "所有 PROMPT 均不要求 Gemini 渲染文字 ⭐"
        ),
    )


PERSONAL_VOICE_REGEX = re.compile(
    r"我(?:在|曾|的|会|用|选|踩|测|觉得|发现|猜|赌|最后)"
    r"|踩坑|实测|我的(?:经验|理解|做法)"
    r"|生产环境.*?(?:我|本人)"
)


def check_rule_17(content: str, lines: List[str]) -> CheckResult:
    """Rule 17: Register Naturalness (tone-aware).

    Reads `tone:` from article frontmatter; falls back to writing_style
    default; final fallback is "neutral". Runs four sub-checks; collects
    Violation objects with severity; returns a CheckResult.
    """
    frontmatter = parse_frontmatter(content)
    tone = resolve_tone(
        cli_tone=None,
        frontmatter_tone=frontmatter.get("tone"),
        writing_style=frontmatter.get("writing_style"),
    )

    body = get_body(content)
    body = strip_code_blocks(body)
    body = _strip_callout_blocks(body)
    body = _strip_image_lines(body)

    cn_chars = len(re.findall(r"[一-鿿]", body))
    if cn_chars < 200:
        return CheckResult(
            rule_id="rule_17",
            rule_name=f"Register Naturalness (tone={tone})",
            passed=True,
            skipped=True,
            skip_reason="样本太小 (<200 字), 密度抖动失真",
            violations=[],
        )

    thresholds = TONE_THRESHOLDS[tone]
    violations: List[Violation] = []

    # ── Sub-check A: First-person density ───────────────────────
    first_person_hits = len(PERSONAL_VOICE_REGEX.findall(body))
    density = (first_person_hits / cn_chars) * 800
    threshold_a = thresholds["first_person_per_800w"]
    if density < threshold_a:
        violations.append(Violation(
            line=0,
            text=f"第一人称密度: {density:.1f} 处/800字",
            suggestion=(
                f"tone={tone} 要求 ≥{threshold_a} 处/800字, "
                f"补充第一人称经验 / 选型理由 / 踩坑记录"
            ),
            severity="warning",
        ))

    # ── Sub-check B: Strong-opinion presence ─────────────────────
    threshold_b = thresholds["strong_opinion_min"]
    if threshold_b > 0:
        opinion_count = sum(
            len(p.findall(body)) for p in STRONG_OPINION_PATTERNS
        )
        if opinion_count < threshold_b:
            sev = "error" if tone == "opinionated" else "info"
            msg = (
                "tone=opinionated 要求至少 1 处明确个人立场"
                if tone == "opinionated"
                else "考虑加 1 处个人判断 / 预测, 提升可读性"
            )
            violations.append(Violation(
                line=0,
                text=f"强观点 sentence 数: {opinion_count} (需要 {threshold_b})",
                suggestion=msg,
                severity=sev,
            ))

    # ── Sub-check C: Summary-phrase ceiling ──────────────────────
    # Reuses the same EMPTY_JUDGEMENT_PHRASES + SUMMARY_TONE_PHRASES used
    # by Rule 5. Different lens: Rule 5 looks at structural arrangement
    # (consecutive paragraphs, no anchors); Rule 17 only at total count.
    summary_hits = sum(
        len(re.findall(p, body))
        for p in EMPTY_JUDGEMENT_PHRASES + SUMMARY_TONE_PHRASES
    )
    limit_c = thresholds["max_summary_phrases"]
    if summary_hits > limit_c:
        violations.append(Violation(
            line=0,
            text=f"总结腔短语命中: {summary_hits} (上限 {limit_c})",
            suggestion=(
                f"tone={tone} 上限 {limit_c}, "
                f"删 {summary_hits - limit_c} 处或换具体陈述"
            ),
            severity="warning",
        ))

    # Sub-check D added in next task.

    return CheckResult(
        rule_id="rule_17",
        rule_name=f"Register Naturalness (tone={tone})",
        passed=not any(v.severity == "error" for v in violations),
        violations=violations,
        meta={"tone": tone},
    )


# ─── Runner ──────────────────────────────────────────────────────

ALL_CHECKS = [
    check_rule_1, check_rule_2, check_rule_3, check_rule_4,
    check_rule_5, check_rule_6, check_rule_7, check_rule_8,
    check_rule_9, check_rule_10, check_rule_11, check_rule_12,
    check_rule_13, check_rule_14, check_rule_15, check_rule_16,
]


def run_all_checks(article_path: str) -> Tuple[List[CheckResult], bool]:
    """Run all 16 rules. Returns (results, all_passed)."""
    content = Path(article_path).read_text(encoding='utf-8')
    lines_list = content.split('\n')
    results = [check(content, lines_list) for check in ALL_CHECKS]
    all_passed = all(r.passed for r in results)
    return results, all_passed


def print_report(results: List[CheckResult]) -> None:
    """Print the Phase 1 self-check report."""
    print("════════════════════════════════════════════════════════════")

    all_passed = all(r.passed for r in results)
    gate_result = results[10]  # Rule 11 (index 10)

    if all_passed:
        print("✅ PHASE 1 SELF-CHECK COMPLETE")
    elif not gate_result.passed:
        print("❌ REVIEW BLOCKED: Placeholder Residue Detected")
    else:
        print("⚠️  PHASE 1 SELF-CHECK: Issues Found")

    print("════════════════════════════════════════════════════════════")
    print()
    print("📋 Self-Check Results (16 Rules):")

    for r in results:
        icon = "✅" if r.passed else "❌"
        gate_tag = " ⭐" if r.is_gate else ""
        print(f"   {icon} Rule {r.rule_id}: {r.rule_name} — {r.details}{gate_tag}")

        if not r.passed:
            for v in r.violations[:3]:  # Show max 3 violations per rule
                line_info = f"L{v.line}" if v.line > 0 else ""
                print(f"      {line_info} {v.text[:60]}")
                if v.suggestion:
                    print(f"      → {v.suggestion}")

    print()
    if all_passed:
        print("✨ Status: READY FOR CONTENT-REVIEWER SCORING")
    elif not gate_result.passed:
        print(f"🔴 Status: BLOCKED — {len(gate_result.violations)} 个未处理占位符")
        print("   → 运行 /article-craft:images 后重试")
    else:
        failed_count = sum(1 for r in results if not r.passed)
        print(f"⚠️  Status: {failed_count} 条规则未通过（非阻断，可继续审查）")

    print("════════════════════════════════════════════════════════════")


def to_json(results: List[CheckResult]) -> str:
    """Convert results to JSON string."""
    data = []
    for r in results:
        d = {
            "rule_id": r.rule_id,
            "rule_name": r.rule_name,
            "passed": r.passed,
            "is_gate": r.is_gate,
            "details": r.details,
            "violations": [
                {
                    "line": v.line,
                    "text": v.text,
                    "suggestion": v.suggestion,
                    "severity": v.severity,
                }
                for v in r.violations
            ],
            "skipped": r.skipped,
            "skip_reason": r.skip_reason,
            "meta": r.meta,
        }
        data.append(d)
    return json.dumps(data, ensure_ascii=False, indent=2)


# ─── Main ────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Article self-check (16 rules)")
    parser.add_argument("article", help="Path to .md file")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--gate-only", action="store_true", help="Only check Rule 11 (placeholder gate)")
    args = parser.parse_args()

    if not os.path.exists(args.article):
        print(f"❌ File not found: {args.article}", file=sys.stderr)
        sys.exit(2)

    if args.gate_only:
        content = Path(args.article).read_text(encoding='utf-8')
        lines_list = content.split('\n')
        result = check_rule_11(content, lines_list)
        if args.json:
            print(to_json([result]))
        else:
            icon = "✅" if result.passed else "❌"
            print(f"{icon} Rule 11 (Placeholder Gate): {result.details}")
        sys.exit(0 if result.passed else 1)

    results, all_passed = run_all_checks(args.article)

    if args.json:
        print(to_json(results))
    else:
        print_report(results)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
