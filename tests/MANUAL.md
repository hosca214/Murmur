# Murmur Manual QA Checklist

Run all checks on the target Mac (Apple Silicon and/or Intel). Mark each ✓ before declaring the release done.

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
- [ ] Back button works on steps 2-5 without losing choices.

## B. Core dictation flow

- [ ] Tap Right Option → soft start sound, pill shows "Listening" with a live level meter that moves when you speak.
- [ ] Tap again → soft stop sound, pill cycles "Transcribing…" → "Polishing…" → text pastes at cursor (in TextEdit, Notes, Slack, Gmail) → pill flashes "✓ Pasted (N words)".
- [ ] Hold Right Option > 250ms → push-to-talk works; release ends.
- [ ] On Apple Silicon: 10s dictation → text appears in < 4s after stop.
- [ ] Dictating twice in a row: second paste continues after the first with a space between.

## C. Cancel and combo safety

- [ ] Press Esc while recording → pill flashes "✕ Canceled", nothing pastes.
- [ ] Type Option+E then "e" (é) while Murmur runs → no recording starts (combo typing is ignored).
- [ ] Start a dictation by TAP, then while it records type Option+E (é) → recording keeps going (combo typing never kills a tap-toggled dictation).
- [ ] Start a dictation by TAP, then hold bare Right Option > 250ms and release → recording keeps going (only a tap stops a tap-toggled dictation).

## D. Clipboard preservation

- [ ] Copy some text, then dictate. ~10s after the paste, ⌘V pastes your ORIGINAL copied text (clipboard restored).
- [ ] Copy something new within 10s of a paste → your new copy survives (no clobber).
- [ ] Right after a paste, ⌘V still pastes the dictation (manual fallback if the auto-paste missed).

## E. Cleanup quality (Email mode)

- [ ] "um so like send mike an email tell him uh the meeting is moved to thursday" → fillers gone, proper sentence.
- [ ] "let's meet on Tuesday no wait make that Wednesday at three PM" → only "Wednesday at 3 PM" survives.
- [ ] "the the report is ready" → single "the".
- [ ] "thanks new paragraph talk soon" → two paragraphs, the words "new paragraph" not printed.
- [ ] **Raw** mode → contains "um", "uh" verbatim (bypasses Gemini).

## F. Auto mode (match app)

- [ ] Mode menu shows "Auto (match app)" checked by default.
- [ ] Dictate in Slack or Messages → casual output (lowercase ok).
- [ ] Dictate in Mail → formal output.
- [ ] Dictate in Notes/Obsidian with "first… second… third…" → bullets.
- [ ] Pick "Email" in the menu → Auto unchecks; every app now gets email tone. Re-select Auto to restore.

## G. Custom vocabulary

- [ ] Menu → Edit vocabulary opens the file in a text editor (creates it with instructions on first use).
- [ ] Add "BookWise", dictate "send the bookwise launch update to nora" → output spells "BookWise".

## H. Privacy mode

- [ ] Toggle privacy mode from menu bar.
- [ ] Dictate something. Output is raw (no Gemini call).
- [ ] No new file appears in `~/Library/Application Support/Murmur/audio/` even if `store_audio: true`.

## I. Failure modes

- [ ] Turn wifi off. Dictate. Text still pastes (local cleanup: fillers stripped, capitalized).
- [ ] Turn wifi off, quit and relaunch → app still starts (cached Whisper model, no network needed).
- [ ] Hit the hotkey immediately at app launch (during cold start) → pill shows "Warming up…", then auto-starts recording when ready.
- [ ] Record silence, stop → pill flashes "No speech detected", nothing pastes.
- [ ] Record for > 5 minutes → auto-stops with "5 min limit, processing".

## J. Menu bar

- [ ] Mode submenu shows correct ✓ on active mode (or Auto).
- [ ] Hotkey submenu: pick "Left Option" → old key stops working, new key works immediately, choice persists after relaunch.
- [ ] Sounds toggle silences/restores the start/stop sounds.
- [ ] History submenu lists recent dictations; clicking copies (notification confirms).
- [ ] Help → Copy diagnostics puts a non-empty bundle on the clipboard, with no `AIza…` substring (key redaction).
- [ ] Quit removes the icon and stops the listener (no more dictation triggers).

## K. Persistence

- [ ] Reboot. Murmur auto-launches via launchd; menu bar icon present without manual action.
- [ ] Mode, auto-mode, sounds, and hotkey from previous session are restored.

## L. Uninstall

- [ ] `bash uninstall.sh` removes the menu bar icon, launch agent, and app support files.
- [ ] User is prompted before .env removal.
