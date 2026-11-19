"""Supabase email-code authentication and explicit, credential-free preference sync."""
import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from bol_features import DEFAULTS

SYNC_KEYS = ('profile_name', 'theme', 'start_page', 'language', 'output_mode',
             'polish', 'writing_rules', 'profiles', 'vocabulary', 'corrections',
             'snippets', 'review_edits')


def preferences(settings):
    """Strict allowlist: never upload provider keys, tokens, history or local paths."""
    result = {}
    for key in SYNC_KEYS:
        if key not in settings:
            continue
        value = settings[key]
        if type(value) is not type(DEFAULTS[key]):
            raise ValueError('Invalid preference type: ' + key)
        if isinstance(value, dict) and any(not isinstance(k, str) or not isinstance(v, str) for k, v in value.items()):
            raise ValueError('Invalid preference entries: ' + key)
        if isinstance(value, list) and any(not isinstance(v, str) for v in value):
            raise ValueError('Invalid preference entries: ' + key)
        result[key] = value
    from bol_themes import THEMES
    from bol_features import LANGUAGES, MODES
    if result.get('theme', 'dark') not in THEMES or result.get('start_page', 'History') not in ('History', 'Text to Audio'):
        raise ValueError('Unsupported appearance preference.')
    if result.get('language', 'unknown') not in LANGUAGES or result.get('output_mode', 'transcribe') not in MODES:
        raise ValueError('Unsupported speech preference.')
    if len(result.get('profile_name', '')) > 80 or len(result.get('vocabulary', [])) > 50 or any(len(v) > 64 for v in result.get('vocabulary', [])):
        raise ValueError('Profile or vocabulary is too long.')
    if len(json.dumps(result, ensure_ascii=False).encode()) > 60000:
        raise ValueError('Cloud preferences must be smaller than 60 KB.')
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('The account server redirected the request. Check the project URL.')


