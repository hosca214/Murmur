import pytest

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


def test_tap_during_recording_starts_processing():
    sm = StateMachine()
    sm.warmup_complete()
    sm.on_tap()
    action = sm.on_tap()
    assert action == "stop_and_process"
    assert sm.state == RecordingState.TRANSCRIBING


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


def test_tap_during_transcribing_queues_one():
    sm = StateMachine()
    sm.warmup_complete()
    sm.on_tap()
    sm.on_tap()
    action = sm.on_tap()
    assert action == "queue_next"
    assert sm.state == RecordingState.TRANSCRIBING
    assert sm.queued_tap is True


def test_tap_during_cleaning_cancels_cleanup():
    sm = StateMachine()
    sm.warmup_complete()
    sm.on_tap()
    sm.on_tap()
    sm.transcription_complete()
    action = sm.on_tap()
    assert action == "cancel_cleanup_and_paste_raw"


def test_tap_during_pasting_queues_next():
    sm = StateMachine()
    sm.warmup_complete()
    sm.on_tap()
    sm.on_tap()
    sm.transcription_complete()
    sm.cleaning_complete()
    action = sm.on_tap()
    assert action == "queue_next"


def test_pipeline_complete_returns_to_idle():
    sm = StateMachine()
    sm.warmup_complete()
    sm.on_tap()
    sm.on_tap()
    sm.transcription_complete()
    sm.cleaning_complete()
    sm.paste_complete()
    assert sm.state == RecordingState.IDLE


def test_pipeline_complete_starts_queued_recording():
    sm = StateMachine()
    sm.warmup_complete()
    sm.on_tap()
    sm.on_tap()
    sm.on_tap()
    sm.transcription_complete()
    sm.cleaning_complete()
    action = sm.paste_complete()
    assert action == "start_recording"
    assert sm.state == RecordingState.RECORDING


def test_max_recording_auto_stops():
    sm = StateMachine()
    sm.warmup_complete()
    sm.on_tap()
    action = sm.recording_max_reached()
    assert action == "stop_and_process"
    assert sm.state == RecordingState.TRANSCRIBING
