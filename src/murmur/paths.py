import os
from pathlib import Path


def app_support_dir() -> Path:
    override = os.environ.get("MURMUR_APP_SUPPORT")
    if override:
        return Path(override)
    return Path.home() / "Library" / "Application Support" / "Murmur"


def config_path() -> Path:
    return app_support_dir() / "config.json"


def history_path() -> Path:
    return app_support_dir() / "history.jsonl"


def audio_dir() -> Path:
    return app_support_dir() / "audio"


def vocabulary_path() -> Path:
    return app_support_dir() / "vocabulary.txt"


def log_path() -> Path:
    return Path.home() / "Library" / "Logs" / "Murmur" / "murmur.log"


def env_path() -> Path:
    return Path.home() / ".murmur" / ".env"


def ensure_dirs() -> None:
    for d in (app_support_dir(), audio_dir(), log_path().parent, env_path().parent):
        d.mkdir(parents=True, exist_ok=True)
