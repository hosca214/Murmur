from pathlib import Path
from murmur import paths


def test_app_support_dir_uses_env_override(tmp_app_support):
    assert paths.app_support_dir() == Path(tmp_app_support)


def test_config_path_under_app_support(tmp_app_support):
    assert paths.config_path() == Path(tmp_app_support) / "config.json"


def test_history_path_under_app_support(tmp_app_support):
    assert paths.history_path() == Path(tmp_app_support) / "history.jsonl"


def test_audio_dir_under_app_support(tmp_app_support):
    assert paths.audio_dir() == Path(tmp_app_support) / "audio"


def test_vocabulary_path_under_app_support(tmp_app_support):
    assert paths.vocabulary_path() == Path(tmp_app_support) / "vocabulary.txt"


def test_log_path_default_is_user_logs():
    assert "Library/Logs/Murmur" in str(paths.log_path())


def test_env_path_under_dot_murmur():
    assert ".murmur/.env" in str(paths.env_path())
