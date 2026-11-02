import http.cookiejar
import json
import secrets
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

import server


class PrivateTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.old_db = server.DB_PATH
        server.DB_PATH = str(Path(self.temporary.name) / 'private.sqlite3')
        server.initialize(seed=False)
        self.token = secrets.token_urlsafe(32)
        class PrivateHandler(server.Handler):
            private_mode = True
            setup_token = self.token
            auth_attempts = {}
            auth_lock = threading.Lock()
        self.handler = PrivateHandler
        self.http = server.ThreadingHTTPServer(('127.0.0.1', 0), PrivateHandler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.http.server_port}/api/'
        self.client = self.new_client()

    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join()
        server.DB_PATH = self.old_db
        self.temporary.cleanup()

    def new_client(self):
        return urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, path, payload=None, client=None):
        request=urllib.request.Request(self.base+path, data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json'})
        try:
            with (client or self.client).open(request) as response:return response.status,json.load(response),response.headers
        except urllib.error.HTTPError as error:return error.code,json.load(error),error.headers

    def create_owner(self):
        response=self.call('setup',{'token':self.token,'name':'Propietario','email':'owner@example.test','password':'PersonalPassword2026!'})
        self.assertEqual(response[0],200)
        response=self.call('login',{'email':'owner@example.test','password':'PersonalPassword2026!'})
        self.assertEqual(response[0],200)
        return response

    def test_no_demo_and_bootstrap_requires_secret(self):
        self.assertEqual(self.call('config')[1],{'private':True,'setup_required':True})
        self.assertEqual(self.call('setup',{'token':'wrong','name':'Attack','email':'a@example.test','password':'LongEnoughPassword'})[0],403)
        with server.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0],0)
        self.assertEqual(self.call('login',{'email':'gestor@demo.local','password':'TenisDemo2026!'})[0],401)
        self.assertEqual(self.call('state')[0],401)

    def test_single_owner_no_reconfiguration_and_persistence(self):
        self.create_owner()
        self.assertEqual(self.call('config')[1]['setup_required'],False)
        s=self.call('state')[1]
        self.assertEqual(s['user']['role'],'manager')
        self.assertEqual(s['students'],[])
        self.assertEqual(self.call('setup',{'token':self.token,'name':'Another','email':'other@example.test','password':'AnotherPassword2026!'})[0],400)
        server.initialize(seed=False)
        with server.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0],1)

    def test_setup_rejects_weak_password(self):
        self.assertEqual(self.call('setup',{'token':self.token,'name':'Owner','email':'owner@example.test','password':'weak'})[0],400)

    def test_private_disables_client_accounts_and_old_tokens(self):
        self.create_owner()
        self.assertEqual(self.call('tutors',{'name':'Tutor','email':'tutor@example.test','password':'FamilyPassword2026!'})[0],200)
        client=self.new_client()
        self.assertEqual(self.call('login',{'email':'tutor@example.test','password':'FamilyPassword2026!'},client)[0],401)

    def test_secure_cookie_and_password_change_invalidates_other_devices(self):
        self.create_owner()
        other=self.new_client()
        self.assertEqual(self.call('login',{'email':'owner@example.test','password':'PersonalPassword2026!'},other)[0],200)
        self.handler.secure_cookie=True
        code,_,headers=self.call('password',{'current_password':'PersonalPassword2026!','password':'ReplacementPassword2026!'})
        self.assertEqual(code,200)
        self.assertIn('Secure',headers['Set-Cookie']);self.assertIn('HttpOnly',headers['Set-Cookie']);self.assertIn('SameSite=Strict',headers['Set-Cookie'])
        self.handler.secure_cookie=False
        self.assertEqual(self.call('state',client=other)[0],401)
        self.assertEqual(self.call('login',{'email':'owner@example.test','password':'PersonalPassword2026!'})[0],401)
        self.assertEqual(self.call('login',{'email':'owner@example.test','password':'ReplacementPassword2026!'})[0],200)

    def test_rate_limit_failed_passwords(self):
        self.create_owner()
        for _ in range(8):self.assertEqual(self.call('login',{'email':'owner@example.test','password':'wrong'})[0],401)
        self.assertEqual(self.call('login',{'email':'owner@example.test','password':'wrong'})[0],429)

    def test_startup_rejects_demo_database(self):
        server.initialize(seed=True)
        with self.assertRaisesRegex(server.Invalid,'demostración'):server.validate_private_configuration()

    def test_private_initialization_never_seeds_demo(self):
        with mock.patch.object(server,'PRIVATE_MODE',True):server.initialize()
        with server.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0],0)
