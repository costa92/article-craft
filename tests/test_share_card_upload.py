import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


def _load_module():
    p = Path(__file__).resolve().parents[1] / "scripts" / "share_card.py"
    spec = importlib.util.spec_from_file_location("share_card_for_test", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["share_card_for_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_upload_all_prefers_shared_uploader():
    mod = _load_module()
    fake_upload = mock.Mock(side_effect=[
        "https://cdn.example.com/a.png",
        "https://cdn.example.com/b.png",
    ])
    fake_module = SimpleNamespace(upload_image=fake_upload)
    results = [
        {"success": True, "platform": "wechat-cover", "output_path": "/tmp/a.png"},
        {"success": True, "platform": "twitter", "output_path": "/tmp/b.png"},
        {"success": False, "platform": "zhihu", "error": "skip"},
    ]

    with mock.patch.dict(sys.modules, {"generate_and_upload_images": fake_module}):
        mod.upload_all(results)

    assert results[0]["cdn_url"] == "https://cdn.example.com/a.png"
    assert results[1]["cdn_url"] == "https://cdn.example.com/b.png"
    assert "cdn_url" not in results[2]
    assert fake_upload.call_count == 2


def test_upload_all_shared_uploader_failure_keeps_local_only():
    mod = _load_module()
    fake_upload = mock.Mock(side_effect=RuntimeError("upload failed"))
    fake_module = SimpleNamespace(upload_image=fake_upload)
    results = [
        {"success": True, "platform": "wechat-cover", "output_path": "/tmp/a.png"},
    ]

    with mock.patch.dict(sys.modules, {"generate_and_upload_images": fake_module}):
        mod.upload_all(results)

    assert "cdn_url" not in results[0]
    fake_upload.assert_called_once_with("/tmp/a.png")
