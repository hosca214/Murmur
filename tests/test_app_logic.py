from murmur.app import MurmurApp
from murmur.settings import Settings


def make_app(auto_mode: bool, privacy: bool = False, mode: str = "email") -> MurmurApp:
    app = MurmurApp.__new__(MurmurApp)
    app._privacy = privacy
    app._mode = mode
    app._settings = Settings(auto_mode=auto_mode)
    return app


def test_privacy_forces_raw(mocker):
    app = make_app(auto_mode=True, privacy=True)
    detect = mocker.patch("murmur.app.frontmost.detect_mode")
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


def test_hold_end_ignored_for_tap_toggled_recording(mocker):
    # A long bare Option press during a tap-toggled dictation must not stop it
    app = make_app(auto_mode=False)
    app._ptt_active = False
    app._sm = mocker.MagicMock()
    end = mocker.patch.object(app, "_end_recording")
    app._handle_hold_end()
    app._sm.stop_if_recording.assert_not_called()
    end.assert_not_called()


def test_hold_end_stops_ptt_recording(mocker):
    app = make_app(auto_mode=False)
    app._ptt_active = True
    app._sm = mocker.MagicMock()
    app._sm.stop_if_recording.return_value = "stop_and_process"
    end = mocker.patch.object(app, "_end_recording")
    app._handle_hold_end()
    end.assert_called_once()
    assert app._ptt_active is False


def test_hold_cancel_ignored_for_tap_toggled_recording(mocker):
    # Option+E combo typing while a tap-toggled dictation runs: keep recording
    app = make_app(auto_mode=False)
    app._ptt_active = False
    cancel = mocker.patch.object(app, "_cancel_recording")
    app._handle_hold_cancel()
    cancel.assert_not_called()


def test_hold_cancel_cancels_ptt_recording(mocker):
    app = make_app(auto_mode=False)
    app._ptt_active = True
    cancel = mocker.patch.object(app, "_cancel_recording")
    app._handle_hold_cancel()
    cancel.assert_called_once()
    assert app._ptt_active is False
