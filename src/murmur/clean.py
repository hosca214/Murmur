import logging
from importlib import resources
from pathlib import Path
from typing import Optional

import google.generativeai as genai

logger = logging.getLogger(__name__)
_last_polished = False
_VALID_MODES = {"email", "chat", "notes", "raw"}
MODELS_FALLBACK = (
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash-latest",
)
_working_model: str = ""


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
    global _working_model
    genai.configure(api_key=api_key)
    candidates = []
    if _working_model:
        candidates.append(_working_model)
    candidates.extend(m for m in MODELS_FALLBACK if m != _working_model)
    last_exc: Optional[Exception] = None
    for name in candidates:
        try:
            model = genai.GenerativeModel(name)
            response = model.generate_content(prompt, request_options={"timeout": 30})
            _working_model = name
            _last_polished = True
            return response.text.strip()
        except Exception as exc:
            last_exc = exc
            logger.debug("Gemini model %s unavailable: %s", name, exc)
            if _working_model == name:
                _working_model = ""
    logger.warning("Gemini cleanup failed; falling back to raw: %s", last_exc)
    _last_polished = False
    return transcript
