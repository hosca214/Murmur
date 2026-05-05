# Murmur Manual QA Checklist

Run all checks on the target Mac (Apple Silicon and/or Intel). Mark each ✓ before declaring v1 done.

## A. Install / first run

- [ ] On a fresh user account, `bash install.sh` completes with no errors.
- [ ] Whisper model download completes (or retries and succeeds).
- [ ] Onboarding window opens automatically.
- [ ] Step 1: pasting a real Gemini key + "Test key" returns ✓.
- [ ] Step 1: pasting a bogus key returns red error.
- [ ] Step 2: each "Open Settings" button opens the correct pane.
- [ ] Step 3: hotkey radio choice persists in `config.json`.
- [ ] Step 4: audio storage choice persists.
- [ ] Step 5: clicking Done leaves the menu bar icon visible.

## B. Core dictation flow

- [ ] Tap Right Option → pill shows "Listening…".
- [ ] Tap again → pill cycles "Transcribing…" → "Polishing…" → text pastes at cursor (in TextEdit, Notes, Slack, Gmail).
- [ ] Hold Right Option > 250ms → push-to-talk works; release ends.
- [ ] On Apple Silicon: 10s dictation → text appears in < 4s after stop.
- [ ] On Intel: 10s dictation → text appears in < 8s after stop.

## C. Cleanup modes

For each, dictate "um so like send mike an email tell him uh the meeting is moved to thursday":

- [ ] **Email** → "Send Mike an email telling him the meeting is moved to Thursday." (formal, no contractions)
- [ ] **Chat** → "send mike an email — meeting moved to thursday" or similar (casual contractions ok)
- [ ] **Notes** → either compact sentence or bulletized form
- [ ] **Raw** → contains "um", "uh", no punctuation cleanup (verifies raw mode bypasses Gemini)

## D. Custom vocabulary

- [ ] Add "BookWise" to `~/Library/Application Support/Murmur/vocabulary.txt`.
- [ ] Dictate "send the bookwise launch update to nora" in Email mode.
- [ ] Output spells "BookWise" with correct capitalization.

## E. Privacy mode

- [ ] Toggle privacy mode from menu bar.
- [ ] Dictate something. Output is raw (no Gemini call). Pill shows 🔒.
- [ ] No new file appears in `~/Library/Application Support/Murmur/audio/` even if `store_audio: true`.

## F. Replay hotkey

- [ ] After a successful dictation, ⌥⌘V re-pastes the same text.

## G. Failure modes

- [ ] Turn airplane mode on. Dictate. Raw transcript pastes; toast says "(unpolished — Gemini unreachable)".
- [ ] Hit Right Option immediately at app launch (during cold start). Pill shows "Warming up…", then auto-starts recording when ready.
- [ ] Record for > 5 minutes. Auto-stops with "5 min limit — processing".
- [ ] Tap-tap quickly: second tap during transcribing → pill shows "Queued (1)"; second recording starts after first finishes.
- [ ] Tap during cleaning: cleanup is canceled, raw pastes, then second recording starts.

## H. Menu bar

- [ ] Mode submenu shows correct ✓ on active mode.
- [ ] History submenu lists recent dictations; clicking copies (notification confirms).
- [ ] Help → Copy diagnostics puts a non-empty bundle on the clipboard, with no `AIza…` substring (key redaction).
- [ ] Quit removes the icon and stops the listener (no more dictation triggers).

## I. Persistence

- [ ] Reboot. Murmur auto-launches via launchd; menu bar icon present without manual action.
- [ ] Mode and privacy state from previous session are restored.

## J. Uninstall

- [ ] `bash uninstall.sh` removes the menu bar icon, launch agent, and app support files.
- [ ] User is prompted before .env removal.
