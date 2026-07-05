import collections
import logging
import logging.handlers
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

_API_KEY_PATTERN = re.compile(r"AIza[A-Za-z0-9_\-]{20,}")
_WARMUP_ERROR_DISPLAY_S = 10.0

from dotenv import load_dotenv

from murmur import clean, history, output, paths, settings as settings_mod
from murmur.hotkey import HotkeyListener
from murmur.pipeline import AudioRecorder, Transcriber, save_wav
from murmur.state import RecordingState, StateMachine
from murmur.ui.bar import MenuBar
from murmur.ui.pill import Pill

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    paths.ensure_dirs()
    handler = logging.handlers.RotatingFileHandler(
        paths.log_path(), maxBytes=5 * 1024 * 1024, backupCount=2
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()])


class MurmurApp:
    def __init__(self) -> None:
        _setup_logging()
        load_dotenv(paths.env_path())
        self._api_key = os.environ.get("GEMINI_API_KEY", "")
        self._settings = settings_mod.load()
        self._sm = StateMachine()
        self._levels: collections.deque[str] = collections.deque(maxlen=10)
        self._recorder = AudioRecorder(
            max_seconds=self._settings.max_recording_seconds,
            level_callback=self._on_audio_level,
        )
        self._transcriber: Optional[Transcriber] = None
        self._pill = Pill()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pipeline")
        self._mode = self._settings.default_mode
        self._privacy = False
        self._paused = False
        self._hotkey: Optional[HotkeyListener] = None
        self._bar: Optional[MenuBar] = None
        self._onboarding_proc: Optional[subprocess.Popen] = None
        history.purge_old_audio(self._settings.audio_retention_days)

    def run(self) -> None:
        threading.Thread(target=self._warmup, daemon=True, name="warmup").start()
        self._hotkey = HotkeyListener(
            key_name=self._settings.hotkey,
            tap_threshold_ms=self._settings.tap_threshold_ms,
            on_tap=self._handle_tap,
            on_hold_start=self._handle_hold_start,
            on_hold_end=self._handle_hold_end,
            on_double_tap=self._handle_double_tap,
        )
        self._hotkey.start()
        self._bar = MenuBar(
            on_mode_change=self._set_mode,
            on_pause_toggle=self._toggle_pause,
            on_privacy_toggle=self._toggle_privacy,
            on_open_settings=self._open_settings,
            on_rerun_onboarding=self._rerun_onboarding,
            on_quit=self._quit,
            on_diagnostics=self._diagnostics,
        )
        self._bar.set_active_mode(self._mode)
        logger.info("MenuBar starting (rumps event loop)")
        self._bar.run()

    def _warmup(self) -> None:
        try:
            self._pill.show("Warming up…")
            self._transcriber = Transcriber(self._settings.model, self._settings.compute_type)
            action = self._sm.warmup_complete()
            self._pill.hide()
            if action == "start_recording":
                self._begin_recording()
        except Exception:
            logger.exception("Warmup failed")
            self._pill.show("⚠ Whisper failed — see logs")
            threading.Timer(_WARMUP_ERROR_DISPLAY_S, self._pill.hide).start()

    def _handle_tap(self) -> None:
        if self._paused:
            return
        action = self._sm.on_tap()
        self._dispatch(action)

    def _handle_hold_start(self) -> None:
        if self._paused:
            return
        if self._sm.state == RecordingState.IDLE:
            self._sm.on_tap()
            self._begin_recording()

    def _handle_hold_end(self) -> None:
        if self._sm.state == RecordingState.RECORDING:
            self._sm.on_tap()
            self._end_recording()

    def _dispatch(self, action: str) -> None:
        if action == "start_recording":
            self._begin_recording()
        elif action == "stop_and_process":
            self._end_recording()
        elif action == "queue_after_warmup":
            self._pill.show("Warming up…")

    def _begin_recording(self) -> None:
        self._levels.clear()
        self._pill.show("Listening…")
        if self._bar:
            self._bar.set_recording(True)
        self._recorder.start(on_auto_stop=self._on_recording_max)

    def _on_audio_level(self, rms: float) -> None:
        if self._sm.state != RecordingState.RECORDING:
            return
        bars = " ▁▂▃▄▅▆▇█"
        scaled = min(1.0, rms * 12.0)
        idx = int(scaled * (len(bars) - 1))
        self._levels.append(bars[idx])
        self._pill.show(f"Listening {''.join(self._levels)}")

    def _on_recording_max(self) -> None:
        action = self._sm.recording_max_reached()
        if action == "stop_and_process":
            self._pill.show("5 min limit — processing")
            self._end_recording()

    def _end_recording(self) -> None:
        if self._bar:
            self._bar.set_recording(False)
        audio = self._recorder.stop()
        duration_s = len(audio) / 16000.0
        if duration_s < 0.3:
            logger.info("Discarded recording (%.2fs, too short)", duration_s)
            self._pill.hide()
            return
        self._executor.submit(self._process, audio)

    def _handle_double_tap(self) -> None:
        if self._paused:
            return
        if self._sm.state != RecordingState.IDLE:
            return
        output.undo_paste()
        self._pill.show("↶ Undid last")
        threading.Timer(1.5, self._pill.hide).start()

    def _process(self, audio) -> None:
        try:
            t0 = time.time()
            if self._sm.state != RecordingState.RECORDING:
                self._pill.show("Transcribing…")
            assert self._transcriber is not None
            raw = self._transcriber.transcribe(audio)
            t1 = time.time()
            logger.info("TIMING: transcribe=%.2fs (audio=%.1fs)", t1 - t0, len(audio) / 16000.0)
            mode = "raw" if self._privacy else self._mode
            if self._sm.state != RecordingState.RECORDING:
                self._pill.show("Polishing…" if mode != "raw" else "Pasting…")
            vocab = clean.load_vocabulary(self._settings.vocabulary_path)
            cleaned = clean.clean(raw, mode=mode, api_key=self._api_key, vocabulary=vocab)
            t2 = time.time()
            logger.info("TIMING: cleanup=%.2fs (mode=%s, polished=%s)", t2 - t1, mode, clean.was_polished())
            if cleaned:
                cleaned = cleaned.rstrip() + " "
            output.paste_text(cleaned)
            t3 = time.time()
            logger.info("TIMING: paste=%.2fs total=%.2fs", t3 - t2, t3 - t0)
            audio_path = ""
            if self._settings.store_audio and not self._privacy and audio.size > 0:
                audio_path = str(paths.audio_dir() / f"{int(time.time())}.wav")
                save_wav(audio, Path(audio_path))
            history.append(history.Entry(
                ts=time.time(),
                raw=raw,
                cleaned=cleaned,
                mode=mode,
                audio_path=audio_path,
            ))
        except Exception:
            logger.exception("Pipeline failed")
        finally:
            if self._sm.state != RecordingState.RECORDING:
                self._pill.hide()

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        s = settings_mod.load()
        s.default_mode = mode
        settings_mod.save(s)

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        if self._bar:
            self._bar.set_paused(self._paused)

    def _toggle_privacy(self) -> None:
        self._privacy = not self._privacy
        if self._bar:
            self._bar.set_privacy(self._privacy)

    def _open_settings(self) -> None:
        if self._onboarding_proc and self._onboarding_proc.poll() is None:
            return
        self._onboarding_proc = subprocess.Popen([sys.executable, "-m", "murmur.onboarding"])

    def _rerun_onboarding(self) -> None:
        self._open_settings()

    def _quit(self) -> None:
        if self._hotkey:
            self._hotkey.stop()
        self._executor.shutdown(wait=False, cancel_futures=True)
        if self._bar:
            self._bar.quit_application()

    def _diagnostics(self) -> str:
        try:
            log = "\n".join(paths.log_path().read_text().splitlines()[-200:])
        except Exception:
            log = "(no log)"
        cfg_dict = settings_mod.load().__dict__
        bundle = f"--- Murmur diagnostics ---\nConfig: {cfg_dict}\n\nLast 200 log lines:\n{log}"
        return _API_KEY_PATTERN.sub("[REDACTED]", bundle)
