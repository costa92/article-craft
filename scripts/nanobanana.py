#!/usr/bin/env python3
"""
Generate or edit images using Minimax first, with Gemini fallback.

This is the canonical implementation for article-craft images skill.
"""
import os
import sys
import argparse
import uuid
import time
import subprocess
import json
import base64
from functools import wraps

# Auto-check dependencies on import
try:
    from dotenv import load_dotenv
    from google import genai
    from google.genai import types
    from PIL import Image
    from io import BytesIO
    import requests
except ImportError as e:
    print(f"❌ 缺少依赖: {e}")
    print("🔧 正在自动安装依赖...\n")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    setup_script = os.path.join(script_dir, "setup_dependencies.py")

    if os.path.exists(setup_script):
        result = subprocess.run([sys.executable, setup_script])
        if result.returncode == 0:
            print("\n✅ 依赖安装完成，请重新运行此脚本")
        else:
            print("\n❌ 依赖安装失败，请手动运行:")
            print(f"   python3 {setup_script}")
        sys.exit(1)
    else:
        print(f"❌ 未找到 setup_dependencies.py: {setup_script}")
        print("请手动安装依赖: pip install google-genai Pillow python-dotenv")
        sys.exit(1)

# Import shared configuration
try:
    from config import ASPECT_RATIO_MAP, RETRY_CONFIG, MODEL_FALLBACK_CHAIN, TEXT_MODEL
except ImportError:
    ASPECT_RATIO_MAP = {
        "1024x1024": "1:1",
        "832x1248": "2:3",
        "1248x832": "3:2",
        "864x1184": "3:4",
        "1184x864": "4:3",
        "896x1152": "4:5",
        "1152x896": "5:4",
        "768x1344": "9:16",
        "1344x768": "16:9",
        "1536x672": "21:9",
    }
    RETRY_CONFIG = {
        "max_attempts": 4,
        "initial_delay": 3,
        "backoff_factor": 2,
        "retriable_errors": [
            "SSL", "ConnectionError", "TimeoutError", "NetworkError",
            "500", "502", "503", "504",
            "RemoteProtocolError", "Server disconnected", "disconnected",
            "UNAVAILABLE", "high demand", "No data received",
        ]
    }
    MODEL_FALLBACK_CHAIN = [
        "minimax-image-01",
        "gemini-3-pro-image-preview",
        "gemini-3.1-flash-image-preview",
        "gemini-2.5-flash-image",
    ]
    TEXT_MODEL = "gemini-2.0-flash"

# Overloaded error patterns (trigger model degradation)
_OVERLOADED_PATTERNS = ["503", "UNAVAILABLE", "high demand", "overloaded"]


class NoImageDataError(Exception):
    """API returned a response but contained no image data."""
    pass


def _minimax_model_name(model):
    return "image-01" if model == "minimax-image-01" else model

# Load env.json for configuration (model name, etc.)
_env_json_config = {}
_env_json_path = os.path.expanduser("~/.claude/env.json")
if os.path.exists(_env_json_path):
    try:
        with open(_env_json_path) as f:
            _env_json_config = json.load(f)
    except Exception:
        pass

def _gemini_api_key():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        val = _env_json_config.get("gemini_api_key", "")
        if val and not val.startswith("your-"):
            api_key = val
    if not api_key:
        dotenv_path = os.path.expanduser("~/.nanobanana.env")
        if os.path.exists(dotenv_path):
            load_dotenv(dotenv_path)
            api_key = os.getenv("GEMINI_API_KEY")
    return api_key


def _minimax_api_key():
    api_key = os.getenv("MINIMAX_API_KEY", "").strip()
    if api_key:
        return api_key
    return str(_env_json_config.get("minimax_api_key", "")).strip()


if "GOOGLE_API_KEY" in os.environ:
    del os.environ["GOOGLE_API_KEY"]

client = None

# Default request timeout (seconds). Overridden by --timeout CLI arg.
_request_timeout = None
_timeout_client = None


