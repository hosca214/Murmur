# Murmur — Design Spec

**Date:** 2026-05-05
**Author:** Aya Hosch + Claude
**Status:** Draft v1, awaiting review
**Target platform:** macOS 13+ (Ventura and later)

---

## 1. What Murmur is

A free, open-source voice dictation app for macOS. Press a hotkey, speak, and cleaned-up text appears at your cursor — anywhere you can type.

It is a Wispr Flow / Superwhisper alternative, with the same core experience but $0 cost:

- **Transcription** runs locally via `faster-whisper` (no audio leaves your Mac).
- **Cleanup** uses Google's Gemini 2.0 Flash on the free API tier (15 RPM, 1M tokens/day — far more than one person can consume).
- **Privacy mode** disables Gemini and audio storage for sensitive work (e.g. bookkeeping client data).

## 2. Goals & non-goals

**Goals**
- One-hotkey dictation that "just works" anywhere on macOS
- Cleaned-up output that reads like written text, not transcribed speech
- Free to run forever for normal personal use
- Shareable: friends install with one terminal command and provide their own free Gemini key
- Auto-starts at login; lives quietly in the menu bar

**Non-goals (v1)**
- Streaming live transcription
- Voice commands ("delete that", "new paragraph")
- Multi-language support (English-only for v1)
- App-aware automatic mode switching
- iOS / Windows / Linux support
- Usage statistics dashboard

## 3. User experience

### First-run onboarding
1. User runs the install command (see §10).
2. App launches a multi-step onboarding window. Each step has a "Next" button that's disabled until the step is complete.

   **Step 1 — Gemini API key (with built-in walkthrough)**

   The window shows a numbered guide alongside a "Get my key" button that auto-opens the right page in the user's browser. Each step has a screenshot thumbnail (stored in `src/murmur/assets/onboarding/`) so the user sees what to look for:

   1. *Click "Get my key" — this opens **aistudio.google.com/apikey** in your browser.*
   2. *Sign in with your Google account if you aren't already.*
   3. *Click the blue **"Create API key"** button (top-right of the page).*
   4. *Choose **"Create API key in new project"** if asked. (You can also pick an existing project — both work.)*
   5. *Google shows you a key starting with `AIza...`. Click the copy icon next to it.*
   6. *Come back to this window and paste the key in the field below.*
   7. *Click **Test key** — Murmur sends one tiny test request to verify it works.*

   The paste field validates format (`AIza` prefix, length) immediately. The "Test key" button makes a minimal Gemini call (e.g. cleanup of "hello world") and shows a green check or a red error message with the actual API response. "Next" is enabled once the test succeeds.

   A small disclosure below the field: *"Your key is saved at `~/.murmur/.env` on this Mac only. It never gets sent anywhere except to Google. The free tier gives you 1 million tokens/day — far more than you'll use."*

   **Step 2 — Grant permissions**
   "Murmur needs three macOS permissions: Microphone, Accessibility, Input Monitoring." Three rows, each with a status indicator (✗ / ✓) and an "Open Settings" button that jumps to the right pane. Step refreshes automatically every 2 seconds; "Next" is enabled when all three show ✓.

   **Step 3 — Choose your hotkey**
   Default Right Option. Dropdown to change. A "Press the key now to test" field that confirms the chosen key fires.

   **Step 4 — Audio storage preference**
   "Want Murmur to keep a few seconds of audio for your last 20 dictations? Useful if a transcript looks wrong and you want to remember what you actually said. Audio never leaves your Mac." Default: No. Privacy mode overrides this anyway.

   **Step 5 — Try it**
   "Press your hotkey and say 'Hello, this is my first Murmur dictation.'" Shows the live transcript and cleaned output side-by-side so the user sees the difference cleanup makes. Done button enables when one successful dictation is logged.

3. Onboarding window closes; menu bar icon stays. Re-runnable anytime from menu bar → Settings → "Re-run onboarding".

### Normal use
- **Tap Right Option** → recording starts; floating pill shows waveform; tap again to stop.
- **Hold Right Option > 250ms** → push-to-talk; release to stop.
- After stop: pill shows "Transcribing…" → "Polishing…" → text pastes at cursor.
- **⌥⌘V** → re-pastes the most recent dictation.
- **Click menu bar icon** → menu with: pause, current cleanup mode, history, settings, quit.

