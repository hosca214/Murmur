import logging
import subprocess
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import ttk
from typing import Callable, Optional

import google.generativeai as genai

from murmur import paths, settings as settings_mod
from murmur.hotkey import resolve_key

logger = logging.getLogger(__name__)


def _write_env(api_key: str) -> None:
    paths.ensure_dirs()
    env = paths.env_path()
    env.write_text(f"GEMINI_API_KEY={api_key}\n")
    env.chmod(0o600)


def _test_gemini_key(api_key: str) -> tuple[bool, str]:
    try:
        genai.configure(api_key=api_key)
        m = genai.GenerativeModel("gemini-2.0-flash")
        r = m.generate_content(
            "Reply with the single word: ok",
            request_options={"timeout": 15},
        )
        return True, r.text.strip()
    except Exception as exc:
        logger.warning("Gemini key test failed: %s", exc)
        return False, str(exc)


def _open_settings_pane(pane: str) -> None:
    url_map = {
        "mic": "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
        "accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
        "input": "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent",
    }
    subprocess.run(["open", url_map[pane]])


class OnboardingWindow:
    def __init__(self, on_finish: Callable[[], None]) -> None:
        self._on_finish = on_finish
        self._root = tk.Tk()
        self._root.title("Welcome to Murmur")
        self._root.geometry("600x520")
        self._step = 0
        self._steps = [
            self._build_step_key,
            self._build_step_permissions,
            self._build_step_hotkey,
            self._build_step_audio,
            self._build_step_test,
        ]
        self._frame: Optional[tk.Frame] = None
        self._render()

    def run(self) -> None:
        self._root.mainloop()

    def _render(self) -> None:
        if self._frame:
            self._frame.destroy()
        self._frame = tk.Frame(self._root, padx=20, pady=20)
        self._frame.pack(fill="both", expand=True)
        self._steps[self._step]()

    def _next(self) -> None:
        if self._step + 1 >= len(self._steps):
            self._on_finish()
            self._root.destroy()
            return
        self._step += 1
        self._render()

    def _heading(self, text: str) -> None:
        tk.Label(self._frame, text=text, font=("SF Pro", 18, "bold")).pack(anchor="w", pady=(0, 10))

    def _body(self, text: str) -> None:
        tk.Label(self._frame, text=text, justify="left", wraplength=540).pack(anchor="w", pady=(0, 10))

    def _build_step_key(self) -> None:
        self._heading("Step 1 of 5 — Get a Gemini API key")
        self._body(
            "Murmur uses Google's free Gemini Flash to clean up your dictations. "
            "Free tier is 1 million tokens/day — far more than you'll use.\n\n"
            "1. Click 'Get my key' below — opens aistudio.google.com/apikey in your browser.\n"
            "2. Sign in with your Google account.\n"
            "3. Click the blue 'Create API key' button (top-right).\n"
            "4. Choose 'Create API key in new project'.\n"
            "5. Copy the key (starts with AIza…).\n"
            "6. Paste it here and click 'Test key'."
        )
        btn_row = tk.Frame(self._frame)
        btn_row.pack(anchor="w", pady=4)
        tk.Button(btn_row, text="Get my key", command=lambda: webbrowser.open("https://aistudio.google.com/apikey")).pack(side="left")
        tk.Label(self._frame, text="API Key:").pack(anchor="w", pady=(10, 0))
        entry = tk.Entry(self._frame, width=70, show="•")
        entry.pack(anchor="w")
        status = tk.Label(self._frame, text="", fg="gray")
        status.pack(anchor="w", pady=4)
        next_btn = tk.Button(self._frame, text="Next →", state="disabled", command=self._next)

        def test_key():
            key = entry.get().strip()
            if not key.startswith("AIza"):
                status.config(text="Key should start with AIza…", fg="red")
                return
            status.config(text="Testing…", fg="gray")
            self._root.update()

            def worker():
                ok, msg = _test_gemini_key(key)

                def apply():
                    if ok:
                        _write_env(key)
                        status.config(text=f"✓ Working ({msg})", fg="green")
                        next_btn.config(state="normal")
                    else:
                        status.config(text=f"✗ {msg[:120]}", fg="red")

                self._root.after(0, apply)

            threading.Thread(target=worker, daemon=True).start()

        tk.Button(self._frame, text="Test key", command=test_key).pack(anchor="w", pady=4)
        tk.Label(self._frame, text="Stored only at ~/.murmur/.env on this Mac.", fg="gray").pack(anchor="w", pady=4)
        next_btn.pack(anchor="e", pady=10)

    def _build_step_permissions(self) -> None:
        self._heading("Step 2 of 5 — Grant macOS permissions")
        self._body("Murmur needs three permissions. Click each 'Open Settings' button, toggle Murmur on, then come back.")
        rows = [
            ("Microphone", "mic", "Capture your voice"),
            ("Accessibility", "accessibility", "Paste at the cursor"),
            ("Input Monitoring", "input", "Listen for the hotkey"),
        ]
        for name, pane, why in rows:
            row = tk.Frame(self._frame)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=f"• {name} — {why}").pack(side="left")
            tk.Button(row, text="Open Settings", command=lambda p=pane: _open_settings_pane(p)).pack(side="right")
        tk.Label(self._frame, text="(Restart Murmur after granting if asked.)", fg="gray").pack(anchor="w", pady=8)
        tk.Button(self._frame, text="Next →", command=self._next).pack(anchor="e", pady=10)

    def _build_step_hotkey(self) -> None:
        self._heading("Step 3 of 5 — Choose your hotkey")
        self._body("Default is Right Option. Tap to toggle, hold > 250ms for push-to-talk.")
        s = settings_mod.load()
        var = tk.StringVar(value=s.hotkey)
        for label, value in [
            ("Right Option (default)", "right_option"),
            ("Left Option", "left_option"),
            ("Right Command", "right_command"),
            ("Caps Lock", "caps_lock"),
        ]:
            tk.Radiobutton(self._frame, text=label, variable=var, value=value).pack(anchor="w")

        def save_and_next():
            s2 = settings_mod.load()
            s2.hotkey = var.get()
            settings_mod.save(s2)
            self._next()

        tk.Button(self._frame, text="Next →", command=save_and_next).pack(anchor="e", pady=10)

    def _build_step_audio(self) -> None:
        self._heading("Step 4 of 5 — Audio storage")
        self._body(
            "Want Murmur to keep audio of your last 20 dictations? Useful for replaying mistranscriptions. "
            "Audio never leaves your Mac. Auto-purges after 7 days. (Privacy mode disables this anyway.)"
        )
        s = settings_mod.load()
        var = tk.BooleanVar(value=s.store_audio)
        tk.Radiobutton(self._frame, text="Yes, keep audio", variable=var, value=True).pack(anchor="w")
        tk.Radiobutton(self._frame, text="No, transcripts only (default)", variable=var, value=False).pack(anchor="w")

        def save_and_next():
            s2 = settings_mod.load()
            s2.store_audio = var.get()
            settings_mod.save(s2)
            self._next()

        tk.Button(self._frame, text="Next →", command=save_and_next).pack(anchor="e", pady=10)

    def _build_step_test(self) -> None:
        self._heading("Step 5 of 5 — You're ready")
        self._body(
            "Try it: press your hotkey, say 'Hello, this is my first Murmur dictation,' "
            "and tap the hotkey again. The text should appear at your cursor.\n\n"
            "You can re-run this onboarding anytime from the menu bar → Help → Re-run onboarding."
        )
        tk.Button(self._frame, text="Done", command=self._next).pack(anchor="e", pady=10)