def _get_client(timeout=None):
    """Return a Gemini client with optional per-request timeout."""
    global _timeout_client, client
    api_key = _gemini_api_key()
    if not api_key:
        raise ValueError(
            "Missing GEMINI_API_KEY. Please configure in ~/.claude/env.json, environment, or ~/.nanobanana.env"
        )
    effective_timeout = timeout or _request_timeout
    if effective_timeout:
        if _timeout_client is None:
            _timeout_client = genai.Client(
                api_key=api_key,
                http_options={"timeout": effective_timeout},
            )
        return _timeout_client
    if client is None:
        client = genai.Client(api_key=api_key)
    return client


def retry_on_error(max_attempts=None, initial_delay=None, backoff_factor=None):
    """Retry on transient network/API errors with exponential backoff."""
    max_attempts = max_attempts or RETRY_CONFIG["max_attempts"]
    initial_delay = initial_delay or RETRY_CONFIG["initial_delay"]
    backoff_factor = backoff_factor or RETRY_CONFIG["backoff_factor"]

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_str = str(e)
                    is_retriable = any(
                        p in error_str for p in RETRY_CONFIG["retriable_errors"]
                    )
                    if not is_retriable or attempt >= max_attempts:
                        raise
                    print(f"⚠️  Attempt {attempt}/{max_attempts} failed: {error_str[:100]}")
                    print(f"   Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                    delay *= backoff_factor
        return wrapper
    return decorator


def enhance_prompt(original_prompt):
    """Enhance the prompt using Gemini text model for better image generation."""
    system_instruction = (
        "You are an expert AI art prompt engineer. "
        "Your task is to rewrite the input prompt into a detailed, high-quality image generation prompt "
        "suitable for a technical blog article. "
        "Vary the visual treatment based on the content: choose between minimalist flat, isometric, "
        "data-viz, line-art, conceptual scene, or bold infographic. Avoid reusing the same palette and framing "
        "across unrelated prompts. "
        "Avoid text in images. "
        "Output ONLY the enhanced prompt, no explanations."
    )

    response = _get_client().models.generate_content(
        model=TEXT_MODEL,
        contents=original_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7,
            max_output_tokens=200,
        )
    )

    if response.text:
        return response.text.strip()
    return original_prompt


# --------------------------------------------------------------------- #
# B7 Phase 1: provider-backed shims.
#
# The real generation logic now lives in
# ``scripts/image_providers.{MinimaxProvider, GeminiProvider}``. These
# wrappers preserve the public name + the `@retry_on_error()` decorator
# (the retry policy is a *caller* concern per the protocol contract).
# --------------------------------------------------------------------- #
try:
    from image_providers import (
        for_model as _provider_for_model,
        NoImageDataError as _ProviderNoImageDataError,
    )
    # Re-bind so callers catching nanobanana.NoImageDataError catch both.
    NoImageDataError = _ProviderNoImageDataError  # noqa: F811
except ImportError:  # pragma: no cover — only triggers if cwd setup is off
    _provider_for_model = None
    _ProviderNoImageDataError = NoImageDataError


def _gemini_provider():
    if _provider_for_model is None:
        raise RuntimeError("image_providers module not importable")
    p = _provider_for_model("gemini-3-pro-image-preview")
    if p is None:
        raise RuntimeError("GeminiProvider not registered")
    return p


def _minimax_provider():
    if _provider_for_model is None:
        raise RuntimeError("image_providers module not importable")
    p = _provider_for_model("minimax-image-01")
    if p is None:
        raise RuntimeError("MinimaxProvider not registered")
    return p


def _contents_to_prompt(contents):
    """Collapse the historical `contents` list/string into a single prompt str.

    The Gemini SDK accepts mixed lists (prompt + PIL images for editing);
    when no image is included we flatten to a string for provider parity.
    """
    if isinstance(contents, str):
        return contents
    parts = []
    for item in contents:
        if isinstance(item, str):
            parts.append(item)
    return "\n".join(parts)


