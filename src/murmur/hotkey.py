import logging
import threading
import time
from typing import Callable, Optional

from pynput import keyboard

logger = logging.getLogger(__name__)

_KEY_MAP = {
    "right_option": keyboard.Key.alt_r,
    "left_option": keyboard.Key.alt_l,
    "right_command": keyboard.Key.cmd_r,
    "left_command": keyboard.Key.cmd_l,
    "right_control": keyboard.Key.ctrl_r,
    "left_control": keyboard.Key.ctrl_l,
    "caps_lock": keyboard.Key.caps_lock,
    "fn": keyboard.Key.f19,
}

# If another key is pressed within this window of the hotkey going down, the
# user is typing a keyboard combo (e.g. Option+E for accents), not dictating.
_INTERRUPT_WINDOW_S = 1.0


def resolve_key(name: str) -> keyboard.Key:
    if name not in _KEY_MAP:
        raise ValueError(f"Unknown hotkey: {name}")
    return _KEY_MAP[name]


class HotkeyListener:
    def __init__(
        self,
        key_name: str,
        tap_threshold_ms: int,
        on_tap: Callable[[], None],
        on_hold_start: Callable[[], None],
        on_hold_end: Callable[[], None],
        on_double_tap: Optional[Callable[[], None]] = None,
        on_hold_cancel: Optional[Callable[[], None]] = None,
        on_esc: Optional[Callable[[], None]] = None,
        double_tap_window_ms: int = 300,
    ) -> None:
        self._key = resolve_key(key_name)
        self._threshold_s = tap_threshold_ms / 1000.0
        self._double_tap_window_s = double_tap_window_ms / 1000.0
        self._on_tap = on_tap
        self._on_hold_start = on_hold_start
        self._on_hold_end = on_hold_end
        self._on_double_tap = on_double_tap
        self._on_hold_cancel = on_hold_cancel
        self._on_esc = on_esc
        self._press_time: Optional[float] = None
        self._hold_active = False
        self._interrupted = False
        self._hold_timer: Optional[threading.Timer] = None
        self._last_tap_time: float = 0.0
        self._listener: Optional[keyboard.Listener] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._listener.start()

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None

    def is_alive(self) -> bool:
        return self._listener is not None and self._listener.is_alive()

    def _on_press(self, key) -> None:
        if key == keyboard.Key.esc and self._on_esc is not None:
            try:
                self._on_esc()
            except Exception:
                logger.exception("on_esc raised")
            return
        if key != self._key:
            self._note_other_key()
            return
        with self._lock:
            if self._press_time is not None:
                return
            self._press_time = time.time()
            self._hold_active = False
            self._interrupted = False
            self._hold_timer = threading.Timer(self._threshold_s, self._fire_hold_start)
            self._hold_timer.daemon = True
            self._hold_timer.start()

    def _note_other_key(self) -> None:
        """Another key was pressed. If our hotkey just went down, the user is
        typing a combo, so cancel the gesture instead of dictating."""
        fire_cancel = False
        with self._lock:
            if self._press_time is None or self._interrupted:
                return
            if time.time() - self._press_time > _INTERRUPT_WINDOW_S:
                return
            self._interrupted = True
            if self._hold_timer:
                self._hold_timer.cancel()
                self._hold_timer = None
            fire_cancel = self._hold_active
        if fire_cancel and self._on_hold_cancel is not None:
            try:
                self._on_hold_cancel()
            except Exception:
                logger.exception("on_hold_cancel raised")

    def _fire_hold_start(self) -> None:
        with self._lock:
            if self._press_time is None or self._interrupted:
                return
            self._hold_active = True
        try:
            self._on_hold_start()
        except Exception:
            logger.exception("on_hold_start raised")

    def _on_release(self, key) -> None:
        if key != self._key:
            return
        with self._lock:
            if self._press_time is None:
                return
            if self._hold_timer:
                self._hold_timer.cancel()
                self._hold_timer = None
            was_hold = self._hold_active
            was_interrupted = self._interrupted
            self._press_time = None
            self._hold_active = False
            self._interrupted = False
            now = time.time()
            is_double = (
                not was_hold
                and not was_interrupted
                and self._on_double_tap is not None
                and (now - self._last_tap_time) < self._double_tap_window_s
            )
            if was_interrupted:
                self._last_tap_time = 0.0
            else:
                self._last_tap_time = 0.0 if is_double else now
        if was_interrupted:
            return
        try:
            if was_hold:
                self._on_hold_end()
            else:
                self._on_tap()
                if is_double:
                    self._on_double_tap()
        except Exception:
            logger.exception("hotkey callback raised")
