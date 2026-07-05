import logging
import threading
import time

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
_KEY_Z = 6
_PASTE_SETTLE_S = 0.1
_CLIPBOARD_RESTORE_DELAY_S = 0.7


def paste_text(text: str, restore_clipboard: bool = True) -> None:
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
    if restore_clipboard and previous and previous != text:
        timer = threading.Timer(_CLIPBOARD_RESTORE_DELAY_S, _restore_clipboard, args=(previous, text))
        timer.daemon = True
        timer.start()


def _restore_clipboard(previous: str, pasted: str) -> None:
    try:
        # Only restore if the clipboard still holds our pasted text;
        # if the user copied something in between, leave theirs alone.
        if pyperclip.paste() == pasted:
            pyperclip.copy(previous)
    except Exception:
        logger.debug("Clipboard restore skipped", exc_info=True)


def undo_paste() -> None:
    _post_cmd_key(_KEY_Z)


def _post_cmd_key(keycode: int) -> None:
    down = CGEventCreateKeyboardEvent(None, keycode, True)
    CGEventSetFlags(down, kCGEventFlagMaskCommand)
    CGEventPost(kCGHIDEventTap, down)
    up = CGEventCreateKeyboardEvent(None, keycode, False)
    CGEventSetFlags(up, kCGEventFlagMaskCommand)
    CGEventPost(kCGHIDEventTap, up)


def copy_only(text: str) -> None:
    pyperclip.copy(text)
