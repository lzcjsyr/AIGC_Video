"""Shared HyperFrames runtime configuration."""

import os
import shutil
from pathlib import Path

HYPERFRAMES_VERSION = "hyperframes@0.7.10"
# A packaged app ships this pinned CLI and points this at its dist/cli.js.
BUNDLED_CLI_ENV = "AIGC_HYPERFRAMES_CLI"


def hyperframes_command() -> list[str]:
    """Command prefix for the pinned HyperFrames CLI."""
    bundled = os.environ.get(BUNDLED_CLI_ENV, "").strip()
    if bundled:
        return [shutil.which("node", path=subprocess_env()["PATH"]) or "node", bundled]
    return ["npx", "--yes", HYPERFRAMES_VERSION]


def parse_size(size: str) -> tuple[int, int]:
    raw = (
        (size or "1280x720")
        .lower()
        .replace(" ", "")
        .replace("×", "x")
        .replace("*", "x")
    )
    width, height = raw.split("x", 1)
    return int(width), int(height)


def subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    path_parts = [
        "/opt/homebrew/bin",
        "/usr/local/bin",
        str(Path.home() / ".nvm/versions/node/v22.22.3/bin"),
        str(Path.home() / ".nvm/versions/node/v22.22.2/bin"),
    ]
    # Common install locations are fallbacks; the caller's PATH wins.
    current_path = env.get("PATH", "")
    env["PATH"] = os.pathsep.join(
        [current_path, *path_parts] if current_path else path_parts
    )
    return env
