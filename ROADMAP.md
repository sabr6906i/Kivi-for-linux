# Bol development roadmap

Bol is an early Linux dictation app. Matching the day-to-day quality of mature dictation products requires measured reliability, model performance and compatibility work; a feature list alone is not parity.

## Current milestone: controlled editing and retention

Implemented:

- Voice-edit review with editable proposals, copy-only, approval and discard.
- Generation checks reject approvals for cancelled/replaced drafts.
- Approval rechecks the original window and selection; changed targets fall back to copying.
- History retention choices: up to 200 entries, 24 hours, 7 days or 30 days. Expired rows are removed when history is accessed.
- Local/cloud providers, search, date-grouped history, vocabulary, snippets, writing profiles and exports from previous milestones.

Verified by automated tests and GTK smoke checks. This is not a claim of broad desktop compatibility or model quality parity.

## Next: faster local speech

- Integrate an optional persistent whisper.cpp server to avoid model reload per utterance.
- Measure cold/warm latency, peak memory and cancellation time against the existing CLI engine.
- Add a multilingual model manager with explicit download sizes, progress, cancellation and checksum validation.
- Test English, Punjabi, Hindi and mixed-language samples with multilingual models. The currently detected `.en` model covers English only.

Done when warm inference is measurably faster, cancellation leaves no child inference job running, and local mode never silently uses cloud speech.

## Daily-use desktop controls

- System-tray menu: start/finish/cancel, quick provider/language selection and pending review.
- Live microphone level based on captured samples, not a decorative animation.
- Clear microphone failures, provider failures and paste outcomes.
- Settings backup/import with credentials excluded by default.
- Optional launch at login and a managed background service.

Done when these controls remain responsive during recording, API delays and local inference.

## Writing quality and recovery

- Structured per-app profiles with presets and a preview sandbox.
- Clipboard restoration that respects clipboard-manager and application timing.
- A tested undo workflow for approved replacements.
- Optional recovery of failed recordings with explicit retention controls; no audio retention by default.
- Explicit correction suggestions without reading arbitrary edits in the background.

Done when source text, code identifiers and multilingual text survive the tested transformation cases, and failed insertion can be recovered without losing the result.

## Distribution and compatibility

- A clean-machine installer/uninstaller and versioned releases.
- Hyprland testing across browser fields, editors, chat clients, rich-text apps and terminals.
- Investigate GNOME/KDE Wayland shortcuts and insertion through supported desktop APIs.
- Provider contract tests, HTTP failure tests and a reproducible audio quality/latency benchmark.

Release readiness requires evidence from real use in the supported app/desktop matrix, not only mocked tests. Cross-desktop support, streaming recognition and automatic updates are not implemented yet.
