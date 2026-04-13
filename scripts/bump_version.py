#!/usr/bin/env python3
"""
article-craft Version Bump Script

用法:
    python3 bump_version.py              # 默认 minor bump
    python3 bump_version.py major        # 大版本: 1.3.4 → 2.0.0
    python3 bump_version.py minor        # 小版本: 1.3.4 → 1.4.0
    python3 bump_version.py patch        # 补丁版本: 1.3.4 → 1.3.5
    python3 bump_version.py 1.5.0        # 直接指定版本
    python3 bump_version.py patch --no-tag --no-push  # 只改文件

工作流程:
    1. 更新 .claude-plugin/plugin.json 中的 version 和 description
    2. 更新 .claude-plugin/marketplace.json 中的 plugins[0].version
    3. 更新 skills/*/SKILL.md frontmatter 的 version
    4. (可选) 创建 git tag v{version}
    5. (可选) 提示推送到远程

workflow 集成:
    `.github/workflows/tag-release.yml` 在 push 到 main 时会读取 plugin.json
    并自动创建 tag + release。所以常规流程不需要本地 tag:
        python3 scripts/bump_version.py patch --no-tag
        git commit -am "chore(release): vX.Y.Z"
        git push
"""

import argparse
import json
import re
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
REPO_ROOT = SCRIPT_DIR.parent
PLUGIN_JSON = REPO_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"
SKILLS_DIR = REPO_ROOT / "skills"

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


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

    # 同步 description 里嵌入的 "— vX.Y.Z" 尾标(如果存在)
    desc = data.get("description", "")
    new_desc = re.sub(r"v\d+\.\d+\.\d+", f"v{version}", desc)
    if new_desc != desc:
        data["description"] = new_desc

    with open(PLUGIN_JSON, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"  ✅ .claude-plugin/plugin.json: {old} → {version}")


def update_marketplace_json(version: str) -> None:
    """更新 .claude-plugin/marketplace.json 中第一个 plugin 的 version"""
    if not MARKETPLACE_JSON.exists():
        print(f"  ⚠️  {MARKETPLACE_JSON.relative_to(REPO_ROOT)} not found, skipping")
        return

    with open(MARKETPLACE_JSON) as f:
        data = json.load(f)

    plugins = data.get("plugins", [])
    if not plugins:
        print(f"  ⚠️  marketplace.json has no plugins[] entries, skipping")
        return

    old = plugins[0].get("version", "unknown")
    plugins[0]["version"] = version

    with open(MARKETPLACE_JSON, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"  ✅ .claude-plugin/marketplace.json: {old} → {version}")


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


def parse_bump_arg(value: str) -> str:
    """Accept either major/minor/patch or an explicit X.Y.Z version string."""
    if value in ("major", "minor", "patch"):
        return value
    if VERSION_RE.match(value):
        return value
    raise argparse.ArgumentTypeError(
        f"must be 'major' / 'minor' / 'patch' or an explicit X.Y.Z version, got {value!r}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Bump article-craft version (plugin.json + marketplace.json + all SKILL.md)"
    )
    parser.add_argument(
        "bump",
        nargs="?",
        default="minor",
        type=parse_bump_arg,
        help="major | minor | patch | X.Y.Z (default: minor)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only show what would change")
    parser.add_argument("--no-tag", action="store_true", help="Skip local git tag creation (workflow does it on push)")
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

    if new_version == current:
        print(f"\n  ⚠️  目标版本与当前版本相同，无需更改")
        return

    if args.dry_run:
        print(f"\n  [dry-run] 以上为模拟结果，未实际修改")
        return

    print(f"\n  开始更新...")

    # Step 1: plugin.json (version + description)
    update_plugin_json(new_version)

    # Step 2: marketplace.json
    update_marketplace_json(new_version)

    # Step 3: 所有 SKILL.md
    updated_skills = update_skill_versions(new_version)

    # Step 4: 可选 — 创建 git tag
    if not args.no_tag:
        print(f"\n  创建 git tag v{new_version}...")
        create_git_tag(new_version)

    print(f"\n  {'='*40}")
    print(f"  ✅ 版本已更新: v{new_version}")
    print(f"  ✅ 更新了 {updated_skills} 个 skill SKILL.md")
    if args.no_tag:
        print(f"  ⏭️  跳过本地 tag 创建 (workflow 会在 push 后创建)")
    print(f"  {'='*40}")

    # Step 5: 可选 — 提示推送(仅当创建了 tag 时)
    if not args.no_tag and not args.no_push:
        push_tag(new_version)


if __name__ == "__main__":
    main()
