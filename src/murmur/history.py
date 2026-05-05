import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from murmur import paths, settings as settings_mod


@dataclass
class Entry:
    ts: float
    raw: str
    cleaned: str
    mode: str
    audio_path: str = ""


def append(entry: Entry) -> None:
    paths.ensure_dirs()
    cap = settings_mod.load().history_size
    existing = load(limit=cap - 1)
    all_entries = [entry] + existing
    p = paths.history_path()
    tmp = p.with_suffix(".jsonl.tmp")
    tmp.write_text("\n".join(json.dumps(asdict(e)) for e in all_entries) + "\n")
    tmp.replace(p)


def load(limit: int = 20) -> list[Entry]:
    p = paths.history_path()
    if not p.exists():
        return []
    out: list[Entry] = []
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        out.append(Entry(**json.loads(line)))
        if len(out) >= limit:
            break
    return out


def latest() -> Optional[Entry]:
    entries = load(limit=1)
    return entries[0] if entries else None


def purge_old_audio(retention_days: int) -> None:
    audio_dir = paths.audio_dir()
    if not audio_dir.exists():
        return
    cutoff = time.time() - (retention_days * 24 * 3600)
    for f in audio_dir.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            f.unlink()
