import logging
import threading
import time
from typing import Optional

import pyperclip
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventPost,
    CGEventSetFlags,
    kCGEventFlagMaskCommand,
    kCGHIDEventTap,
)

logger = logging.getLogger(__name__)
_KEY_V = 9
_PASTE_SETTLE_S = 0.1
# Long enough that (a) slow apps reading the pasteboard after the keystroke
# still get the dictation, and (b) if the synthetic paste never landed, the
# user has time to press Cmd+V manually before the old clipboard returns.
_CLIPBOARD_RESTORE_DELAY_S = 10.0

# Back-to-back dictations inside the restore window must hand the USER'S
# original clipboard forward, not restore one dictation over another.
_restore_lock = threading.Lock()
_pending_previous: Optional[str] = None
_pending_timer: Optional[threading.Timer] = None


def paste_text(text: str, restore_clipboard: bool = True) -> None:
    global _pending_previous, _pending_timer
    if not text:
        return
    previous = ""
    if restore_clipboard:
        try:
            previous = pyperclip.paste()
        except Exception:
            previous = ""
    pyperclip.copy(text)
    time.sleep(_PASTE_SETTLE_S)
    _post_cmd_key(_KEY_V)
    if not restore_clipboard:
        return
    with _restore_lock:
        if _pending_timer is not None:
            # A restore from the previous dictation is still pending: keep
            # ITS original clipboard, since what we just read was our own paste.
            _pending_timer.cancel()
            _pending_timer = None
            previous = _pending_previous or ""
        if not previous or previous == text:
            _pending_previous = None
            return
        _pending_previous = previous
        _pending_timer = threading.Timer(
            _CLIPBOARD_RESTORE_DELAY_S, _restore_clipboard_cb, args=(previous, text)
        )
        _pending_timer.daemon = True
        _pending_timer.start()


def _restore_clipboard_cb(previous: str, pasted: str) -> None:
    global _pending_previous, _pending_timer
    try:
        # Only restore if the clipboard still holds our pasted text;
        # if the user copied something in between, leave theirs alone.
        if pyperclip.paste() == pasted:
            pyperclip.copy(previous)
    except Exception:
        logger.debug("Clipboard restore skipped", exc_info=True)
    finally:
        with _restore_lock:
            _pending_previous = None
            _pending_timer = None


def _post_cmd_key(keycode: int) -> None:
    down = CGEventCreateKeyboardEvent(None, keycode, True)
    CGEventSetFlags(down, kCGEventFlagMaskCommand)
    CGEventPost(kCGHIDEventTap, down)
    up = CGEventCreateKeyboardEvent(None, keycode, False)
    CGEventSetFlags(up, kCGEventFlagMaskCommand)
    CGEventPost(kCGHIDEventTap, up)


def copy_only(text: str) -> None:
    pyperclip.copy(text)
