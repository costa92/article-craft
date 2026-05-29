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
import hashlib
import yaml
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Union
from dataclasses import dataclass, field, asdict

# Make this script work three ways:
#   1. Direct script:    python3 scripts/review_selfcheck.py article.md
#   2. Module from root: python3 -m scripts.review_selfcheck article.md
#   3. Pytest import:    from scripts.review_selfcheck import check_rule_17
# Path 1 broke historically because the import was `from scripts.config`,
# which requires the repo root on sys.path. Adding the script's own
# directory makes `from config import ...` work in all three modes.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from config import TONE_THRESHOLDS, resolve_tone, STRONG_OPINION_PATTERNS

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
    r'你的点赞是我最大的动力', r'如果这篇文章对你有帮助',
    # 一键三连（4 动作堆砌通用模板，读者会忽略；Style H 文末"⭐点赞、转发、在看一键三连⭐"
    # 通过 Style H 专用规则放行，这里只拦其他风格的滥用）
    r'一键三连',
]

# Rule 23: 反推荐特征词黑名单（v1.7.1+，A/B 级官方依据）
#
# error（阻断）：违反珊瑚安全公告"不得删除/篡改/伪造平台添加的 AI 标识"——
#   反向声明会被平台识别为伪造非 AI 标识，触发流量限制。
#
# warning（不阻断）：违反《微信公众号推荐运营规范》"通过捏造扭曲事实
#   吸引眼球" / "仅以营销、广告为目的，缺乏实际价值的宣传"——
#   命中后文章可能不被推荐。
#
# 依据：
#   - 微信珊瑚安全 2025-08-31《关于进一步规范人工智能生成合成内容标识的公告》
#   - developers.weixin.qq.com《微信公众号推荐运营规范》(2024-05-10)
#
AIGC_REVERSE_DECLARATIONS = [
    # 直接反向声明（违反珊瑚安全公告"伪造标识"）
    r'非\s*AI\s*生成', r'非\s*AI\s*创作',
    r'完全\s*人工\s*(撰写|创作|生成|编写)',
    r'纯\s*手写', r'纯\s*手工\s*(撰写|创作)',
    r'(本文|全文)\s*(完全|纯|皆|均).*?(由\s*人工|非\s*机器|非\s*AI)',
    r'非\s*机器\s*生成',
    r'人工\s*100%', r'100%\s*人工\s*(撰写|创作|原创)',
    # 弱化版（"无 AI 参与" 措辞）
    r'(没有|无|未).*?(借助|使用|依赖)\s*AI',
    r'(没有|无|未).*?AI\s*(辅助|协助|参与)',
]

# 营销标题党词头（《推荐运营规范》"捏造扭曲事实吸引眼球"软命中）
MARKETING_HEADLINE_HEADS = [
    r'^震惊[,，:：!！]?',
    r'^重磅[,，:：!！]?',
    r'^紧急[,，:：!！]?',
    r'^速看[,，:：!！]?',
    r'^必看[,，:：!！]?',
    r'^爆[,，:：!！]?',
    r'^独家解密[,，:：!！]?',
    r'^内部消息[,，:：!！]?',
    r'^不看后悔', r'^错过.*?(后悔|遗憾)',
    r'.*?(最|超|秒).*?震撼',
]

# Rule 24: 虚构具体数字检测（v1.7.2+，warning，不阻断）
#
# 动机：LLM 写文章时倾向"自信地编数字"让文章看起来更可信。
# 第一轮微信调研推翻 10 条来自 CSDN 的循环引用数字（40/30/20/10、
# 30 天保护期、1.3 倍加成、0.89% 等），但 22 条规则没有一条检测
# "AI 自己编的数字"。Rule 23 抓反向声明，Rule 22 数主观判断密度，
# 都不验证数字真伪。这条规则补这个盲区。
#
# 检测策略：扫描正文（非代码块、非 frontmatter）的"数字 + 单位"，
# 不命中下列豁免条件 → 标 warning：
#   1. 被 backtick `..` 包围
#   2. 同段落含 markdown link [..](http..)
#   3. 数字在 frontmatter verified_numbers 白名单
#   4. 限定词前缀（"约/大概/估计/粗估/我赌/我猜/几/某/不到/超过"）
#
# 仅 warning 不阻断 — FP 率天然高，目的是提醒作者人工核对，
# 不是机械阻断。
NUMERIC_CLAIM_PATTERN = re.compile(
    # 数字（含小数、范围、百分比、加减号）+ 单位
    r'(?<![`\w\.])'  # 前置不是 backtick / 字母数字 / .
    r'(\d+(?:\.\d+)?(?:\s*[-~–]\s*\d+(?:\.\d+)?)?)'  # 数字或范围
    r'\s*'
    r'(%|倍|分钟|小时|天|周|月|年|秒|毫秒|ms|MB|GB|KB|TB|'
    r'tokens?|美元|\$|元|人|起|条|次|篇|个|文件|行|轮|组|'
    r'倍?数|tps|qps|rps)',
    re.IGNORECASE,
)

# 数字前的限定词（命中则视为非"声明事实"，豁免）
HEDGE_PREFIXES = [
    # 直接 hedge 词，允许后跟 0-5 字的连接词（"可能就 30%"）
    r'(约|大概|估计|粗估|大致|大约|可能|预计|应该|差不多|接近|至少|最多|超过|不到|不下于|有时|偶尔|每?周?可能就|大约就)[^。\n]{0,5}\d',
    r'(我?(?:估计|猜|赌|觉得|认为|敢断言))[^。\n]*\d',
    r'(基线|目标|预期|理想|阈值)[^。\n]*\d',  # 目标值不是事实声明
    r'<?\s*\d+(?:\.\d+)?\s*[%%]\s*?(?:以内|以上|以下)',  # X% 以内/以上 = 范围声明
    r'(几|十几|数|某|个把|若干)\s*(起|条|次|个|篇|文件|行)',  # 中文模糊量词
    # backtick 包裹的内容里出现数字 — 例如 `Style G threshold=1`、`v1.7.2`
    r'`[^`]*\d[^`]*`',
]

