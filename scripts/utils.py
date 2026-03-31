#!/usr/bin/env python3
"""
文章生成器工具模块
包含智能占位符管理、目录匹配等辅助功能
"""

import os
import re
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any


class PlaceholderManager:
    """
    智能占位符管理器

    学习和建议图片提示词，管理占位符历史
    """

    def __init__(self, history_file: str = "~/.claude/article-gen-placeholder-history.json"):
        self.history_file = Path(history_file).expanduser()
        self.history = self._load_history()

    def _load_history(self) -> Dict[str, Any]:
        """加载历史记录"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "templates": {},  # {image_type: [prompt1, prompt2, ...]}
            "recent": []      # [{type: ..., prompt: ..., used_at: ...}]
        }

    def _save_history(self) -> None:
        """保存历史记录"""
        try:
            # 确保父目录存在
            self.history_file.parent.mkdir(exist_ok=True)
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️  保存占位符历史失败: {e}")

    def suggest_prompt(self, image_type: str, topic: Optional[str] = None) -> Optional[str]:
        """
        根据历史记录建议提示词

        Args:
            image_type: 图片类型（cover, architecture, diagram等）
            topic: 可选主题关键词

        Returns:
            建议的提示词，或None如果没有建议
        """
        # 按类型查找
        if image_type in self.history["templates"]:
            templates = self.history["templates"][image_type]
            if not templates:
                return None

            if topic:
                # 尝试匹配主题
                for t in templates:
                    if topic.lower() in t.lower():
                        return t

            # 返回最常用的（第一条）
            return templates[0]

        return None

    def learn_from_image(self, image_type: str, prompt: str) -> None:
        """
        从图片中学习好的提示词

        Args:
            image_type: 图片类型
            prompt: 提示词
        """
        if not prompt or len(prompt) < 10:
            return  # 跳过太短的提示词

        # 记录到模板
        if image_type not in self.history["templates"]:
            self.history["templates"][image_type] = []

        if prompt not in self.history["templates"][image_type]:
            self.history["templates"][image_type].insert(0, prompt)
            # 保持最多10个模板
            self.history["templates"][image_type] = self.history["templates"][image_type][:10]

        # 记录最近使用
        self.history["recent"].insert(0, {
            "type": image_type,
            "prompt": prompt,
            "used_at": time.time()
        })
        # 保持最近20条
        self.history["recent"] = self.history["recent"][:20]

        self._save_history()

    def get_recent_prompts(self, limit: int = 5) -> List[Dict]:
        """
        获取最近使用的提示词

        Args:
            limit: 返回数量限制

        Returns:
            最近提示词列表
        """
        return self.history["recent"][:limit]

    def clear_history(self) -> None:
        """清除历史记录"""
        self.history = {"templates": {}, "recent": []}
        if self.history_file.exists():
            self.history_file.unlink()


class SmartDirectoryMatcher:
    """
    智能目录匹配器

    基于文章内容自动学习和调整目录匹配策略
    """

    def __init__(self, kb_root: str = "~/docs"):
        self.kb_root = Path(kb_root).expanduser()
        self.rules_file = self.kb_root / ".article-gen-dir-rules.json"
        self.rules = self._load_rules()

    def _load_rules(self) -> Dict[str, Any]:
        """加载匹配规则"""
        if self.rules_file.exists():
            try:
                with open(self.rules_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "keywords": {},  # {keyword: directory}
            "patterns": [],  # [{pattern: regex, dir: directory}]
            "history": []     # [{title: "", dir: "", chosen: bool, timestamp: float}]
        }

    def _save_rules(self) -> None:
        """保存匹配规则"""
        try:
            # 确保父目录存在
            self.rules_file.parent.mkdir(exist_ok=True)
            with open(self.rules_file, 'w', encoding='utf-8') as f:
                json.dump(self.rules, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️  保存目录匹配规则失败: {e}")

    def match_directory(self, article_title: str, article_content: Optional[str] = None) -> Optional[str]:
        """
        智能匹配目录

        Args:
            article_title: 文章标题
            article_content: 可选文章内容

        Returns:
            匹配的目录路径，或None如果无法匹配
        """
        candidates = []

        # 1. 关键词匹配
        for keyword, dir_path in self.rules["keywords"].items():
            if keyword.lower() in article_title.lower():
                candidates.append((dir_path, "keyword", 10))

        # 2. 模式匹配
        for pattern_rule in self.rules["patterns"]:
            try:
                if re.search(pattern_rule["pattern"], article_title):
                    candidates.append((pattern_rule["dir"], "pattern", 8))
            except Exception:
                pass

        # 3. 历史匹配（基于类似文章）
        for hist in self.rules["history"][:20]:  # 最近20条
            if hist.get("chosen"):
                # 简单相似度：关键词重叠
                title_words = set(article_title.lower().split())
                hist_words = set(hist.get("title", "").lower().split())
                overlap = len(title_words & hist_words)
                if overlap > 0:
                    candidates.append((hist["dir"], "history", overlap * 2))

        # 排序并返回最佳匹配
        if candidates:
            candidates.sort(key=lambda x: x[2], reverse=True)
            return candidates[0][0]

        return None

    def learn_feedback(self, article_title: str, chosen_dir: str, is_correct: bool = True) -> None:
        """
        学习用户反馈

        Args:
            article_title: 文章标题
            chosen_dir: 选择的目录
            is_correct: 是否正确
        """
        # 记录历史
        self.rules["history"].insert(0, {
            "title": article_title,
            "dir": chosen_dir,
            "chosen": is_correct,
            "timestamp": time.time()
        })
        # 保持最近100条
        self.rules["history"] = self.rules["history"][:100]

        if is_correct:
            # 从标题提取关键词
            words = article_title.lower().split()
            # 中文停用词（简单版本）
            stop_words = {"的", "了", "和", "与", "在", "是", "为", "对", "用", "等", "这", "那"}

            for word in words:
                word = word.strip()
                if len(word) > 1 and word not in stop_words:
                    if word not in self.rules["keywords"]:
                        self.rules["keywords"][word] = chosen_dir
                        print(f"💡 学习关键词映射: '{word}' → '{chosen_dir}'")

        self._save_rules()

    def add_keyword_rule(self, keyword: str, directory: str) -> None:
        """
        添加关键词规则

        Args:
            keyword: 关键词
            directory: 目标目录
        """
        self.rules["keywords"][keyword.lower()] = directory
        self._save_rules()

    def add_pattern_rule(self, pattern: str, directory: str) -> None:
        """
        添加模式规则

        Args:
            pattern: 正则表达式模式
            directory: 目标目录
        """
        # 验证正则表达式
        try:
            re.compile(pattern)
            self.rules["patterns"].append({
                "pattern": pattern,
                "dir": directory
            })
            self._save_rules()
        except re.error as e:
            print(f"⚠️  无效的正则表达式: {e}")

    def get_rules(self) -> Dict[str, Any]:
        """获取当前规则"""
        return self.rules.copy()

    def clear_rules(self) -> None:
        """清除所有规则"""
        self.rules = {"keywords": {}, "patterns": [], "history": []}
        if self.rules_file.exists():
            self.rules_file.unlink()


# 全局单例实例
_placeholder_manager: Optional[PlaceholderManager] = None
_directory_matcher: Optional[SmartDirectoryMatcher] = None


def get_placeholder_manager() -> PlaceholderManager:
    """获取占位符管理器单例"""
    global _placeholder_manager
    if _placeholder_manager is None:
        _placeholder_manager = PlaceholderManager()
    return _placeholder_manager


def get_directory_matcher(kb_root: str = "~/docs") -> SmartDirectoryMatcher:
    """获取目录匹配器单例"""
    global _directory_matcher
    if _directory_matcher is None:
        _directory_matcher = SmartDirectoryMatcher(kb_root)
    return _directory_matcher


if __name__ == "__main__":
    # 简单测试
    print("Testing PlaceholderManager...")
    pm = PlaceholderManager()
    pm.learn_from_image("cover", "现代软件工作流程，极简插画风格，暖色调")
    pm.learn_from_image("architecture", "技术架构图，包含用户界面层、核心引擎层，使用蓝色调扁平设计")
    print(f"Suggested for cover: {pm.suggest_prompt('cover')}")
    print(f"Recent prompts: {pm.get_recent_prompts(2)}")

    print("\nTesting SmartDirectoryMatcher...")
    dm = SmartDirectoryMatcher("/tmp/test-kb")
    dm.learn_feedback("Docker 入门教程", "02-技术/基础设施/Docker", is_correct=True)
    dm.learn_feedback("Claude Code 高级用法", "02-技术/AI-生态/Claude-Code", is_correct=True)
    print(f"Matched for 'Docker': {dm.match_directory('Docker 入门教程')}")
    print(f"Rules: {dm.get_rules()}")
