import threading
from enum import Enum, auto
from typing import Optional


class RecordingState(Enum):
    COLD_START = auto()
    IDLE = auto()
    RECORDING = auto()


class StateMachine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.state = RecordingState.COLD_START
        self.queued_tap: bool = False

    def warmup_complete(self) -> Optional[str]:
        with self._lock:
            if self.state != RecordingState.COLD_START:
                return None
            if self.queued_tap:
                self.queued_tap = False
                self.state = RecordingState.RECORDING
                return "start_recording"
            self.state = RecordingState.IDLE
            return None

    def on_tap(self) -> str:
        with self._lock:
            if self.state == RecordingState.COLD_START:
                self.queued_tap = True
                return "queue_after_warmup"
            if self.state == RecordingState.IDLE:
                self.state = RecordingState.RECORDING
                return "start_recording"
            if self.state == RecordingState.RECORDING:
                self.state = RecordingState.IDLE
                return "stop_and_process"
            return ""

    def recording_max_reached(self) -> str:
        with self._lock:
            if self.state == RecordingState.RECORDING:
                self.state = RecordingState.IDLE
                return "stop_and_process"
            return ""

    def cancel(self) -> str:
        with self._lock:
            if self.state == RecordingState.RECORDING:
                self.state = RecordingState.IDLE
                return "cancel_recording"
            if self.state == RecordingState.COLD_START and self.queued_tap:
                self.queued_tap = False
                return "cancel_queued"
            return ""
