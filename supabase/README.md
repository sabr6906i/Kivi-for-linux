# Bol accounts on Supabase

Bol uses Supabase Auth for passwordless email-link/code accounts and Postgres for a private preference document per account. No separately hosted Python server, paid hosting commitment, or database password is required in the desktop app. The public build bundles the Bol project URL and publishable key; users only sign in. The setup below is for maintainers creating a different project, not for ordinary users.

## Project setup

1. Create a project at [Supabase Dashboard](https://supabase.com/dashboard). Keep its database password private.
2. Open **SQL Editor**, paste [the migration](migrations/202611190001_accounts.sql), and run it. It creates `public.bol_preferences`, enables row-level security, and installs `bol_save_preferences` for revision-checked writes. Supabase Auth already stores account identities; Bol does not maintain a password table.
3. Enable the Email provider in **Authentication → Sign In / Providers** and allow new user signups if you want registration. This client accepts the original emailed sign-in link or a numeric code, without a browser callback or password.
4. The default email template works: right-click its **Sign in** link, copy the link address, and paste it into Bol before opening it. Bol checks that it belongs to the configured project and exchanges its token directly with Supabase. If you prefer numeric codes, template editing currently requires custom SMTP or Pro. Include the code in **Authentication → Emails → Magic link or OTP**:

   ```html
   <h2>Your Bol sign-in code</h2>
   <p>Enter this code in Bol: <strong>{{ .Token }}</strong></p>
   <p>If you did not request it, ignore this email.</p>
   ```

   Keep email verification enabled. The `/otp` endpoint creates new accounts and sends a code; `/verify` verifies it before a session is stored. Both default magic links and numeric codes work with the desktop sign-in flow. A link already opened in a browser may have been consumed; request a fresh email if needed.
5. Configure **custom SMTP** for emails to real app users. Supabase's default sender is restricted to authorized project-team addresses and has tight limits. Test with your own project-member email first. Review Supabase's authentication rate limits before opening signups publicly.
6. Get the **Project URL** from Project Settings / Connect and the **publishable key** (`sb_publishable_…`) from **Settings → API Keys**. Do not use a secret key, a service-role key, or a database connection string. Bol intentionally rejects admin and legacy JWT keys.
7. For a custom developer project, start a fresh Bol workspace with `BOL_DEVELOPER_MODE=1 bol settings`, then open **Profile & settings → Your profile → Bol account → Cloud project setup**. Enter the project URL and publishable key, then click **Save cloud connection**.
8. Click **Sign in**, enter your email, request the email, and paste its original sign-in link or enter its numeric code in Bol. No password is stored.
9. Save settings on the first device. They sync automatically after sign-in and on save, with a background check every 45 seconds while the workspace is open (including when hidden). Sign in to the same account on another device to restore them. Users can pause **Automatic sync**, run **Sync now**, or use **Sync recovery** for explicit uploads/restores. No per-user project setup is required.

The publishable key can ship with a desktop app; access control comes from the signed-in user's JWT and database policies. Keep Supabase secret keys out of the app and repository. Existing speech/writing API keys still belong to each user; a Bol account does not grant or bill provider access.

## What syncs

- Display name, theme, opening page, speech language and output mode.
- Polish and voice-edit review preferences, writing rules and per-app writing instructions.
- Vocabulary, spelling corrections, and snippets.

Sync is automatic after sign-in, on save, and every 45 seconds while the workspace is open. It pauses for unsaved edits, never replaces text being edited, and retries when offline. Closing the workspace stops its timer; reopening resumes sync. History, generated audio, microphone/shortcuts, local model paths, provider credentials, and account tokens are excluded. Cloud preferences are private through RLS, not end-to-end encrypted; the Supabase project operator can access the database. Signing out does not delete local preferences or isolate the existing workspace for another person.

Automatic sync uses the last synced preferences as a three-way merge baseline. Changes to different fields merge automatically; changes to the same field pause sync and show **Review changes**. On a new device with no baseline, default preferences serve as the starting point; existing customizations are preserved and conflicts are reviewed. Users can choose this device’s version or review the cloud snapshot. Revision-checked writes prevent silent overwrites when another device uploads concurrently. Manual restore replaces the synced fields. Canceling its preview leaves local settings and the saved revision unchanged.

## Sessions

Session access/refresh tokens live in `~/.config/bol-linux/account-session.json` (or the matching `XDG_CONFIG_HOME`) with permissions `0600`, separate from general settings. They are not encrypted with an OS keyring in this version. Tokens are scoped to the configured project. Refresh tokens rotate through Supabase Auth; sign-out requests revocation for this device and clears the local session even if offline. Offline sign-out cannot guarantee server revocation until tokens expire.

## Verification

```bash
python -m unittest discover -s tests -q
# Optional: installed PostgreSQL binaries; creates and removes its own temporary database.
BOL_TEST_POSTGRES=1 python -m unittest discover -s tests -p test_account_database.py -v
```

The integration checks exercise actual Postgres policies with an emulated Supabase `auth.uid()` context: cross-user reads/writes, anonymous requests, forbidden payload fields, and stale revisions. They do not test email delivery or a hosted Supabase project. Before release, test two real accounts against your project, email delivery, sign-out, and a two-device restore. The public build points to the configured Bol project; automated tests use fake sessions or an isolated PostgreSQL instance, never real users’ accounts.

References: [Email OTP](https://supabase.com/docs/guides/auth/auth-email-passwordless), [RLS](https://supabase.com/docs/guides/database/postgres/row-level-security), [publishable keys](https://supabase.com/docs/guides/getting-started/api-keys), [custom SMTP](https://supabase.com/docs/guides/auth/auth-smtp).
