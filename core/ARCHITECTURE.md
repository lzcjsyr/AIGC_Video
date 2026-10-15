# core Architecture

## Goal

`core` is the engine shared by the CLI (`core/cli/`) and Book2Video Studio, which
bundles it. Orchestration lives in `pipeline`, business logic in `domain`, and
external systems in `infra`. Packages export nothing themselves: import the module
that defines a name (`from core.pipeline import steps`).

## Layout

```text
core/
├── config.py              # YAML settings, API keys, validation, VideoGenerationConfig
├── prompts.py             # Loads prompts/ templates and style presets
├── resources.py           # Where prompts/ and skills/ live (desktop overrides it)
├── shared.py              # Logging, errors, retry, JSON and file helpers
├── startup.py             # CLI provider inference from model names
├── dependency_check.py    # `python -m core.dependency_check` for install/test scripts
│
├── cli/                   # Interactive CLI
│   ├── main.py
│   └── ui_helpers.py
│
├── pipeline/              # Step orchestration
│   ├── steps.py           # run_step_1 … run_step_6
│   ├── run_auto.py        # Full automatic run
│   └── scanner.py         # Input/project discovery and step progress
│
├── domain/                # Business logic
│   ├── summarizer.py      # Step 1.5 segmentation, step 2 summary
│   ├── subtitles.py       # Subtitle line breaking and timing
│   ├── composer.py        # Step 5 video composition (MoviePy)
│   ├── docx_transform.py  # raw/script JSON <-> DOCX
│   └── metadata.py        # Title, quote and focus-marker helpers
│
└── infra/                 # External systems
    ├── project_paths.py
    ├── ai/
    │   ├── llm_client.py      # OpenAI-compatible text, Doubao/Google image calls
    │   ├── image_providers.py
    │   ├── image_client.py    # Step 4 images, step 6 covers, step 3 voice batch + SRT
    │   ├── tts_client.py      # ByteDance TTS and silence trimming
    │   └── claude_agent.py    # Claude Agent SDK runs for steps 1, 1.5 and 4
    ├── motion/                # Shared Chrome capture, capabilities, opening and agent clips
    └── media/
        ├── ffmpeg.py
        ├── exporter.py
        └── three_by_four.py   # 3:4 distribution copy
```

## Dependency Rules

1. `pipeline/` may import `domain/`, `infra/`, and the top-level modules.
2. `domain/` holds the logic; it calls `infra/` for providers and media tools.
3. `infra/` never imports `pipeline/` or `cli/`.
4. Adapters (`cli/`, the desktop backend) call `core.pipeline` as their entry.
