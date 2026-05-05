"""Manual: record 5 seconds, transcribe, print result."""
import sys
import time

from murmur.pipeline import AudioRecorder, Transcriber
from murmur.settings import load


def main() -> int:
    s = load()
    rec = AudioRecorder(max_seconds=s.max_recording_seconds)
    print(f"Recording 5 seconds (model={s.model})...")
    rec.start()
    time.sleep(5)
    audio = rec.stop()
    print(f"Captured {audio.size / 16000:.1f}s of audio.")
    print("Loading Whisper (first time = slow)...")
    t0 = time.time()
    tx = Transcriber(s.model, s.compute_type)
    print(f"Loaded in {time.time() - t0:.1f}s.")
    print("Transcribing...")
    t0 = time.time()
    text = tx.transcribe(audio)
    print(f"Transcribed in {time.time() - t0:.1f}s.")
    print(f"\nTranscript: {text!r}")
    return 0 if text else 1


if __name__ == "__main__":
    sys.exit(main())
