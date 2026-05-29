"""Tests for body-form resolution: levels enum, resolve_body_form() precedence + wechat_target alias."""

import sys
from pathlib import Path
from unittest import TestCase, main

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import config


class BodyFormLevelsTests(TestCase):
    def test_levels_enum_is_two_strings_in_order(self):
        self.assertEqual(config.BODY_FORM_LEVELS, ("wechat-native", "long-form"))

    def test_default_is_wechat_native(self):
        self.assertEqual(config.DEFAULT_BODY_FORM, "wechat-native")


class ResolveBodyFormTests(TestCase):
    def test_default_when_everything_missing(self):
        self.assertEqual(config.resolve_body_form(), "wechat-native")

    def test_cli_wins(self):
        self.assertEqual(
            config.resolve_body_form(cli_body_form="long-form",
                                     frontmatter_body_form="wechat-native",
                                     frontmatter_wechat_target=True),
            "long-form",
        )

    def test_frontmatter_body_form_wins_over_alias(self):
        self.assertEqual(
            config.resolve_body_form(frontmatter_body_form="long-form",
                                     frontmatter_wechat_target=True),
            "long-form",
        )

    def test_legacy_wechat_target_false_maps_to_long_form(self):
        self.assertEqual(
            config.resolve_body_form(frontmatter_wechat_target=False),
            "long-form",
        )

    def test_legacy_wechat_target_string_false_maps_to_long_form(self):
        # frontmatter parser yields strings, not bools
        self.assertEqual(
            config.resolve_body_form(frontmatter_wechat_target="false"),
            "long-form",
        )

    def test_wechat_target_true_stays_native(self):
        self.assertEqual(
            config.resolve_body_form(frontmatter_wechat_target=True),
            "wechat-native",
        )

    def test_invalid_values_degrade_to_default(self):
        self.assertEqual(
            config.resolve_body_form(cli_body_form="blog",
                                     frontmatter_body_form="zzz"),
            "wechat-native",
        )


if __name__ == "__main__":
    main()
