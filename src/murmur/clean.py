import logging
from importlib import resources
from pathlib import Path
from typing import Optional

import google.generativeai as genai

logger = logging.getLogger(__name__)
_last_polished = False
_VALID_MODES = {"email", "chat", "notes", "raw"}
MODELS_FALLBACK = (
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.0-flash",
)
_GEN_CONFIG = {"max_output_tokens": 1024, "temperature": 0.0}
_dead_models: set[str] = set()


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
    genai.configure(api_key=api_key)
    last_exc: Optional[Exception] = None
    for name in MODELS_FALLBACK:
        if name in _dead_models:
            continue
        try:
            model = genai.GenerativeModel(name)
            response = model.generate_content(
                prompt,
                request_options={"timeout": 5},
                generation_config=_GEN_CONFIG,
            )
            cleaned = response.text.strip()
            if _looks_hallucinated(transcript, cleaned):
                logger.warning(
                    "Hallucination guard: %s expanded %d→%d; trying next model",
                    name, len(transcript), len(cleaned),
                )
                continue
            _last_polished = True
            return cleaned
        except Exception as exc:
            last_exc = exc
            logger.debug("Gemini model %s failed: %s", name, exc)
            if _is_quota_error(exc):
                _dead_models.add(name)
                logger.info("Marked %s as quota-exhausted for this session", name)
    logger.warning("All Gemini models failed or hallucinated; using raw. Last error: %s", last_exc)
    _last_polished = False
    return transcript


def _looks_hallucinated(raw: str, cleaned: str) -> bool:
    raw_len = len(raw.strip())
    if raw_len == 0:
        return len(cleaned) > 0
    return len(cleaned) > max(raw_len * 3, raw_len + 200)


def _is_quota_error(exc: Exception) -> bool:
    s = str(exc).lower()
    return "429" in s or "quota" in s or "resource_exhausted" in s or "rate" in s
