# Multi-Provider Image Generation Abstraction (B7)

**Status**: Phases 1-3 ✅ done v1.6.17 / v1.6.20 / v1.6.22; Phase 4 queued
**Date**: 2026-05-20
**Target version**: multi-phase
**Author**: costa
**Backlog ref**: B7 in `docs/research/2026-05-20-feature-candidates.md`
**Strategic enabler for**: D2 (English-language output) in same backlog doc
**Closes pattern**: hard coupling to Minimax + Gemini in `MODEL_FALLBACK_CHAIN`

---

## 0. Problem statement

`scripts/generate_and_upload_images.py` and `scripts/nanobanana.py`
hard-code two image providers in three different ways:

| Where | What it hardcodes |
|-------|-------------------|
| `config.py:307-312` `MODEL_FALLBACK_CHAIN` | Literal model-name list: `minimax-image-01`, then 3 Gemini variants |
| `generate_and_upload_images.py:708,749` | `_generate_minimax_image*` Minimax-specific API call |
| `generate_and_upload_images.py:817` (the Gemini branch is dispatched inline at the fallback loop) | Gemini SDK direct usage |
| `nanobanana.py:211,250` | `_generate_single_model` (Gemini) / `_generate_single_minimax` (Minimax) |
| `nanobanana.py:102-120` | `_gemini_api_key()` / `_minimax_api_key()` |
| `config.py:filter_chain_by_available_keys` | `prefix == "minimax"` / `prefix == "gemini"` literal branches |
| `setup_dependencies.py:check_minimax_api_key`, `check_gemini_api_key` | Per-provider preflight in doctor |

Adding a third provider — OpenAI `gpt-image-1`, Stable Diffusion API,
Flux, DALL-E 3 — requires **5+ files** to change in lockstep. Worse,
each addition has its own retry semantics / rate-limit signal /
auth-token shape, so a poorly-designed addition will accrete `if
model.startswith("X")` branches across the file.

This blocks two strategic moves:

1. **D2 — English-language output**. The Chinese-market Minimax key
   is hard to get for English-market users. They'd lean on
   OpenAI / Stable Diffusion / Flux, none of which the codebase
   currently knows about.
2. **Self-hosted models**. Users running Ollama / Replicate / vLLM
   for image gen have no integration path short of a fork.

The v1.6.9 `filter_chain_by_available_keys` already had to learn the
two prefixes — every new prefix is one more `elif` branch in that
function plus another `check_<provider>_api_key` in doctor.

---

## 1. Design goals

1. **One protocol, many implementations.** Define `ImageProvider`
   with a fixed contract; every existing or future model is a
   subclass.
2. **Net-zero behavior change for current Minimax + Gemini users.**
   No env.json key renames, no `MODEL_FALLBACK_CHAIN` reorder, no
   change to which API the default config calls.
3. **Adding a provider = subclass + register.** No edits to
   `generate_and_upload_images.py` main flow, no new branches in
   `filter_chain_by_available_keys`, one new `check_<provider>_api_key`
   in doctor follows a registered factory.
4. **Preserve the v1.5.0 parallel rate-limit coordinator.** The
   cross-worker backoff coalescing (see `_ParallelRateLimitCoordinator`,
   `generate_and_upload_images.py:1616`) operates against
   `RateLimitExhausted` raised by any provider, not a model-name
   string. Refactor must not regress.
5. **Surface provider identity in error messages.** Today a Gemini
   "service unavailable" and a Minimax "throttle" look interchangeable
   in logs. New design emits `provider=X model=Y reason=Z` shape.
6. **Don't break tests.** 331 tests pass today; the refactor must
   maintain (or grow) coverage without regressing any existing assertion.

---

## 2. Non-goals (explicitly)

- ❌ **Adding OpenAI / SD / Flux / DALL-E in the same release** as the
  abstraction. The protocol lands first; the first new provider
  follows as a separate, scoped release.
- ❌ **Replacing `MODEL_FALLBACK_CHAIN` with a registry-only mechanism**.
  The chain stays — it's the *order policy*. The registry is the
  *implementation policy*. Two different concepts.
- ❌ **Auto-discovering providers from env.json**. Explicit registration
  in `image_providers.py` (one Python file) is the contract. No
  plugin/entry-point system.
- ❌ **Per-request provider routing based on prompt content**.
  ("Pictures of people → use Flux because it's better with faces.")
  Worth doing later; out of scope here.
- ❌ **Generic LLM-provider abstraction.** This is image-gen only.
  Text generation (used by `nanobanana --enhance`) keeps its current
  shape — the abstraction surface is narrower.
