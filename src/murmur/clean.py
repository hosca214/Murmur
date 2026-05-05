import logging
from importlib import resources
from pathlib import Path

import google.generativeai as genai

logger = logging.getLogger(__name__)
_last_polished = False
_VALID_MODES = {"email", "chat", "notes", "raw"}
_MODEL_NAME = "gemini-2.0-flash"


def was_polished() -> bool:
    return _last_polished


def _read_prompt(mode: str) -> str:
    return resources.files("murmur.prompts").joinpath(f"{mode}.txt").read_text()


def _format_vocabulary(vocab: list[str]) -> str:
    if not vocab:
        return ""
    joined = ", ".join(vocab)
    return f"The speaker uses these terms — preserve their exact spelling: {joined}."


def load_vocabulary(path: str) -> list[str]:
    p = Path(path)
    if not p.exists():
        return []
    return [line.strip() for line in p.read_text().splitlines() if line.strip()]


def clean(transcript: str, *, mode: str, api_key: str, vocabulary: list[str]) -> str:
    global _last_polished
    if mode not in _VALID_MODES:
        raise ValueError(f"Unknown mode: {mode}")
    if mode == "raw":
        _last_polished = False
        return transcript
    template = _read_prompt(mode)
    prompt = template.format(
        vocabulary=_format_vocabulary(vocabulary),
        transcript=transcript,
    )
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(_MODEL_NAME)
        response = model.generate_content(prompt)
        cleaned = response.text.strip()
        _last_polished = True
        return cleaned
    except Exception as exc:
        logger.warning("Gemini cleanup failed; falling back to raw: %s", exc)
        _last_polished = False
        return transcript
