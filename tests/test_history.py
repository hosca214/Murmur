import time
from pathlib import Path

from murmur import history, paths


def _entry(ts: float, raw: str = "raw", cleaned: str = "cleaned", mode: str = "email", audio: str = "") -> history.Entry:
    return history.Entry(ts=ts, raw=raw, cleaned=cleaned, mode=mode, audio_path=audio)


def test_append_creates_file(tmp_app_support):
    history.append(_entry(1.0))
    assert paths.history_path().exists()


def test_load_after_append(tmp_app_support):
    history.append(_entry(1.0, raw="hello"))
    history.append(_entry(2.0, raw="world"))
    entries = history.load(limit=10)
    assert [e.raw for e in entries] == ["world", "hello"]


def test_trim_to_history_size(tmp_app_support):
    for i in range(25):
        history.append(_entry(float(i)))
    entries = history.load(limit=100)
    assert len(entries) == 20
    assert entries[0].ts == 24.0


def test_latest_returns_most_recent(tmp_app_support):
    history.append(_entry(1.0, cleaned="first"))
    history.append(_entry(2.0, cleaned="second"))
    assert history.latest().cleaned == "second"


def test_latest_returns_none_when_empty(tmp_app_support):
    assert history.latest() is None


def test_purge_old_audio_files(tmp_app_support):
    audio_dir = paths.audio_dir()
    audio_dir.mkdir(parents=True, exist_ok=True)
    old = audio_dir / "old.wav"
    fresh = audio_dir / "fresh.wav"
    old.write_bytes(b"x")
    fresh.write_bytes(b"x")
    eight_days_ago = time.time() - (8 * 24 * 3600)
    Path(old).touch()
    import os as _os
    _os.utime(old, (eight_days_ago, eight_days_ago))
    history.purge_old_audio(retention_days=7)
    assert not old.exists()
    assert fresh.exists()
