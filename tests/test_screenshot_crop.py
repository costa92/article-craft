"""Regression tests for screenshot height defaults + crop behavior.

Background: in v1.5.2 and earlier, capture_screenshot's --max-height
defaulted to 0 (no cropping), so element screenshots returned the full
height of the matched element. In practice that meant 1400px+ for
GitHub READMEs / docs sites — too tall for typical viewport reading.
v1.5.3 changed the default to 900 and moved crop application from
batch_capture's outer loop into capture_screenshot itself, so all
callers (CLI direct, batch, programmatic) benefit.
"""

import importlib.util
import inspect
import sys
import tempfile
from pathlib import Path

import pytest
from PIL import Image


def _load_module():
    p = Path(__file__).resolve().parents[1] / "scripts" / "screenshot_tool.py"
    spec = importlib.util.spec_from_file_location("screenshot_tool_crop_test", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["screenshot_tool_crop_test"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


def test_capture_screenshot_default_max_height_is_900(mod):
    """The default must be 900 (≈ one viewport), not 0 or some legacy value.

    If someone changes this without thinking, screenshots will silently
    grow back to 1400px+ and the original bug returns.
    """
    sig = inspect.signature(mod.capture_screenshot)
    assert sig.parameters["max_height"].default == 900


def test_crop_to_max_height_skips_when_image_already_short(mod, tmp_path):
    """No-op when the image is already shorter than max_height."""
    p = tmp_path / "short.png"
    Image.new("RGB", (800, 500), "white").save(p)
    cropped = mod.crop_to_max_height(str(p), 900)
    assert cropped is False
    assert Image.open(p).size == (800, 500)


def test_crop_to_max_height_crops_to_top_when_too_tall(mod, tmp_path):
    """Tall image gets cropped from the top down to max_height pixels."""
    p = tmp_path / "tall.png"
    Image.new("RGB", (800, 1500), "white").save(p)
    cropped = mod.crop_to_max_height(str(p), 900)
    assert cropped is True
    assert Image.open(p).size == (800, 900)


def test_crop_to_max_height_handles_exact_match(mod, tmp_path):
    """Image at exactly max_height is not cropped."""
    p = tmp_path / "exact.png"
    Image.new("RGB", (800, 900), "white").save(p)
    cropped = mod.crop_to_max_height(str(p), 900)
    assert cropped is False
    assert Image.open(p).size == (800, 900)


def test_screenshot_subcommand_max_height_default_in_argparse(mod):
    """The argparse default for the screenshot subcommand must also be 900.

    The signature default + the CLI default need to agree, otherwise
    using --max-height from CLI vs calling capture_screenshot() directly
    behaves inconsistently.
    """
    # We can't easily introspect argparse's defaults without invoking
    # main(), so probe by importing argparse and parsing a minimal
    # fake set of args. Instead, scan the source for the argparse
    # default to fail loud if someone changes it without thinking.
    src = (Path(__file__).resolve().parents[1] / "scripts" / "screenshot_tool.py").read_text()
    # Both `sc` and `ba` subparsers should declare default=900 for --max-height.
    occurrences = src.count('"--max-height", type=int, default=900')
    assert occurrences == 2, (
        f"Expected 2 argparse occurrences of --max-height default=900 "
        f"(screenshot + batch subcommands), found {occurrences}. "
        "Did you change one but forget the other?"
    )
