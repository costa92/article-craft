"""Regression: the cross-process verify cache must be written atomically.

Both write_verify_cache.save_cache and screenshot_tool's cache writer did
`open(path, "w")` + json.dump directly onto the live verify-cache.json. open("w")
truncates first, so a serialization failure mid-write (or two writers
interleaving) left a corrupt/empty cache. The file is an explicit cross-process
contract between the verify and screenshot skills — write to a temp file and
os.replace it in.
"""

import importlib.util
import json
import sys
from pathlib import Path


def _load(name):
    p = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"{name}_atomic_test", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


ORIGINAL = {"http://a": {"is_404": False}}
UNSERIALIZABLE = {"http://b": {1, 2, 3}}  # a set is not JSON-serializable


def test_write_verify_cache_save_is_atomic(tmp_path, monkeypatch):
    wv = _load("write_verify_cache")
    cache_file = tmp_path / "verify-cache.json"
    cache_file.write_text(json.dumps(ORIGINAL), encoding="utf-8")
    monkeypatch.setattr(wv, "CACHE_FILE", str(cache_file))

    wv.save_cache(UNSERIALIZABLE)  # fails to serialize; must not touch live file

    assert json.loads(cache_file.read_text(encoding="utf-8")) == ORIGINAL
    assert list(tmp_path.glob("*.tmp")) == []


def test_screenshot_save_verify_cache_is_atomic(tmp_path, monkeypatch):
    st = _load("screenshot_tool")
    cache_file = tmp_path / "verify-cache.json"
    cache_file.write_text(json.dumps(ORIGINAL), encoding="utf-8")
    monkeypatch.setattr(st, "VERIFY_CACHE_FILE", str(cache_file))

    try:
        st._save_verify_cache(UNSERIALIZABLE)
    except TypeError:
        pass  # serialization may raise; the point is the live file is intact

    assert json.loads(cache_file.read_text(encoding="utf-8")) == ORIGINAL
    assert list(tmp_path.glob("*.tmp")) == []


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
