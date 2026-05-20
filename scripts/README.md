# Shared Python Scripts

Deterministic helpers the SKILL.md files shell out to. Each script is
self-contained (no inter-script ad-hoc state) and reads configuration from
`~/.claude/env.json` via `config.py`. SKILL.md files reference these scripts
by `${CLAUDE_PLUGIN_ROOT}/scripts/<name>.py` — never hardcode the install
path.

```
article-craft/scripts/
├── doctor.py                       # Runtime healthcheck CLI (v1.6.0+)
├── setup_dependencies.py           # Auto-dependency installer; backs doctor.py
├── config.py                       # VerificationCache, MODEL_FALLBACK_CHAIN,
│                                   # kb_category_root(), share_card_logo(), etc.
├── utils.py                        # PlaceholderManager, SmartDirectoryMatcher
├── nanobanana.py                   # Single-image generation (Minimax → Gemini fallback)
├── generate_and_upload_images.py   # Batch image processing + CDN upload
├── screenshot_tool.py              # Playwright screenshots + per-host selectors
├── share_card.py                   # Social-platform share-card generator
├── publish_plan.py                 # KB auto-placement + collision detection + sidecar copy (v1.6.0+)
├── series_state.py                 # Series state machine: status/next/mark-published/validate (v1.6.0+)
├── pipeline_state.py               # Persistent `.article-craft-state.json` for --upgrade resume
├── review_selfcheck.py             # 17 self-check rules invoked by the review skill
├── lint_article.py                 # Vale-style lint with tone-aware rewrites
├── verify_claims.py                # Post-write shell-command existence check
├── write_verify_cache.py           # Writer for ~/.cache/article-craft/verify-cache.json
├── evidence.py                     # Style H materials.md → _evidence.json
├── bump_version.py                 # Bumps plugin.json + marketplace.json + all SKILL.md
└── requirements.txt                # Python dependencies (installed by install.sh)
```

Install dependencies:

```bash
pip3 install -r ${CLAUDE_PLUGIN_ROOT}/scripts/requirements.txt
```

Run the healthcheck to verify the runtime is set up correctly:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py check
```
