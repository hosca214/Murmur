import logging
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


def paste_text(text: str) -> None:
    if not text:
        return
    pyperclip.copy(text)
    time.sleep(0.05)
    _post_cmd_key(_KEY_V)


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
