import json
import os
import platform
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from murmur import paths

SCHEMA_VERSION = 1


def _default_model() -> str:
    return "small.en" if platform.machine() == "arm64" else "base.en"


@dataclass
class Settings:
    schema_version: int = SCHEMA_VERSION
    hotkey: str = "right_option"
    tap_threshold_ms: int = 250
    model: str = field(default_factory=_default_model)
    compute_type: str = "int8"
    default_mode: str = "email"
    auto_mode: bool = True
    play_sounds: bool = True
    store_audio: bool = False
    audio_retention_days: int = 7
    history_size: int = 20
    max_recording_seconds: int = 300
    vocabulary_path: str = ""

    def __post_init__(self) -> None:
        if not self.vocabulary_path:
            self.vocabulary_path = str(paths.vocabulary_path())


def load() -> Settings:
    path = paths.config_path()
    if not path.exists():
        return Settings()
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError:
        return Settings()
    valid = {f.name for f in fields(Settings)}
    filtered = {k: v for k, v in raw.items() if k in valid}
    return Settings(**filtered)


def save(s: Settings) -> None:
    paths.ensure_dirs()
    target = paths.config_path()
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(asdict(s), indent=2))
    os.replace(tmp, target)
