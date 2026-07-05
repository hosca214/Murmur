import logging
import re
import time
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
_DEAD_MODEL_RETRY_S = 3600.0
_dead_models: dict[str, float] = {}

_FILLER_PATTERN = re.compile(r"\b(?:um+|uh+|uhm+|erm+|hmm+)\b[,.]?\s*", re.IGNORECASE)
_REPEAT_PATTERN = re.compile(r"\b(\w+)(,?\s+\1)+\b", re.IGNORECASE)


def was_polished() -> bool:
    return _last_polished


def _read_prompt(mode: str) -> str:
    return resources.files("murmur.prompts").joinpath(f"{mode}.txt").read_text()


def _format_vocabulary(vocab: list[str]) -> str:
    if not vocab:
        return ""
    joined = ", ".join(vocab)
    return f"The speaker uses these terms; preserve their exact spelling: {joined}."


def load_vocabulary(path: str) -> list[str]:
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        term = line.strip()
        if term and not term.startswith("#"):
            out.append(term)
    return out


def warm(api_key: str) -> None:
    """Fire one tiny request to warm the TLS connection and verify the key.

    Called once at startup off the critical path; failures are logged only.
    """
    if not api_key:
        return
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(MODELS_FALLBACK[0])
        model.generate_content(
            "Reply with the single word: ok",
            request_options={"timeout": 10},
            generation_config={"max_output_tokens": 5, "temperature": 0.0},
        )
        logger.info("Gemini warm-up ok (%s)", MODELS_FALLBACK[0])
    except Exception as exc:
        logger.warning("Gemini warm-up failed: %s", exc)


def local_polish(text: str) -> str:
    """Offline cleanup used when Gemini is unavailable: strip fillers and
    stutters, tidy spacing, capitalize, and close the sentence."""
    out = _FILLER_PATTERN.sub("", text)
    out = _REPEAT_PATTERN.sub(r"\1", out)
    out = re.sub(r"\s+([,.!?;:])", r"\1", out)
    out = re.sub(r"[ \t]{2,}", " ", out).strip()
    out = re.sub(r"^[,.;:\s]+", "", out)
    if not out:
        return ""
    out = out[0].upper() + out[1:]
    if out[-1] not in ".!?…":
        out += "."
    return out


def _model_is_dead(name: str) -> bool:
    marked = _dead_models.get(name)
    if marked is None:
        return False
    if time.time() - marked > _DEAD_MODEL_RETRY_S:
        del _dead_models[name]
        return False
    return True


def clean(transcript: str, *, mode: str, api_key: str, vocabulary: list[str]) -> str:
    global _last_polished
    if mode not in _VALID_MODES:
        raise ValueError(f"Unknown mode: {mode}")
    if not transcript.strip():
        _last_polished = False
        return ""
    if mode == "raw":
        _last_polished = False
        return transcript
    if not api_key:
        _last_polished = False
        return local_polish(transcript)
    template = _read_prompt(mode)
    prompt = template.format(
        vocabulary=_format_vocabulary(vocabulary),
        transcript=transcript,
    )
    genai.configure(api_key=api_key)
    last_exc: Optional[Exception] = None
    for name in MODELS_FALLBACK:
        if _model_is_dead(name):
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
                _dead_models[name] = time.time()
                logger.info("Marked %s as quota-exhausted; retrying after an hour", name)
    logger.warning("All Gemini models failed or hallucinated; local polish. Last error: %s", last_exc)
    _last_polished = False
    return local_polish(transcript)


def _looks_hallucinated(raw: str, cleaned: str) -> bool:
    raw_len = len(raw.strip())
    if raw_len == 0:
        return len(cleaned) > 0
    return len(cleaned) > max(raw_len * 3, raw_len + 200)


def _is_quota_error(exc: Exception) -> bool:
    s = str(exc).lower()
    return "429" in s or "quota" in s or "resource_exhausted" in s or "rate" in s
