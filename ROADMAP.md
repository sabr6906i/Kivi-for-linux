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

## Account experience beyond local profiles

Implemented: local display name/startup preferences, a profile settings menu, first-run setup, browser-guided Sarvam key connection, and optional Supabase email-code authentication with manual preference sync. The Supabase migration includes owner-only RLS and revision conflict checks. A hosted project and real email delivery still need to be configured and verified. Provider API credentials remain device-local.

A real keyless account experience needs a separate project:

- Choose and configure a Bol-owned identity provider with external-browser OAuth/PKCE and secure session storage.
- Host an authenticated service that can authorize and meter cloud speech/writing/audio generation without distributing a shared provider key in the desktop app.
- Define account quotas, cost ownership, logout/revocation, and optional preference synchronization.
- Keep local dictation available without an account and make cloud processing an explicit choice.

An ElevenLabs CLI browser-sign-in adapter is now implemented; account authorization and a live account transcription still need user verification. It uses the official provider helper, not a Bol-hosted identity service.

Provider dashboard cookies or website sign-in pages are not a replacement for a supported API authorization flow. No backend or billing service has been deployed for Bol.
