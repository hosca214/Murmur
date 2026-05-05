import json
from murmur import paths, settings


def test_load_returns_defaults_when_file_missing(tmp_app_support):
    s = settings.load()
    assert s.schema_version == 1
    assert s.hotkey == "right_option"
    assert s.replay_hotkey == "cmd+option+v"
    assert s.tap_threshold_ms == 250
    assert s.model in {"base.en", "small.en"}
    assert s.compute_type == "int8"
    assert s.default_mode == "email"
    assert s.store_audio is False
    assert s.audio_retention_days == 7
    assert s.history_size == 20
    assert s.max_recording_seconds == 300


def test_save_then_load_roundtrip(tmp_app_support):
    s = settings.load()
    s.default_mode = "chat"
    s.store_audio = True
    settings.save(s)
    reloaded = settings.load()
    assert reloaded.default_mode == "chat"
    assert reloaded.store_audio is True


def test_load_handles_missing_keys_with_defaults(tmp_app_support):
    paths.config_path().parent.mkdir(parents=True, exist_ok=True)
    paths.config_path().write_text(json.dumps({"schema_version": 1, "default_mode": "notes"}))
    s = settings.load()
    assert s.default_mode == "notes"
    assert s.tap_threshold_ms == 250


def test_save_writes_schema_version(tmp_app_support):
    settings.save(settings.load())
    raw = json.loads(paths.config_path().read_text())
    assert raw["schema_version"] == 1


def test_save_atomic_no_partial_writes(tmp_app_support):
    s = settings.load()
    settings.save(s)
    assert paths.config_path().exists()
    assert not paths.config_path().with_suffix(".json.tmp").exists()
