import logging
from pathlib import Path
from typing import Callable

import rumps

from murmur import history, output

logger = logging.getLogger(__name__)
_ASSETS = Path(__file__).parent.parent / "assets"

_HOTKEY_LABELS = (
    ("Right Option", "right_option"),
    ("Left Option", "left_option"),
    ("Right Command", "right_command"),
    ("Caps Lock", "caps_lock"),
)


class MenuBar(rumps.App):
    def __init__(
        self,
        on_mode_change: Callable[[str], None],
        on_auto_mode_toggle: Callable[[], None],
        on_hotkey_change: Callable[[str], None],
        on_sounds_toggle: Callable[[], None],
        on_pause_toggle: Callable[[], None],
        on_privacy_toggle: Callable[[], None],
        on_edit_vocabulary: Callable[[], None],
        on_open_settings: Callable[[], None],
        on_rerun_onboarding: Callable[[], None],
        on_quit: Callable[[], None],
        on_diagnostics: Callable[[], str],
    ) -> None:
        super().__init__(
            "Murmur",
            title="Murmur",
            icon=str(_ASSETS / "icon-idle.png"),
            template=True,
            quit_button=None,
        )
        self._on_mode_change = on_mode_change
        self._on_auto_mode_toggle = on_auto_mode_toggle
        self._on_hotkey_change = on_hotkey_change
        self._on_sounds_toggle = on_sounds_toggle
        self._on_pause_toggle = on_pause_toggle
        self._on_privacy_toggle = on_privacy_toggle
        self._on_edit_vocabulary = on_edit_vocabulary
        self._on_open_settings = on_open_settings
        self._on_rerun_onboarding = on_rerun_onboarding
        self._on_quit = on_quit
        self._on_diagnostics = on_diagnostics
        self._mode_items: dict[str, rumps.MenuItem] = {}
        self._hotkey_items: dict[str, rumps.MenuItem] = {}
        self._auto_item: rumps.MenuItem | None = None
        self._build()

    def _build(self) -> None:
        mode_menu = rumps.MenuItem("Mode")
        self._auto_item = rumps.MenuItem(
            "Auto (match app)", callback=lambda _: self._on_auto_mode_toggle()
        )
        mode_menu.add(self._auto_item)
        mode_menu.add(None)
        for m in ("email", "chat", "notes", "raw"):
            item = rumps.MenuItem(m.capitalize(), callback=self._make_mode_callback(m))
            self._mode_items[m] = item
            mode_menu.add(item)

        hotkey_menu = rumps.MenuItem("Hotkey")
        for label, value in _HOTKEY_LABELS:
            item = rumps.MenuItem(label, callback=self._make_hotkey_callback(value))
            self._hotkey_items[value] = item
            hotkey_menu.add(item)

        history_menu = rumps.MenuItem("History", callback=self._refresh_history)
        help_menu = rumps.MenuItem("Help")
        help_menu.add(rumps.MenuItem("Copy diagnostics", callback=self._copy_diagnostics))
        help_menu.add(rumps.MenuItem("Re-run onboarding", callback=lambda _: self._on_rerun_onboarding()))
        self.menu = [
            mode_menu,
            rumps.MenuItem("Pause", callback=lambda _: self._on_pause_toggle()),
            rumps.MenuItem("Privacy mode", callback=lambda _: self._on_privacy_toggle()),
            None,
            history_menu,
            rumps.MenuItem("Edit vocabulary", callback=lambda _: self._on_edit_vocabulary()),
            None,
            hotkey_menu,
            rumps.MenuItem("Sounds", callback=lambda _: self._on_sounds_toggle()),
            rumps.MenuItem("Settings", callback=lambda _: self._on_open_settings()),
            help_menu,
            None,
            rumps.MenuItem("Quit Murmur", callback=lambda _: self._on_quit()),
        ]

    def _make_mode_callback(self, mode: str) -> Callable[[rumps.MenuItem], None]:
        def cb(_):
            self._on_mode_change(mode)
        return cb

    def _make_hotkey_callback(self, value: str) -> Callable[[rumps.MenuItem], None]:
        def cb(_):
            self._on_hotkey_change(value)
        return cb

    def set_active_mode(self, mode: str, auto: bool = False) -> None:
        if self._auto_item is not None:
            self._auto_item.state = 1 if auto else 0
        for m, item in self._mode_items.items():
            item.state = 1 if (m == mode and not auto) else 0

    def set_active_hotkey(self, value: str) -> None:
        for v, item in self._hotkey_items.items():
            item.state = 1 if v == value else 0

    def set_sounds(self, enabled: bool) -> None:
        self.menu["Sounds"].state = 1 if enabled else 0

    def set_recording(self, recording: bool) -> None:
        self.icon = str(_ASSETS / ("icon-recording.png" if recording else "icon-idle.png"))

    def set_paused(self, paused: bool) -> None:
        self.menu["Pause"].state = 1 if paused else 0

    def set_privacy(self, privacy: bool) -> None:
        self.menu["Privacy mode"].state = 1 if privacy else 0

    def set_hotkey_warning(self, warn: bool) -> None:
        self.title = "⚠ Murmur" if warn else "Murmur"

    def _refresh_history(self, sender) -> None:
        sender.clear()
        for entry in history.load(limit=20):
            label = entry.cleaned[:60].replace("\n", " ")
            mi = rumps.MenuItem(label, callback=self._make_recopy_callback(entry.cleaned))
            sender.add(mi)
        if not sender:
            sender.add(rumps.MenuItem("(empty)"))

    def _make_recopy_callback(self, text: str) -> Callable[[rumps.MenuItem], None]:
        def cb(_):
            output.copy_only(text)
            rumps.notification("Murmur", "Copied to clipboard", text[:80])
        return cb

    def _copy_diagnostics(self, _) -> None:
        bundle = self._on_diagnostics()
        output.copy_only(bundle)
        rumps.notification("Murmur", "Diagnostics copied", "Paste into your support message.")
