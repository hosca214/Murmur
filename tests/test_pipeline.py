import numpy as np

from murmur.pipeline import _NOISE_FLOOR_PEAK, _NORMALIZE_TARGET, prepare_audio


def test_whisper_quiet_audio_is_normalized():
    # A whispered dictation peaks around 0.01; it must be boosted to a
    # strong level or the VAD discards it as non-speech
    quiet = np.sin(np.linspace(0, 100, 16000)).astype(np.float32) * 0.01
    out = prepare_audio(quiet)
    assert abs(float(np.max(np.abs(out))) - _NORMALIZE_TARGET) < 0.01


def test_noise_floor_audio_left_alone():
    # Near-silence must NOT be amplified (hallucination guard)
    noise = np.sin(np.linspace(0, 100, 16000)).astype(np.float32) * 0.001
    assert _NOISE_FLOOR_PEAK > 0.001
    out = prepare_audio(noise)
    assert float(np.max(np.abs(out))) <= 0.0011


def test_normal_volume_audio_untouched():
    loud = np.sin(np.linspace(0, 100, 16000)).astype(np.float32) * 0.8
    out = prepare_audio(loud)
    assert out is loud


def test_empty_audio_passthrough():
    empty = np.zeros(0, dtype=np.float32)
    assert prepare_audio(empty).size == 0
