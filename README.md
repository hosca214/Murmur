# Murmur

Free voice dictation for macOS. Press a hotkey, speak, and cleaned-up text appears at your cursor — anywhere.

A Wispr Flow / Superwhisper alternative. Local Whisper + Gemini Flash free tier = $0 to run.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/hosca214/Murmur/main/install.sh | bash
```

You'll be walked through:
1. Getting a free Gemini API key
2. Granting macOS permissions (Mic, Accessibility, Input Monitoring)
3. Picking a hotkey (default Right Option)
4. A first test dictation

## Use

- **Tap Right Option** → start recording. Tap again → stop and paste.
- **Hold Right Option** → push-to-talk; release to stop.
- **⌥⌘V** → re-paste your last dictation.
- Click the menu bar icon to switch cleanup modes (Email / Chat / Notes / Raw), toggle privacy, view history, or copy diagnostics.

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/hosca214/Murmur/main/uninstall.sh | bash
```

## License

MIT.
