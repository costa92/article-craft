import importlib.util
import json
import sys
from pathlib import Path
from unittest import mock

import pytest


def _load_module():
    p = Path(__file__).resolve().parents[1] / "scripts" / "screenshot_tool.py"
    spec = importlib.util.spec_from_file_location("screenshot_tool_cli_test", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["screenshot_tool_cli_test"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


def _extract_json(print_mock):
    printed = "".join(call.args[0] for call in print_mock.call_args_list if call.args)
    return json.loads(printed)


def test_check_command_emits_standard_payload(mod):
    fake_status = {"status_code": 200, "is_valid": True, "reason": "Direct access"}
    with mock.patch.object(mod, "check_url_status", return_value=fake_status), \
         mock.patch.object(sys, "argv", ["screenshot_tool.py", "check", "https://example.com"]), \
         mock.patch("builtins.print") as print_mock:
        mod.main()
    payload = _extract_json(print_mock)
    assert payload["ok"] is True
    assert payload["message"] == "url check complete"
    assert payload["details"]["result"]["status_code"] == 200


def test_harvest_command_emits_standard_payload(mod):
    fake_harvest = {
        "source_url": "https://example.com/post",
        "title": "Demo",
        "cover": "",
        "captured_at": "2026-01-01T00:00:00Z",
        "method": "playwright",
        "images": [{"idx": 0, "url": "https://img.example.com/1.png"}],
        "warnings": [],
        "error": "",
    }
    with mock.patch.object(mod, "harvest_images", return_value=fake_harvest), \
         mock.patch.object(sys, "argv", ["screenshot_tool.py", "harvest", "https://example.com/post"]), \
         mock.patch("builtins.print") as print_mock:
        mod.main()
    payload = _extract_json(print_mock)
    assert payload["ok"] is True
    assert payload["message"] == "harvest complete"
    assert payload["details"]["result"]["method"] == "playwright"


def test_expand_harvest_command_emits_standard_payload_and_exit_code(mod):
    fake_expand = {"ok": False, "expanded": 0, "failed": 1, "trace": []}
    with mock.patch.object(mod, "expand_harvest", return_value=fake_expand), \
         mock.patch.object(sys, "argv", ["screenshot_tool.py", "expand-harvest", "--article", "/tmp/article.md"]), \
         mock.patch("builtins.print") as print_mock, \
         pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1
    payload = _extract_json(print_mock)
    assert payload["ok"] is False
    assert payload["message"] == "expand-harvest complete"
    assert payload["details"]["result"]["failed"] == 1