### Failure modes the user sees
- **Hotkey not detected:** menu bar shows a yellow warning icon; clicking opens a "diagnose hotkey" dialog with options to change keys or restart the listener.
- **Cold start (model still loading):** pill shows "Warming up…" instead of "Listening…"; recording auto-starts the moment the model is ready (typically < 5s after launch).
- **No mic input detected:** pill shows "No audio — check mic" and aborts.
- **Recording exceeds 5 minutes:** auto-stops with pill message "5 min limit — processing".
- **Whisper failure:** "Transcription failed" notification; nothing pasted.
- **Gemini unreachable / rate-limited:** raw transcript is pasted with a small notification "(unpolished — Gemini unreachable)". Never lose a dictation.
- **Privacy mode active:** raw transcript pastes; pill shows a 🔒 icon.

## 4. Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                          Murmur (Python 3.11+)                         │
│                                                                        │
│  ┌─────────────────┐   ┌────────────────┐   ┌─────────────────────┐  │
│  │ Hotkey listener │──▶│ Audio capture  │──▶│ Transcriber         │  │
│  │ (pynput)        │   │ (sounddevice)  │   │ (faster-whisper)    │  │
│  └─────────────────┘   └────────────────┘   └──────────┬──────────┘  │
│           ▲                                             │             │
│           │                                             ▼             │
│  ┌─────────────────┐   ┌────────────────┐   ┌─────────────────────┐  │
│  │ Menu bar UI     │   │ Output         │◀──│ Cleaner             │  │
│  │ (rumps)         │   │ (clipboard +   │   │ (Gemini 2.0 Flash)  │  │
│  │ + Floating pill │   │  CGEvent ⌘V)   │   └─────────────────────┘  │
│  │ (PyObjC NSPanel)│   └────────────────┘                            │
│  └─────────────────┘                                                  │
│                                                                        │
│  Settings store (JSON) │ History (JSONL) │ Audio cache │ Logs         │
└────────────────────────────────────────────────────────────────────────┘
```

### Components — one job each (7 modules + 2 entry points)

1. **`hotkey.py`** — global key listener via `pynput`. Distinguishes tap (≤ 250ms) vs hold. Emits `start_recording` / `stop_recording` to a thread-safe queue. On startup, runs a self-check confirming the listener is reachable. If not, surfaces a "hotkey not detected" banner in the menu bar with a one-click "diagnose" action.
2. **`pipeline.py`** — combines audio capture + transcription. `sounddevice` records mic to a 16 kHz mono ring buffer with a hard **5-minute cap** (then auto-stops with a "5 min limit" pill message). VAD trimming uses `faster-whisper`'s built-in `vad_filter=True` (Silero ONNX, **no torch dependency**). Apple Silicon → `compute_type="int8"`, model `small.en`. Intel → `compute_type="int8"`, model `base.en`. Chip detected at install time; configurable later.
3. **`clean.py`** — calls Gemini 2.0 Flash with the prompt for the active cleanup mode. Streams response. Falls back to raw transcript on any failure.
4. **`output.py`** — copies clean text to clipboard and triggers ⌘V via `CGEventCreateKeyboardEvent`. **No clipboard auto-restore** — the dictation stays on the clipboard so a follow-up ⌘V re-pastes it, and any clipboard manager preserves prior content naturally.
5. **`ui/bar.py`** — rumps menu: status, cleanup mode (4 options), pause, history (last 20 entries; clicking re-copies to clipboard), settings, **Help → Copy diagnostics**, quit. Diagnostics action assembles last 200 lines of `murmur.log` + config (with `GEMINI_API_KEY` redacted) into the clipboard.
6. **`ui/pill.py`** — borderless `NSPanel` floating overlay. Shows phase: "Warming up…" / "Listening…" / "Transcribing…" / "Polishing…" / "Queued (1)". NSPanel updates marshalled to the Cocoa main thread. **Fallback**: if NSPanel init fails on a given macOS version, falls back to a Tk text-only overlay.
7. **`settings.py`** — JSON config at `~/Library/Application Support/Murmur/config.json`. Always writes `"schema_version": 1` for future migrations. Settings UI is a small Tk window reusing onboarding form widgets.
8. **`history.py`** — append-only JSONL. Each entry: `{ts, raw, cleaned, mode, audio_path}`. Trims to last 20 on write.

Plus two entry points:
- **`onboarding.py`** — first-run flow (Tk window). 5 steps, walks through key + permissions + hotkey + audio preference + first-dictation test. Re-runnable from menu bar.
- **`app.py`** — wires everything together. Owns the worker thread pool. Single entry point.

### Threading model

Three long-lived threads + a worker pool:

| Thread | Responsibility |
|---|---|
| Main (UI) | rumps menu loop + NSPanel updates. Never blocks. |
| Hotkey | `pynput` listener loop. Posts events to the recording state machine. |
| Audio | Captures mic into a ring buffer when recording is active. |
| Worker pool (size 1) | Runs transcribe → clean → output as a single sequential pipeline per dictation, so two fast taps don't race. |

State transitions guarded by a single `threading.Lock` on the `RecordingState` enum (`COLD_START → IDLE → RECORDING → TRANSCRIBING → CLEANING → PASTING → IDLE`). `COLD_START` is the brief window after launch while the Whisper model loads; the pill shows "Warming up…" if the user hits the hotkey during this state, then auto-starts recording the moment the model is ready.

**Concurrent-tap rules:**
- Tap during `RECORDING` → stop & process current dictation (normal toggle).
- Tap during `TRANSCRIBING` → queue the new tap; pill shows "Queued (1)". When the current pipeline finishes, the new recording starts immediately.
- Tap during `CLEANING` or `PASTING` → cancel the in-flight cleanup (paste raw transcript instead), finish the paste, then immediately start the new recording. Avoids the user feeling like the app froze.
- Queue depth capped at 1. A second queued tap during a queue replaces the first, with a pill flash.

### Data flow (single dictation)

```
[hotkey tap]
   ↓
