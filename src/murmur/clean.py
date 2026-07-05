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
_GEN_CONFIG = {"max_output_tokens": 8192, "temperature": 0.0}
_DEAD_MODEL_RETRY_S = 3600.0
_dead_models: dict[str, float] = {}  # model name -> timestamp when it may be retried
_MAX_TOKENS_FINISH = 2  # google.generativeai FinishReason.MAX_TOKENS

_FILLER_PATTERN = re.compile(r"\b(?:um+|uh+|uhm+|erm+|hmm+)\b[,.]?\s*", re.IGNORECASE)
_QUOTA_PATTERN = re.compile(r"\b429\b|quota|resource_exhausted|rate.?limit", re.IGNORECASE)
_RETRY_DELAY_PATTERN = re.compile(r"retry_delay\s*\{\s*seconds:\s*(\d+)", re.IGNORECASE)


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


# Connections to Gemini go cold after a few idle minutes and re-establishing
# one adds 1-3s to the next cleanup. Recording time is free cover: firing a
# tiny warm request when recording STARTS means the connection is hot by the
# time the transcript needs polishing.
_WARM_MAX_AGE_S = 180.0
_last_request_ts = 0.0


def warm(api_key: str) -> None:
    """Fire one tiny request to warm the TLS connection and verify the key.

    Called at startup and (via warm_if_stale) when recording starts;
    failures are logged only.
    """
    global _last_request_ts
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
        _last_request_ts = time.time()
        logger.info("Gemini warm-up ok (%s)", MODELS_FALLBACK[0])
    except Exception as exc:
        logger.warning("Gemini warm-up failed: %s", exc)


def warm_if_stale(api_key: str) -> None:
    """Warm the connection only if it has likely gone idle."""
    if time.time() - _last_request_ts > _WARM_MAX_AGE_S:
        warm(api_key)


def local_polish(text: str) -> str:
    """Offline cleanup used when Gemini is unavailable. Fidelity first:
    only unambiguous fillers are removed; the user's words are never
    reordered, collapsed, or rewritten."""
    out = _FILLER_PATTERN.sub("", text)
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
    retry_at = _dead_models.get(name)
    if retry_at is None:
        return False
    if time.time() >= retry_at:
        del _dead_models[name]
        return False
    return True


def _quota_retry_after_s(exc: Exception) -> float:
    """A per-minute 429 says 'retry in ~20s'; benching the model for an hour
    would silently degrade quality. Honor the API's own retry hint."""
    m = _RETRY_DELAY_PATTERN.search(str(exc))
    if m:
        return max(float(m.group(1)), 30.0) + 5.0
    return _DEAD_MODEL_RETRY_S


def clean(transcript: str, *, mode: str, api_key: str, vocabulary: list[str]) -> str:
    global _last_polished, _last_request_ts
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
            _last_request_ts = time.time()
            if _hit_token_cap(response):
                logger.warning("Model %s hit the output token cap; trying next model", name)
                continue
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
                retry_after = _quota_retry_after_s(exc)
                _dead_models[name] = time.time() + retry_after
                logger.info("Marked %s quota-exhausted; retrying in %.0fs", name, retry_after)
    logger.warning("All Gemini models failed or hallucinated; local polish. Last error: %s", last_exc)
    _last_polished = False
    return local_polish(transcript)


def _hit_token_cap(response) -> bool:
    try:
        candidate = response.candidates[0]
        return int(candidate.finish_reason) == _MAX_TOKENS_FINISH
    except Exception:
        return False


def _looks_hallucinated(raw: str, cleaned: str) -> bool:
    raw_len = len(raw.strip())
    if raw_len == 0:
        return len(cleaned) > 0
    # Short inputs are the most hallucination-prone, so keep the ceiling
    # tight there: a 4-char "test" must not come back as a 100-char email.
    return len(cleaned) > max(raw_len * 3, 60)


def _is_quota_error(exc: Exception) -> bool:
    return bool(_QUOTA_PATTERN.search(str(exc)))
