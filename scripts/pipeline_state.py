#!/usr/bin/env python3
"""
Pipeline state management between article-craft skills.

Provides a simple JSON state file that skills can read/write to coordinate
pipeline status and pass context between stages.

Usage:
    from pipeline_state import PipelineState

    ps = PipelineState("/path/to/article.md")
    ps.mark_started("images")
    # ... do work ...
    ps.mark_completed("images", {"generated": 3, "uploaded": 3})

    # In next skill:
    ps = PipelineState("/path/to/article.md")
    if ps.is_stage_complete("images"):
        print("Images already done, skipping")
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

STATE_FILENAME = ".article-craft-state.json"

# Standard stage names
STAGES = [
    "requirements", "verify", "write", "screenshot",
    "images", "review_selfcheck", "review_scorer", "publish"
]


class PipelineState:
    """Manages a per-article state file at {article_dir}/.article-craft-state.json"""

    def __init__(self, article_path: str):
        self.article_path = Path(article_path).resolve()
        self.state_file = self.article_path.parent / STATE_FILENAME
        self._state = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {
            "article": str(self.article_path),
            "created_at": time.time(),
            "stages": {},
        }

    def save(self) -> None:
        self.state_file.write_text(
            json.dumps(self._state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def mark_started(self, stage: str) -> None:
        self._state["stages"][stage] = {
            "status": "running",
            "started_at": time.time(),
            "completed_at": None,
            "result": None,
        }
        self.save()

    def mark_completed(self, stage: str, result: Any = None) -> None:
        if stage not in self._state["stages"]:
            self._state["stages"][stage] = {"started_at": time.time()}
        self._state["stages"][stage].update({
            "status": "completed",
            "completed_at": time.time(),
            "result": result,
        })
        self.save()

    def mark_failed(self, stage: str, error: str) -> None:
        if stage not in self._state["stages"]:
            self._state["stages"][stage] = {"started_at": time.time()}
        self._state["stages"][stage].update({
            "status": "failed",
            "completed_at": time.time(),
            "result": {"error": error},
        })
        self.save()

    def get_stage(self, stage: str) -> Optional[Dict]:
        return self._state["stages"].get(stage)

    def is_stage_complete(self, stage: str) -> bool:
        s = self.get_stage(stage)
        return s is not None and s.get("status") == "completed"

    def get_all_stages(self) -> Dict:
        return self._state["stages"].copy()

    def get_article_path(self) -> str:
        return self._state.get("article", str(self.article_path))

    def cleanup(self) -> None:
        if self.state_file.exists():
            self.state_file.unlink()


if __name__ == "__main__":
    import tempfile, os

    print("Testing PipelineState...")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("# Test Article\n")
        temp_file = f.name

    try:
        ps = PipelineState(temp_file)

        # Test mark_started
        ps.mark_started("images")
        assert ps.get_stage("images")["status"] == "running"
        print("  ✅ mark_started works")

        # Test mark_completed
        ps.mark_completed("images", {"generated": 3})
        assert ps.is_stage_complete("images")
        assert ps.get_stage("images")["result"]["generated"] == 3
        print("  ✅ mark_completed works")

        # Test mark_failed
        ps.mark_failed("review", "score too low")
        assert ps.get_stage("review")["status"] == "failed"
        print("  ✅ mark_failed works")

        # Test persistence
        ps2 = PipelineState(temp_file)
        assert ps2.is_stage_complete("images")
        print("  ✅ persistence works")

        # Test cleanup
        ps.cleanup()
        assert not ps.state_file.exists()
        print("  ✅ cleanup works")

        print("\n✅ All PipelineState tests passed!")

    finally:
        os.unlink(temp_file)
