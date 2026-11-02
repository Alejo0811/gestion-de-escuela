import concurrent.futures
import datetime as dt
import http.cookiejar
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import server


class SchoolTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        server.DB_PATH = str(Path(self.temp.name) / 'school.db')
        server.initialize()
        self.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.http.server_port}/api/'
        self.manager = self.login('gestor')
        self.family = self.login('familia')

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()
        self.temp.cleanup()

    def call(self, opener, path, payload=None):
        req=urllib.request.Request(self.base+path, data=json.dumps(payload).encode() if payload is not None else None,
                                   headers={'Content-Type':'application/json'})
        try:
            with opener.open(req) as response:
                return response.status,json.load(response)
        except urllib.error.HTTPError as error:
            return error.code,json.load(error)

    def login(self, role):
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        code,_=self.call(opener,'login',{'email':role+'@demo.local','password':'TenisDemo2026!'})
        self.assertEqual(code,200)
        return opener

    def state(self, who=None):
        code,s=self.call(who or self.manager,'state')
        self.assertEqual(code,200)
        return s

    def test_family_scope_and_authorization(self):
        s=self.state(self.family)
        self.assertEqual([s['id'] for s in s['students']],[1,2])
        self.assertEqual({m['student_id'] for m in s['payments']},{1,2})
        self.assertEqual(s['tutors'],[])
        self.assertEqual(s['history'],[])
        self.assertNotIn('cost',s['groups'][0])
        self.assertEqual(self.call(self.family,'close',{'group_id':1})[0],400)
        self.assertEqual(self.call(self.family,'requests',{'student_id':3,'kind':'alta','target_id':6})[0],400)

    def test_pending_request_and_approval(self):
        before=self.state(self.family)['memberships']
        code,s=self.call(self.family,'requests',{'student_id':1,'kind':'cambio','source_id':1,'target_id':6})
        self.assertEqual(code,200)
        self.assertEqual(s['memberships'],before)
        rid=s['requests'][-1]['id']
        code,s=self.call(self.manager,'resolve',{'id':rid,'decision':'approved'})
        self.assertEqual(code,200)
        self.assertIn({'student_id':1,'group_id':6},s['memberships'])
        self.assertNotIn({'student_id':1,'group_id':1},s['memberships'])
        self.assertEqual(self.call(self.manager,'resolve',{'id':rid,'decision':'approved'})[0],400)

    def test_capacity_keeps_waitlist_and_original_membership(self):
        with server.connect() as db:
            db.execute('UPDATE groups SET capacity=3 WHERE id=6')
        _,s=self.call(self.family,'requests',{'student_id':1,'kind':'cambio','source_id':1,'target_id':6})
        rid=s['requests'][-1]['id']
        code,error=self.call(self.manager,'resolve',{'id':rid,'decision':'approved'})
        self.assertEqual(code,400)
        self.assertIn('completo',error['error'])
        s=self.state()
        self.assertIn({'student_id':1,'group_id':1},s['memberships'])
        self.assertEqual(next(r for r in s['requests'] if r['id']==rid)['status'],'pending')

    def test_reject_and_drop(self):
        _,s=self.call(self.family,'requests',{'student_id':1,'kind':'baja','source_id':1})
        rid=s['requests'][-1]['id']
        self.call(self.manager,'resolve',{'id':rid,'decision':'rejected'})
        self.assertIn({'student_id':1,'group_id':1},self.state()['memberships'])
        _,s=self.call(self.family,'requests',{'student_id':1,'kind':'baja','source_id':1})
        _,s=self.call(self.manager,'resolve',{'id':s['requests'][-1]['id'],'decision':'approved'})
        self.assertNotIn({'student_id':1,'group_id':1},s['memberships'])
        self.assertTrue(any(p['student_id']==1 for p in s['payments']))

    def group_payload(self):
        g=self.state()['groups'][0].copy()
        g.pop('id');g.pop('count');g.pop('status')
        return g

    def test_group_conflicts_and_valid_duplication(self):
        p=self.group_payload();p['name']='Duplicado'
        code,error=self.call(self.manager,'groups',p)
        self.assertEqual(code,400)
        self.assertIn('Incompatibilidad',error['error'])
        p['start']='08:00';p['end']='09:00';p['duplicate_of']=1
        code,s=self.call(self.manager,'groups',p)
        self.assertEqual(code,200)
        self.assertEqual(s['groups'][-1]['count'],0)
        self.assertEqual(s['groups'][-1]['days'],p['days'])

    def test_invalid_age_level_and_capacity_reduction(self):
        for sid,gid in [(1,3),(2,6)]:
            self.assertEqual(self.call(self.manager,'membership',{'action':'add','student_id':sid,'group_id':gid})[0],400)
        p=self.group_payload();p['id']=1;p['capacity']=1
        self.assertEqual(self.call(self.manager,'groups',p)[0],400)

    def test_student_schedule_conflict(self):
        p=self.group_payload();p.update(name='Paralelo',coach_id=5,court_id=8)
        code,s=self.call(self.manager,'groups',p);self.assertEqual(code,200)
        code,error=self.call(self.manager,'membership',{'action':'add','student_id':1,'group_id':s['groups'][-1]['id']})
        self.assertEqual(code,400);self.assertIn('Incompatibilidad',error['error'])

    def test_attendance_and_makeup(self):
        now=dt.date.today()
        with server.connect() as db:
            db.execute('UPDATE groups SET starts_on=?,ends_on=? WHERE id=1',((now-dt.timedelta(days=30)).isoformat(),(now+dt.timedelta(days=30)).isoformat()))
        day=now
        while day.weekday() not in (0,2):day-=dt.timedelta(days=1)
        code,s=self.call(self.manager,'attendance',{'student_id':1,'group_id':1,'date':day.isoformat(),'status':'absent'})
        self.assertEqual(code,200);self.assertEqual(len(s['makeups']),1)
        m=s['makeups'][0]
        code,s=self.call(self.manager,'makeups',{'id':m['id'],'recovery_date':(day+dt.timedelta(days=7)).isoformat(),'status':'scheduled'})
        self.assertEqual(code,200)
        self.assertEqual(s['makeups'][0]['status'],'scheduled')
        self.assertEqual(self.state(self.family)['attendance'][0]['status'],'absent')

    def test_billing_idempotence_and_payment(self):
        month=dt.date.today().strftime('%Y-%m')
        before=len(self.state()['payments'])
        for _ in range(2):self.assertEqual(self.call(self.manager,'bill',{'month':month})[0],200)
        s=self.state();self.assertEqual(len(s['payments']),before)
        p=next(p for p in s['payments'] if p['status']=='pending')
        code,s=self.call(self.manager,'payment',{'id':p['id'],'status':'paid'})
        self.assertEqual(code,200)
        self.assertEqual(next(x for x in s['payments'] if x['id']==p['id'])['status'],'paid')

    def test_catalog_tutor_student_and_persistence(self):
        self.assertEqual(self.call(self.manager,'catalog',{'kind':'level','name':'Adultos iniciación'})[0],200)
        _,s=self.call(self.manager,'tutors',{'name':'Nuevo tutor','email':'nuevo@example.test','password':'UnaClaveSegura2026'})
        tutor=s['tutors'][-1]
        code,s=self.call(self.manager,'students',{'name':'Nuevo alumno','birth':'2019-01-01','level_id':1,'guardian_id':tutor['id']})
        self.assertEqual(code,200)
        server.initialize()
        self.assertEqual(len(self.state()['students']),31)
        self.assertEqual(s['students'][-1]['guardian_id'],tutor['id'])

    def test_closed_group_refuses_enrollment(self):
        code,_=self.call(self.manager,'close',{'group_id':6});self.assertEqual(code,200)
        code,e=self.call(self.manager,'membership',{'action':'add','student_id':1,'group_id':6})
        self.assertEqual(code,400);self.assertIn('cerrado',e['error'])

    def test_tutor_edit_and_credential_rotation(self):
        code,_=self.call(self.manager,'tutors',{'id':2,'name':'María Actualizada','email':'familia@demo.local','password':'OtraClaveSegura2026'})
        self.assertEqual(code,200)
        # Changing a password invalidates previous sessions.
        self.assertEqual(self.call(self.family,'state')[0],401)
        self.assertEqual(self.call(self.family,'login',{'email':'familia@demo.local','password':'TenisDemo2026!'})[0],401)
        code,_=self.call(self.family,'login',{'email':'familia@demo.local','password':'OtraClaveSegura2026'})
        self.assertEqual(code,200)
        self.assertEqual(self.state(self.family)['user']['name'],'María Actualizada')

    def test_concurrent_last_place(self):
        # Group 6 has three pupils. Two simultaneous approvals compete for one place.
        with server.connect() as db:db.execute('UPDATE groups SET capacity=4 WHERE id=6')
        ids=[]
        for sid in (1,3):
            _,s=self.call(self.manager,'requests',{'student_id':sid,'kind':'cambio','source_id':1,'target_id':6})
            ids.append(s['requests'][-1]['id'])
        def approve(rid):
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            # Copy the authenticated cookie for independent HTTP clients.
            cookie=next(h for h in self.manager.handlers if isinstance(h,urllib.request.HTTPCookieProcessor)).cookiejar
            opener.add_handler(urllib.request.HTTPCookieProcessor(cookie))
            return self.call(opener,'resolve',{'id':rid,'decision':'approved'})[0]
        with concurrent.futures.ThreadPoolExecutor(2) as pool: codes=list(pool.map(approve,ids))
        self.assertEqual(sorted(codes),[200,400])
        self.assertEqual(next(g for g in self.state()['groups'] if g['id']==6)['count'],4)


if __name__=='__main__':unittest.main()
