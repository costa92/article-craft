import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class DoctorTests(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.scripts_dir = self.repo_root / "scripts"
        self.env_backup = os.environ.copy()
        sys.path.insert(0, str(self.scripts_dir))

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.env_backup)
        if str(self.scripts_dir) in sys.path:
            sys.path.remove(str(self.scripts_dir))
        for name in ["setup_dependencies", "doctor"]:
            sys.modules.pop(name, None)

    def _load_modules(self, home: Path):
        os.environ["HOME"] = str(home)
        setup = load_module("setup_dependencies", self.scripts_dir / "setup_dependencies.py")
        doctor = load_module("doctor", self.scripts_dir / "doctor.py")
        return setup, doctor

    def test_doctor_blocks_when_minimax_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".claude").mkdir(parents=True, exist_ok=True)
            (home / ".claude" / "env.json").write_text("{}", encoding="utf-8")
            setup, doctor = self._load_modules(home)
            pass_result = setup._result("x", "pass", "ok")
            with mock.patch.dict(os.environ, {"MINIMAX_API_KEY": ""}, clear=False), \
                 mock.patch.object(setup, "run_all_checks", return_value=[pass_result, setup.check_minimax_api_key()]), \
                 mock.patch.object(doctor, "run_all_checks", return_value=[pass_result, setup.check_minimax_api_key()]):
                code = doctor.main(["check", "--json"])
            self.assertEqual(code, 2)

    def test_doctor_blocks_when_playwright_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg = home / ".claude"
            cfg.mkdir(parents=True, exist_ok=True)
            (cfg / "env.json").write_text('{"gemini_api_key":"x","s3":{"enabled":true}}', encoding="utf-8")
            setup, doctor = self._load_modules(home)
            play_block = setup._result("playwright", "block", "missing playwright")
            with mock.patch.object(doctor, "run_all_checks", return_value=[setup.check_gemini_api_key(), play_block]):
                code = doctor.main(["check", "--json"])
            self.assertEqual(code, 2)

    def test_check_playwright_falls_back_after_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg = home / ".claude"
            cfg.mkdir(parents=True, exist_ok=True)
            (cfg / "env.json").write_text('{"minimax_api_key":"x","s3":{"enabled":true}}', encoding="utf-8")
            setup, _doctor = self._load_modules(home)
            timeout = setup.subprocess.TimeoutExpired(cmd=["python3"], timeout=10)
            with mock.patch.object(setup.subprocess, "run", side_effect=timeout), \
                 mock.patch.object(setup, "_probe_playwright_inprocess", return_value="/tmp/chromium"):
                result = setup.check_playwright()
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["details"]["chromium_executable"], "/tmp/chromium")
            self.assertTrue(result["details"]["fallback_used"])

    def test_check_playwright_blocks_when_timeout_and_fallback_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg = home / ".claude"
            cfg.mkdir(parents=True, exist_ok=True)
            (cfg / "env.json").write_text('{"minimax_api_key":"x","s3":{"enabled":true}}', encoding="utf-8")
            setup, _doctor = self._load_modules(home)
            timeout = setup.subprocess.TimeoutExpired(cmd=["python3"], timeout=10)
            with mock.patch.object(setup.subprocess, "run", side_effect=timeout), \
                 mock.patch.object(setup, "_probe_playwright_inprocess", side_effect=OSError("fallback failed")):
                result = setup.check_playwright()
            self.assertEqual(result["status"], "block")
            self.assertIn("TimeoutExpired", result["message"])

    def test_doctor_warns_when_ytdlp_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg = home / ".claude"
            cfg.mkdir(parents=True, exist_ok=True)
            (cfg / "env.json").write_text('{"gemini_api_key":"x","s3":{"enabled":true}}', encoding="utf-8")
            setup, doctor = self._load_modules(home)
            with mock.patch.object(setup, "check_command_exists", side_effect=lambda cmd: False if cmd == "yt-dlp" else True):
                result = setup.check_ytdlp()
            self.assertEqual(result["status"], "warn")
            with mock.patch.object(doctor, "run_all_checks", return_value=[setup._result("a", "pass", "ok"), result]):
                code = doctor.main(["check", "--json"])
            self.assertEqual(code, 1)

    def test_doctor_warns_when_notebooklm_cli_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg = home / ".claude"
            cfg.mkdir(parents=True, exist_ok=True)
            (cfg / "env.json").write_text('{"minimax_api_key":"x","s3":{"enabled":true}}', encoding="utf-8")
            setup, doctor = self._load_modules(home)
            with mock.patch.object(setup, "check_command_exists", return_value=False):
                result = setup.check_notebooklm_cli()
            self.assertEqual(result["status"], "warn")
            with mock.patch.object(doctor, "run_all_checks", return_value=[setup._result("a", "pass", "ok"), result]):
                code = doctor.main(["check", "--json"])
            self.assertEqual(code, 1)

    def test_doctor_accepts_notebooklm_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg = home / ".claude"
            cfg.mkdir(parents=True, exist_ok=True)
            (cfg / "env.json").write_text('{"minimax_api_key":"x","s3":{"enabled":true}}', encoding="utf-8")
            setup, _doctor = self._load_modules(home)
            with mock.patch.object(setup, "check_command_exists", side_effect=lambda cmd: cmd == "notebooklm"):
                result = setup.check_notebooklm_cli()
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["details"]["command"], "notebooklm")
            self.assertEqual(result["details"]["flavor"], "research-cli")

    def test_doctor_accepts_nlm_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg = home / ".claude"
            cfg.mkdir(parents=True, exist_ok=True)
            (cfg / "env.json").write_text('{"minimax_api_key":"x","s3":{"enabled":true}}', encoding="utf-8")
            setup, _doctor = self._load_modules(home)
            with mock.patch.object(setup, "check_command_exists", side_effect=lambda cmd: cmd == "nlm"):
                result = setup.check_notebooklm_cli()
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["details"]["command"], "nlm")
            self.assertEqual(result["details"]["flavor"], "research-cli")

    def test_doctor_accepts_notebooklm_mcp_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg = home / ".claude"
            cfg.mkdir(parents=True, exist_ok=True)
            (cfg / "env.json").write_text('{"minimax_api_key":"x","s3":{"enabled":true}}', encoding="utf-8")
            setup, _doctor = self._load_modules(home)
            with mock.patch.object(setup, "check_command_exists", side_effect=lambda cmd: cmd == "notebooklm-mcp"):
                result = setup.check_notebooklm_cli()
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["details"]["command"], "notebooklm-mcp")
            self.assertEqual(result["details"]["flavor"], "mcp-compat")

    def test_doctor_warns_when_picgo_missing_but_not_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg = home / ".claude"
            cfg.mkdir(parents=True, exist_ok=True)
            (cfg / "env.json").write_text(
                '{"gemini_api_key":"x","s3":{"enabled":true},"upload_mode":"s3"}',
                encoding="utf-8",
            )
            setup, doctor = self._load_modules(home)
            with mock.patch.object(setup.shutil, "which", return_value=None):
                result = setup.check_picgo()
            self.assertEqual(result["status"], "warn")
            self.assertFalse(result["details"]["required"])
            with mock.patch.object(doctor, "run_all_checks", return_value=[setup._result("a", "pass", "ok"), result]):
                code = doctor.main(["check", "--json"])
            self.assertEqual(code, 1)

    def test_doctor_json_payload_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cfg = home / ".claude"
            cfg.mkdir(parents=True, exist_ok=True)
            (cfg / "env.json").write_text('{"gemini_api_key":"x","s3":{"enabled":true}}', encoding="utf-8")
            setup, doctor = self._load_modules(home)
            payload_checks = [
                setup._result("gemini_api_key", "pass", "ok"),
                setup._result("yt_dlp", "warn", "missing"),
            ]
            with mock.patch.object(doctor, "run_all_checks", return_value=payload_checks), \
                 mock.patch("builtins.print") as print_mock:
                code = doctor.main(["check", "--json"])
            self.assertEqual(code, 1)
            printed = "".join(call.args[0] for call in print_mock.call_args_list if call.args)
            payload = json.loads(printed)
            self.assertEqual(payload["status"], "warn")
            self.assertEqual(payload["summary"]["pass"], 1)
            self.assertEqual(payload["summary"]["warn"], 1)
            self.assertEqual(payload["summary"]["block"], 0)


    # --- B5: env_json / plugin_root / network_reachability checks ---

    def test_check_env_json_passes_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            setup, _doctor = self._load_modules(home)
            result = setup.check_env_json()
            self.assertEqual(result["status"], "pass")
            self.assertIn("not present", result["message"])

    def test_check_env_json_passes_when_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".claude").mkdir(parents=True, exist_ok=True)
            (home / ".claude" / "env.json").write_text('{"gemini_api_key": "x"}', encoding="utf-8")
            setup, _doctor = self._load_modules(home)
            result = setup.check_env_json()
            self.assertEqual(result["status"], "pass")

    def test_check_env_json_blocks_on_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".claude").mkdir(parents=True, exist_ok=True)
            (home / ".claude" / "env.json").write_text("{not valid json,}", encoding="utf-8")
            setup, doctor = self._load_modules(home)
            result = setup.check_env_json()
            self.assertEqual(result["status"], "block")
            self.assertIn("invalid JSON", result["message"])
            # And the doctor as a whole should exit 2 if env_json blocks.
            with mock.patch.object(doctor, "run_all_checks", return_value=[result]):
                code = doctor.main(["check", "--json"])
            self.assertEqual(code, 2)

    def test_check_env_json_warns_on_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".claude").mkdir(parents=True, exist_ok=True)
            (home / ".claude" / "env.json").write_text("", encoding="utf-8")
            setup, _doctor = self._load_modules(home)
            result = setup.check_env_json()
            self.assertEqual(result["status"], "warn")
            self.assertIn("empty", result["message"])

    def test_check_plugin_root_warns_when_unset(self):
        with tempfile.TemporaryDirectory() as tmp:
            setup, _doctor = self._load_modules(Path(tmp))
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
                result = setup.check_plugin_root()
            self.assertEqual(result["status"], "warn")

    def test_check_plugin_root_blocks_on_nonexistent_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            setup, _doctor = self._load_modules(Path(tmp))
            bogus = str(Path(tmp) / "does_not_exist_anywhere")
            with mock.patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": bogus}, clear=False):
                result = setup.check_plugin_root()
            self.assertEqual(result["status"], "block")

    def test_check_plugin_root_passes_when_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            setup, _doctor = self._load_modules(Path(tmp))
            with mock.patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": tmp}, clear=False):
                result = setup.check_plugin_root()
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["details"]["path"], tmp)

    def test_check_path_python3_blocks_when_critical_import_missing(self):
        """PATH python3 without PyYAML must block — skills invoke that binary."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            setup, _doctor = self._load_modules(home)
            fake_path_py = str(Path(tmp) / "fake-python3")
            with mock.patch.object(setup, "_path_python3", return_value=fake_path_py), \
                 mock.patch.object(
                     setup, "_probe_python_imports", return_value=["yaml"]
                 ), \
                 mock.patch.object(setup, "_same_python", return_value=False):
                result = setup.check_path_python3()
            self.assertEqual(result["status"], "block")
            self.assertIn("yaml", result["message"])
            self.assertIn("pip install", result["fix"])
            self.assertEqual(result["details"]["path_python3"], fake_path_py)

    def test_check_path_python3_passes_when_same_as_sys_and_imports_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            setup, _doctor = self._load_modules(home)
            with mock.patch.object(setup, "_path_python3", return_value=sys.executable), \
                 mock.patch.object(setup, "_probe_python_imports", return_value=[]), \
                 mock.patch.object(setup, "_same_python", return_value=True):
                result = setup.check_path_python3()
            self.assertEqual(result["status"], "pass")
            self.assertTrue(result["details"]["same_as_sys_executable"])

    def test_check_path_python3_warns_when_python3_missing_from_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            setup, _doctor = self._load_modules(home)
            with mock.patch.object(setup, "_path_python3", return_value=None):
                result = setup.check_path_python3()
            self.assertEqual(result["status"], "warn")
            self.assertIn("not found on PATH", result["message"])

    def test_script_entrypoints_also_probe_path_python_when_different(self):
        """Entrypoint check must fail under PATH python3 if that binary is broken."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            setup, _doctor = self._load_modules(home)
            path_py = str(Path(tmp) / "path-python3")

            def fake_run(python_bin, path, argv):
                # sys.executable ok; PATH binary fails
                if python_bin == path_py:
                    return "ModuleNotFoundError: No module named 'yaml'"
                return None

            with mock.patch.object(setup, "_path_python3", return_value=path_py), \
                 mock.patch.object(setup, "_same_python", return_value=False), \
                 mock.patch.object(setup, "_run_entrypoint", side_effect=fake_run):
                result = setup.check_script_entrypoints()
            self.assertEqual(result["status"], "block")
            self.assertTrue(
                any(k.endswith("@path") for k in result["details"]["failures"]),
                result["details"],
            )

    def test_network_check_excluded_by_default(self):
        """Default `doctor check` must NOT probe the network."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".claude").mkdir(parents=True, exist_ok=True)
            (home / ".claude" / "env.json").write_text(
                '{"gemini_api_key": "x", "minimax_api_key": "y"}', encoding="utf-8"
            )
            setup, doctor = self._load_modules(home)
            with mock.patch.object(setup, "_probe_url") as probe_mock:
                doctor.main(["check", "--json"])
            probe_mock.assert_not_called()

    def test_network_check_runs_with_flag(self):
        """`--network` enables the probe; mock the probe to avoid real HTTP."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".claude").mkdir(parents=True, exist_ok=True)
            (home / ".claude" / "env.json").write_text(
                '{"gemini_api_key": "x", "minimax_api_key": "y"}', encoding="utf-8"
            )
            setup, doctor = self._load_modules(home)
            with mock.patch.object(setup, "_probe_url", return_value=(True, "HTTP 200")) as probe_mock:
                doctor.main(["check", "--json", "--network"])
            # Two keys configured → two probes
            self.assertEqual(probe_mock.call_count, 2)

    def test_network_check_warns_when_no_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".claude").mkdir(parents=True, exist_ok=True)
            (home / ".claude" / "env.json").write_text("{}", encoding="utf-8")
            setup, _doctor = self._load_modules(home)
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("GEMINI_API_KEY", None)
                os.environ.pop("MINIMAX_API_KEY", None)
                with mock.patch.object(setup, "_probe_url") as probe_mock:
                    result = setup.check_network_reachability()
            self.assertEqual(result["status"], "warn")
            self.assertIn("nothing to probe", result["message"])
            probe_mock.assert_not_called()

    def test_network_check_warns_when_endpoint_unreachable(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".claude").mkdir(parents=True, exist_ok=True)
            (home / ".claude" / "env.json").write_text(
                '{"minimax_api_key": "x"}', encoding="utf-8"
            )
            setup, _doctor = self._load_modules(home)
            with mock.patch.object(setup, "_probe_url", return_value=(False, "DNS failed")):
                result = setup.check_network_reachability()
            self.assertEqual(result["status"], "warn")
            self.assertIn("unreachable", result["message"])
            self.assertIn("minimax", result["details"]["failures"])


if __name__ == "__main__":
    unittest.main()
