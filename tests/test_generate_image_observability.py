"""The Minimax success path must be observable.

Bug: in generate_image the Minimax branch did `config.local_path = ...; return
True` silently — no "使用 minimax" log and no record of which model produced the
image, while the Gemini branch logs "✅ 生成成功 (使用 X)". A user watching the
output (which lists Gemini in the fallback chain) could not tell Minimax was
actually used, nor that a silent fallback to Gemini had happened.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def _load():
    p = Path(__file__).resolve().parents[1] / "scripts" / "generate_and_upload_images.py"
    spec = importlib.util.spec_from_file_location("images_obs_test", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["images_obs_test"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load()


def test_minimax_success_is_observable(mod, monkeypatch, tmp_path, capsys):
    import config

    # Chain = minimax only; pretend its key is available.
    monkeypatch.setattr(mod, "MODEL_FALLBACK_CHAIN", ["minimax-image-01"])
    monkeypatch.setattr(config, "filter_chain_by_available_keys", lambda chain: ["minimax-image-01"])
    monkeypatch.setattr(mod, "ensure_images_dir", lambda: tmp_path)

    # Make the Minimax call "succeed" by writing the output file — no real API.
    def fake_minimax(model, prompt, output_path, **kw):
        Path(output_path).write_bytes(b"\xff\xd8\xff")
    monkeypatch.setattr(mod, "_generate_minimax_image_with_options", fake_minimax)

    cfg = mod.ImageConfig(name="封面", prompt="a red circle", aspect_ratio="1:1", filename="x.jpg")
    ok = mod.generate_image(cfg, model="minimax-image-01")

    assert ok is True
    # Programmatic record of which model produced the image.
    assert cfg.used_model == "minimax-image-01"
    # And a visible success line naming the model.
    out = capsys.readouterr().out
    assert "minimax-image-01" in out
    assert "成功" in out


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
