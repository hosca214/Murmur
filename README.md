# Murmur

Free voice dictation for macOS. Press a hotkey, speak, and cleaned-up text appears at your cursor, anywhere.

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

- **Tap Right Option**: start recording. Tap again: stop and paste.
- **Hold Right Option**: push-to-talk; release to stop.
- **Esc while recording**: cancel, nothing is pasted.
- **Double-tap Right Option**: undo the last paste (within 15 seconds).
- Click the menu bar icon to switch cleanup modes, change the hotkey, toggle sounds or privacy, view history, or edit your vocabulary.

## What the cleanup does

- Removes filler words ("um", "uh") and stutters.
- Resolves self-corrections: "Tuesday, no wait, Wednesday" pastes as "Wednesday".
- Handles spoken commands like "new paragraph" and "new line".
- **Auto mode (on by default)** matches tone to the app you're pasting into: casual in Slack and Messages, formal in Mail and Outlook, structured bullets in Notes and Obsidian. Pick a fixed mode from the menu to turn it off.
- Your clipboard is preserved: whatever you had copied is restored after the paste.
- If Gemini is unreachable, Murmur still cleans fillers locally and pastes; dictation never breaks offline.
- **Privacy mode** skips Gemini entirely (nothing leaves your Mac) and pastes the raw transcript.

## Vocabulary

Menu bar → Edit vocabulary. One term per line (names, brands, jargon); Murmur keeps their exact spelling when polishing.

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/hosca214/Murmur/main/uninstall.sh | bash
```

## License

MIT.
