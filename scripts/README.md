# Shared Python Scripts

Scripts are bundled directly in this directory (self-contained):

```
article-craft/scripts/
├── nanobanana.py                    # Single image generation (Gemini API)
├── generate_and_upload_images.py    # Batch image processing + upload
├── config.py                        # VerificationCache, MODEL_FALLBACK_CHAIN, constants
├── utils.py                         # PlaceholderManager, SmartDirectoryMatcher
├── setup_dependencies.py            # Auto-dependency installer
└── requirements.txt                 # Python dependencies
```

Install dependencies: `pip install -r ~/.claude/plugins/article-craft/scripts/requirements.txt`
