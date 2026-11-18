"""Load versioned prompt files from the prompts/ folder."""

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class PromptNotFoundError(Exception):
    """Raised when a requested prompt file does not exist."""


@lru_cache
def load_prompt(name: str, version: str) -> str:
    """Return the text of prompts/<name>_<version>.md, for example triage_v2.md."""
    path = PROMPTS_DIR / f"{name}_{version}.md"
    if not path.is_file():
        raise PromptNotFoundError(f"Prompt file not found: {path.name}")
    return path.read_text(encoding="utf-8").strip()