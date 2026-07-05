"""Subtle audio feedback for recording start/stop, like Wispr Flow's
dictation sounds. Uses macOS system sounds via NSSound (no subprocesses)."""
import logging

logger = logging.getLogger(__name__)

_VOLUME = 0.25
_NAMES = {
    "start": "Tink",
    "stop": "Pop",
    "error": "Basso",
}

enabled = True


def play(event: str) -> None:
    if not enabled:
        return
    name = _NAMES.get(event)
    if not name:
        return
    try:
        from AppKit import NSSound

        sound = NSSound.soundNamed_(name)
        if sound is None:
            return
        sound.setVolume_(_VOLUME)
        sound.play()
    except Exception:
        logger.debug("Sound %s failed", event, exc_info=True)
