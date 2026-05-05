import threading
from enum import Enum, auto
from typing import Optional


class RecordingState(Enum):
    COLD_START = auto()
    IDLE = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()
    CLEANING = auto()
    PASTING = auto()


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
                self.state = RecordingState.TRANSCRIBING
                return "stop_and_process"
            if self.state == RecordingState.TRANSCRIBING:
                self.queued_tap = True
                return "queue_next"
            if self.state == RecordingState.CLEANING:
                return "cancel_cleanup_and_paste_raw"
            if self.state == RecordingState.PASTING:
                self.queued_tap = True
                return "queue_next"
            return ""

    def recording_max_reached(self) -> str:
        with self._lock:
            if self.state == RecordingState.RECORDING:
                self.state = RecordingState.TRANSCRIBING
                return "stop_and_process"
            return ""

    def transcription_complete(self) -> None:
        with self._lock:
            if self.state == RecordingState.TRANSCRIBING:
                self.state = RecordingState.CLEANING

    def cleaning_complete(self) -> None:
        with self._lock:
            if self.state == RecordingState.CLEANING:
                self.state = RecordingState.PASTING

    def paste_complete(self) -> Optional[str]:
        with self._lock:
            if self.state != RecordingState.PASTING:
                return None
            if self.queued_tap:
                self.queued_tap = False
                self.state = RecordingState.RECORDING
                return "start_recording"
            self.state = RecordingState.IDLE
            return None
