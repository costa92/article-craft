r"""Tone-calibration logging must resolve its cache dir through config.cache_dir()
so a `~`-prefixed ARTICLE_CRAFT_CACHE_DIR override is expanded.

Bug: _maybe_log_tone_calibration wrapped the raw env value in Path(...) with no
expanduser, unlike config.cache_dir() / the other cache writers. With
ARTICLE_CRAFT_CACHE_DIR=~/foo the file landed in a literal ./~/foo directory
relative to cwd, diverging from every other cache.
"""

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


def load_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "review_selfcheck.py"
    spec = importlib.util.spec_from_file_location("review_selfcheck", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


rs = load_module()


class ToneCalibrationCacheDirTests(unittest.TestCase):
    def test_tilde_override_is_expanded(self):
        with tempfile.TemporaryDirectory() as home:
            # Point HOME at a temp dir and use a ~-relative override.
            old_home = os.environ.get("HOME")
            old_cache = os.environ.get("ARTICLE_CRAFT_CACHE_DIR")
            old_calib = os.environ.get("ARTICLE_CRAFT_TONE_CALIBRATION")
            try:
                os.environ["HOME"] = home
                os.environ["ARTICLE_CRAFT_CACHE_DIR"] = "~/acache"
                os.environ["ARTICLE_CRAFT_TONE_CALIBRATION"] = "true"
                rs._maybe_log_tone_calibration(
                    tone="neutral", writing_style="A", article_content="x",
                    metrics={}, violations=[], passed=True,
                )
                expanded = Path(home) / "acache" / "tone-calibration.jsonl"
                literal = Path("~/acache") / "tone-calibration.jsonl"
                self.assertTrue(expanded.exists(), "expected file at expanded ~ path")
                self.assertFalse(literal.exists(), "must not create a literal ./~/ dir")
            finally:
                for k, v in (("HOME", old_home),
                             ("ARTICLE_CRAFT_CACHE_DIR", old_cache),
                             ("ARTICLE_CRAFT_TONE_CALIBRATION", old_calib)):
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