class AccountClient:
    def __init__(self, folder, settings):
        self.folder = Path(folder)
        self.path = self.folder / 'account-session.json'
        self.url = str(settings.get('supabase_url', '')).strip().rstrip('/')
        self.key = str(settings.get('supabase_publishable_key', '')).strip()
        self.session = {}
        try:
            saved = json.loads(self.path.read_text())
            if saved.get('project_url') == self.url:
                self.session = saved
        except (FileNotFoundError, ValueError, AttributeError):
            pass

    @property
    def signed_in(self):
        return bool(self.session.get('refresh_token') and self.session.get('user', {}).get('id'))

    def validate_project(self):
        parsed = urllib.parse.urlsplit(self.url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment or parsed.port not in (None, 443):
            raise ValueError('Enter your Supabase HTTPS project URL, without a path.')
        # Never allow an admin key in a desktop client.
        if self.key.startswith('sb_secret_'):
            raise ValueError('Use a publishable key, never a secret or service-role key.')
        if not self.key.startswith('sb_publishable_'):
            raise ValueError('Use the sb_publishable_ key from Supabase Project Settings → API Keys.')

    def request(self, route, body=None, token=None):
        self.validate_project()
        headers = {'apikey': self.key, 'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.url + route, data=data, headers=headers)
        try:
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=25) as response:
                raw = response.read(1048577)
                if len(raw) > 1048576:
                    raise ValueError('The account server returned too much data.')
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            # Use documented error codes, never display raw server bodies or tokens.
            try:
                details = json.loads(error.read(8192))
                auth_code = details.get('error_code', details.get('code', ''))
            except (ValueError, AttributeError):
                auth_code = ''
            finally:
                error.close()
            auth_messages = {
                'email_address_not_authorized': 'Supabase’s default email sender only permits project-team addresses. The app owner must configure custom SMTP for other users.',
                'over_email_send_rate_limit': 'Supabase’s email sending limit has been reached. Wait before requesting another email; the app owner can configure custom SMTP for public use.',
                'email_not_confirmed': 'Your email has not been confirmed. Use the latest sign-in email and double-check its address.',
                'otp_expired': 'The sign-in link or code expired or was already used. Request a new email and paste its link into Bol before opening it.',
                'signup_disabled': 'New account registration is disabled in this Supabase project.',
                'email_provider_disabled': 'Email sign-in is disabled in this Supabase project.',
            }
            if auth_code in auth_messages:
                raise ValueError(auth_messages[auth_code]) from None
            if error.code == 409:
                raise ValueError('Another device changed your cloud preferences. Restore the cloud version before uploading again.') from None
            messages = {400: 'The email or code was rejected. Check it or request a new code.',
                        401: 'Your session or project key is invalid. Sign in again.',
                        403: 'Access was denied. Check the project key and database policies.',
                        404: 'Cloud setup is incomplete. Run the Bol database migration in Supabase.',
                        429: 'Too many requests. Wait a minute before trying again.'}
            raise ValueError(messages.get(error.code, f'Account service returned HTTP {error.code}.')) from None
        except (urllib.error.URLError, TimeoutError):
            raise ValueError('Could not reach Supabase. Check your connection and project URL.') from None

    def persist(self):
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=self.folder, delete=False) as output:
                name = output.name
                os.chmod(name, 0o600)
                json.dump(self.session, output)
            os.replace(name, self.path)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)

    @staticmethod
    def email(value):
        value = value.strip()
        if len(value) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Enter a valid email address.')
        return value

    def send_code(self, email):
        return self.request('/auth/v1/otp', {'email': self.email(email), 'create_user': True})

    def verify_code(self, email, code):
        email = self.email(email)
        code = code.strip()
        if code.startswith('https://'):
            # Consume only this project's original email link, never follow URLs
            # or accept access tokens supplied in a browser redirect fragment.
            self.validate_project()
            link = urllib.parse.urlsplit(code)
            project = urllib.parse.urlsplit(self.url)
            query = urllib.parse.parse_qs(link.query)
            kind = query.get('type', [''])[0]
            token_hash = query.get('token_hash', query.get('token', ['']))[0]
            if (link.scheme != 'https' or link.netloc != project.netloc or
                    link.path != '/auth/v1/verify' or link.fragment or
                    kind not in ('magiclink', 'signup', 'email') or
                    not re.fullmatch(r'[A-Za-z0-9_-]{20,256}', token_hash)):
                raise ValueError('Paste the original sign-in link from this project’s email, or enter the numeric code.')
            payload = {'token_hash': token_hash, 'type': kind}
        else:
            if not re.fullmatch(r'\d{6,10}', code):
                raise ValueError('Enter the email code, or paste the original sign-in link from the email.')
            payload = {'email': email, 'token': code, 'type': 'email'}
        result = self.request('/auth/v1/verify', payload)
        if result.get('user', {}).get('email', '').casefold() != email.casefold():
            raise ValueError('That sign-in link belongs to a different email address. Request a new one for the email you entered.')
        self.accept_session(result)
        return self.session['user']

    def accept_session(self, result):
        if not isinstance(result, dict) or not result.get('access_token') or not result.get('refresh_token') or not result.get('user', {}).get('id'):
            raise ValueError('The account service did not return a complete session.')
        old_user = self.session.get('user', {}).get('id')
        revision = self.session.get('revision', 0) if old_user == result['user']['id'] else 0
        self.session = {'project_url': self.url, 'access_token': result['access_token'],
                        'refresh_token': result['refresh_token'], 'expires_at': time.time() + int(result.get('expires_in', 3600)),
                        'user': {'id': result['user']['id'], 'email': result['user'].get('email', '')},
                        'revision': revision, 'last_sync': self.session.get('last_sync', '') if old_user == result['user']['id'] else ''}
        self.persist()

    def access_token(self):
        if not self.signed_in:
            raise ValueError('Sign in to your Bol account first.')
        if self.session.get('expires_at', 0) < time.time() + 60:
            self.accept_session(self.request('/auth/v1/token?grant_type=refresh_token', {'refresh_token': self.session['refresh_token']}))
        return self.session['access_token']

    def upload(self, settings):
        payload = preferences(settings)
        result = self.request('/rest/v1/rpc/bol_save_preferences',
                              {'new_payload': payload, 'expected_revision': self.session.get('revision', 0)}, self.access_token())
        if type(result) is not int:
            raise ValueError('Unexpected sync response. Check the database migration.')
        self.session['revision'] = result
        self.mark_synced()
        return result

    def download(self):
        user_id = self.session.get('user', {}).get('id', '')
        query = urllib.parse.urlencode({'user_id': 'eq.' + user_id, 'select': 'payload,revision,updated_at'})
        result = self.request('/rest/v1/bol_preferences?' + query, token=self.access_token())
        if not isinstance(result, list):
            raise ValueError('Unexpected cloud preferences response.')
        if not result:
            raise ValueError('No preferences saved in the cloud yet. Upload from your first device.')
        row = result[0]
        payload = preferences(row['payload'])
        if set(row['payload']) - set(SYNC_KEYS) or type(row['revision']) is not int:
            raise ValueError('Cloud preferences contain unsupported fields.')
        return payload, row['revision']

    def applied(self, revision):
        self.session['revision'] = revision
        self.mark_synced()

    def mark_synced(self):
        self.session['last_sync'] = time.strftime('%Y-%m-%d %H:%M')
        self.persist()

    def sign_out(self):
        error = None
        try:
            if self.signed_in:
                self.request('/auth/v1/logout?scope=local', {}, self.access_token())
        except Exception as caught:
            error = caught
        finally:
            self.path.unlink(missing_ok=True)
            self.session = {}
        if error:
            raise ValueError('Signed out on this device. Could not revoke the remote session; it may remain valid until it expires.') from None
