import logging
import logging.handlers
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

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
        self._recorder = AudioRecorder(max_seconds=self._settings.max_recording_seconds)
        self._transcriber: Optional[Transcriber] = None
        self._pill = Pill()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pipeline")
        self._mode = self._settings.default_mode
        self._privacy = False
        self._paused = False
        self._hotkey: Optional[HotkeyListener] = None
        self._bar: Optional[MenuBar] = None
        self._raw_for_current: str = ""
        self._cancel_cleanup = threading.Event()
        history.purge_old_audio(self._settings.audio_retention_days)

    def run(self) -> None:
        threading.Thread(target=self._warmup, daemon=True, name="warmup").start()
        self._hotkey = HotkeyListener(
            key_name=self._settings.hotkey,
            tap_threshold_ms=self._settings.tap_threshold_ms,
            on_tap=self._handle_tap,
            on_hold_start=self._handle_hold_start,
            on_hold_end=self._handle_hold_end,
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
        elif action == "queue_next":
            self._pill.show("Queued (1)")
        elif action == "cancel_cleanup_and_paste_raw":
            self._cancel_cleanup.set()
            self._sm.queued_tap = True

    def _begin_recording(self) -> None:
        self._pill.show("Listening…")
        if self._bar:
            self._bar.set_recording(True)
        self._recorder.start(on_auto_stop=self._on_recording_max)

    def _on_recording_max(self) -> None:
        action = self._sm.recording_max_reached()
        if action == "stop_and_process":
            self._pill.show("5 min limit — processing")
            self._end_recording()

    def _end_recording(self) -> None:
        if self._bar:
            self._bar.set_recording(False)
        audio = self._recorder.stop()
        self._executor.submit(self._process, audio)

    def _process(self, audio) -> None:
        try:
            self._pill.show("Transcribing…")
            assert self._transcriber is not None
            raw = self._transcriber.transcribe(audio)
            self._raw_for_current = raw
            self._sm.transcription_complete()
            mode = "raw" if self._privacy else self._mode
            self._cancel_cleanup.clear()
            self._pill.show("Polishing…" if mode != "raw" else "Pasting…")
            vocab = clean.load_vocabulary(self._settings.vocabulary_path)
            cleaned = self._cleanup(raw, mode, vocab)
            self._sm.cleaning_complete()
            output.paste_text(cleaned)
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
            self._pill.hide()
            next_action = self._sm.paste_complete()
            if next_action == "start_recording":
                self._begin_recording()

    def _cleanup(self, raw: str, mode: str, vocab: list[str]) -> str:
        if self._cancel_cleanup.is_set():
            return raw
        return clean.clean(raw, mode=mode, api_key=self._api_key, vocabulary=vocab)

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
        from murmur.onboarding import OnboardingWindow
        threading.Thread(
            target=lambda: OnboardingWindow(on_finish=lambda: None).run(),
            daemon=True,
        ).start()

    def _rerun_onboarding(self) -> None:
        self._open_settings()

    def _quit(self) -> None:
        if self._hotkey:
            self._hotkey.stop()
        self._executor.shutdown(wait=False, cancel_futures=True)
        if self._bar:
            self._bar.quit_application()

    def _diagnostics(self) -> str:
        log = ""
        try:
            log = paths.log_path().read_text().splitlines()[-200:]
            log = "\n".join(log)
        except Exception:
            log = "(no log)"
        cfg = settings_mod.load()
        cfg_dict = cfg.__dict__.copy()
        return f"--- Murmur diagnostics ---\nConfig: {cfg_dict}\n\nLast 200 log lines:\n{log}"
