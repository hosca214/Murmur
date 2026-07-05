import logging
import threading
import tkinter as tk
from typing import Optional

logger = logging.getLogger(__name__)


class _NSPanelPill:
    def __init__(self) -> None:
        import AppKit  # noqa: F401  — probe import; build lazily on first show
        self._panel = None
        self._label = None

    def _build(self) -> None:
        from AppKit import (
            NSBackingStoreBuffered,
            NSColor,
            NSFloatingWindowLevel,
            NSPanel,
            NSScreen,
            NSTextField,
            NSWindowStyleMaskBorderless,
            NSWindowStyleMaskNonactivatingPanel,
        )
        from Foundation import NSMakeRect

        w, h = 220, 44
        screen = NSScreen.mainScreen().frame()
        x = (screen.size.width - w) / 2
        rect = NSMakeRect(x, 80, w, h)
        mask = NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel
        self._panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, mask, NSBackingStoreBuffered, False
        )
        self._panel.setLevel_(NSFloatingWindowLevel)
        self._panel.setOpaque_(False)
        self._panel.setBackgroundColor_(NSColor.colorWithCalibratedWhite_alpha_(0.0, 0.85))
        self._panel.setHasShadow_(True)
        self._label = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 10, w, 24))
        self._label.setBezeled_(False)
        self._label.setDrawsBackground_(False)
        self._label.setEditable_(False)
        self._label.setSelectable_(False)
        self._label.setAlignment_(2)
        self._label.setTextColor_(NSColor.whiteColor())
        self._label.setStringValue_("Murmur")
        self._panel.contentView().addSubview_(self._label)

    def show(self, text: str) -> None:
        from PyObjCTools import AppHelper

        def _do():
            if self._panel is None:
                self._build()
            self._label.setStringValue_(text)
            self._panel.orderFront_(None)

        AppHelper.callAfter(_do)

    def hide(self) -> None:
        from PyObjCTools import AppHelper

        def _do():
            if self._panel is not None:
                self._panel.orderOut_(None)

        AppHelper.callAfter(_do)


class _TkPill:
    def __init__(self) -> None:
        self._root: Optional[tk.Tk] = None
        self._label: Optional[tk.Label] = None
        self._lock = threading.Lock()

    def _ensure(self) -> None:
        if self._root is None:
            self._root = tk.Tk()
            self._root.overrideredirect(True)
            self._root.attributes("-topmost", True)
            self._root.attributes("-alpha", 0.85)
            self._root.configure(bg="#111")
            self._label = tk.Label(self._root, text="Murmur", fg="white", bg="#111", font=("SF Pro", 14))
            self._label.pack(padx=20, pady=10)
            self._root.geometry("+{}+80".format(self._root.winfo_screenwidth() // 2 - 110))
            self._root.withdraw()

    def show(self, text: str) -> None:
        with self._lock:
            self._ensure()
            self._label.config(text=text)
            self._root.deiconify()
            self._root.update_idletasks()

    def hide(self) -> None:
        with self._lock:
            if self._root:
                self._root.withdraw()
                self._root.update_idletasks()


class Pill:
    def __init__(self) -> None:
        self._impl = None
        try:
            self._impl = _NSPanelPill()
            logger.info("Pill: using NSPanel")
        except Exception as exc:
            logger.warning("NSPanel failed (%s); falling back to Tk", exc)
            self._impl = _TkPill()

    def show(self, text: str) -> None:
        self._impl.show(text)

    def hide(self) -> None:
        self._impl.hide()
