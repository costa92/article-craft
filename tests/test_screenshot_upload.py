"""Regression tests for screenshot_tool.upload_to_cdn picgo parsing.

History: upload_to_cdn used to assume picgo emitted JSON on stdout. In
practice it emits multiple INFO/SUCCESS log lines followed by a bare URL.
The old parser ran json.loads on the full multi-line stdout (which always
fails) and then checked `output.startswith("http")` on that same multi-
line blob (also always fails), so it returned the local path and the
upstream caller silently treated every screenshot as "upload failed".
"""

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest


def _load_module():
    p = Path(__file__).resolve().parents[1] / "scripts" / "screenshot_tool.py"
    # screenshot_tool.py uses lazy sibling imports (`from uploaders import …`,
    # `from generate_and_upload_images import …`). In production scripts/ is
    # sys.path[0]; replicate that here so those imports resolve deterministically
    # instead of depending on whether another test already added scripts/ to the
    # path. Without this, `from uploaders import parse_picgo_output` raises
    # ModuleNotFoundError → upload_to_cdn silently returns the local path.
    scripts_dir = str(p.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("screenshot_tool_for_test", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["screenshot_tool_for_test"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


def _stub_run(stdout: str, returncode: int = 0):
    return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)


@pytest.fixture
def no_shared_uploader():
    """Hermetically disable the shared uploader so upload_to_cdn falls through
    to the PicGo branch these tests target.

    upload_to_cdn() tries `from generate_and_upload_images import upload_image`
    FIRST. In a credentialed environment the real upload_image actually uploads
    to the production CDN and returns a live URL — so without this fixture the
    PicGo-parsing tests (a) never reach the mocked PicGo branch, (b) assert
    against a real CDN URL → flaky, and (c) pollute the image repo with junk
    uploads on every test run. Stubbing it to raise routes execution into the
    PicGo path with zero network.
    """
    raising = SimpleNamespace(
        upload_image=mock.Mock(side_effect=RuntimeError("shared uploader disabled in test"))
    )
    with mock.patch.dict(sys.modules, {"generate_and_upload_images": raising}):
        yield


def test_picgo_multiline_log_then_bare_url(mod, no_shared_uploader):
    """The real-world picgo output: log lines + a final URL line."""
    fake = (
        "[PicGo INFO]: Before transform\n"
        "[PicGo INFO]: Transforming... Current transformer is [path]\n"
        "[PicGo INFO]: Before upload\n"
        "[PicGo INFO]: Uploading to GitHub\n"
        "[PicGo SUCCESS]:\n"
        "https://cdn.jsdelivr.net/gh/foo/bar/img.png\n"
    )
    with mock.patch.object(mod.shutil, "which", return_value="/usr/bin/picgo"), \
         mock.patch.object(mod.subprocess, "run", return_value=_stub_run(fake)):
        assert mod.upload_to_cdn("/tmp/img.png") == \
            "https://cdn.jsdelivr.net/gh/foo/bar/img.png"


def test_upload_to_cdn_prefers_shared_uploader(mod):
    fake_uploader = mock.Mock(return_value="https://cdn.example.com/shared.png")
    fake_module = SimpleNamespace(upload_image=fake_uploader)
    with mock.patch.dict(sys.modules, {"generate_and_upload_images": fake_module}):
        assert mod.upload_to_cdn("/tmp/img.png") == "https://cdn.example.com/shared.png"
    fake_uploader.assert_called_once_with("/tmp/img.png")


def test_upload_to_cdn_shared_uploader_failure_returns_local_path(mod):
    fake_uploader = mock.Mock(side_effect=RuntimeError("upload failed"))
    fake_module = SimpleNamespace(upload_image=fake_uploader)
    # When the shared uploader raises, upload_to_cdn falls through to the PicGo
    # branch. Mock picgo as absent so it deterministically returns the local
    # path — otherwise it hits the machine's real (GitHub-configured) picgo and
    # performs a real upload.
    with mock.patch.dict(sys.modules, {"generate_and_upload_images": fake_module}), \
         mock.patch.object(mod.shutil, "which", return_value=None):
        assert mod.upload_to_cdn("/tmp/img.png") == "/tmp/img.png"
    fake_uploader.assert_called_once_with("/tmp/img.png")


def test_picgo_json_dict_format(mod, no_shared_uploader):
    """Future-proof: if picgo ever switches to JSON dict output."""
    fake = '{"url": "https://cdn.example.com/x.png"}'
    with mock.patch.object(mod.shutil, "which", return_value="/usr/bin/picgo"), \
         mock.patch.object(mod.subprocess, "run", return_value=_stub_run(fake)):
        assert mod.upload_to_cdn("/tmp/img.png") == "https://cdn.example.com/x.png"


def test_picgo_json_list_format(mod, no_shared_uploader):
    """Future-proof: list-of-objects JSON variant."""
    fake = '[{"url": "https://cdn.example.com/y.png"}]'
    with mock.patch.object(mod.shutil, "which", return_value="/usr/bin/picgo"), \
         mock.patch.object(mod.subprocess, "run", return_value=_stub_run(fake)):
        assert mod.upload_to_cdn("/tmp/img.png") == "https://cdn.example.com/y.png"


def test_picgo_no_url_returns_local_path(mod, no_shared_uploader):
    """When picgo output has no parseable URL, fall back to the local path."""
    fake = "[PicGo ERROR]: upload failed\n"
    with mock.patch.object(mod.shutil, "which", return_value="/usr/bin/picgo"), \
         mock.patch.object(mod.subprocess, "run", return_value=_stub_run(fake)):
        assert mod.upload_to_cdn("/tmp/img.png") == "/tmp/img.png"


def test_picgo_not_installed_returns_local_path(mod, no_shared_uploader):
    """No picgo on PATH → return the local path unchanged."""
    with mock.patch.object(mod.shutil, "which", return_value=None):
        assert mod.upload_to_cdn("/tmp/img.png") == "/tmp/img.png"


def test_picgo_nonzero_exit_returns_local_path(mod, no_shared_uploader):
    """picgo crashed → return local path."""
    fake = "[PicGo ERROR]: ...\n"
    with mock.patch.object(mod.shutil, "which", return_value="/usr/bin/picgo"), \
         mock.patch.object(mod.subprocess, "run", return_value=_stub_run(fake, returncode=1)):
        assert mod.upload_to_cdn("/tmp/img.png") == "/tmp/img.png"
