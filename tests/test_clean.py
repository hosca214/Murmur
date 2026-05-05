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


def test_falls_back_to_raw_on_gemini_error(mocker):
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = RuntimeError("Network down")
    mocker.patch("murmur.clean.genai.GenerativeModel", return_value=mock_model)
    mocker.patch("murmur.clean.genai.configure")
    out = clean.clean("hello world", mode="email", api_key="fake", vocabulary=[])
    assert out == "hello world"
    assert clean.was_polished() is False


def test_unknown_mode_raises():
    with pytest.raises(ValueError):
        clean.clean("hi", mode="bogus", api_key="fake", vocabulary=[])


def test_load_vocabulary_strips_blanks(tmp_path):
    vocab_file = tmp_path / "vocab.txt"
    vocab_file.write_text("BookWise\n\nZen Bookkeeper\n  Plaid  \n")
    out = clean.load_vocabulary(str(vocab_file))
    assert out == ["BookWise", "Zen Bookkeeper", "Plaid"]


def test_load_vocabulary_missing_file_returns_empty(tmp_path):
    out = clean.load_vocabulary(str(tmp_path / "nope.txt"))
    assert out == []
