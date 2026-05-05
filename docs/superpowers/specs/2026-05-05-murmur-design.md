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
2. App launches a small onboarding window:
   - "Paste your Gemini API key" (with a link to `aistudio.google.com/apikey`)
   - "Grant Microphone, Accessibility, and Input Monitoring permissions" (each opens the relevant System Settings pane)
   - "Choose your hotkey" (default Right Option, configurable)
   - "Keep audio of dictations so you can replay mistranscriptions? Yes / No" (default No)
   - "Test your hotkey now — say something" (sanity check)
3. Onboarding window closes; menu bar icon stays.

### Normal use
- **Tap Right Option** → recording starts; floating pill shows waveform; tap again to stop.
- **Hold Right Option > 250ms** → push-to-talk; release to stop.
- After stop: pill shows "Transcribing…" → "Polishing…" → text pastes at cursor.
- **⌥⌘V** → re-pastes the most recent dictation.
- **Click menu bar icon** → menu with: pause, current cleanup mode, history, settings, quit.

### Failure modes the user sees
- **No mic input detected:** pill shows "No audio — check mic" and aborts.
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

### Components — one job each

1. **`hotkey.py`** — global key listener via `pynput`. Distinguishes tap (≤ 250ms) vs hold. Emits `start_recording` / `stop_recording` to a thread-safe queue.
2. **`audio.py`** — captures mic via `sounddevice` to an in-memory `numpy` buffer at 16 kHz mono. Voice-activity-detection (Silero VAD via `torch`) trims leading/trailing silence.
3. **`transcribe.py`** — wraps `faster-whisper`. Loads model once at startup. Default `base.en` (74 MB), configurable to `small.en` (244 MB).
4. **`clean.py`** — calls Gemini 2.0 Flash with the prompt for the active cleanup mode. Streams response. Falls back to raw transcript on failure.
5. **`output.py`** — copies clean text to clipboard, restores the previous clipboard contents 200ms after pasting. Triggers ⌘V via `CGEventCreateKeyboardEvent`.
6. **`menubar.py`** — rumps menu with: status, cleanup mode (4 options), pause, history (last 20 entries; clicking an entry re-copies that text to clipboard so the user can paste it manually), settings, quit.
7. **`pill.py`** — borderless `NSPanel` floating overlay at bottom-center of screen. Shows recording state, audio level meter, and current phase ("Listening…" / "Transcribing…" / "Polishing…"). Auto-fades on idle.
8. **`settings.py`** — JSON config at `~/Library/Application Support/Murmur/config.json`. Hotkey, model size, default cleanup mode, audio storage on/off, custom vocab path.
9. **`history.py`** — append-only JSONL at `~/Library/Application Support/Murmur/history.jsonl`. Each entry: `{ts, raw, cleaned, mode, audio_path}`. Trims to last 20 entries on write.
10. **`onboarding.py`** — first-run flow (Tk window). Sets up `.env`, walks through permissions.
11. **`app.py`** — wires everything together. Owns the worker thread pool. Single entry point.

### Threading model

Three long-lived threads + a worker pool:

| Thread | Responsibility |
|---|---|
| Main (UI) | rumps menu loop + NSPanel updates. Never blocks. |
| Hotkey | `pynput` listener loop. Posts events to the recording state machine. |
| Audio | Captures mic into a ring buffer when recording is active. |
| Worker pool (size 1) | Runs transcribe → clean → output as a single sequential pipeline per dictation, so two fast taps don't race. |

State transitions guarded by a single `threading.Lock` on the `RecordingState` enum (`IDLE → RECORDING → TRANSCRIBING → CLEANING → PASTING → IDLE`).

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
worker: clipboard ← cleaned text → CGEvent ⌘V → restore old clipboard
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
  "hotkey": "right_option",
  "replay_hotkey": "cmd+option+v",
  "tap_threshold_ms": 250,
  "model": "base.en",
  "default_mode": "email",
  "store_audio": false,
  "audio_retention_days": 7,
  "history_size": 20,
  "vocabulary_path": "~/Library/Application Support/Murmur/vocabulary.txt"
}
```

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
| Clipboard restore fails | Log only; original clipboard already overwritten |
| Hotkey listener dies | Auto-restart once; if fails twice, surface a menu-bar warning |

All errors append to `~/Library/Logs/Murmur/murmur.log` with timestamp + traceback. Log level configurable.

## 10. Distribution & install

**Repo:** `github.com/<user>/murmur` (public, MIT license)

**One-line install:**
```bash
curl -fsSL https://raw.githubusercontent.com/<user>/murmur/main/install.sh | bash
```

**`install.sh` does, in order:**
1. Verify macOS ≥ 13. Verify arch (Apple Silicon or Intel).
2. Verify Python 3.11+. If missing, install via Homebrew (and install Homebrew if missing).
3. Clone repo to `~/.murmur/src/`.
4. Create venv at `~/.murmur/venv/`. `pip install -r requirements.txt`.
5. Pre-download the default Whisper model (`base.en`).
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
│       ├── app.py              # entry point
│       ├── settings.py
│       ├── hotkey.py
│       ├── audio.py
│       ├── transcribe.py
│       ├── clean.py
│       ├── output.py
│       ├── menubar.py
│       ├── pill.py
│       ├── history.py
│       ├── onboarding.py
│       ├── prompts/
│       │   ├── email.txt
│       │   ├── chat.txt
│       │   ├── notes.txt
│       │   └── raw.txt
│       └── assets/
│           ├── icon-idle.png
│           └── icon-recording.png
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
| VAD | `silero-vad` (via torch) | Trims silence pre-Whisper, saves time |
| Hotkey | `pynput` | Reliable global key listener on macOS |
| Audio capture | `sounddevice` | Cleaner API than pyaudio, no PortAudio install pain |
| Menu bar | `rumps` | The standard for Python macOS menu bar apps |
| Floating pill | `pyobjc` (NSPanel) | Native window, transparent, click-through |
| Clipboard + paste | `pyperclip` + `Quartz` (CGEvent) | Set clipboard, simulate ⌘V |
| Cleanup LLM | `google-generativeai` | Official Gemini SDK |
| Onboarding UI | `tkinter` | Bundled with Python; no extra deps |
| Config / env | stdlib `json` + `python-dotenv` | Familiar |
| Logging | stdlib `logging` with `RotatingFileHandler` | Simple |

Total install: ~600 MB including the Whisper model and torch. Acceptable for a one-time download.

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
- [ ] Tap Right Option → speak → cleaned text appears at cursor in < 4 seconds for a 10-second dictation (base.en)
- [ ] Hold Right Option for push-to-talk works in any focused app
- [ ] All four cleanup modes produce visibly different output for the same input
- [ ] Custom vocabulary file influences cleanup output
- [ ] Privacy mode forces raw + skips audio storage
- [ ] ⌥⌘V re-pastes the most recent dictation
- [ ] Gemini-down scenario pastes raw transcript with a toast
- [ ] Auto-starts at login after reboot
- [ ] Menu bar icon shows recording state
- [ ] Floating pill appears only while recording / processing
- [ ] Total install footprint ≤ 700 MB
- [ ] Idle CPU < 1%, idle RAM < 300 MB (Whisper model loaded but not running)
