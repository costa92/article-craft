#!/usr/bin/env python3
"""
article-craft Version Bump Script

用法:
    python3 bump_version.py              # 交互式选择版本类型
    python3 bump_version.py major       # 大版本: 1.1.0 → 2.0.0
    python3 bump_version.py minor       # 小版本: 1.1.0 → 1.2.0
    python3 bump_version.py patch       # 补丁版本: 1.1.0 → 1.1.1
    python3 bump_version.py 1.2.0       # 直接指定版本

工作流程:
    1. 更新 plugin.json 中的 version 字段
    2. 更新各 SKILL.md 的 version 字段（自动同步）
    3. 创建 git tag v{version}
    4. 提示推送到远程
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
REPO_ROOT = SCRIPT_DIR.parent
PLUGIN_JSON = REPO_ROOT / ".claude-plugin" / "plugin.json"
SKILLS_DIR = REPO_ROOT / "skills"


def get_current_version() -> str:
    with open(PLUGIN_JSON) as f:
        return json.load(f)["version"]


def bump_version(version: str, bump_type: str) -> str:
    parts = version.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid version format: {version} (expected X.Y.Z)")
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

    if bump_type == "major":
        major += 1; minor = 0; patch = 0
    elif bump_type == "minor":
        minor += 1; patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        raise ValueError(f"Unknown bump type: {bump_type}")

    return f"{major}.{minor}.{patch}"


def update_plugin_json(version: str) -> None:
    with open(PLUGIN_JSON) as f:
        data = json.load(f)

    old = data["version"]
    data["version"] = version

    with open(PLUGIN_JSON, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"  ✅ .claude-plugin/plugin.json: {old} → {version}")


def update_skill_versions(version: str) -> int:
    """更新所有 SKILL.md 的 version 字段"""
    updated = 0
    for skill_md in SKILLS_DIR.glob("*/SKILL.md"):
        try:
            content = skill_md.read_text(encoding="utf-8")
            # 匹配 YAML frontmatter 中的 version 行
            # version: 1.1.0 或 version: "1.1.0"
            pattern = r'^version: ["\']?[\d.]+["\']?\s*$'
            new_line = f'version: {version}'

            new_content, count = re.subn(
                pattern, new_line, content,
                count=1, flags=re.MULTILINE
            )

            if count > 0:
                skill_md.write_text(new_content, encoding="utf-8")
                print(f"  ✅ {skill_md.parent.name}/SKILL.md: updated to {version}")
                updated += 1
        except Exception as e:
            print(f"  ⚠️  {skill_md}: {e}")

    return updated


def create_git_tag(version: str) -> None:
    tag = f"v{version}"
    # 检查 tag 是否已存在
    result = subprocess.run(
        ["git", "tag"], capture_output=True, text=True
    )
    if tag in result.stdout.splitlines():
        print(f"  ⚠️  Tag {tag} already exists")
        return

    subprocess.run(["git", "add", str(PLUGIN_JSON.relative_to(REPO_ROOT))], check=True)
    # 也 add 所有修改过的 SKILL.md
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True, text=True
    )
    for f in result.stdout.strip().splitlines():
        subprocess.run(["git", "add", f], check=True)

    # 如果有 staged 文件，先 amend（如果没有，用新 commit）
    subprocess.run(
        ["git", "tag", "-a", tag, "-m", f"Release {tag} — article-craft v{version}"],
        check=True
    )
    print(f"  ✅ Created git tag: {tag}")


def push_tag(version: str) -> None:
    tag = f"v{version}"
    print(f"\n  推送 tag 到远程:")
    print(f"    git push origin {tag}")
    print(f"\n  或推送所有:")
    print(f"    git push --tags")
    response = input(f"\n  立即推送? [y/N] ").strip().lower()
    if response == "y":
        result = subprocess.run(["git", "push", "origin", tag], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  ✅ 已推送: {tag}")
        else:
            print(f"  ❌ 推送失败: {result.stderr.strip()}")


def main():
    parser = argparse.ArgumentParser(description="Bump article-craft version")
    parser.add_argument(
        "bump",
        nargs="?",
        default="minor",
        choices=["major", "minor", "patch"],
        help="Version bump type (default: minor)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Only show what would change")
    parser.add_argument("--no-push", action="store_true", help="Skip push prompt")
    args = parser.parse_args()

    current = get_current_version()
    print(f"\n  article-craft version bump")
    print(f"  {'='*40}")
    print(f"  当前版本: {current}")

    if args.bump in ("major", "minor", "patch"):
        new_version = bump_version(current, args.bump)
        print(f"  目标版本: {new_version} ({args.bump})")
    else:
        new_version = args.bump
        print(f"  目标版本: {new_version} (直接指定)")

    if args.dry_run:
        print(f"\n  [dry-run] 以上为模拟结果，未实际修改")
        return

    print(f"\n  开始更新...")

    # Step 1: 更新 plugin.json
    update_plugin_json(new_version)

    # Step 2: 更新所有 SKILL.md
    updated_skills = update_skill_versions(new_version)

    # Step 3: Create git tag
    print(f"\n  创建 git tag v{new_version}...")
    create_git_tag(new_version)

    print(f"\n  {'='*40}")
    print(f"  ✅ 版本已更新: v{new_version}")
    print(f"  ✅ 更新了 {updated_skills} 个 skill SKILL.md")
    print(f"  {'='*40}")

    # Step 4: 提示推送
    if not args.no_push:
        push_tag(new_version)


if __name__ == "__main__":
    main()
