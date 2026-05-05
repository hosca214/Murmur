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


def paste_text(text: str) -> None:
    if not text:
        return
    pyperclip.copy(text)
    time.sleep(0.05)
    _post_cmd_v()


def _post_cmd_v() -> None:
    down = CGEventCreateKeyboardEvent(None, _KEY_V, True)
    CGEventSetFlags(down, kCGEventFlagMaskCommand)
    CGEventPost(kCGHIDEventTap, down)
    up = CGEventCreateKeyboardEvent(None, _KEY_V, False)
    CGEventSetFlags(up, kCGEventFlagMaskCommand)
    CGEventPost(kCGHIDEventTap, up)


def copy_only(text: str) -> None:
    pyperclip.copy(text)