# 数字后的限定词（"20 分钟左右"等）
HEDGE_POSTFIXES = [
    r'^\s*(左右|上下|前后|出头|出点|多一些|少一些|或更多|或更少|不到|开外)',
]

# 不算虚构数字的特殊模式（年份、版本号等）
EXCLUDED_PATTERNS = [
    r'^(19|20)\d{2}\s*年',     # 年份 19xx/20xx 年
    r'^\d+\s*年(?:代)?$',         # 80 年代 / 2025 年
]

# Rule 18: AIGC 显式标识合规（GB 45438-2025 + cac.gov.cn 标识办法）
# 任一匹配即认为有 AIGC 标识
AIGC_LABEL_PATTERNS = [
    r'本文.*?AI.*?(辅助|协助|帮助).*?(起稿|创作|生成|写作|改写)',
    r'AI\s*辅助.*?(起稿|创作|改写)',
    r'本文由\s*AI\s*(辅助|协助)',
    r'本文使用\s*AI.*?(工具|辅助).*?(写作|创作)',
    r'AI[-\s]*(辅助|协助|generated|assisted)',
]

# Rule 3 修订版（v1.7+）：CTA 引导动作 patterns
# 文末必须含至少 1 个具体引导动作
CTA_ACTION_PATTERNS = [
    # 点♡/在看类
    r'点(个|一下|了)?[「\"\']?[♡心]',
    r'(点|加|来个)\s*在看',
    r'(觉得|对你).*(有用|有帮助|有启发).*(点|推荐)',
    # 转发类
    r'(转发|分享|发给|转给).*?(朋友|同事|群|团队)',
    r'(分享|转发)\s*(到|给|给你的)',
    # 收藏类
    r'(建议|先).*?收藏',
    r'收藏.*?(慢慢|再看|备查|按图索骥)',
    # 留言类
    r'(评论区|留言).*?(聊聊|说|告诉|分享|讨论)',
    r'(你|大家).*?(踩过|遇到|怎么看).*?[?？]',
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

# Style → per-section code-block threshold for Rule 6.
# Source of truth: `skills/write/SKILL.md` "风格特定的章节结构" table.
#   A 教程 (tutorial) → 3 blocks per section
#   B 分享 (share) → 1 block
#   C 深度 (deep) → 5+ blocks
#   D 评测 (review) → 2 blocks
#   E 资讯 (news) → 1 block
#   F 复盘 (retrospective) → 2 blocks
#   G 观点 (opinion) → 1 block
#   H 爆料 (leak) → defaults to 2 (not in style table)
# Default for missing / unknown style: 2 (the pre-v1.6.14 hardcoded value).
STYLE_CODE_BLOCK_THRESHOLD = {
    "A": 3,
    "B": 1,
    "C": 5,
    "D": 2,
    "E": 1,
    "F": 2,
    "G": 1,
    "H": 2,
}
DEFAULT_CODE_BLOCK_THRESHOLD = 2


# Canonical personal-anchor regex (B21, v1.6.16+).
# Used by both check_rule_5 (anti-AI structure) and Rule 17 sub-check A
# (Register Naturalness — first-person density per tone tier). Prior to
# v1.6.16 these were two separate inline regexes that had drifted —
# check_rule_5 had a ~30-verb list while PERSONAL_VOICE_REGEX had ~10
# plus `猜` and `生产环境.*?本人`. Unified here as the union of both
# so the two rules see the same "is this a personal-voice anchor"
# decision.
#
# Note: broadening Rule 17's matcher means the existing first_person
# thresholds (2 / 3 / 6 per 800 chars for neutral / casual / opinionated)
# will be hit by more articles. That is the intended direction —
# v1.4.18 tone thresholds were tuned against the OLD narrow regex and
# may need re-calibration once v1.6.16 has run on a few articles
# (see B11 in the backlog for the scheduled re-tune).
PERSONAL_ANCHOR_REGEX = re.compile(
    r"我(?:在|曾|的|会|用|选|踩|测|最后|发现|看|做|跑|试|觉得|以为|之前|后来|当时|"
    r"读|查|翻|改|写|删|跑通|没跑通|发觉|意识到|意外|没料到|接|搞|想|担心|赌|碰|自己|猜)"
    r"|踩坑|踩过|实测|本机实测|实测下来|我的(?:经验|理解|做法)"
    r"|生产环境.*?(?:我|本人)"
    r"|从.{0,6}经验看|我们最后|这次我"
)


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
    """Closing Paragraph (v1.7+ 修订版).

    Two checks:
    1. 禁用空话/伸手党语气（FORBIDDEN_CLOSINGS）
    2. **必须含至少 1 个具体 CTA 引导动作**（CTA_ACTION_PATTERNS）— 4 篇实测都缺。
    """
    body = get_body(content)
    # Find last ~10 non-empty lines (含 callout，因为 CTA 可能在 > 引用块里)
    body_lines = body.strip().split('\n')
    last_lines = []
    for line in reversed(body_lines):
        stripped = line.strip()
        if stripped and not stripped.startswith('---'):
            last_lines.insert(0, stripped)
            if len(last_lines) >= 10:
                break

    last_text = ' '.join(last_lines)
    violations = []

    # 提前检测 Style H（爆料自媒体）— Style H 有专属的"⭐点赞、转发、在看一键三连⭐"放行，
    # 这是 references/writing-styles.md § Style H "公众号三板斧收尾" 定义的合法行为
    fm = parse_frontmatter(content)
    style_raw = fm.get("writing_style", "") or ""
    style_key = style_raw.strip()[:1].upper() if style_raw else ""
    is_style_h = (style_key == "H")

    # Check 1: 禁用空话/伸手党语气（Style H 例外覆盖整个 FORBIDDEN_CLOSINGS 检查）
    for pattern in FORBIDDEN_CLOSINGS:
        # Style H 专属放行：'一键三连' 是 Style H 三板斧收尾的合法句式
        if is_style_h and pattern == r'一键三连':
            continue
        if re.search(pattern, last_text):
            violations.append(Violation(
                line=len(lines), text=last_text[:60],
                suggestion=f"删掉「{pattern}」这类空话/伸手党语气，替换为具体 CTA（见 references/writing-styles.md § Closing Templates）"
            ))

    # Check 2: 必须含 CTA 引导动作（v1.7+ 修订版核心）
    cta_found = False
    cta_match = ""
    for pattern in CTA_ACTION_PATTERNS:
        m = re.search(pattern, last_text)
        if m:
            cta_found = True
            cta_match = m.group()
            break

    if not cta_found:
        # Style H 的"一键三连"也算作有 CTA（一键三连=点♡+转发+在看的复合动作）
        has_implicit_cta = is_style_h and "一键三连" in last_text

        if not has_implicit_cta:
            violations.append(Violation(
                line=len(lines),
                text="文末未检测到 CTA 引导动作",
                suggestion=(
                    "文末必须主推 1-2 个具体引导动作（按 wechat_action 选模板）：\n"
                    "  - heart: 「觉得有用点个♡让更多同行看到」\n"
                    "  - share: 「把这篇转给那个还在 X 的朋友」\n"
                    "  - collect: 「先收藏再看，里面 N 个工具慢慢试」\n"
                    "  - comment: 「你踩过哪些坑？评论区聊聊」\n"
                    "  详见 references/writing-styles.md § Closing Templates"
                ),
                severity="error",
            ))

    return CheckResult(
        rule_id=3, rule_name="结尾 CTA + 禁用词",
        passed=len(violations) == 0, violations=violations,
        details=(
            f"CTA: {cta_match[:30]}" if cta_found and not violations
            else f"{len(violations)} 处问题"
        ),
    )


def check_rule_4(content: str, lines: List[str]) -> CheckResult:
    """Description Field + ≥3 中文 tags (v1.7+ 扩展).

    Two checks:
    1. frontmatter description ≤120 chars
    2. tags ≥3 个 且 ≥3 个中文标签（看一看 NLP 标签匹配中文读者）
    """
    fm = parse_frontmatter(content)
    desc = fm.get('description', '')
    tags = fm.get('tags', []) or []

    violations = []

    # Check 1: description
    if not desc:
        violations.append(Violation(
            line=1, text="frontmatter", suggestion="添加 description 字段（≤120 中文字符）"
        ))
    elif count_chinese(desc) > 120:
        violations.append(Violation(
            line=1, text=desc[:60] + "...",
            suggestion=f"Description 有 {count_chinese(desc)} 字，需缩减到 120 以内"
        ))

    # Check 2: tags（v1.7+ 扩展）
    if not isinstance(tags, list):
        violations.append(Violation(
            line=1, text=f"tags is not a list (got {type(tags).__name__})",
            suggestion="tags 必须是列表格式 tags: [tag1, tag2, tag3]"
        ))
        tags = []

    tag_strs = [str(t) for t in tags if t]
    if len(tag_strs) < 3:
        violations.append(Violation(
            line=1, text=f"tags 仅 {len(tag_strs)} 个",
            suggestion="tags ≥3 个（看一看 NLP 标签匹配需要足够标签覆盖）"
        ))

    chinese_tag_count = sum(1 for t in tag_strs if count_chinese(t) >= 2)
    if chinese_tag_count < 3 and len(tag_strs) >= 3:
        violations.append(Violation(
            line=1, text=f"中文标签 {chinese_tag_count} 个（共 {len(tag_strs)} 个标签）",
            suggestion=(
                "≥3 个中文标签（公众号读者 99% 中文用户，全英文 tags 如 [MCP, AI, DevOps] "
                "会让看一看 NLP 算法无法匹配中文兴趣画像）。"
                "示例：tags: [Kubernetes, Docker, 容器运维, AI工具, 实战教程]"
            )
        ))

    desc_msg = f"{count_chinese(desc)} 字" if desc else "缺失"
    tag_msg = f"{len(tag_strs)} 标签 / {chinese_tag_count} 中文"
    return CheckResult(
        rule_id=4, rule_name="Description + 中文标签",
        passed=len(violations) == 0, violations=violations,
        details=f"desc={desc_msg}, tags={tag_msg}"
    )


def check_rule_5(content: str, lines: List[str]) -> CheckResult:
    """Anti-AI Structure: varied paragraphs + personal perspective."""
    body = get_body(content)

    # Tone-aware gating: Rule 17 sub-check A owns this dimension at
    # casual/opinionated; we only fire here at neutral.
    frontmatter = parse_frontmatter(content)
    tone = resolve_tone(
        cli_tone=None,
        frontmatter_tone=frontmatter.get("tone"),
        writing_style=frontmatter.get("writing_style"),
    )

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

    # Check personal perspective count.
    # Pattern intentionally lists explicit follow-on tokens after `我` rather
    # than `.{0,2}` wildcards — broad wildcards match neutral statements like
    # "我是开发者" and create false positives. Tokens cover natural Chinese
    # tech-blog verbs and the explicit `我自己` self-reference.
    # v1.6.16 (B21): switched from inline regex to canonical
    # PERSONAL_ANCHOR_REGEX shared with Rule 17 sub-check A.
    personal_markers = PERSONAL_ANCHOR_REGEX.findall(body)
    if tone == "neutral" and len(personal_markers) < 2:
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
    """Chapter Depth: each section needs ≥N code blocks where N is style-specific.

    The threshold N comes from the writing_style table in skills/write/SKILL.md.
    Intro/motivation chapters (background/motivation/challenges) accept N-1
    (min 1) since they naturally have fewer code blocks.
    """
    body = get_body(content)
    sections = get_sections(body)
    violations = []

    # Style-aware threshold: read writing_style from frontmatter.
    frontmatter = parse_frontmatter(content)
    style_raw = frontmatter.get("writing_style", "") or ""
    # Style fields may be "A", "A 教程", "a", etc. — take the first letter and uppercase.
    style_key = style_raw.strip()[:1].upper() if style_raw else ""
    base_threshold = STYLE_CODE_BLOCK_THRESHOLD.get(style_key, DEFAULT_CODE_BLOCK_THRESHOLD)

    # Body-form-aware: wechat-native sections are punchier and fewer, so they
    # need one fewer code block per section (min 1). long-form keeps the full
    # style threshold. Missing field degrades to wechat-native (the default).
    # Match config.resolve_body_form() precedence: an explicit body_form field
    # wins over the legacy wechat_target:false alias; the alias only applies
    # when the field is unset/invalid.
    body_form_raw = (frontmatter.get("body_form", "") or "").strip()
    if body_form_raw not in ("wechat-native", "long-form"):
        if frontmatter.get("wechat_target") in (False, "false", "False"):
            body_form_raw = "long-form"
    if body_form_raw != "long-form":  # wechat-native or unset (default)
        base_threshold = max(1, base_threshold - 1)

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

        # Intro/motivation chapters allow one fewer code block (min 1).
        if intro_keywords.search(heading):
            threshold = max(1, base_threshold - 1)
        else:
            threshold = base_threshold

        if code_count < threshold and len(section_content) > 200:
            violations.append(Violation(
                line=0, text=heading[:60],
                suggestion=f"章节「{heading.strip('# ')}」仅有 {code_count} 个代码块，建议补充到 {threshold} 个以上"
            ))

    return CheckResult(
        rule_id=6, rule_name="章节深度",
        passed=len(violations) == 0, violations=violations,
        details=f"{len(violations)} 个浅层章节 (style={style_key or '?'}, body_form={'long-form' if body_form_raw == 'long-form' else 'wechat-native'}, threshold={base_threshold})"
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
                            suggestion="流程图/架构图转 <!-- IMAGE: name - desc (ratio) --> 占位符；目录树（├──/└──）改用 Markdown 列表"
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


# B21 (v1.6.16+): PERSONAL_VOICE_REGEX is now an alias for the canonical
# PERSONAL_ANCHOR_REGEX defined at the top of this module. Kept as an alias
# so any external `from review_selfcheck import PERSONAL_VOICE_REGEX` still
# resolves. Rule 17 sub-check A reads it via this name; check_rule_5 reads
# the canonical name directly.
PERSONAL_VOICE_REGEX = PERSONAL_ANCHOR_REGEX


def _maybe_log_tone_calibration(
    *, tone: str, writing_style: str, article_content: str,
    metrics: Dict, violations: List, passed: bool,
) -> None:
    """Append one JSONL line to tone-calibration.jsonl unless disabled.

    Default: enabled. Opt-out via env var ARTICLE_CRAFT_TONE_CALIBRATION=false.
    Cache dir: ~/.cache/article-craft/ (override via ARTICLE_CRAFT_CACHE_DIR).
    Stores SHA256 of article content (NOT the content itself), for privacy.
    """
    enabled = os.environ.get("ARTICLE_CRAFT_TONE_CALIBRATION", "true").lower() == "true"
    if not enabled:
        return
    cache_dir = Path(os.environ.get(
        "ARTICLE_CRAFT_CACHE_DIR",
        Path.home() / ".cache" / "article-craft",
    ))
    cache_dir.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(article_content.encode("utf-8")).hexdigest()
    record = {
        "ts": datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z",
        "article": sha,
        "writing_style": writing_style,
        "tone_resolved": tone,
        "metrics": metrics,
        "violations": [{"severity": s, "text": t} for s, t in violations],
        "final_pass": passed,
    }
    try:
        with (cache_dir / "tone-calibration.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except (OSError, IOError):
        # Don't crash the review pipeline if calibration logging fails
        pass


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

    # Safe defaults for metric variables — sub-checks B and D have conditional
    # execution paths that may leave these unbound.
    density: float = 0.0
    opinion_count: int = 0
    summary_hits: int = 0
    cv: Optional[float] = None

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

    # ── Sub-check D: Sentence-length coefficient of variation ────
    threshold_d = thresholds["sentence_len_variance_min"]
    if threshold_d > 0:
        sentences = re.split(r"[。！？\n]", body)
        # Filter implausibly short fragments (TOC items, headings) and
        # implausibly long lines (URLs, log dumps).
        lens = [len(s) for s in sentences if 5 <= len(s) <= 200]
        if len(lens) >= 10:
            mean = statistics.mean(lens)
            stdev = statistics.stdev(lens)
            cv = stdev / mean if mean > 0 else 0
            if cv < threshold_d:
                violations.append(Violation(
                    line=0,
                    text=f"句长变异系数: {cv:.2f} (需要 ≥{threshold_d})",
                    suggestion=(
                        "句子长度过于均匀（AI 节奏特征）。"
                        "拆 1-2 句长句为短句, 或合并连续短句为长句"
                    ),
                    severity="warning",
                ))

    # ── Calibration logging (opt-out via env var) ───────────────
    _passed = not any(v.severity == "error" for v in violations)
    _maybe_log_tone_calibration(
        tone=tone,
        writing_style=frontmatter.get("writing_style", "?"),
        article_content=content,
        metrics={
            "first_person_per_800w": density,
            "strong_opinion_count": opinion_count,
            "summary_phrase_hits": summary_hits,
            "sentence_len_cv": cv,
        },
        violations=[(v.severity, v.text[:50]) for v in violations],
        passed=_passed,
    )

    return CheckResult(
        rule_id="rule_17",
        rule_name=f"Register Naturalness (tone={tone})",
        passed=_passed,
        violations=violations,
        meta={"tone": tone},
    )


# ─── Rules 18-22 (v1.7+, WeChat-targeted, based on A/B-tier official research) ─

def check_rule_18(content: str, lines: List[str]) -> CheckResult:
    """Rule 18: AIGC 显式标识（A 级合规，GB 45438-2025 强制国标 2025-09-01 生效）.

    文末必须含 AI 辅助创作声明的小字脚注。任一 AIGC_LABEL_PATTERNS 匹配即通过。
    """
    body = get_body(content)
    found = False
    matched_text = ""
    for pattern in AIGC_LABEL_PATTERNS:
        m = re.search(pattern, body, re.IGNORECASE)
        if m:
            found = True
            matched_text = m.group()
            break

    violations = []
    if not found:
        violations.append(Violation(
            line=0,
            text="未检测到 AIGC 显式标识",
            suggestion=(
                "文末追加（在 --- 分割线之下）：\n"
                "  > 本文 AI 辅助起稿 + 人工核实改写。\n"
                "依据：GB 45438-2025 强制国标 + 网信办《标识办法》(2025-09-01 已生效)\n"
                "publish 前另需在公众号后台勾选「创作来源 → 内容由 AI 生成」(4 选 1，发布后不可改)"
            ),
            severity="error",
        ))

    return CheckResult(
        rule_id=18, rule_name="AIGC 显式标识",
        passed=found, violations=violations,
        details=(
            f"已含：{matched_text[:40]}" if found
            else "缺失（违反 GB 45438-2025 + 网信办标识办法）"
        ),
    )


# Rule 19 patterns
TITLE_HOOK_DIGIT = re.compile(r'\d')
TITLE_HOOK_CONTRAST = re.compile(r'(为什么|不再|颠覆|反|偏偏|居然|竟然|没想到|意外|更|比|超过|输给|败给)')
TITLE_HOOK_PAIN = re.compile(r'(坑|陷阱|翻车|崩|宕|暴雷|烧钱|裁员|跑路|被.*?坑|注意|警告|避坑)')
TITLE_HOOK_STORY = re.compile(r'(我|后来|被|发现|踩|从|到|这次|那次|当年|去年|上周)')
TITLE_HOOK_SUSPENSE = re.compile(r'(为什么|怎么|如何|是不是|到底|究竟)')

TITLE_BLACKLIST = re.compile(r'(震惊|重磅|解密|厉害了|官方通知|紧急|必看|逆天|疯狂|爆炸|爆了)')


def _extract_title(content: str) -> str:
    fm = parse_frontmatter(content)
    title = fm.get('title', '')
    if not title:
        # Fall back to first H1
        m = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = m.group(1).strip() if m else ''
    return title.strip().strip('"\'').strip()


def check_rule_19(content: str, lines: List[str]) -> CheckResult:
    """Rule 19: 标题钩子规则 + 长度约束.

    - 长度 ≤ 28 字（建议）/ ≤ 64 字（硬上限）
    - 钩子类型至少命中 1（数字 / 反差 / 痛点 / 故事 / 悬念）
    - 不命中黑名单词（震惊/重磅/解密 等）
    """
    title = _extract_title(content)
    violations = []

    if not title:
        return CheckResult(
            rule_id=19, rule_name="标题钩子 + 长度",
            passed=True, skipped=True, skip_reason="未检测到标题",
            details="无标题",
        )

    # 长度（中文字符 + 英文字符各按 1 计）
    title_len = len(title)
    if title_len > 64:
        violations.append(Violation(
            line=1, text=title[:60],
            suggestion=f"标题 {title_len} 字超 64 字硬上限，必须缩短",
            severity="error",
        ))
    elif title_len > 28:
        violations.append(Violation(
            line=1, text=title[:60],
            suggestion=f"标题 {title_len} 字超 28 字推荐值（信息流卡片可能折叠），建议缩短",
            severity="warning",
        ))

    # 钩子类型
    hooks_hit = []
    if TITLE_HOOK_DIGIT.search(title):
        hooks_hit.append("数字")
    if TITLE_HOOK_CONTRAST.search(title):
        hooks_hit.append("反差")
    if TITLE_HOOK_PAIN.search(title):
        hooks_hit.append("痛点")
    if TITLE_HOOK_STORY.search(title):
        hooks_hit.append("故事")
    if TITLE_HOOK_SUSPENSE.search(title):
        hooks_hit.append("悬念")

    if not hooks_hit:
        violations.append(Violation(
            line=1, text=title[:60],
            suggestion=(
                "标题 0 钩子类型命中。公众号高 CTR 标题至少含 1：\n"
                "  - 数字（5 分钟 / 10 个 / 100 万次）\n"
                "  - 反差（为什么我不再 / Rust 比 Go 慢？）\n"
                "  - 痛点（暴雷 / 翻车 / 坑）\n"
                "  - 故事（我 / 被裁员后 / 去年踩过）\n"
                "  - 悬念（为什么 / 怎么 / 到底）"
            ),
            severity="warning",
        ))

    # 黑名单词
    bl_match = TITLE_BLACKLIST.search(title)
    if bl_match:
        violations.append(Violation(
            line=1, text=title[:60],
            suggestion=f"标题含黑名单词「{bl_match.group()}」可能被算法判定为标题党降权，建议替换",
            severity="warning",
        ))

    passed = not any(v.severity == "error" for v in violations)
    return CheckResult(
        rule_id=19, rule_name="标题钩子 + 长度",
        passed=passed, violations=violations,
        details=(
            f"len={title_len}, hooks=[{','.join(hooks_hit) or '无'}]"
        ),
    )


def _extract_h2_blocks(body: str) -> List[Tuple[str, str]]:
    """Extract (heading, body_until_next_h2) for each H2."""
    out = []
    sections = re.split(r'^(##\s+.+)$', body, flags=re.MULTILINE)
    # sections looks like ["intro", "## H2 title 1", "body 1", "## H2 title 2", "body 2", ...]
    i = 1
    while i < len(sections):
        heading = sections[i].strip()
        block = sections[i + 1] if i + 1 < len(sections) else ""
        # Skip if also matches H3+
        if heading.startswith('## ') and not heading.startswith('### '):
            out.append((heading, block.strip()))
        i += 2
    return out


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio()


def check_rule_20(content: str, lines: List[str]) -> CheckResult:
    """Rule 20: 段落相似度去重 + 模板雷同检测.

    检测两两 H2 段是否过度相似（标题 ≥ 0.85 OR 首句 ≥ 0.85 AND 内容 ≥ 0.7）。
    防止 LLM 上下文跳跃事故（如「引用是怎么工作的」重复两次）。
    """
    body = get_body(content)
    h2_blocks = _extract_h2_blocks(body)

    violations = []
    n = len(h2_blocks)
    for i in range(n):
        for j in range(i + 1, n):
            h_i, b_i = h2_blocks[i]
            h_j, b_j = h2_blocks[j]

            # 去掉 H2 标记后比较
            t_i = re.sub(r'^##\s+', '', h_i).strip()
            t_j = re.sub(r'^##\s+', '', h_j).strip()

            title_sim = _similarity(t_i, t_j)

            # 首段（首 80 字符）
            first_i = b_i[:200].strip()[:80]
            first_j = b_j[:200].strip()[:80]
            first_sim = _similarity(first_i, first_j)

            # 内容（整段）
            content_sim = _similarity(b_i[:500], b_j[:500])

            if title_sim >= 0.85:
                violations.append(Violation(
                    line=0,
                    text=f"H2「{t_i}」与「{t_j}」标题相似度 {title_sim:.2f}",
                    suggestion=f"两节标题过度相似（≥0.85），可能是 LLM 重复生成事故，请合并或区分",
                    severity="error",
                ))
            elif first_sim >= 0.85 and content_sim >= 0.7:
                violations.append(Violation(
                    line=0,
                    text=f"H2「{t_i}」vs「{t_j}」首段相似 {first_sim:.2f} + 内容 {content_sim:.2f}",
                    suggestion=f"两节内容高度重复（LLM 上下文跳跃事故），请合并",
                    severity="error",
                ))

    return CheckResult(
        rule_id=20, rule_name="段落相似度去重",
        passed=len(violations) == 0, violations=violations,
        details=f"扫描 {n} 个 H2 段，{len(violations)} 处重复" if n > 1 else f"{n} 个 H2，无重复",
    )


# Rule 22 patterns
PERSONAL_EXPERIENCE_REGEX = re.compile(
    r'(我(在|曾|的|会|用|选|踩|测|跑|试|觉得|以为|之前|后来|当时|读|查|改|写|删|跑通|没跑通|发觉|意识到|意外|没料到|想|担心|赌|碰|自己))'
    r'|去年|上周|这次|那次|当年|前几天|前两天'
    r'|试过|踩过|踩坑|本机实测|实测下来'
)
SUBJECTIVE_JUDGMENT_REGEX = re.compile(
    r'(我推荐|我不推荐|我觉得|我建议|我赌|我选|我会用|我不用|我反对|我支持|我喜欢|我不喜欢|个人觉得|个人推荐|个人不推荐)'
)
SPECIFIC_NUMBER_REGEX = re.compile(
    r'\b\d+(\.\d+)?\s*(分钟|秒|小时|天|周|月|年|次|个|条|GB|MB|KB|ms|s|%|倍|快|慢|节省|减少|提升)\b'
)


def check_rule_22(content: str, lines: List[str]) -> CheckResult:
    """Rule 22: 个人化注入软检测（warning）.

    - 个人经历关键词 ≥ 2 处
    - 具体数字（非代码块内）≥ 1 处
    - 主观判断 ≥ 1 处
    """
    body = strip_code_blocks(get_body(content))

    exp_count = len(PERSONAL_EXPERIENCE_REGEX.findall(body))
    judg_count = len(SUBJECTIVE_JUDGMENT_REGEX.findall(body))
    num_count = len(SPECIFIC_NUMBER_REGEX.findall(body))

    violations = []
    if exp_count < 2:
        violations.append(Violation(
            line=0,
            text=f"个人经历关键词 {exp_count} 处",
            suggestion="补充 ≥ 2 处个人经历（我用 / 去年试过 / 上周踩坑等）",
            severity="warning",
        ))
    if judg_count < 1:
        violations.append(Violation(
            line=0,
            text=f"主观判断 {judg_count} 处",
            suggestion="补充 ≥ 1 处主观判断（我推荐 X 因为... / 我不用 Y 因为...）",
            severity="warning",
        ))
    if num_count < 1:
        violations.append(Violation(
            line=0,
            text=f"具体数字 {num_count} 处",
            suggestion="补充 ≥ 1 处具体数字（实测耗时 47ms / 节省 30%）",
            severity="warning",
        ))

    return CheckResult(
        rule_id=22, rule_name="个人化注入",
        passed=len(violations) == 0, violations=violations,
        details=f"经历 {exp_count} / 判断 {judg_count} / 数字 {num_count}",
    )


def check_rule_23(content: str, lines: List[str]) -> CheckResult:
    """Rule 23: 反推荐特征词黑名单（v1.7.1+，A/B 级官方依据）.

    - error: AIGC 反向声明（违反珊瑚安全公告"不得伪造标识"）
    - warning: 标题营销词头部（违反《推荐运营规范》反推荐特征）

    依据：
    - 微信珊瑚安全 2025-08-31 公告（B 级官方间接）
    - 《微信公众号推荐运营规范》developers.weixin.qq.com（A 级官方一手）

    实现注意：code-block 内的反向声明字串（用于规则文档化的反例）必须豁免，
    否则讨论 Rule 23 本身的文章无法绕过规则。修复前版本误扫了 ```text 块。
    """
    fm = parse_frontmatter(content)

    # 标记所有处于 fenced code block 内的行号（包括 fence 自身）
    code_lines: set = set()
    in_code = False
    for i, line in enumerate(content.split("\n"), 1):
        if line.strip().startswith("```"):
            in_code = not in_code
            code_lines.add(i)
            continue
        if in_code:
            code_lines.add(i)

    violations: List[Violation] = []

    # ① AIGC 反向声明检测（error，阻断）—— 跳过 code-block 内的行
    for line_no, line in enumerate(lines, 1):
        if line_no in code_lines:
            continue
        for pattern in AIGC_REVERSE_DECLARATIONS:
            m = re.search(pattern, line)
            if m:
                violations.append(Violation(
                    line=line_no,
                    text=f"反向声明: {m.group(0)[:30]}",
                    suggestion=(
                        "删除该反向声明。违反微信珊瑚安全公告"
                        "「不得删除/篡改/伪造平台标识」——"
                        "article-craft 生成的内容应保留 AIGC 显式标识（Rule 18）"
                    ),
                    severity="error",
                ))

    # ② 标题营销词检测（warning，不阻断）
    # 标题在 frontmatter title 字段，或 body 第一个 # 行
    title = fm.get("title", "")
    if not title:
        for line in lines:
            if line.startswith("# ") and not line.startswith("## "):
                title = line[2:].strip()
                break

    if title:
        for pattern in MARKETING_HEADLINE_HEADS:
            m = re.search(pattern, title)
            if m:
                violations.append(Violation(
                    line=0,
                    text=f"标题营销词头部: {m.group(0)[:20]}",
                    suggestion=(
                        f"标题《{title[:30]}...》命中营销词头部，违反"
                        "《微信公众号推荐运营规范》「捏造扭曲事实吸引眼球」"
                        "——可能不被平台推荐。"
                        "建议改为知识传递/经验分享/个人观点钩子。"
                    ),
                    severity="warning",
                ))
                break  # 同一标题只报一次

    # 通过条件：无 error 级 violation（warning 不影响 passed）
    has_error = any(v.severity == "error" for v in violations)
    error_count = sum(1 for v in violations if v.severity == "error")
    warning_count = sum(1 for v in violations if v.severity == "warning")

    return CheckResult(
        rule_id=23, rule_name="反推荐特征词黑名单",
        passed=not has_error,
        violations=violations,
        details=(
            f"反向声明 {error_count} / 营销词 {warning_count}"
            if violations
            else "无反向声明，标题无营销词头部"
        ),
    )


def check_rule_24(content: str, lines: List[str]) -> CheckResult:
    """Rule 24: 虚构具体数字检测（v1.7.2+，warning，不阻断）.

    扫描正文（非代码块、非 frontmatter）的"数字 + 单位"声明，
    未命中豁免条件的标 warning，提醒作者核对来源。

    豁免条件：
      1. 被 backtick `..` 包围（认为是代码/引用）
      2. 同段落含 markdown link [..](http..)（认为有出处）
      3. 数字在 frontmatter verified_numbers 白名单
      4. 限定词前缀（约/估计/我猜/我赌/基线/目标 等）

    设计意图：第一轮微信调研推翻 10 条 CSDN 循环引用伪事实，
    article-craft v1.7.1 没有规则检测 "AI 自己编的数字"——这是
    LLM 写作的最大失败模式之一。这条规则补这个盲区。

    设计取舍：FP 率天然高，所以严格 warning 不阻断。目的是提醒
    作者人工核对，不是机械拦截。
    """
    body_content = get_body(content)
    fm = parse_frontmatter(content)
    verified = set(str(x) for x in fm.get("verified_numbers", []))

    # 标记 fenced code block 行号（含 fence 自身）
    code_lines: set = set()
    in_code = False
    for i, line in enumerate(content.split("\n"), 1):
        if line.strip().startswith("```"):
            in_code = not in_code
            code_lines.add(i)
            continue
        if in_code:
            code_lines.add(i)

    violations: List[Violation] = []
    seen_per_line: set = set()  # 同行同数字只报一次

    for line_no, line in enumerate(lines, 1):
        if line_no in code_lines:
            continue
        # 跳过 frontmatter 行（粗略：前 20 行内的 yaml）
        if line_no <= 20 and re.match(r'^\s*\w+:\s', line):
            continue

        # 整行是否在 markdown link 内（粗略豁免：有 (http..) 出现）
        has_link_in_line = bool(re.search(r'\]\(https?://', line))

        for m in NUMERIC_CLAIM_PATTERN.finditer(line):
            num_str, unit = m.group(1), m.group(2)
            full_match = m.group(0)

            # 豁免 1: backtick 包围
            start = m.start()
            backtick_before = line.rfind('`', 0, start)
            backtick_after = line.find('`', m.end())
            if backtick_before >= 0 and backtick_after > start:
                # 检查 backtick_before 和 backtick_after 之间是否只有 1 个 `
                between = line[backtick_before:backtick_after + 1]
                if between.count('`') == 2:
                    continue

            # 豁免 2: 同行有 markdown link
            if has_link_in_line:
                continue

            # 豁免 3: frontmatter 白名单
            if num_str in verified or f"{num_str}{unit}" in verified:
                continue

            # 豁免 4: 限定词前缀（句子级）
            sentence_ends = '。!！?？，,\n'
            sent_start = start
            while sent_start > 0 and line[sent_start - 1] not in sentence_ends:
                sent_start -= 1
            sent_end = m.end()
            while sent_end < len(line) and line[sent_end] not in sentence_ends:
                sent_end += 1
            sentence = line[sent_start:sent_end]
            if any(re.search(pat, sentence) for pat in HEDGE_PREFIXES):
                continue

            # 豁免 5: 后置限定词（"20 分钟左右"）
            following = line[m.end():m.end() + 8]
            if any(re.match(pat, following) for pat in HEDGE_POSTFIXES):
                continue

            # 豁免 6: 排除年份、版本号等特殊模式
            if any(re.match(pat, full_match) for pat in EXCLUDED_PATTERNS):
                continue

            # 同行同数字+单位只报一次
            key = (line_no, num_str, unit)
            if key in seen_per_line:
                continue
            seen_per_line.add(key)

            violations.append(Violation(
                line=line_no,
                text=f"未标注来源: {full_match[:30]}",
                suggestion=(
                    f"数字「{full_match}」缺少出处。三选一修复：(a) 加 "
                    f"`{full_match}` 让它出现在代码块/引用中；(b) 同段落加 "
                    f"[来源](url) 链接；(c) 加限定词「约/估计/我赌」表明这是判断不是事实；"
                    f"或在 frontmatter verified_numbers: ['{num_str}{unit}'] 白名单显式声明"
                ),
                severity="warning",
            ))

    # 阈值：>5 个未标注数字视为高密度警告（仍不阻断）
    high_density = len(violations) > 5

    return CheckResult(
        rule_id=24, rule_name="虚构数字检测",
        passed=True,  # 永远 passed（warning 级）
        violations=violations,
        details=(
            f"{len(violations)} 个未标注数字声明" + (" (高密度)" if high_density else "")
            if violations
            else "无未标注具体数字"
        ),
    )


# ─── Runner ──────────────────────────────────────────────────────

ALL_CHECKS = [
    check_rule_1, check_rule_2, check_rule_3, check_rule_4,
    check_rule_5, check_rule_6, check_rule_7, check_rule_8,
    check_rule_9, check_rule_10, check_rule_11, check_rule_12,
    check_rule_13, check_rule_14, check_rule_15, check_rule_16,
    check_rule_17,
    # v1.7+ WeChat-targeted rules (A/B-tier official-research backed)
    check_rule_18, check_rule_19, check_rule_20, check_rule_22,
    # v1.7.1+ 反推荐特征词黑名单（推荐运营规范 + 珊瑚安全公告）
    check_rule_23,
    # v1.7.2+ 虚构数字检测（warning, 防 LLM 自信编造数字）
    check_rule_24,
]


def check_all(content: str) -> List[CheckResult]:
    """Run all checks against raw article content. Returns list of CheckResult."""
    lines_list = content.split('\n')
    return [check(content, lines_list) for check in ALL_CHECKS]


def run_all_checks(article_path: str) -> Tuple[List[CheckResult], bool]:
    """Run all rules. Returns (results, all_passed)."""
    content = Path(article_path).read_text(encoding='utf-8')
    results = check_all(content)
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
    print(f"📋 Self-Check Results ({len(results)} Rules):")

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

_RULE_DISPATCH = {
    1: check_rule_1, 2: check_rule_2, 3: check_rule_3, 4: check_rule_4,
    5: check_rule_5, 6: check_rule_6, 7: check_rule_7, 8: check_rule_8,
    9: check_rule_9, 10: check_rule_10, 11: check_rule_11, 12: check_rule_12,
    13: check_rule_13, 14: check_rule_14, 15: check_rule_15, 16: check_rule_16,
    17: check_rule_17,
    18: check_rule_18, 19: check_rule_19, 20: check_rule_20,
    22: check_rule_22,  # Rule 21 reserved
    23: check_rule_23,
    24: check_rule_24,
}

# Pre-save GATE for the write skill: blocks save when any of these fail.
# Source: references/self-check-rules.md "Who enforces what" matrix —
# write column. Keep this constant in sync with that matrix; the test
# `CLIRuleSelectionTests.test_write_gate_rules_constant_matches_doc`
# pins the tuple to (1, 2, 6, 13, 14, 16) on purpose.
#
# NOTE: Rule 11 (占位符残留 / placeholder residue) is deliberately NOT here.
# At write time the article still carries `<!-- IMAGE: -->` placeholders by
# design (the images stage resolves them later), so gating on Rule 11 would
# block every legitimate draft. Placeholder residue is a REVIEW-stage gate
# (post-images). Rule 14 (ASCII in non-executable code blocks) is the
# pre-images gate that forces ASCII diagrams into IMAGE placeholders.
WRITE_GATE_RULES = (1, 2, 6, 13, 14, 16)


def run_selected_rules(article_path: str, rule_ids: List[int]) -> Tuple[List[CheckResult], bool]:
    """Run a subset of rules by ID. Returns (results, all_passed).

    Unknown rule IDs are skipped silently (a CheckResult with skipped=True
    is emitted so the caller can see the gap)."""
    content = Path(article_path).read_text(encoding='utf-8')
    lines_list = content.split('\n')
    results: List[CheckResult] = []
    for rid in rule_ids:
        fn = _RULE_DISPATCH.get(rid)
        if fn is None:
            results.append(CheckResult(
                rule_id=rid, rule_name=f"unknown rule {rid}",
                passed=True, details="not implemented",
                skipped=True, skip_reason="unknown rule id",
            ))
            continue
        results.append(fn(content, lines_list))
    all_passed = all(r.passed for r in results)
    return results, all_passed


def _parse_rule_list(s: str) -> List[int]:
    out: List[int] = []
    for token in s.split(','):
        token = token.strip()
        if not token:
            continue
        try:
            out.append(int(token))
        except ValueError:
            raise SystemExit(f"❌ Invalid rule id in --rules: {token!r}")
    return out


def main():
    import argparse

    parser = argparse.ArgumentParser(description=f"Article self-check ({len(ALL_CHECKS)} rules)")
    parser.add_argument("article", help="Path to .md file")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--gate-only", action="store_true",
                        help="Only check Rule 11 (placeholder gate) — alias for --rules 11")
    parser.add_argument("--write-gate", action="store_true",
                        help=f"Run only the write skill pre-save GATE rules ({','.join(str(r) for r in WRITE_GATE_RULES)})")
    parser.add_argument("--rules", type=str, default=None,
                        help='Comma-separated rule IDs to run (e.g. "1,2,6,11,13"). '
                             'Overrides --gate-only and --write-gate when present.')
    args = parser.parse_args()

    if not os.path.exists(args.article):
        print(f"❌ File not found: {args.article}", file=sys.stderr)
        sys.exit(2)

    # Resolve which rules to run. Precedence: --rules > --write-gate > --gate-only > all.
    # `args.rules is not None` — distinguishes "--rules was passed (even as '')"
    # from "--rules omitted entirely". An empty string must error, not fall through.
    if args.rules is not None:
        selected = _parse_rule_list(args.rules)
        if not selected:
            parser.error("--rules requires at least one valid rule ID "
                         f"(got {args.rules!r}; example: --rules 1,6,11)")
    elif args.write_gate:
        selected = list(WRITE_GATE_RULES)
    elif args.gate_only:
        selected = [11]
    else:
        selected = None

    if selected is not None:
        results, all_passed = run_selected_rules(args.article, selected)
        if args.json:
            print(to_json(results))
        else:
            for r in results:
                icon = "✅" if r.passed else "❌"
                print(f"{icon} Rule {r.rule_id} ({r.rule_name}): {r.details}")
                if not r.passed:
                    for v in r.violations[:5]:
                        line_info = f"L{v.line}" if v.line > 0 else ""
                        print(f"   {line_info} {v.text[:80]}")
                        if v.suggestion:
                            print(f"   → {v.suggestion}")
        sys.exit(0 if all_passed else 1)

    results, all_passed = run_all_checks(args.article)

    if args.json:
        print(to_json(results))
    else:
        print_report(results)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
