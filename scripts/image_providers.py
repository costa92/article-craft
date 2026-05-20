"""Image-provider abstraction (B7 Phase 1).

One Protocol + a tiny registry. Built-in providers wrap the two existing
backends (Minimax HTTP + Gemini SDK). Adding a third provider means
subclassing :class:`ImageProvider` and calling :func:`register` — no
edits to ``generate_and_upload_images.py`` / ``nanobanana.py`` /
``config.filter_chain_by_available_keys`` required.

Phase 1 is deliberately net-zero behaviour change:

- The hot ``MinimaxProvider.generate`` body is byte-for-byte the same HTTP
  call as the previous ``_generate_minimax_image_with_options``.
- The ``GeminiProvider.generate`` body is the same SDK call as the
  previous ``nanobanana._generate_single_model``.
- Existing module-level functions (``_generate_minimax_image*`` in the
  batch file, ``_generate_single_*`` in nanobanana) stay as thin shims
  so tests that mock them by name still work.

Future phases (see ``docs/superpowers/specs/2026-05-20-multi-provider-image-abstraction.md``):

- Phase 2 adds ``OpenAIImageProvider``
- Phase 3 adds a self-hosted provider (Stable Diffusion / Replicate)
- Phase 4 namespaces per-provider config under ``image_providers`` key

The registry is **compile-time** — `register()` is called once at module
import for each built-in. Forks add a provider by editing this file.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Protocol, runtime_checkable

# --------------------------------------------------------------------- #
# Optional deps — providers import lazily so the module loads even when
# Gemini / requests aren't installed. Concrete `is_configured()` /
# `generate()` calls fail loudly when their dep is missing.
# --------------------------------------------------------------------- #
try:
    import requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    requests = None  # type: ignore[assignment]
    _REQUESTS_AVAILABLE = False

try:
    from google import genai  # noqa: F401
    from google.genai import types as _genai_types  # noqa: F401
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


# --------------------------------------------------------------------- #
# Shared helpers — env.json resolution, common errors
# --------------------------------------------------------------------- #

_MINIMAX_API_URL = "https://api.minimaxi.com/v1/image_generation"
_DEFAULT_REQUEST_TIMEOUT = 120


def _load_env_json() -> dict:
    """Resolve ~/.claude/env.json silently (returns {} on missing/invalid).

    Prefers ``config._user_config`` when ``config`` is importable — that
    keeps a single source of truth for env.json across the codebase and
    lets tests monkey-patch ``config._user_config`` without also having
    to patch this function.
    """
    try:
        import config as _cfg  # type: ignore[import-not-found]
        return getattr(_cfg, "_user_config", None) or {}
    except ImportError:
        pass
    path = Path(os.path.expanduser("~/.claude/env.json"))
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _env_or_json(env_var: str, json_key: str) -> str:
    """Return env var if set + non-empty, else env.json key, else ''."""
    val = os.environ.get(env_var, "").strip()
    if val:
        return val
    return str(_load_env_json().get(json_key, "")).strip()


class NoImageDataError(Exception):
    """API returned 200-ish but the payload contained no image bytes.

    Callers should treat this as recoverable — try the next model in the
    fallback chain rather than failing the whole batch.
    """


# --------------------------------------------------------------------- #
# Protocol
# --------------------------------------------------------------------- #


@runtime_checkable
class ImageProvider(Protocol):
    """Contract for an image-generation backend.

    Lifecycle:
      1. ``is_configured()`` is called early — by ``filter_chain_by_available_keys``
         and by ``doctor`` preflight. Returns False if the provider's API
         key isn't set; the model is pruned from the fallback chain.
      2. ``generate(...)`` is called per image. Raises
         :class:`NoImageDataError` when the API returned no image bytes
         (recoverable). Raises ``RuntimeError`` (with provider-tagged
         message) for hard failures. The pipeline-level
         ``RateLimitExhausted`` is raised by the caller after the
         **whole** fallback chain is exhausted — providers don't raise it.
      3. ``model_names()`` returns the canonical model strings this
         provider handles. The fallback chain matches a chain entry to
         a provider via this list.

    Implementations are stateless. Provider instances may be shared across
    parallel workers — the rate-limit coordinator relies on this.
    """

    name: str

    def model_names(self) -> List[str]: ...

    def is_configured(self) -> bool: ...

    def generate(
        self,
        model: str,
        prompt: str,
        output_path: Path,
        *,
        aspect_ratio: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        resolution: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None: ...


# --------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------- #


_REGISTRY: "dict[str, ImageProvider]" = {}


def register(provider: ImageProvider) -> None:
    """Register a provider. Called at module import for each built-in.

    Re-registering the same name silently replaces the previous entry
    (useful for tests that swap in a fake).
    """
    _REGISTRY[provider.name] = provider


def unregister(name: str) -> None:
    """Drop a provider by name (test cleanup)."""
    _REGISTRY.pop(name, None)


def for_model(model: str) -> Optional[ImageProvider]:
    """Resolve a model name (e.g. 'minimax-image-01') to its provider, or None."""
    for provider in _REGISTRY.values():
        if model in provider.model_names():
            return provider
    return None


def configured_providers() -> List[ImageProvider]:
    """Providers whose API keys are set right now.

    Used by ``config.filter_chain_by_available_keys`` and ``doctor``.
    """
    return [p for p in _REGISTRY.values() if p.is_configured()]


def all_providers() -> List[ImageProvider]:
    """All registered providers (configured or not). Order is insertion order."""
    return list(_REGISTRY.values())


# --------------------------------------------------------------------- #
# Built-in: Minimax (HTTP)
# --------------------------------------------------------------------- #


def _minimax_model_name(model: str) -> str:
    """Public model name → Minimax internal alias.

    ``minimax-image-01`` is the alias the fallback chain uses; the API
    itself expects ``image-01``.
    """
    return "image-01" if model == "minimax-image-01" else model


class MinimaxProvider:
    """Direct HTTP call to https://api.minimaxi.com/v1/image_generation."""

    name = "minimax"

    def model_names(self) -> List[str]:
        return ["minimax-image-01"]

    def is_configured(self) -> bool:
        return bool(_env_or_json("MINIMAX_API_KEY", "minimax_api_key"))

    def generate(
        self,
        model: str,
        prompt: str,
        output_path: Path,
        *,
        aspect_ratio: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        resolution: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        if not _REQUESTS_AVAILABLE:
            raise RuntimeError("requests not installed (minimax provider needs it)")
        if not _PIL_AVAILABLE:
            raise RuntimeError("Pillow not installed (minimax provider needs it)")

        api_key = _env_or_json("MINIMAX_API_KEY", "minimax_api_key")
        if not api_key:
            raise RuntimeError("MINIMAX_API_KEY missing")

        payload = {
            "model": _minimax_model_name(model),
            "prompt": prompt,
            "response_format": "base64",
        }
        if aspect_ratio:
            payload["aspect_ratio"] = aspect_ratio
        if width and height:
            payload["width"] = width
            payload["height"] = height

        response = requests.post(
            _MINIMAX_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout or _DEFAULT_REQUEST_TIMEOUT,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Minimax API error {response.status_code}: {(response.text or '')[:200]}"
            )

        data = response.json() if response.text else {}
        image_b64 = (
            (data.get("data") or {}).get("image_base64")
            if isinstance(data, dict)
            else None
        )
        if isinstance(image_b64, list):
            image_b64 = image_b64[0] if image_b64 else None

        if image_b64:
            image = Image.open(BytesIO(base64.b64decode(image_b64)))
            image.save(output_path)
            return

        image_urls = (
            (data.get("data") or {}).get("image_urls")
            if isinstance(data, dict)
            else None
        ) or []
        if image_urls:
            img_resp = requests.get(
                image_urls[0], timeout=timeout or _DEFAULT_REQUEST_TIMEOUT
            )
            img_resp.raise_for_status()
            image = Image.open(BytesIO(img_resp.content))
            image.save(output_path)
            return

        raise NoImageDataError("No image data in Minimax response.")


# --------------------------------------------------------------------- #
# Built-in: Gemini (SDK)
# --------------------------------------------------------------------- #


class GeminiProvider:
    """google-genai SDK call.

    Supports the three image-capable models in the fallback chain:
    ``gemini-3-pro-image-preview``, ``gemini-3.1-flash-image-preview``,
    ``gemini-2.5-flash-image``.

    Note: width/height arguments are accepted but currently unused — the
    Gemini API takes ``image_size`` (1K/2K/4K) instead. The Phase 1 contract
    keeps these parameters in the protocol for cross-provider parity.
    """

    name = "gemini"

    # Default resolution if caller doesn't pass one.
    _DEFAULT_RESOLUTION = "1K"

    def model_names(self) -> List[str]:
        return [
            "gemini-3-pro-image-preview",
            "gemini-3.1-flash-image-preview",
            "gemini-2.5-flash-image",
        ]

    def is_configured(self) -> bool:
        return bool(_env_or_json("GEMINI_API_KEY", "gemini_api_key"))

    def generate(
        self,
        model: str,
        prompt: str,
        output_path: Path,
        *,
        aspect_ratio: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        resolution: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        if not _GENAI_AVAILABLE:
            raise RuntimeError("google-genai not installed (gemini provider needs it)")
        if not _PIL_AVAILABLE:
            raise RuntimeError("Pillow not installed (gemini provider needs it)")

        api_key = _env_or_json("GEMINI_API_KEY", "gemini_api_key")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY missing")

        # google-genai sometimes resolves keys from GOOGLE_API_KEY — drop
        # it to keep this call deterministic.
        if "GOOGLE_API_KEY" in os.environ:
            del os.environ["GOOGLE_API_KEY"]

        from google import genai
        from google.genai import types

        client_opts = {}
        if timeout:
            client_opts["http_options"] = {"timeout": timeout}
        client = genai.Client(api_key=api_key, **client_opts)

        image_config_kwargs = {}
        if aspect_ratio:
            image_config_kwargs["aspect_ratio"] = aspect_ratio
        image_config_kwargs["image_size"] = resolution or self._DEFAULT_RESOLUTION

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(**image_config_kwargs),
            ),
        )

        if (
            response.candidates is None
            or len(response.candidates) == 0
            or response.candidates[0].content is None
            or response.candidates[0].content.parts is None
        ):
            raise ValueError("No data received from the API.")

        saved = False
        for part in response.candidates[0].content.parts:
            if part.text is not None:
                # Surface narration the SDK occasionally emits — preserves
                # the v1.6.16 stdout shape callers rely on.
                print(f"{part.text}", end="")
            elif part.inline_data is not None and part.inline_data.data is not None:
                image = Image.open(BytesIO(part.inline_data.data))
                image.save(output_path)
                saved = True

        if not saved:
            raise NoImageDataError(
                "No image data in Gemini response. Try a more specific prompt."
            )


# --------------------------------------------------------------------- #
# Built-in registrations
# --------------------------------------------------------------------- #

register(MinimaxProvider())
register(GeminiProvider())


__all__ = [
    "ImageProvider",
    "MinimaxProvider",
    "GeminiProvider",
    "NoImageDataError",
    "register",
    "unregister",
    "for_model",
    "configured_providers",
    "all_providers",
]
