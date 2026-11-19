import json
import os
from copy import deepcopy
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from bol_accounts import AccountClient, preferences, SYNC_KEYS
from bol_features import DEFAULTS


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.settings = {**deepcopy(DEFAULTS), 'supabase_url': 'https://example.supabase.co', 'supabase_publishable_key': 'sb_publishable_test'}
        self.client = AccountClient(self.tmp.name, self.settings)

    def session(self, user='user-one'):
        self.client.accept_session({'access_token': 'access', 'refresh_token': 'refresh', 'expires_in': 3600, 'user': {'id': user, 'email': 'user@example.com'}})

    def test_only_allowlisted_settings_uploaded(self):
        self.settings.update({'api_key': 'secret', 'writing_api_key': 'secret', 'whisper_model': '/private/model', 'supabase_publishable_key': 'client-key'})
        data = preferences(self.settings)
        self.assertEqual(set(data), set(SYNC_KEYS))
        self.assertNotIn('secret', json.dumps(data))
        self.assertNotIn('/private/model', json.dumps(data))

    def test_invalid_cloud_types_and_enums_rejected(self):
        for data in ({'polish': 'yes'}, {'snippets': {'name': {'api_key': 'x'}}}, {'theme': '../../file'}, {'language': 'bad'}, {'vocabulary': ['x' * 65]}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                preferences(data)

    def test_session_is_private_and_not_general_config(self):
        self.session()
        self.assertEqual(os.stat(self.client.path).st_mode & 0o777, 0o600)
        self.assertNotIn('access_token', self.settings)
        other = AccountClient(self.tmp.name, {**self.settings, 'supabase_url': 'https://other.supabase.co'})
        self.assertFalse(other.signed_in)

    def test_project_rejects_http_admin_keys_paths_and_userinfo(self):
        for url, key in [('http://example.supabase.co', 'sb_publishable_ok'), ('https://example.supabase.co/path', 'sb_publishable_ok'), ('https://user@example.supabase.co', 'sb_publishable_ok'), ('https://example.supabase.co', 'sb_secret_bad'), ('https://example.supabase.co', 'legacy-service-role')]:
            with self.subTest(url=url, key=key), self.assertRaises(ValueError):
                AccountClient(self.tmp.name, {'supabase_url': url, 'supabase_publishable_key': key}).validate_project()

    def test_email_code_signin_and_validation(self):
        with patch.object(self.client, 'request', return_value={}) as request:
            self.client.send_code('user@example.com')
            request.assert_called_once_with('/auth/v1/otp', {'email': 'user@example.com', 'create_user': True})
        with patch.object(self.client, 'request') as request:
            with self.assertRaises(ValueError):self.client.verify_code('user@example.com', 'nonsense')
            request.assert_not_called()
        result = {'access_token': 'a', 'refresh_token': 'r', 'user': {'id': 'id', 'email': 'user@example.com'}}
        with patch.object(self.client, 'request', return_value=result):self.client.verify_code('user@example.com', '123456')
        self.assertTrue(self.client.signed_in)

    def test_expired_session_refresh_retains_sync_revision(self):
        self.session();self.client.session.update({'expires_at': 0, 'revision': 8})
        refreshed = {'access_token': 'new', 'refresh_token': 'rotated', 'user': {'id': 'user-one'}}
        with patch.object(self.client, 'request', return_value=refreshed) as request:
            self.assertEqual(self.client.access_token(), 'new')
            request.assert_called_once_with('/auth/v1/token?grant_type=refresh_token', {'refresh_token': 'refresh'})
        self.assertEqual(self.client.session['revision'], 8)
        self.assertEqual(json.loads(self.client.path.read_text())['refresh_token'], 'rotated')

    def test_switching_account_resets_sync_revision(self):
        self.session();self.client.session['revision'] = 7
        self.session('user-two')
        self.assertEqual(self.client.session['revision'], 0)

    def test_upload_uses_revision_and_excludes_credentials(self):
        self.session();self.client.session['revision'] = 3
        with patch.object(self.client, 'request', return_value=4) as request:
            self.client.upload({**self.settings, 'api_key': 'secret'})
            args = request.call_args.args
            self.assertEqual(args[0], '/rest/v1/rpc/bol_save_preferences')
            self.assertEqual(args[1]['expected_revision'], 3)
            self.assertNotIn('api_key', args[1]['new_payload'])
        self.assertEqual(self.client.session['revision'], 4)

    def test_download_validates_without_applying_or_advancing_revision(self):
        self.session()
        with patch.object(self.client, 'request', return_value=[{'payload': {'theme': 'ivory'}, 'revision': 5}]):
            self.assertEqual(self.client.download(), ({'theme': 'ivory'}, 5))
        self.assertEqual(self.client.session['revision'], 0)
        self.client.applied(5)
        self.assertEqual(self.client.session['revision'], 5)

    def test_download_rejects_secret_fields(self):
        self.session()
        with patch.object(self.client, 'request', return_value=[{'payload': {'api_key': 'secret'}, 'revision': 2}]):
            with self.assertRaises(ValueError):self.client.download()

    def test_failed_signout_still_clears_local_session(self):
        self.session()
        with patch.object(self.client, 'request', side_effect=ValueError('offline')):
            with self.assertRaisesRegex(ValueError, 'Signed out on this device'):self.client.sign_out()
        self.assertFalse(self.client.path.exists())
        self.assertFalse(self.client.signed_in)

    def test_redirect_cannot_forward_credentials(self):
        from bol_accounts import NoRedirect
        with self.assertRaises(ValueError):NoRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.example')

    def test_default_supabase_email_link_is_exchanged_without_following_redirect(self):
        token = 'a' * 64
        result = {'access_token': 'a', 'refresh_token': 'r', 'user': {'id': 'id', 'email': 'user@example.com'}}
        with patch.object(self.client, 'request', return_value=result) as request:
            self.client.verify_code('user@example.com', self.client.url + '/auth/v1/verify?token=' + token + '&type=magiclink&redirect_to=http://localhost:3000')
            request.assert_called_once_with('/auth/v1/verify', {'token_hash': token, 'type': 'magiclink'})
        self.assertTrue(self.client.signed_in)

    def test_email_link_from_another_project_or_unsupported_flow_rejected(self):
        for link in ('https://evil.example/auth/v1/verify?token=' + 'a'*64 + '&type=magiclink',
                     self.client.url + '/auth/v1/verify?token=' + 'a'*64 + '&type=recovery',
                     self.client.url + '/other?token=' + 'a'*64 + '&type=signup'):
            with self.subTest(link=link), patch.object(self.client, 'request') as request:
                with self.assertRaises(ValueError):self.client.verify_code('user@example.com', link)
                request.assert_not_called()

    def test_link_cannot_sign_in_as_a_different_email(self):
        result = {'access_token': 'a', 'refresh_token': 'r', 'user': {'id': 'id', 'email': 'other@example.com'}}
        with patch.object(self.client, 'request', return_value=result):
            with self.assertRaisesRegex(ValueError, 'different email'):self.client.verify_code('user@example.com', '123456')
        self.assertFalse(self.client.path.exists())

    def test_auth_errors_explain_email_delivery_and_expired_links(self):
        import io
        import urllib.error
        from unittest.mock import Mock
        for error_code, message in [('email_address_not_authorized', 'custom SMTP'), ('over_email_send_rate_limit', 'sending limit'), ('otp_expired', 'already used')]:
            body = json.dumps({'error_code': error_code, 'message': 'private-server-text'}).encode()
            error = urllib.error.HTTPError(self.client.url, 403, '', {}, io.BytesIO(body))
            opener = Mock();opener.open.side_effect = error
            with self.subTest(error_code=error_code), patch('urllib.request.build_opener', return_value=opener):
                with self.assertRaisesRegex(ValueError, message) as caught:self.client.send_code('user@example.com')
                self.assertNotIn('private-server-text', str(caught.exception))
