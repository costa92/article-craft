import importlib.util
import json
import sys
from pathlib import Path
from unittest import mock

import pytest


# Make scripts/ importable so the loaded module's `from config import ...`
# resolves even when this file runs on its own (not just inside the full suite
# where a sibling test happens to set sys.path first).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def _load_module():
    p = Path(__file__).resolve().parents[1] / "scripts" / "generate_and_upload_images.py"
    spec = importlib.util.spec_from_file_location("images_cli_test", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["images_cli_test"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


def _extract_json(print_mock):
    candidates = [call.args[0] for call in print_mock.call_args_list if call.args]
    for candidate in reversed(candidates):
        text = candidate.strip()
        if text.startswith("{") and text.endswith("}"):
            return json.loads(text)
    raise AssertionError("no JSON payload found in print output")


def test_check_mode_emits_standard_payload(mod):
    with mock.patch.object(mod, "check_dependencies", return_value=[]), \
         mock.patch.object(sys, "argv", ["generate_and_upload_images.py", "--check"]), \
         mock.patch("builtins.print") as print_mock, \
         pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 0
    payload = _extract_json(print_mock)
    assert payload["ok"] is True
    assert payload["message"] == "dependency check complete"
    assert payload["details"]["errors"] == []


def test_probe_mode_emits_standard_payload(mod):
    fake_completed = mock.Mock(returncode=0, stderr="")
    with mock.patch.object(mod, "MODEL_FALLBACK_CHAIN", ("minimax-image-01", "model-b")), \
         mock.patch.object(mod, "IMAGE_DEFAULTS", {"model": "minimax-image-01"}), \
         mock.patch.object(mod.os.path, "exists", return_value=True), \
         mock.patch.object(mod.os, "remove"), \
         mock.patch.object(mod.subprocess, "run", return_value=fake_completed), \
         mock.patch.object(sys, "argv", ["generate_and_upload_images.py", "--probe"]), \
         mock.patch("builtins.print") as print_mock, \
         pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 0
    payload = _extract_json(print_mock)
    assert payload["ok"] is True
    assert payload["message"] == "probe complete"
    assert payload["details"]["best_model"] == "minimax-image-01"
    assert any("BEST_MODEL:minimax-image-01" in call.args[0] for call in print_mock.call_args_list if call.args)


def test_process_file_missing_emits_standard_payload(mod):
    with mock.patch.object(mod.os.path, "exists", return_value=False), \
         mock.patch.object(sys, "argv", ["generate_and_upload_images.py", "--process-file", "/tmp/missing.md"]), \
         mock.patch("builtins.print") as print_mock, \
         pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1
    payload = _extract_json(print_mock)
    assert payload["ok"] is False
    assert payload["message"] == "process-file validation failed"
    assert payload["error_code"] == "process_file_missing"


def test_check_dependencies_accepts_minimax_only_and_s3(mod):
    with mock.patch.object(mod, "_minimax_api_key", return_value="minimax-key"), \
         mock.patch.object(mod, "S3_CONFIG", {"enabled": True}), \
         mock.patch.object(mod.subprocess, "run") as subproc_run:
        errors = mod.check_dependencies()

    assert errors == []
    subproc_run.assert_not_called()


def test_check_dependencies_skips_picgo_when_no_upload(mod):
    with mock.patch.object(mod, "_minimax_api_key", return_value="minimax-key"), \
         mock.patch.object(mod, "S3_CONFIG", {"enabled": False}), \
         mock.patch.object(mod.subprocess, "run") as subproc_run:
        errors = mod.check_dependencies(upload_required=False)

    assert errors == []
    subproc_run.assert_not_called()


def test_check_dependencies_blocks_without_minimax(mod):
    with mock.patch.object(mod, "_minimax_api_key", return_value=""), \
         mock.patch.object(mod, "S3_CONFIG", {"enabled": True}), \
         mock.patch.object(mod.subprocess, "run") as subproc_run:
        errors = mod.check_dependencies()

    assert any("MINIMAX_API_KEY" in err for err in errors)
    subproc_run.assert_not_called()


def test_generate_image_prefers_minimax_without_nanobanana(mod):
    cfg = mod.ImageConfig(name="cover", prompt="a test prompt", aspect_ratio="16:9", filename="cover.jpg")
    def fake_generate(model, prompt, output_path, aspect_ratio=None, width=None, height=None):
        output_path.write_bytes(b"fake-image")

    with mock.patch.dict("os.environ", {"MINIMAX_API_KEY": "test-key"}), \
         mock.patch.object(mod, "_generate_minimax_image_with_options", side_effect=fake_generate) as minimax_gen, \
         mock.patch.object(mod, "ensure_images_dir", return_value=Path("/tmp")), \
         mock.patch.object(mod.subprocess, "run") as subproc_run:
        ok = mod.generate_image(cfg, model="minimax-image-01")

    assert ok is True
    assert cfg.local_path == "/tmp/cover.jpg"
    minimax_gen.assert_called_once()
    subproc_run.assert_not_called()


def test_generate_image_passes_minimax_options(mod):
    cfg = mod.ImageConfig(name="cover", prompt="a test prompt", aspect_ratio="16:9", filename="cover.jpg", enhance=True)
    captured = {}

    def fake_enhance(prompt):
        return f"enhanced::{prompt}"

    def fake_generate(model, prompt, output_path, aspect_ratio=None, width=None, height=None):
        captured["model"] = model
        captured["prompt"] = prompt
        captured["aspect_ratio"] = aspect_ratio
        captured["width"] = width
        captured["height"] = height
        output_path.write_bytes(b"fake-image")

    with mock.patch.dict("os.environ", {"MINIMAX_API_KEY": "test-key"}), \
         mock.patch.object(mod, "enhance_prompt", side_effect=fake_enhance), \
         mock.patch.object(mod, "_generate_minimax_image_with_options", side_effect=fake_generate), \
         mock.patch.object(mod, "ensure_images_dir", return_value=Path("/tmp")), \
         mock.patch.object(mod.subprocess, "run") as subproc_run:
        ok = mod.generate_image(cfg, resolution="4K", model="minimax-image-01", enhance=True)

    assert ok is True
    assert captured["prompt"] == "enhanced::a test prompt"
    assert captured["aspect_ratio"] == "16:9"
    assert captured["width"] == 1344
    assert captured["height"] == 768
    subproc_run.assert_not_called()


def test_generate_image_minimax_enhance_uses_local_enhancer(mod):
    cfg = mod.ImageConfig(name="cover", prompt="a test prompt", aspect_ratio="16:9", filename="cover.jpg", enhance=True)
    captured = {}

    def fake_enhance(prompt):
        return f"enhanced::{prompt}"

    def fake_generate(model, prompt, output_path, aspect_ratio=None, width=None, height=None):
        captured["prompt"] = prompt
        output_path.write_bytes(b"fake-image")

    with mock.patch.dict("os.environ", {"MINIMAX_API_KEY": "test-key"}), \
         mock.patch.object(mod, "_enhance_prompt", side_effect=fake_enhance), \
         mock.patch.object(mod, "_generate_minimax_image_with_options", side_effect=fake_generate), \
         mock.patch.object(mod, "ensure_images_dir", return_value=Path("/tmp")), \
         mock.patch.object(mod.subprocess, "run") as subproc_run:
        ok = mod.generate_image(cfg, model="minimax-image-01")

    assert ok is True
    assert captured["prompt"] == "enhanced::a test prompt"
    subproc_run.assert_not_called()


def test_nabobanana_default_model_prefers_minimax(monkeypatch, tmp_path):
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "nanobanana.py"
    spec = importlib.util.spec_from_file_location("nanobanana_test", module_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["nanobanana_test"] = mod
    monkeypatch.setenv("HOME", str(tmp_path))
    spec.loader.exec_module(mod)

    with mock.patch.object(mod, "generate_image") as generate_image, \
         mock.patch.object(sys, "argv", ["nanobanana.py", "--prompt", "x", "--output", str(tmp_path / "out.png")]):
        mod.run(default_size="1344x768")

    assert generate_image.call_args.args[0] == "minimax-image-01"
