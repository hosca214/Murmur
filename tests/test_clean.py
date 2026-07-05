from unittest.mock import MagicMock, patch

import pytest

from murmur import clean


def test_raw_mode_returns_transcript_unmodified():
    out = clean.clean("hello world", mode="raw", api_key="fake", vocabulary=[])
    assert out == "hello world"
    assert clean.was_polished() is False


def test_email_mode_calls_gemini(mocker):
    mock_response = MagicMock()
    mock_response.text = "Hello, world."
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    mocker.patch("murmur.clean.genai.GenerativeModel", return_value=mock_model)
    mocker.patch("murmur.clean.genai.configure")
    out = clean.clean("hello world", mode="email", api_key="fake", vocabulary=[])
    assert out == "Hello, world."
    assert clean.was_polished() is True


def test_vocabulary_injected_into_prompt(mocker):
    mock_response = MagicMock()
    mock_response.text = "BookWise launch on Friday."
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    mocker.patch("murmur.clean.genai.GenerativeModel", return_value=mock_model)
    mocker.patch("murmur.clean.genai.configure")
    clean.clean("bookwise launch on friday", mode="email", api_key="fake", vocabulary=["BookWise"])
    call_args = mock_model.generate_content.call_args
    sent_prompt = call_args[0][0]
    assert "BookWise" in sent_prompt


def test_falls_back_to_local_polish_on_gemini_error(mocker):
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = RuntimeError("Network down")
    mocker.patch("murmur.clean.genai.GenerativeModel", return_value=mock_model)
    mocker.patch("murmur.clean.genai.configure")
    out = clean.clean("um hello world", mode="email", api_key="fake", vocabulary=[])
    assert out == "Hello world."
    assert clean.was_polished() is False


def test_unknown_mode_raises():
    with pytest.raises(ValueError):
        clean.clean("hi", mode="bogus", api_key="fake", vocabulary=[])


def test_empty_transcript_short_circuits(mocker):
    configure = mocker.patch("murmur.clean.genai.configure")
    out = clean.clean("   ", mode="email", api_key="fake", vocabulary=[])
    assert out == ""
    assert clean.was_polished() is False
    configure.assert_not_called()


def test_no_api_key_uses_local_polish():
    out = clean.clean("um so the meeting is at noon", mode="email", api_key="", vocabulary=[])
    assert out == "So the meeting is at noon."
    assert clean.was_polished() is False


def test_quota_error_marks_model_dead_then_expires(mocker):
    clean._dead_models.clear()
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = RuntimeError("429 quota exceeded")
    mocker.patch("murmur.clean.genai.GenerativeModel", return_value=mock_model)
    mocker.patch("murmur.clean.genai.configure")
    clean.clean("hello there friend", mode="email", api_key="fake", vocabulary=[])
    assert len(clean._dead_models) == len(clean.MODELS_FALLBACK)
    # After the retry window passes, models are eligible again
    for name in clean._dead_models:
        clean._dead_models[name] -= clean._DEAD_MODEL_RETRY_S + 1
    assert clean._model_is_dead(clean.MODELS_FALLBACK[0]) is False
    clean._dead_models.clear()


def test_local_polish_strips_fillers_only():
    assert clean.local_polish("um the report is uh ready") == "The report is ready."
    assert clean.local_polish("hello world") == "Hello world."
    assert clean.local_polish("done!") == "Done!"
    assert clean.local_polish("um uh") == ""


def test_local_polish_keeps_real_words():
    # "umbrella" and "hummus" must not be eaten by the filler pattern
    out = clean.local_polish("bring the umbrella and hummus")
    assert out == "Bring the umbrella and hummus."


def test_local_polish_never_rewrites_repeated_words():
    # Fidelity first: "nine, nine thirty" is real content, not a stutter
    out = clean.local_polish("the meeting is at nine, nine thirty at the latest")
    assert out == "The meeting is at nine, nine thirty at the latest."
    assert clean.local_polish("it was really really good") == "It was really really good."


def test_quota_error_detection_is_precise():
    assert clean._is_quota_error(RuntimeError("429 Too Many Requests")) is True
    assert clean._is_quota_error(RuntimeError("RESOURCE_EXHAUSTED: quota")) is True
    assert clean._is_quota_error(RuntimeError("rate limit exceeded")) is True
    # 'generate'/'generateContent' contains 'rate' but is NOT a quota error
    assert clean._is_quota_error(
        RuntimeError("404 models/gemini-x is not found or not supported for generateContent")
    ) is False


def test_hallucination_guard_catches_short_input_fabrication():
    template = "Hi [Name], I hope you're doing well. I wanted to follow up on our meeting."
    assert clean._looks_hallucinated("test", template) is True
    assert clean._looks_hallucinated("test", "Test.") is False
    assert clean._looks_hallucinated("test test", "Test, test.") is False


def test_token_capped_response_is_rejected(mocker):
    capped = MagicMock()
    capped.candidates = [MagicMock(finish_reason=2)]
    capped.text = "truncated half of a long dictation"
    mock_model = MagicMock()
    mock_model.generate_content.return_value = capped
    mocker.patch("murmur.clean.genai.GenerativeModel", return_value=mock_model)
    mocker.patch("murmur.clean.genai.configure")
    out = clean.clean(
        "a long dictation " * 20, mode="email", api_key="fake", vocabulary=[]
    )
    # All models return capped output, so cleanup falls back locally
    assert clean.was_polished() is False
    assert "truncated" not in out


def test_load_vocabulary_strips_blanks(tmp_path):
    vocab_file = tmp_path / "vocab.txt"
    vocab_file.write_text("BookWise\n\nZen Bookkeeper\n  Plaid  \n")
    out = clean.load_vocabulary(str(vocab_file))
    assert out == ["BookWise", "Zen Bookkeeper", "Plaid"]


def test_load_vocabulary_skips_comment_lines(tmp_path):
    vocab_file = tmp_path / "vocab.txt"
    vocab_file.write_text("# how to use this file\nBookWise\n# another comment\n")
    out = clean.load_vocabulary(str(vocab_file))
    assert out == ["BookWise"]


def test_load_vocabulary_missing_file_returns_empty(tmp_path):
    out = clean.load_vocabulary(str(tmp_path / "nope.txt"))
    assert out == []


def test_warm_if_stale_skips_when_connection_is_fresh(mocker):
    import time as _time
    warm = mocker.patch("murmur.clean.warm")
    old_ts = clean._last_request_ts
    clean._last_request_ts = _time.time()
    clean.warm_if_stale("key")
    warm.assert_not_called()
    clean._last_request_ts = old_ts


def test_warm_if_stale_fires_after_idle(mocker):
    import time as _time
    warm = mocker.patch("murmur.clean.warm")
    old_ts = clean._last_request_ts
    clean._last_request_ts = _time.time() - clean._WARM_MAX_AGE_S - 1
    clean.warm_if_stale("key")
    warm.assert_called_once_with("key")
    clean._last_request_ts = old_ts
