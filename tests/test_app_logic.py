import time

from murmur.app import MurmurApp, _UNDO_WINDOW_S
from murmur.settings import Settings


def make_app(auto_mode: bool, privacy: bool = False, mode: str = "email") -> MurmurApp:
    app = MurmurApp.__new__(MurmurApp)
    app._privacy = privacy
    app._mode = mode
    app._settings = Settings(auto_mode=auto_mode)
    return app


def test_privacy_forces_raw(mocker):
    app = make_app(auto_mode=True, privacy=True)
    detect = mocker.patch("murmur.frontmost.detect_mode")
    assert app._pick_mode() == "raw"
    detect.assert_not_called()


def test_auto_mode_uses_frontmost_detection(mocker):
    app = make_app(auto_mode=True)
    mocker.patch("murmur.app.frontmost.detect_mode", return_value="chat")
    assert app._pick_mode() == "chat"


def test_manual_mode_skips_detection(mocker):
    app = make_app(auto_mode=False, mode="notes")
    detect = mocker.patch("murmur.app.frontmost.detect_mode")
    assert app._pick_mode() == "notes"
    detect.assert_not_called()


def test_double_tap_undo_respects_window(mocker):
    app = make_app(auto_mode=False)
    app._paused = False
    app._last_paste_ts = time.time() - (_UNDO_WINDOW_S + 1)

    class FakeSM:
        state = __import__("murmur.state", fromlist=["RecordingState"]).RecordingState.IDLE

    app._sm = FakeSM()
    app._pill = mocker.MagicMock()
    undo = mocker.patch("murmur.app.output.undo_paste")
    app._handle_double_tap()
    undo.assert_not_called()
    app._pill.flash.assert_called_once()

    app._last_paste_ts = time.time() - 2
    app._handle_double_tap()
    undo.assert_called_once()
