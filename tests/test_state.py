from murmur.state import RecordingState, StateMachine


def test_initial_state_is_cold_start():
    sm = StateMachine()
    assert sm.state == RecordingState.COLD_START


def test_warmup_complete_moves_to_idle():
    sm = StateMachine()
    sm.warmup_complete()
    assert sm.state == RecordingState.IDLE


def test_tap_during_idle_starts_recording():
    sm = StateMachine()
    sm.warmup_complete()
    action = sm.on_tap()
    assert action == "start_recording"
    assert sm.state == RecordingState.RECORDING


def test_tap_during_recording_stops_and_processes():
    sm = StateMachine()
    sm.warmup_complete()
    sm.on_tap()
    action = sm.on_tap()
    assert action == "stop_and_process"
    assert sm.state == RecordingState.IDLE


def test_tap_during_cold_start_queues_recording():
    sm = StateMachine()
    action = sm.on_tap()
    assert action == "queue_after_warmup"
    assert sm.state == RecordingState.COLD_START
    assert sm.queued_tap is True


def test_warmup_complete_with_queued_tap_starts_recording():
    sm = StateMachine()
    sm.on_tap()
    action = sm.warmup_complete()
    assert action == "start_recording"
    assert sm.state == RecordingState.RECORDING


def test_warmup_complete_only_fires_once():
    sm = StateMachine()
    sm.warmup_complete()
    assert sm.warmup_complete() is None


def test_tap_toggles_recording_repeatedly():
    sm = StateMachine()
    sm.warmup_complete()
    for _ in range(3):
        assert sm.on_tap() == "start_recording"
        assert sm.on_tap() == "stop_and_process"
    assert sm.state == RecordingState.IDLE


def test_max_recording_auto_stops():
    sm = StateMachine()
    sm.warmup_complete()
    sm.on_tap()
    action = sm.recording_max_reached()
    assert action == "stop_and_process"
    assert sm.state == RecordingState.IDLE


def test_max_recording_noop_when_idle():
    sm = StateMachine()
    sm.warmup_complete()
    assert sm.recording_max_reached() == ""
    assert sm.state == RecordingState.IDLE


def test_cancel_while_recording():
    sm = StateMachine()
    sm.warmup_complete()
    sm.on_tap()
    assert sm.cancel() == "cancel_recording"
    assert sm.state == RecordingState.IDLE


def test_cancel_clears_queued_tap_during_cold_start():
    sm = StateMachine()
    sm.on_tap()
    assert sm.queued_tap is True
    assert sm.cancel() == "cancel_queued"
    assert sm.queued_tap is False


def test_cancel_noop_when_idle():
    sm = StateMachine()
    sm.warmup_complete()
    assert sm.cancel() == ""
    assert sm.state == RecordingState.IDLE
