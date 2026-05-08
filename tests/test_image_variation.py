"""Tests for image-variation system (Layer C of feat/image-variety).

Verifies that vary_prompt_for_position() injects camera + composition
directives per image index without breaking the locked-style prefix
that writers put at the start of each PROMPT.
"""

import sys
from pathlib import Path
from unittest import TestCase, main

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.generate_and_upload_images import (
    CAMERA_ROTATION,
    COMPOSITION_ROTATION,
    vary_prompt_for_position,
)


class CameraInjectionTests(TestCase):
    def test_cover_gets_first_camera_directive(self):
        result = vary_prompt_for_position("Minimalist flat illustration. Three boxes.", 0, 4)
        self.assertIn(f"Camera: {CAMERA_ROTATION[0]}", result)
        self.assertIn(f"Composition: {COMPOSITION_ROTATION[0]}", result)

    def test_index_rotates_camera_through_table(self):
        # 4 sibling images get 4 different camera directives.
        cameras_used = set()
        for i in range(4):
            result = vary_prompt_for_position("Style prefix. Content.", i, 4)
            for cam in CAMERA_ROTATION:
                if f"Camera: {cam}" in result:
                    cameras_used.add(cam)
                    break
        self.assertEqual(len(cameras_used), 4, "expected 4 distinct cameras for 4 images")

    def test_index_wraps_around_for_large_batches(self):
        # Image 6 wraps back to index 0 (since len(CAMERA_ROTATION) == 6)
        zero = vary_prompt_for_position("Base.", 0, 12)
        six = vary_prompt_for_position("Base.", 6, 12)
        # Both should reference camera index 0 when modulo wraps
        cam0 = CAMERA_ROTATION[0]
        self.assertIn(f"Camera: {cam0}", zero)
        self.assertIn(f"Camera: {cam0}", six)

    def test_locked_style_prefix_preserved(self):
        # Writers put style + palette + mood at the START of the PROMPT.
        # Augmentation must not corrupt or move that prefix.
        base = (
            "Minimalist isometric illustration, soft blue and teal palette, "
            "white background. A multi-layer architecture diagram with three boxes."
        )
        result = vary_prompt_for_position(base, 1, 4)
        # The locked prefix appears verbatim at the start.
        self.assertTrue(result.startswith(
            "Minimalist isometric illustration, soft blue and teal palette, "
            "white background. A multi-layer architecture diagram with three boxes"
        ))


class AuthorOverrideTests(TestCase):
    def test_skip_camera_injection_when_author_uses_camera_directive(self):
        # Author wrote `Camera: top-down view` — script should NOT inject another.
        base = "Flat illustration. Camera: top-down view. Three layers."
        result = vary_prompt_for_position(base, 1, 4)
        # The original Camera: directive is preserved, no second one appended
        self.assertEqual(result.count("Camera:"), 1)
        self.assertIn("Camera: top-down view", result)
        # Composition was NOT specified, so it should still be injected
        self.assertIn("Composition:", result)

    def test_skip_both_when_author_specified_both_directives(self):
        base = "Camera: top-down overhead view. Composition: centered subject. Three layers."
        result = vary_prompt_for_position(base, 2, 4)
        # When both directives are author-specified, the prompt is returned as-is
        self.assertEqual(result, base)

    def test_partial_override_still_injects_missing_axis(self):
        # Author specified Camera: directive but not Composition: — composition still injected.
        base = "Camera: isometric perspective view. Three layered boxes."
        result = vary_prompt_for_position(base, 1, 4)
        self.assertEqual(result.count("Camera:"), 1)  # not duplicated
        self.assertIn("Composition:", result)


class FalsePositiveRegressionTests(TestCase):
    """Regression tests for v0.1 false-positive bug:
    style adjectives like "isometric illustration" or "perspective view"
    were being interpreted as author camera directives, causing the script
    to skip injection. v0.2 fix: only match the literal `Camera:` /
    `Composition:` directive prefix, not loose adjectives."""

    def test_isometric_illustration_does_not_block_camera_injection(self):
        # "isometric illustration" is a STYLE preset (S2), NOT a camera directive.
        # Script should still inject Camera: based on image index.
        base = "Minimalist isometric illustration, blue and teal palette. Three boxes."
        result = vary_prompt_for_position(base, 1, 4)
        self.assertIn("Camera:", result, "isometric is a style word, not a camera directive")

    def test_perspective_word_in_content_does_not_block_camera(self):
        # "perspective" describes the topic (a developer's perspective), not framing
        base = "Flat illustration. A developer reviewing data from their perspective."
        result = vary_prompt_for_position(base, 2, 4)
        self.assertIn("Camera:", result)

    def test_centered_word_in_content_does_not_block_composition(self):
        # "centered" describes the subject (centered diagram), not the composition rule
        base = "Flat illustration. Three centered architecture boxes connected by arrows."
        result = vary_prompt_for_position(base, 1, 4)
        self.assertIn("Composition:", result)

    def test_data_viz_does_not_block_either(self):
        # "data visualization" historical false-positive on "viz/view"
        base = "Clean data visualization style, chart-inspired layout. Bar comparison."
        result = vary_prompt_for_position(base, 0, 4)
        self.assertIn("Camera:", result)
        self.assertIn("Composition:", result)


class StructuralTests(TestCase):
    def test_camera_rotation_has_six_unique_entries(self):
        self.assertEqual(len(CAMERA_ROTATION), 6)
        self.assertEqual(len(set(CAMERA_ROTATION)), 6)

    def test_composition_rotation_has_six_unique_entries(self):
        self.assertEqual(len(COMPOSITION_ROTATION), 6)
        self.assertEqual(len(set(COMPOSITION_ROTATION)), 6)

    def test_appended_directives_end_with_period(self):
        # Augmented prompt should be a clean sentence string
        result = vary_prompt_for_position("Base prompt", 0, 4)
        self.assertTrue(result.endswith("."))

    def test_no_double_periods_when_base_ends_with_period(self):
        result = vary_prompt_for_position("Base prompt.", 0, 4)
        # Augmented part is appended after stripping trailing period
        self.assertNotIn("..", result)
        self.assertNotIn("., ", result.rstrip("."))


if __name__ == "__main__":
    main()
