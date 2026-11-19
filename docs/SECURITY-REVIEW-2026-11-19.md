# Bol security review — 19 November 2026

## Result and scope

Source-level review and targeted adversarial tests completed for the shared Linux app, accounts, provider adapters, local history, daemon IPC, text insertion and installer/release code. This is not an independent penetration test or a certification that every platform or dependency is secure. Arch, Ubuntu and Fedora ship the same Python code; actual security behavior on each desktop was not retested on physical machines in this review. Flatpak remains an investigation, not a shipped sandbox.

Release update: these fixes are included in the v0.1.0-alpha.2 source and package workflow. They are NOT in v0.1.0-alpha.1. Existing running processes must be restarted after upgrading.

## Findings fixed

| Severity | Finding | Remediation |
|---|---|---|
| High, conditional on a provider redirect | Sarvam's default HTTP opener could follow a redirect with a subscription-key header. | All Sarvam and compatible-provider requests use a redirect-rejecting opener. Account requests already rejected redirects. Local HTTP regression verifies the destination is never contacted. |
| Medium | Unbounded speech/writing/TTS JSON responses could exhaust memory. | Read at most 1 MiB for text responses and 32 MiB for base64 TTS JSON before decoding. |
| Medium | Predictable fallback runtime paths trusted pre-existing directories, including symlinks or shared directories. | Validate owner, directory type and private permissions before creating/opening locks or sockets; validate fallback parent too. Fail closed on unsafe paths. |
| Medium | A client disconnecting before the daemon reply could terminate the daemon. | Handle broken pipe, reset and send timeout without exiting the accept loop. |
| Medium | Multiline/control-character model output could be pasted into a terminal and interpreted as commands by some terminal/shell configurations. | Recognized terminals now require manual pasting of this output. Terminal recognition uses application class names and is not exhaustive. |
| Low | History cap eviction did not explicitly enable SQLite secure deletion on each connection. | Enable secure_delete on every connection. This is not guaranteed physical erasure on SSDs, snapshots or backups. |
| Medium, supply-chain hardening | GitHub Action version tags are movable. | Pin the three used Actions to their verified full commit hashes, retaining version comments. Container images and distro package repositories remain moving dependencies. |

## Verification evidence

- 98 unit/integration tests pass with `BOL_TEST_POSTGRES=1 python -m unittest discover -s tests -q`, including six tests against an isolated real PostgreSQL instance.
- Database tests cover anonymous access, cross-user reads/writes/inserts, payload key restrictions, authenticated identity and revision conflicts. These use the repository migration; they do not prove the complete live project's policies match it.
- Read-only live probe: `/rest/v1/bol_preferences?select=user_id&limit=1`, with the public publishable key and no user token, returned HTTP 401 / PostgreSQL `42501`.
- Live public Auth settings: signup enabled; email autoconfirm disabled. No signup attempts, emails, real user records or account credentials were used for this audit.
- `npm audit --package-lock-only --ignore-scripts` against a temporary copy of the installed ElevenLabs helper lockfile: zero reported vulnerabilities. Registry findings are time-dependent; this does not audit its binary implementation or all transitive native code.
- Bandit scanned all ten application Python modules. Remaining reports are subprocess/PATH review notices and the predictable fallback-directory notice, now guarded by private ownership/type/mode validation. No `shell=True`, dynamic eval or SQL string interpolation of user content was found in application paths. Subprocess arguments use argv lists; user-selected Whisper executables are intentionally executable code and must be trusted.
- Targeted secret-pattern scan across 352 historical Git blobs found no matches for private-key blocks, Supabase secret keys, GitHub tokens or AWS access-key IDs. This is not a complete entropy-based secret scanner and cannot prove no credential was ever committed. The bundled Supabase publishable key is intentionally public.
- Existing tests verify private session files, credential-free sync allowlist, login-link project/email validation, local inference cancellation, target-aware text insertion and package contents.
- `git diff --check` passes. Existing user edits to `bol_ui.py` were preserved.

## Remaining risks and production gates

1. **Local credentials are private plaintext files**, not OS-keyring encrypted secrets. Mode 0600 restricts other Unix users; malware running as the same user can read tokens and provider keys, control the app and inspect audio/history. Full-disk encryption and a locked desktop remain relevant. Account switching does not isolate the local workspace.
2. **Production Supabase settings were not fully verified.** No authenticated dashboard was available. Check Security Advisor, all exposed tables/buckets/functions, team MFA, allowed redirect URLs, OTP expiry, rate limits, logging/backups and SMTP quotas. App CAPTCHA support is not implemented; enabling server CAPTCHA without implementing a supported app challenge flow would break sign-in. Do not change this blindly.
3. **Only preferences have audited RLS tests.** Project administrators can read cloud preferences; this is not end-to-end encryption. The table grants authenticated users direct insert/update on their own row, so clients can bypass the RPC revision convention for their own data; RLS still prevents cross-user access. Free-text allowed preference fields can contain user-entered sensitive information despite excluding dedicated credential fields.
4. **Releases are unsigned.** SHA256SUMS detects corruption but does not independently authenticate a compromised release account. Add artifact attestations/signing and account MFA before stable distribution; container images/distro dependencies also need ongoing monitoring.
5. **Host libraries were not fully CVE-audited.** Python, GTK, PipeWire, FFmpeg, local Whisper models/binaries and platform-specific packages are provided by users/distributions. There is no pip runtime requirements file to audit. The npm result is limited to the installed helper lockfile. Its optional installer executes npm lifecycle scripts; the package version is pinned, but future dependency resolution is not bound to that audited local lockfile.
6. **Desktop integration needs physical GNOME/KDE/X11 testing.** Focus validation narrows accidental insertion but cannot make checking focus and delivering a shortcut atomic. Clipboard contents can be visible to clipboard managers/other software. Recognized-terminal multiline protection does not identify every possible command interpreter or embedded terminal.
7. **Resource limits are partial.** Network response limits and recording timeouts are enforced, but a same-user client can still occupy the daemon's serial socket handler for its read timeout. Configured local executable output is trusted. No account-abuse/load/fuzz campaign or third-party service penetration testing was performed.

## Reproduction

```sh
BOL_TEST_POSTGRES=1 python -m unittest discover -s tests -q
python -m venv /tmp/bol-security-tools
/tmp/bol-security-tools/bin/pip install bandit
/tmp/bol-security-tools/bin/bandit -r bol_accounts.py bol_audio.py bol_desktop.py bol_elevenlabs.py bol_features.py bol_gtk.py bol_providers.py bol_themes.py bol_ui.py kivi_linux.py
```

Reference: [Supabase production security checklist](https://supabase.com/docs/guides/security/production-checklist), [Auth rate limits](https://supabase.com/docs/guides/auth/rate-limits), [CAPTCHA integration](https://supabase.com/docs/guides/auth/auth-captcha), [Python HTTP redirect handler](https://docs.python.org/3/library/urllib.request.html#urllib.request.HTTPRedirectHandler).
