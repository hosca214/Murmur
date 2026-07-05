import time

from pynput import keyboard

from murmur.hotkey import HotkeyListener

TAP_MS = 40
HOLD_WAIT_S = 0.09
DOUBLE_WINDOW_MS = 300


class Recorder:
    def __init__(self):
        self.calls = []

    def make(self, name):
        def cb():
            self.calls.append(name)
        return cb


def make_listener(rec: Recorder) -> HotkeyListener:
    return HotkeyListener(
        key_name="right_option",
        tap_threshold_ms=TAP_MS,
        on_tap=rec.make("tap"),
        on_hold_start=rec.make("hold_start"),
        on_hold_end=rec.make("hold_end"),
        on_double_tap=rec.make("double_tap"),
        on_hold_cancel=rec.make("hold_cancel"),
        on_esc=rec.make("esc"),
        double_tap_window_ms=DOUBLE_WINDOW_MS,
    )


KEY = keyboard.Key.alt_r
OTHER = keyboard.KeyCode.from_char("e")


def test_quick_tap_fires_on_tap():
    rec = Recorder()
    hl = make_listener(rec)
    hl._on_press(KEY)
    hl._on_release(KEY)
    assert rec.calls == ["tap"]


def test_hold_fires_start_and_end():
    rec = Recorder()
    hl = make_listener(rec)
    hl._on_press(KEY)
    time.sleep(HOLD_WAIT_S)
    hl._on_release(KEY)
    assert rec.calls == ["hold_start", "hold_end"]


def test_double_tap_fires_after_second_tap():
    rec = Recorder()
    hl = make_listener(rec)
    hl._on_press(KEY)
    hl._on_release(KEY)
    hl._on_press(KEY)
    hl._on_release(KEY)
    assert rec.calls == ["tap", "tap", "double_tap"]


def test_slow_second_tap_is_not_double():
    rec = Recorder()
    hl = make_listener(rec)
    hl._on_press(KEY)
    hl._on_release(KEY)
    hl._last_tap_time -= (DOUBLE_WINDOW_MS / 1000.0) + 0.05
    hl._on_press(KEY)
    hl._on_release(KEY)
    assert rec.calls == ["tap", "tap"]


def test_combo_typing_cancels_tap():
    # Option+E for an accent: another key while our key is down means no dictation
    rec = Recorder()
    hl = make_listener(rec)
    hl._on_press(KEY)
    hl._on_press(OTHER)
    hl._on_release(KEY)
    assert rec.calls == []


def test_combo_during_active_hold_fires_hold_cancel():
    rec = Recorder()
    hl = make_listener(rec)
    hl._on_press(KEY)
    time.sleep(HOLD_WAIT_S)  # hold timer fires, recording starts
    hl._on_press(OTHER)
    hl._on_release(KEY)
    assert rec.calls == ["hold_start", "hold_cancel"]


def test_interrupted_tap_does_not_count_toward_double():
    rec = Recorder()
    hl = make_listener(rec)
    hl._on_press(KEY)
    hl._on_press(OTHER)
    hl._on_release(KEY)
    hl._on_press(KEY)
    hl._on_release(KEY)
    assert rec.calls == ["tap"]


def test_esc_fires_on_esc():
    rec = Recorder()
    hl = make_listener(rec)
    hl._on_press(keyboard.Key.esc)
    assert rec.calls == ["esc"]


def test_other_key_alone_is_ignored():
    rec = Recorder()
    hl = make_listener(rec)
    hl._on_press(OTHER)
    hl._on_release(OTHER)
    assert rec.calls == []