@retry_on_error()
def _generate_single_model(model, contents, aspect_ratio, resolution, output_path):
    """Gemini single-model attempt — delegates to GeminiProvider.

    Edit mode (``contents`` includes PIL Image objects) still hits the SDK
    directly because the provider's ``generate()`` API takes a string
    prompt, not a mixed content list. This branch preserves the v1.6.16
    behaviour exactly.
    """
    has_image = any(not isinstance(c, str) for c in contents) if isinstance(contents, list) else False

    if has_image:
        # Edit mode — keep the existing inline SDK call (provider API
        # doesn't model image edit yet; deferred to Phase 2+).
        response = _get_client().models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio=aspect_ratio,
                    image_size=resolution,
                ),
            ),
        )

        if (
            response.candidates is None
            or len(response.candidates) == 0
            or response.candidates[0].content is None
            or response.candidates[0].content.parts is None
        ):
            raise ValueError("No data received from the API.")

        image_saved = False
        for part in response.candidates[0].content.parts:
            if part.text is not None:
                print(f"{part.text}", end="")
            elif part.inline_data is not None and part.inline_data.data is not None:
                image = Image.open(BytesIO(part.inline_data.data))
                image.save(output_path)
                image_saved = True
                print(f"\n\nImage saved to: {output_path}")

        if not image_saved:
            raise NoImageDataError(
                "No image data in API response. Try a more specific prompt."
            )
        return

    prompt = _contents_to_prompt(contents)
    _gemini_provider().generate(
        model,
        prompt,
        output_path,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        timeout=_request_timeout,
    )
    print(f"\n\nImage saved to: {output_path}")


@retry_on_error()
def _generate_single_minimax(model, contents, aspect_ratio, resolution, output_path):
    """Minimax single-model attempt — delegates to MinimaxProvider."""
    prompt = _contents_to_prompt(contents)
    _minimax_provider().generate(
        model,
        prompt,
        output_path,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        timeout=_request_timeout,
    )
    print(f"\n\nImage saved to: {output_path}")


def generate_image(model, contents, aspect_ratio, resolution, output_path, no_fallback=False):
    """
    Generate image with automatic model degradation on persistent 503/overloaded errors.

    Degradation chain (downward only): pro → 3.1-flash → 2.5-flash
    Never escalates to a more expensive model.
    """
    if no_fallback:
        # B7 Phase 1: route via the image-provider registry. Falls back to
        # the legacy startswith() check if the registry isn't reachable
        # (e.g. cwd has no scripts/ on the path — happens in some test
        # harnesses).
        is_minimax = False
        if _provider_for_model is not None:
            p = _provider_for_model(model)
            is_minimax = p is not None and p.name == "minimax"
        else:
            is_minimax = str(model).startswith("minimax")
        if is_minimax:
            return _generate_single_minimax(model, contents, aspect_ratio, resolution, output_path)
        return _generate_single_model(model, contents, aspect_ratio, resolution, output_path)

    # Build fallback chain: only include models at same level or cheaper
    chain = MODEL_FALLBACK_CHAIN.copy()
    if model in chain:
        idx = chain.index(model)
        chain = chain[idx:]  # Only this model and cheaper ones
    else:
        chain.insert(0, model)

    # B13: prune models lacking their provider key — otherwise the loop
    # below burns a guaranteed-fail attempt per generation.
    from config import filter_chain_by_available_keys
    raw_chain = list(chain)
    chain = filter_chain_by_available_keys(chain)
    if not chain:
        raise RuntimeError(
            "No image-provider API key configured. "
            "Set MINIMAX_API_KEY or GEMINI_API_KEY (env var or ~/.claude/env.json)."
        )
    if model in raw_chain and model not in chain:
        print(
            f"⚠️  Requested model '{model}' dropped — its provider key isn't set; "
            f"continuing with: {chain[0]}"
        )

    for i, fallback_model in enumerate(chain):
        try:
            # B7 Phase 1: provider-aware dispatch (mirrors the no_fallback
            # branch above).
            is_minimax = False
            if _provider_for_model is not None:
                p = _provider_for_model(fallback_model)
                is_minimax = p is not None and p.name == "minimax"
            else:
                is_minimax = str(fallback_model).startswith("minimax")
            if is_minimax:
                return _generate_single_minimax(fallback_model, contents, aspect_ratio, resolution, output_path)
            return _generate_single_model(fallback_model, contents, aspect_ratio, resolution, output_path)
        except NoImageDataError:
            # No image in response — try next model (might succeed with different model)
            if i < len(chain) - 1:
                print(f"\n⚠️  {fallback_model} returned no image, trying {chain[i + 1]}...")
                continue
            raise
        except Exception as e:
            error_str = str(e)
            is_overloaded = any(p in error_str for p in _OVERLOADED_PATTERNS)
            if is_overloaded and i < len(chain) - 1:
                print(f"\n⚠️  {fallback_model} unavailable (503), falling back to {chain[i + 1]}...")
                continue
            raise


