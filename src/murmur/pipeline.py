import logging
import os
import threading
import time
import wave
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)
SAMPLE_RATE = 16000


class AudioRecorder:
    def __init__(self, max_seconds: int, level_callback=None) -> None:
        self._max_seconds = max_seconds
        self._chunks: list[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()
        self._start_time: float = 0.0
        self._auto_stop_timer: Optional[threading.Timer] = None
        self._auto_stop_callback = None
        self._level_callback = level_callback

    def start(self, on_auto_stop=None) -> None:
        with self._lock:
            self._chunks = []
            self._start_time = time.time()
            self._auto_stop_callback = on_auto_stop
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                callback=self._callback,
                blocksize=1024,
            )
            self._stream.start()
            self._auto_stop_timer = threading.Timer(self._max_seconds, self._auto_stop)
            self._auto_stop_timer.daemon = True
            self._auto_stop_timer.start()

    def _callback(self, indata, frames, time_info, status) -> None:
        if status:
            logger.debug("Audio status: %s", status)
        self._chunks.append(indata.copy())
        if self._level_callback is not None:
            try:
                rms = float(np.sqrt(np.mean(indata.astype(np.float32) ** 2)))
                self._level_callback(rms)
            except Exception:
                pass

    def _auto_stop(self) -> None:
        if self._auto_stop_callback:
            self._auto_stop_callback()

    def stop(self) -> np.ndarray:
        with self._lock:
            if self._auto_stop_timer:
                self._auto_stop_timer.cancel()
                self._auto_stop_timer = None
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
                self._stream = None
            if not self._chunks:
                return np.zeros(0, dtype=np.float32)
            audio = np.concatenate(self._chunks, axis=0).flatten()
            self._chunks = []
            return audio

    def is_recording(self) -> bool:
        return self._stream is not None


def save_wav(audio: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(pcm16.tobytes())


# Whisper-mode support: quiet speech (whispering, low mic gain) records at
# peaks of ~0.005-0.05 and the VAD discards it as non-speech. Normalizing to
# a strong peak first makes whispered dictation work. Recordings whose peak
# is below the noise floor are left alone so amplified room hiss can't turn
# into hallucinated text.
_NORMALIZE_TARGET = 0.9
_NORMALIZE_BELOW_PEAK = 0.5
_NOISE_FLOOR_PEAK = 0.003


def prepare_audio(audio: np.ndarray) -> np.ndarray:
    if audio.size == 0:
        return audio
    peak = float(np.max(np.abs(audio)))
    if _NOISE_FLOOR_PEAK <= peak < _NORMALIZE_BELOW_PEAK:
        return np.clip(audio * (_NORMALIZE_TARGET / peak), -1.0, 1.0)
    return audio


class Transcriber:
    def __init__(self, model_name: str, compute_type: str) -> None:
        logger.info("Loading Whisper model %s (%s)", model_name, compute_type)
        threads = min(8, os.cpu_count() or 4)
        try:
            # Cached model first: no network round trip, works offline
            self._model = WhisperModel(
                model_name, device="cpu", compute_type=compute_type,
                local_files_only=True, cpu_threads=threads,
            )
        except Exception:
            logger.info("Model not cached yet; downloading %s", model_name)
            self._model = WhisperModel(
                model_name, device="cpu", compute_type=compute_type, cpu_threads=threads
            )
        logger.info("Whisper model loaded")

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""
        segments, _info = self._model.transcribe(
            prepare_audio(audio),
            language="en",
            beam_size=1,
            # Dictations are single utterances: skipping timestamps and
            # cross-window conditioning is faster and hallucinates less
            without_timestamps=True,
            condition_on_previous_text=False,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300, "threshold": 0.2},
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
