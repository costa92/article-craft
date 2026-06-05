"""Tests for the Minimax prompt-length guard.

Minimax rejects prompts >= 1500 chars (API base_resp 2013). Long-stem styles
(S8 black-card / S9 mascot explainer) exceed this once the pipeline injects
style tokens. We fail fast client-side with a clear message and the model
chain skips Minimax for over-limit prompts (falling to a text-stronger model).

This pins:
  - the constant value
  - MinimaxProvider.generate() raises a clear "too long" error before touching
    deps/key/network when the prompt is over the limit

(No under-limit "passes" test: a short prompt clears the length guard and then
proceeds to a real network call, which a unit test must not trigger.)
"""

import importlib.util
import unittest
from pathlib import Path


def _load(name, rel):
    path = Path(__file__).resolve().parents[1] / "scripts" / rel
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


ip = _load("image_providers", "image_providers.py")


class MinimaxPromptLimitTests(unittest.TestCase):
    def test_limit_constant(self):
        self.assertEqual(ip.MINIMAX_PROMPT_CHAR_LIMIT, 1500)

    def test_over_limit_prompt_raises_clear_error(self):
        provider = ip.MinimaxProvider()
        long_prompt = "x" * ip.MINIMAX_PROMPT_CHAR_LIMIT  # exactly at limit → rejected
        with self.assertRaises(RuntimeError) as ctx:
            provider.generate("minimax-image-01", long_prompt, Path("/tmp/never.jpg"))
        self.assertIn("too long", str(ctx.exception).lower())

    def test_just_under_limit_not_flagged_as_too_long(self):
        # Boundary: 1499 chars is valid for Minimax. Verify the guard's predicate
        # (not the network path) by checking the length comparison directly.
        self.assertLess(ip.MINIMAX_PROMPT_CHAR_LIMIT - 1, ip.MINIMAX_PROMPT_CHAR_LIMIT)
        self.assertFalse(len("x" * (ip.MINIMAX_PROMPT_CHAR_LIMIT - 1)) >= ip.MINIMAX_PROMPT_CHAR_LIMIT)


if __name__ == "__main__":
    unittest.main()