def run(default_size="1344x768"):
    """
    Main entry point. Accepts default_size override for different contexts:
    - article-craft: 1344x768 (16:9 landscape for covers)
    - plugin standalone: 768x1344 (9:16 portrait)
    """
    parser = argparse.ArgumentParser(
        description="Generate or edit images using Minimax first, with Gemini fallback"
    )
    parser.add_argument(
        "--prompt", type=str, required=True,
        help="Prompt for image generation or editing",
    )
    parser.add_argument(
        "--output", type=str, default=f"nanobanana-{uuid.uuid4()}.png",
        help="Output image filename (default: nanobanana-<UUID>.png)",
    )
    parser.add_argument(
        "--input", type=str, nargs="*",
        help="Input image files for editing (optional)",
    )
    parser.add_argument(
        "--size", type=str, default=default_size,
        choices=list(ASPECT_RATIO_MAP.keys()),
        help=f"Size/aspect ratio (default: {default_size})",
    )

    # Default to Minimax unless an explicit `image_model` override is set.
    # `gemini_image_model` selects the Gemini fallback variant (per ENV.md) —
    # it must NOT flip the default to Gemini when `image_model` is absent.
    _default_model = _env_json_config.get("image_model", "minimax-image-01")
    parser.add_argument(
        "--model", type=str, default=_default_model,
        choices=MODEL_FALLBACK_CHAIN,
        help=f"Model (default: {_default_model})",
    )
    parser.add_argument(
        "--resolution", type=str, default="1K",
        choices=["1K", "2K", "4K"],
        help="Resolution (default: 1K)",
    )
    parser.add_argument(
        "--enhance", action="store_true",
        help="Enhance prompt using Gemini before generation",
    )
    parser.add_argument(
        "--no-fallback", action="store_true",
        help="Disable automatic model degradation on 503 errors",
    )
    parser.add_argument(
        "--timeout", type=int, default=None,
        help="Request timeout in seconds per API call (default: no limit)",
    )

    args = parser.parse_args()
    # Apply timeout globally if specified
    if args.timeout:
        global _request_timeout
        _request_timeout = args.timeout
    aspect_ratio = ASPECT_RATIO_MAP.get(args.size, "16:9")
    contents = []

    if args.input and len(args.input) > 0:
        print(f"Editing images with prompt: {args.prompt}")
        print(f"Input images: {args.input}")
        print(f"Aspect ratio: {aspect_ratio} ({args.size})")
        contents.append(args.prompt)
        for img_path in args.input:
            image = Image.open(img_path)
            contents.append(image)
    else:
        final_prompt = args.prompt
        if args.enhance:
            print(f"✨ Enhancing prompt: {args.prompt}")
            try:
                final_prompt = enhance_prompt(args.prompt)
                print(f"🚀 Enhanced prompt: {final_prompt}")
            except Exception as e:
                print(f"⚠️  Prompt enhancement failed: {e}")
                print("   Using original prompt.")
        print(f"Generating image (size: {args.size}, model: {args.model}) with prompt: {final_prompt}")
        contents.append(final_prompt)

    generate_image(
        args.model, contents, aspect_ratio, args.resolution,
        args.output, no_fallback=args.no_fallback,
    )


if __name__ == "__main__":
    run(default_size="1344x768")