- ❌ **Backwards-incompatible CLI changes**. `--model X` still works
  for any X that's a registered model name.

---

## 3. Architecture

### 3.1 `ImageProvider` protocol

New module `scripts/image_providers.py`:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class ImageProvider(Protocol):
    """Contract for an image-generation backend.

    Lifecycle:
      1. `is_configured()` is called early (doctor preflight + chain filter).
         Returns False if the provider's API key isn't set — model gets
         pruned from the fallback chain.
      2. `generate(...)` is called per image. Raises RateLimitExhausted
         on quota-shaped errors (caller may pause + retry / fall back
         to next provider). Raises RuntimeError on other failures.
      3. `model_names()` returns the canonical model strings this
         provider handles. The fallback chain matches a chain entry
         to a provider via this list.

    Implementations are stateless (provider instances may be shared
    across workers — the parallel coordinator relies on this).
    """

    name: str  # short identifier, e.g. "minimax", "gemini", "openai"

    def model_names(self) -> list[str]:
        ...

    def is_configured(self) -> bool:
        ...

    def generate(
        self,
        model: str,
        prompt: str,
        aspect_ratio: str,
        resolution: str,
        output_path: Path,
        *,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        ...
```

### 3.2 Registry

```python
# scripts/image_providers.py

_REGISTRY: dict[str, ImageProvider] = {}

def register(provider: ImageProvider) -> None:
    """Called once at module import for each built-in provider."""
    _REGISTRY[provider.name] = provider

def for_model(model: str) -> ImageProvider | None:
    """Resolve a model name (e.g. 'minimax-image-01') to its provider."""
    for provider in _REGISTRY.values():
        if model in provider.model_names():
            return provider
    return None

def configured_providers() -> list[ImageProvider]:
    """Subset of registered providers whose API keys are available.
    Used by config.filter_chain_by_available_keys."""
    return [p for p in _REGISTRY.values() if p.is_configured()]

# Built-in registrations at module bottom
register(MinimaxProvider())
register(GeminiProvider())
# Future: register(OpenAIProvider()); register(StableDiffusionProvider())
```

### 3.3 Concrete providers (Phase 1 — extract existing logic)

`MinimaxProvider` subclass moves `_generate_minimax_image*` from
`generate_and_upload_images.py:708-820` and `_generate_single_minimax`
from `nanobanana.py:250` into one place. Same HTTP shape, same
retry handling, same `RateLimitExhausted` raising — just relocated.

`GeminiProvider` subclass moves the inline Gemini SDK calls + the
`_generate_single_model` Gemini variant. Same model-name list
(`gemini-3-pro-image-preview`, `gemini-3.1-flash-image-preview`,
`gemini-2.5-flash-image`), same parameter shape, same error mapping.

### 3.4 Refactor of the existing call sites

`generate_and_upload_images.py:885` main loop changes from:

```python
for i, current_model in enumerate(model_chain, 1):
    try:
        if current_model.startswith("minimax"):
            _generate_minimax_image_with_options(current_model, prompt, ...)
        else:
            # inline Gemini call
            ...
```

to:

```python
for i, current_model in enumerate(model_chain, 1):
    provider = image_providers.for_model(current_model)
    if provider is None:
        raise RuntimeError(f"Unknown model {current_model} — no registered provider")
    try:
        provider.generate(current_model, prompt, ..., output_path=output_path)
```

`config.filter_chain_by_available_keys` becomes:

```python
def filter_chain_by_available_keys(chain: list[str]) -> list[str]:
    from image_providers import for_model
    return [m for m in chain if (p := for_model(m)) is not None and p.is_configured()]
```

The hardcoded `prefix == "minimax"` / `prefix == "gemini"` branches go
away — registry lookup handles arbitrary providers.

### 3.5 Doctor extension

`scripts/setup_dependencies.py` exposes one generic check that loops
over `image_providers.configured_providers()` instead of the
hand-rolled `check_minimax_api_key` + `check_gemini_api_key`:

```python
def check_image_providers() -> list[dict]:
    """Per-provider preflight — one row per registered provider."""
    from image_providers import _REGISTRY
    results = []
    for provider in _REGISTRY.values():
        if provider.is_configured():
            results.append(_result(f"image_provider_{provider.name}", "pass", ...))
        else:
            # warn if at least one other provider IS configured, block if zero
            ...
    return results
```

The aggregation rule: ≥1 provider configured → warn on missing ones
(can't generate images for those models, but pipeline still works);
0 providers configured → block (preflight catches "user has no image
backend at all" before the writing stage spends 20 min producing
placeholders that will never resolve).

### 3.6 Rate-limit coordinator (no change)

`_ParallelRateLimitCoordinator` (line 1616) catches
`RateLimitExhausted` from any worker, sets a shared pause window, and
all other workers `wait_if_paused()` before their next
`provider.generate()` call. The coordinator doesn't need to know
about model names or provider types — it just observes failures and
gates retries. **Untouched by the refactor.**

---

## 4. Implementation phases

### Phase 1 — Extract protocol + 2 existing providers (1 release)

**Scope**: net-zero behavior change for Minimax + Gemini users.

**Deliverables**:

- `scripts/image_providers.py` with `ImageProvider` protocol,
  `_REGISTRY`, `register`, `for_model`, `configured_providers`
- `MinimaxProvider` class (moves `_generate_minimax_image*` body)
- `GeminiProvider` class (moves the inline Gemini SDK call)
- `generate_and_upload_images.py` main fallback loop refactored to
  use `provider.generate()` instead of `if model.startswith(...)`
- `nanobanana.py` similar refactor (uses the same providers — no
  more separate `_generate_single_minimax` / `_generate_single_model`)
- `config.filter_chain_by_available_keys` switched to registry lookup
- `tests/test_image_providers.py` — covers protocol contract,
  registry semantics, provider matching by model name, failure modes

**Done when**: All 331 existing tests pass unchanged. New tests
exercise the new module. `doctor.py check` output unchanged.

**Estimated effort**: 3–5 hours. Risk: medium — touches the hottest
file. Mitigation: keep the public API of `generate_and_upload_images`
identical to today; refactor is internal.

### Phase 2 — Add OpenAI gpt-image-1 (1 release)

**Scope**: First new provider via the new contract. Proves the
abstraction actually buys new-provider velocity.

**Deliverables**:

- `OpenAIImageProvider` in `image_providers.py` (env var
  `OPENAI_API_KEY`, env.json `openai_api_key`)
- Model name(s): `openai-gpt-image-1`, possibly `openai-dall-e-3` as
  a separate model handled by the same provider
- Append to `MODEL_FALLBACK_CHAIN` at a configurable position (default:
  after the Gemini block — Minimax / Gemini stay the headline default)
- `env.example.json` adds `openai_api_key: ""`
- `ENV.md` documents the new key
- `doctor.py` auto-picks it up via the registry change from Phase 1

**Done when**: A user with only `OPENAI_API_KEY` set can generate
images. The fallback chain filter prunes Minimax + Gemini, leaves
OpenAI, runs.

**Estimated effort**: 3–4 hours. Risk: low — Phase 1 already proved
the contract.

### Phase 3 — Add a self-hosted provider (1 release, optional)

**Scope**: Demonstrate the registry handles non-cloud backends.
Replicate or Stable Diffusion via Automatic1111 API.

**Deliverables**:

- `StableDiffusionProvider` (talks to a configurable endpoint URL
  rather than a SaaS API) OR `ReplicateProvider`
- env.json `stable_diffusion_endpoint` / `replicate_api_token`
- Same registry registration pattern

**Done when**: A user pointing at `http://localhost:7860` (a1111)
gets generated images locally.

**Estimated effort**: 4–6 hours. Risk: medium — third-party API
quirks vary widely.

### Phase 4 — Per-provider configuration cleanup (1 release)

**Scope**: Hygiene pass once 3+ providers are registered.

**Deliverables**:

- `config.py` gets a `provider_config(name)` helper returning the
  per-provider env.json sub-block (encourages namespaced config
  rather than top-level sprawl)
- README "Supported image providers" table
- CHANGELOG note in the previously-vague "Minimax-first image
  generation" lines is updated to "configurable provider chain"

**Done when**: A new user reading the README understands all
supported providers in one place.

**Estimated effort**: 2 hours.

---

## 5. Risks

### 5.1 `generate_and_upload_images.py` is the hottest file

**Risk**: The file is ~3000 LOC, has the parallel rate-limit
coordinator, two retry layers (per-image + per-batch), tenacity
wrappers, and the entire image-batch pipeline. Refactoring it
internally is the most-likely-to-introduce-bugs path on the repo.

**Mitigation**:

- Phase 1 explicitly preserves the public function signatures of
  `generate_image()`, `upload_image()`, the main entry points
- The refactor moves *bodies* to providers; the *control flow*
  (model_chain loop, rate-limit handling, output-path management,
  prompt enhancement) stays in the same place
- Run the full test suite (331 tests) after each step in Phase 1,
  not just at the end
- A goal-backward integration test in `tests/test_image_providers.py`
  asserts the exact call sequence: build chain → filter by available
  keys → for each model: lookup provider → provider.generate

### 5.2 `_ParallelRateLimitCoordinator` coupling

**Risk**: The coordinator (line 1616) catches `RateLimitExhausted` —
which today is raised by Minimax-specific or Gemini-specific code.
If a new provider raises a *different* exception, the coordinator
doesn't pause workers, and they all hammer the throttled API.

**Mitigation**:

- Document in the `ImageProvider` protocol docstring that quota /
  throttle errors **must** be normalized to `RateLimitExhausted`
- Add a test in `tests/test_image_providers.py` asserting each
  built-in provider raises `RateLimitExhausted` (not a vendor-specific
  exception) on a mocked 429 / 503 response

### 5.3 Test ergonomics

**Risk**: Existing tests mock `_generate_minimax_image` / Gemini
calls directly. Post-refactor, those private functions don't exist
at the same path — tests break.

**Mitigation**:

- Audit `tests/test_image_variation.py`,
  `tests/test_image_parallel_backoff.py`,
  `tests/test_images_cli.py` for direct mocks of the internal
  functions
- Either (a) move the mocks to `image_providers.MinimaxProvider.generate`
  (preferred — tests the new contract) or (b) keep the old function
  names as thin shims that call `MinimaxProvider().generate()`
  (preferred if it makes the diff smaller in Phase 1)

### 5.4 Provider config schema sprawl

**Risk**: Three providers × six provider-specific knobs = an env.json
that looks like a config server. Users get confused about which keys
apply to which provider.

**Mitigation**:

- Phase 4 namespaces per-provider config under a single key:
  ```json
  "image_providers": {
    "minimax": {"api_key": "..."},
    "gemini": {"api_key": "...", "model": "gemini-3-pro-image-preview"},
    "openai": {"api_key": "...", "model": "gpt-image-1"}
  }
  ```
- Backward compat: top-level `minimax_api_key` / `gemini_api_key`
  still honored, just deprecated path

---

## 6. Open questions (resolve before Phase 1)

1. **Should `ImageProvider` be a Python `Protocol` or an `ABC`?**
   Recommendation: **Protocol** (consistency with
   `scripts/uploaders.Uploader` from B2). Easier to mock in tests;
   `@runtime_checkable` gives `isinstance` support.
2. **One provider class per model, or one per vendor with multiple
   model_names?** Recommendation: **one per vendor**. GeminiProvider
   handles all 3 Gemini model variants because they share the SDK,
   auth, and error shapes. Saves boilerplate.
3. **Where does `MinimaxProvider` live — in `image_providers.py`
   directly, or in a `providers/minimax.py` submodule?**
   Recommendation: **one file**. Three providers, 80–150 LOC each =
   ~500 LOC total. Doesn't justify a package yet. Promote to a
   `scripts/providers/` directory only when the count crosses 5.
4. **Does the per-image rate-limit retry stay in
   `generate_and_upload_images.py`, or move into each provider?**
   Recommendation: **stays in the call site**. The retry policy is
   pipeline-level (per-batch backoff coalescing, parallel coordinator).
   Provider's job is to make one attempt and raise — let the caller
   decide what to do on failure.
5. **Should the registry be writeable at runtime (user-supplied
   providers via env.json plugin path) or compile-time only?**
   Recommendation: **compile-time**. Plugin-loading at runtime adds
   import-order complexity for marginal benefit. Forks can add a
   provider by editing `image_providers.py`.

---

## 7. Concrete next step (when Phase 1 starts)

1. Create `scripts/image_providers.py` with the empty `ImageProvider`
   protocol + empty `_REGISTRY` dict + `register` / `for_model` /
   `configured_providers` helpers.
2. Move `_generate_minimax_image` + `_generate_minimax_image_with_options`
   into a `MinimaxProvider.generate` method. Verify the existing
   `tests/test_image_variation.py` still passes by re-routing through
   `MinimaxProvider().generate()`.
3. Same for Gemini.
4. Refactor the `generate_and_upload_images.generate_image` fallback
   loop to use `image_providers.for_model(model).generate(...)`.
5. Update `config.filter_chain_by_available_keys` to query the
   registry.
6. Add `tests/test_image_providers.py` covering the protocol,
   registry, and provider lookup.

Phase 1 is the contract. Phases 2–4 are cheap extensions once
Phase 1 lands cleanly.

This document is the contract — when someone picks up Phase 1 later,
they should be able to start coding from the architecture in §3 and
the deliverable list in §4 without re-deriving any design decision.