state: IDLE → RECORDING ; pill: show "Listening…"
   ↓
audio thread fills ring buffer
   ↓
[hotkey tap or release]
   ↓
state: RECORDING → TRANSCRIBING ; pill: "Transcribing…"
   ↓
worker: VAD-trim → faster-whisper → raw transcript
   ↓
state: TRANSCRIBING → CLEANING ; pill: "Polishing…"
   ↓
worker: gemini cleanup (skipped if privacy mode) → cleaned text
   ↓
state: CLEANING → PASTING
   ↓
worker: clipboard ← cleaned text → CGEvent ⌘V (no clipboard restore)
   ↓
worker: history append (+ audio file if storage enabled and privacy off)
   ↓
state: PASTING → IDLE ; pill: fade out
```

## 5. Cleanup modes

Switchable from the menu bar. Each mode has its own prompt template.

| Mode | Use for | Behavior |
|---|---|---|
| **Email** (default) | Work email, formal writing | Full punctuation, full sentences, no contractions, polished. |
| **Chat** | Slack, iMessage, casual | Contractions, conversational, can keep "yeah" / "ok". |
| **Notes** | Lists, brainstorms | Bullet-friendly: "first… second… third…" → bullet list. |
| **Raw** | Code dictation, names, technical | No cleanup. Pure faster-whisper output. |

Privacy mode forces Raw regardless of selection.

### Custom vocabulary

Editable text file at `~/Library/Application Support/Murmur/vocabulary.txt`, one term per line. Example:

```
BookWise
Zen Bookkeeper
Plaid
Supabase
QuickBooks
```

Passed to Gemini in the cleanup prompt as: *"The speaker uses these terms — preserve their exact spelling: …"*. No effect in Raw mode.

## 6. Configuration

`~/Library/Application Support/Murmur/config.json`:

```json
{
  "schema_version": 1,
  "hotkey": "right_option",
  "replay_hotkey": "cmd+option+v",
  "tap_threshold_ms": 250,
  "model": "small.en",
  "compute_type": "int8",
  "default_mode": "email",
  "store_audio": false,
  "audio_retention_days": 7,
  "history_size": 20,
  "max_recording_seconds": 300,
  "vocabulary_path": "~/Library/Application Support/Murmur/vocabulary.txt"
}
```

`model` and `compute_type` are written by the installer based on detected chip. `schema_version` enables clean migration when the format changes in v2.

`~/.murmur/.env` (chmod 600, gitignored):

```
GEMINI_API_KEY=...
```

## 7. Permissions

macOS requires three:

| Permission | Why | How |
|---|---|---|
| Microphone | Capture audio | First launch triggers system prompt |
| Accessibility | Synthesize ⌘V keystroke for paste | Onboarding opens System Settings → Privacy & Security → Accessibility; user toggles Murmur on |
| Input Monitoring | Listen to global hotkey | Same flow as Accessibility, in the Input Monitoring pane |

Onboarding detects which are missing by attempting the relevant API (e.g. posting a synthetic key event for Accessibility) and catching the failure. Each missing permission re-opens the right pane until all three are granted.

## 8. Storage & data sizes

| Item | Location | Size |
|---|---|---|
| Config JSON | `~/Library/Application Support/Murmur/config.json` | < 1 KB |
| History (20 entries) | `…/history.jsonl` | ~50 KB |
| Audio cache (20 × 20s WAV) | `…/audio/*.wav` | ~13 MB max |
| Whisper model | `~/.cache/huggingface/...` | 74 MB (base.en) — 244 MB (small.en) |
| Total install footprint | `~/.murmur/venv/` + model | ~600 MB on Apple Silicon (small.en), ~430 MB on Intel (base.en). No torch — Silero VAD ships as ONNX inside `faster-whisper`. |
| Logs | `~/Library/Logs/Murmur/murmur.log` | rotates at 5 MB |

Auto-purge: audio files older than `audio_retention_days` deleted on app launch.

## 9. Error handling

| Failure | Response |
|---|---|
| No mic permission | Onboarding re-opens; pill never shows |
| Mic returns silence | Pill: "No audio detected" for 2s; abort |
| Whisper crashes | Log error; pill: "Transcription failed"; abort |
| Gemini API error (any) | Paste raw transcript; small toast: "(unpolished — Gemini unreachable)" |
| Gemini rate limit | Same as above |
| Hotkey listener dies | Auto-restart once; if fails twice, surface a menu-bar warning |
| NSPanel pill init fails | Fall back to a Tk text-only overlay; log the underlying NSPanel error |
| Whisper model download fails (install) | Retry 3× with exponential backoff (2s / 8s / 30s); on final failure, install.sh prints exact resume command |

All errors append to `~/Library/Logs/Murmur/murmur.log` with timestamp + traceback. Log level configurable.

## 10. Distribution & install

**Repo:** `github.com/<user>/murmur` (public, MIT license)

**One-line install:**
```bash
curl -fsSL https://raw.githubusercontent.com/<user>/murmur/main/install.sh | bash
```

**`install.sh` does, in order:**
1. Verify macOS ≥ 13. Detect arch (Apple Silicon → small.en, Intel → base.en) and write the right model name into the initial config.
2. Verify Python 3.11+. If missing, install via Homebrew (install Homebrew first if missing).
3. Clone repo to `~/.murmur/src/`.
4. Create venv at `~/.murmur/venv/`. `pip install -r requirements.txt`.
5. Pre-download the chosen Whisper model with **3-retry exponential backoff** (2s / 8s / 30s). On final failure, prints the exact resume command and exits non-zero.
6. Write a launchd plist to `~/Library/LaunchAgents/com.murmur.app.plist` so Murmur auto-starts at login.
7. Launch Murmur for the first time → onboarding window opens.

**Uninstall:**
```bash
curl -fsSL https://raw.githubusercontent.com/<user>/murmur/main/uninstall.sh | bash
```
Removes launch agent, src, venv, config, history. Leaves `.env` (asks first).

## 11. Project structure

```
Murmur/
├── README.md
├── LICENSE
├── install.sh
├── uninstall.sh
├── requirements.txt
├── pyproject.toml
├── .gitignore
├── .env.example
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-05-05-murmur-design.md
├── src/
│   └── murmur/
│       ├── __init__.py
│       ├── app.py              # entry point + state machine
│       ├── paths.py            # single source of truth for all I/O paths
│       ├── settings.py
│       ├── hotkey.py
│       ├── pipeline.py         # audio capture + Whisper transcription
│       ├── clean.py
│       ├── output.py
│       ├── history.py
│       ├── onboarding.py
│       ├── ui/
│       │   ├── __init__.py
│       │   ├── bar.py          # rumps menu bar
│       │   └── pill.py         # NSPanel floating pill (with Tk fallback)
│       ├── prompts/
│       │   ├── email.txt
│       │   ├── chat.txt
│       │   ├── notes.txt
│       │   └── raw.txt
│       └── assets/
│           ├── icon-idle.png
│           ├── icon-recording.png
│           └── onboarding/     # screenshots for the API key walkthrough
│               ├── 01-aistudio-home.png
│               ├── 02-create-key.png
│               └── 03-copy-key.png
├── packaging/
│   └── com.murmur.app.plist     # launchd template
└── tests/
    ├── test_settings.py
    ├── test_history.py
    ├── test_clean.py            # mocks Gemini
    └── test_state_machine.py
```

## 12. Tech stack

| Concern | Library | Why |
|---|---|---|
| Transcription | `faster-whisper` | 4× faster than openai-whisper, lower memory, same models |
| VAD | built-in (`vad_filter=True` in faster-whisper) | Silero ONNX, no torch dependency. Saves ~1 GB. |
| Hotkey | `pynput` | Reliable global key listener on macOS |
| Audio capture | `sounddevice` | Cleaner API than pyaudio, no PortAudio install pain |
| Menu bar | `rumps` | The standard for Python macOS menu bar apps |
| Floating pill | `pyobjc` (NSPanel) | Native window, transparent, click-through |
| Pill fallback | `tkinter` | If NSPanel init fails on a given macOS version |
| Clipboard + paste | `pyperclip` + `Quartz` (CGEvent) | Set clipboard, simulate ⌘V |
| Cleanup LLM | `google-generativeai` | Official Gemini SDK |
| Onboarding UI | `tkinter` | Bundled with Python; no extra deps |
| Config / env | stdlib `json` + `python-dotenv` | Familiar |
| Logging | stdlib `logging` with `RotatingFileHandler` | Simple |

Total install: ~600 MB on Apple Silicon, ~430 MB on Intel. One-time download.

## 13. Testing

Unit tests for the deterministic pieces:
- `test_settings.py` — load / save / migration
- `test_history.py` — append, trim, retention purge
- `test_state_machine.py` — recording state transitions, edge cases (double-tap, hold-then-tap)
- `test_clean.py` — mocks Gemini; verifies prompt construction, fallback on error, vocabulary injection

Manual test plan in `tests/MANUAL.md`:
- First-run onboarding on a clean Mac
- Each cleanup mode on a sample sentence
- Privacy mode toggle mid-session
- Gemini unreachable (airplane mode) → raw paste
- Replay hotkey
- Permission revocation mid-use → graceful warning

## 14. Security & privacy

- Gemini API key in `~/.murmur/.env` with `chmod 600` (owner-only read).
- `.env` and `*.env` are in `.gitignore`. Never committed.
- Audio files never leave the Mac. Whisper is fully local.
- Privacy mode disables Gemini AND audio storage in one toggle.
- Free Gemini tier may use prompts for model improvement (Google's policy). README warns about this for sensitive content; privacy mode is the answer.
- History is plaintext on disk. Acceptable for personal use; encrypted history is a v2 consideration.

## 15. Code style guardrails

For implementation efficiency and reviewability:

- Each module ≤ 200 LOC. If it grows, split.
- No comments unless the *why* is non-obvious.
- Type hints throughout (`mypy --strict` passes).
- No abstract base classes or factories. Direct functions and small dataclasses.
- One `RecordingState` enum, one global lock, no other shared mutable state.
- All I/O paths derived from a single `paths.py` module, not hardcoded.

## 16. Open questions for v2 (out of scope for v1)

- App-aware mode switching (Slack ↔ Email)
- Streaming transcription with partial results in pill
- Encrypted history
- Multi-language detection
- Voice commands ("scratch that", "new paragraph")
- Homebrew tap distribution (`brew install murmur`)
- Code signing / notarization for a real `.app` distribution
- Swift rewrite for App Store

## 17. Acceptance criteria for v1

- [ ] Install via one terminal command on a clean macOS 13+ machine
- [ ] First-run onboarding successfully captures Gemini key + 3 permissions
- [ ] Tap Right Option → speak → cleaned text appears at cursor in **< 4 seconds on Apple Silicon** (small.en + int8 + Metal) **or < 8 seconds on Intel** (base.en + int8) for a 10-second dictation
- [ ] Hold Right Option for push-to-talk works in any focused app
- [ ] All four cleanup modes produce visibly different output for the same input
- [ ] Custom vocabulary file influences cleanup output
- [ ] Privacy mode forces raw + skips audio storage
- [ ] ⌥⌘V re-pastes the most recent dictation
- [ ] Gemini-down scenario pastes raw transcript with a toast
- [ ] Auto-starts at login after reboot
- [ ] Menu bar icon shows recording state
- [ ] Floating pill appears only while recording / processing
- [ ] Total install footprint ≤ 700 MB (Apple Silicon) / ≤ 500 MB (Intel)
- [ ] Hotkey self-check passes on launch; warning surfaces in menu bar if it doesn't
- [ ] "Help → Copy diagnostics" produces a shareable, key-redacted log bundle
- [ ] Recording auto-stops at 5 minutes with a clear pill message
- [ ] Concurrent-tap rules behave as specified (queue / cancel-cleanup / replace-queued)
- [ ] Idle CPU < 1%, idle RAM < 300 MB (Whisper model loaded but not running)
