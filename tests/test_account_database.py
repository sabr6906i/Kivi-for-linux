"""Real PostgreSQL RLS checks. Run with BOL_TEST_POSTGRES=1; no existing database touched."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.environ.get('BOL_TEST_POSTGRES') == '1' and shutil.which('initdb') and shutil.which('pg_ctl'), 'Set BOL_TEST_POSTGRES=1 to run isolated PostgreSQL integration checks')
class AccountDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='bol-accounts-pg-')
        cls.folder = Path(cls.tmp.name)
        cls.data = cls.folder / 'data'
        subprocess.run(['initdb', '-D', str(cls.data), '-A', 'trust', '--no-locale', '-E', 'UTF8'], check=True, capture_output=True)
        subprocess.run(['pg_ctl', '-D', str(cls.data), '-l', str(cls.folder / 'server.log'), '-o', f"-F -k {cls.folder} -c listen_addresses=''", '-w', 'start'], check=True, capture_output=True)
        cls.addClassCleanup(cls.stop)
        cls.sql('''create role anon nologin; create role authenticated nologin;
create schema auth; create table auth.users(id uuid primary key);
create function auth.uid() returns uuid language sql stable as $$select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid$$;
grant usage on schema auth to authenticated, anon;
insert into auth.users values ('00000000-0000-0000-0000-000000000001'), ('00000000-0000-0000-0000-000000000002');''')
        migration = Path(__file__).resolve().parents[1] / 'supabase/migrations/202611190001_accounts.sql'
        cls.sql(migration.read_text())
        cls.sql(migration.read_text())  # migration may be rerun safely

    @classmethod
    def stop(cls):
        subprocess.run(['pg_ctl', '-D', str(cls.data), '-m', 'immediate', '-w', 'stop'], capture_output=True)
        cls.tmp.cleanup()

    @classmethod
    def sql(cls, text, user=None, fail=False):
        if user:
            text = f"set role authenticated; set request.jwt.claim.sub='{user}'; " + text
        result = subprocess.run(['psql', '-h', str(cls.folder), '-d', 'postgres', '-v', 'ON_ERROR_STOP=1', '-Atq', '-c', text], capture_output=True, text=True)
        if not fail and result.returncode:
            raise AssertionError(result.stderr)
        return result

    def setUp(self):
        self.sql('truncate public.bol_preferences')
        self.one = '00000000-0000-0000-0000-000000000001'
        self.two = '00000000-0000-0000-0000-000000000002'

    def test_other_user_cannot_read_or_update_preferences(self):
        self.sql('''select public.bol_save_preferences('{"theme":"ivory"}',0)''', self.one)
        self.assertEqual(self.sql('select count(*) from public.bol_preferences', self.two).stdout.strip(), '0')
        self.sql("update public.bol_preferences set payload='{}'", self.two)
        self.assertIn('ivory', self.sql('select payload from public.bol_preferences', self.one).stdout)

    def test_other_user_cannot_insert_for_owner(self):
        result = self.sql(f"insert into public.bol_preferences(user_id) values ('{self.one}')", self.two, fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('row-level security', result.stderr)

    def test_stale_device_cannot_overwrite(self):
        self.sql('''select public.bol_save_preferences('{"theme":"paper"}',0)''', self.one)
        result = self.sql('''select public.bol_save_preferences('{"theme":"ivory"}',0)''', self.one, fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('another device', result.stderr)
        self.assertIn('paper', self.sql('select payload from public.bol_preferences', self.one).stdout)

    def test_anonymous_access_denied(self):
        result = self.sql('set role anon; select * from public.bol_preferences', fail=True)
        self.assertNotEqual(result.returncode, 0)
        result = self.sql("set role anon; select public.bol_save_preferences('{}',0)", fail=True)
        self.assertNotEqual(result.returncode, 0)

    def test_database_rejects_credentials_in_payload(self):
        result = self.sql('''select public.bol_save_preferences('{"api_key":"secret"}',0)''', self.one, fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('bol_payload_fields', result.stderr)

    def test_current_revision_saves_and_user_is_bound_to_auth(self):
        self.assertEqual(self.sql('''select public.bol_save_preferences('{"theme":"ivory"}',0)''', self.one).stdout.strip(), '1')
        self.assertEqual(self.sql('''select public.bol_save_preferences('{"theme":"sage"}',1)''', self.one).stdout.strip(), '2')
        self.assertEqual(self.sql('select user_id from public.bol_preferences', self.one).stdout.strip(), self.one)
