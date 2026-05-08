import importlib.util
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path


def load_config_module(home_dir: Path, extra_env: dict[str, str] | None = None):
    env_backup = os.environ.copy()
    try:
        os.environ["HOME"] = str(home_dir)
        if extra_env:
            os.environ.update(extra_env)

        module_path = Path(__file__).resolve().parents[1] / "scripts" / "config.py"
        module_name = f"config_test_{home_dir.name}"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module
    finally:
        os.environ.clear()
        os.environ.update(env_backup)


@contextmanager
def isolated_home(home_dir: Path, extra_env: dict[str, str] | None = None):
    """Run a block of code with HOME (and optional extra env vars) overridden.

    Use this when the code under test calls ``Path.home()`` or reads
    ``os.environ`` lazily (i.e. AFTER module import). ``load_config_module``
    only keeps env vars set during import, then restores them.
    """
    env_backup = os.environ.copy()
    try:
        os.environ["HOME"] = str(home_dir)
        if extra_env:
            os.environ.update(extra_env)
        yield
    finally:
        os.environ.clear()
        os.environ.update(env_backup)


class ConfigTests(unittest.TestCase):
    def test_load_user_config_reads_env_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg_dir = home / ".claude"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            (cfg_dir / "env.json").write_text(
                '{"gemini_api_key":"key-123","timeouts":{"upload":99}}',
                encoding="utf-8",
            )

            mod = load_config_module(home)

            self.assertEqual(mod._user_config["gemini_api_key"], "key-123")
            self.assertEqual(mod.TIMEOUTS["upload"], 99)
            self.assertEqual(mod.TIMEOUTS["image_generation"], 120)

    def test_load_user_config_falls_back_to_legacy_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".article-generator.conf").write_text(
                '{"gemini_api_key":"legacy-key"}',
                encoding="utf-8",
            )

            mod = load_config_module(home)

            self.assertEqual(mod._user_config["gemini_api_key"], "legacy-key")

    def test_s3_env_vars_override_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg_dir = home / ".claude"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            (cfg_dir / "env.json").write_text(
                '{"s3":{"enabled":true,"endpoint_url":"https://cfg.example","access_key_id":"cfg-ak","secret_access_key":"cfg-sk","bucket_name":"cfg-bucket","public_url_prefix":"https://cfg.cdn"}}',
                encoding="utf-8",
            )

            mod = load_config_module(
                home,
                {
                    "S3_ENDPOINT": "https://env.example",
                    "S3_ACCESS_KEY": "env-ak",
                    "S3_SECRET_KEY": "env-sk",
                    "S3_BUCKET": "env-bucket",
                    "S3_PUBLIC_URL": "https://env.cdn",
                },
            )

            self.assertTrue(mod.S3_CONFIG["enabled"])
            self.assertEqual(mod.S3_CONFIG["endpoint_url"], "https://env.example")
            self.assertEqual(mod.S3_CONFIG["access_key_id"], "env-ak")
            self.assertEqual(mod.S3_CONFIG["secret_access_key"], "env-sk")
            self.assertEqual(mod.S3_CONFIG["bucket_name"], "env-bucket")
            self.assertEqual(mod.S3_CONFIG["public_url_prefix"], "https://env.cdn")

    def test_model_defaults_remain_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = load_config_module(Path(tmp))

            self.assertEqual(mod.MODEL_FALLBACK_CHAIN[-1], "gemini-2.5-flash-image")
            self.assertEqual(mod.IMAGE_DEFAULTS["model"], "gemini-3-pro-image-preview")

    def test_text_model_default_and_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = load_config_module(Path(tmp))
            self.assertEqual(mod.TEXT_MODEL, "gemini-2.0-flash")

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg_dir = home / ".claude"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            (cfg_dir / "env.json").write_text(
                '{"gemini_text_model":"gemini-3-flash"}',
                encoding="utf-8",
            )
            mod = load_config_module(home)
            self.assertEqual(mod.TEXT_MODEL, "gemini-3-flash")

    def test_verify_cdn_whitelist_default_and_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod = load_config_module(Path(tmp))
            self.assertEqual(
                mod.VERIFY_CDN_WHITELIST,
                ["cdn.jsdelivr.net", "mmbiz.qpic.cn", "pbs.twimg.com"],
            )

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg_dir = home / ".claude"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            (cfg_dir / "env.json").write_text(
                '{"verify_cdn_whitelist":["my-cdn.example.com","cdn.jsdelivr.net"]}',
                encoding="utf-8",
            )
            mod = load_config_module(home)
            self.assertEqual(
                mod.VERIFY_CDN_WHITELIST,
                ["my-cdn.example.com", "cdn.jsdelivr.net"],
            )

    def test_cache_dir_default_and_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            mod = load_config_module(home)
            with isolated_home(home):
                d = mod.cache_dir()
                self.assertTrue(d.exists())
                self.assertEqual(d, home / ".cache" / "article-craft")

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            override = Path(tmp) / "custom-cache"
            mod = load_config_module(home, {"ARTICLE_CRAFT_CACHE_DIR": str(override)})
            with isolated_home(home, {"ARTICLE_CRAFT_CACHE_DIR": str(override)}):
                d = mod.cache_dir()
                self.assertTrue(d.exists())
                self.assertEqual(d, override)

    def test_share_card_logo_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            plugin_root = home / "plugin"
            (plugin_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
            (plugin_root / ".claude-plugin" / "plugin.json").write_text(
                '{"name":"my-fork"}', encoding="utf-8"
            )

            mod = load_config_module(home, {"CLAUDE_PLUGIN_ROOT": str(plugin_root)})
            with isolated_home(home, {"CLAUDE_PLUGIN_ROOT": str(plugin_root)}):
                self.assertEqual(mod.share_card_logo(), "my-fork")

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg_dir = home / ".claude"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            (cfg_dir / "env.json").write_text(
                '{"share_card_logo":"My Brand"}', encoding="utf-8"
            )
            mod = load_config_module(home)
            with isolated_home(home):
                self.assertEqual(mod.share_card_logo(), "My Brand")

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            nonexistent = home / "nonexistent"
            mod = load_config_module(home, {"CLAUDE_PLUGIN_ROOT": str(nonexistent)})
            with isolated_home(home, {"CLAUDE_PLUGIN_ROOT": str(nonexistent)}):
                self.assertEqual(mod.share_card_logo(), "article-craft")


if __name__ == "__main__":
    unittest.main()
