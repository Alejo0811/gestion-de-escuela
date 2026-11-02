"""Escuela de tenis: servidor local, API y persistencia sin dependencias externas."""
import argparse
import datetime as dt
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent
DB_PATH = os.environ.get('TENNIS_DB', str(ROOT / 'data' / 'tennis.sqlite3'))
DAYS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']


class Invalid(Exception):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def connect():
    db = sqlite3.connect(DB_PATH, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db


def rows(db, sql, args=()):
    return [dict(r) for r in db.execute(sql, args)]


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 160000).hex()


def initialize(seed=True):
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
          role TEXT NOT NULL CHECK(role IN ('manager','client')), salt TEXT NOT NULL, password TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tokens(token TEXT PRIMARY KEY, user_id INTEGER REFERENCES users(id), expires TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS catalogs(id INTEGER PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL, value REAL NOT NULL DEFAULT 0,
          UNIQUE(kind,name));
        CREATE TABLE IF NOT EXISTS students(id INTEGER PRIMARY KEY, name TEXT NOT NULL, birth TEXT NOT NULL,
          level_id INTEGER REFERENCES catalogs(id), guardian_id INTEGER REFERENCES users(id), user_id INTEGER REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS groups(id INTEGER PRIMARY KEY, name TEXT NOT NULL, level_id INTEGER NOT NULL REFERENCES catalogs(id),
          coach_id INTEGER NOT NULL REFERENCES catalogs(id), court_id INTEGER NOT NULL REFERENCES catalogs(id),
          tariff_id INTEGER NOT NULL REFERENCES catalogs(id), days TEXT NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL,
          starts_on TEXT NOT NULL, ends_on TEXT NOT NULL, capacity INTEGER NOT NULL CHECK(capacity>0),
          min_age INTEGER NOT NULL, max_age INTEGER NOT NULL, cost REAL NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'active');
        CREATE TABLE IF NOT EXISTS memberships(student_id INTEGER REFERENCES students(id), group_id INTEGER REFERENCES groups(id),
          PRIMARY KEY(student_id,group_id));
        CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id),
          kind TEXT NOT NULL, source_id INTEGER REFERENCES groups(id), target_id INTEGER REFERENCES groups(id), note TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'pending', created TEXT NOT NULL, resolved TEXT);
        CREATE TABLE IF NOT EXISTS attendance(student_id INTEGER REFERENCES students(id), group_id INTEGER REFERENCES groups(id),
          date TEXT NOT NULL, status TEXT NOT NULL, PRIMARY KEY(student_id,group_id,date));
        CREATE TABLE IF NOT EXISTS makeups(id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id),
          group_id INTEGER NOT NULL REFERENCES groups(id), missed_date TEXT NOT NULL, recovery_date TEXT, status TEXT NOT NULL DEFAULT 'pending',
          UNIQUE(student_id,group_id,missed_date));
        CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id),
          group_id INTEGER NOT NULL REFERENCES groups(id), month TEXT NOT NULL, amount REAL NOT NULL, status TEXT NOT NULL,
          UNIQUE(student_id,group_id,month));
        CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY, group_id INTEGER REFERENCES groups(id),
          at TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL);
        ''')
        if seed and not db.execute('SELECT 1 FROM users').fetchone():
            for name, email, role in [('Ana Gestora', 'gestor@demo.local', 'manager'), ('María García', 'familia@demo.local', 'client')]:
                salt = secrets.token_hex(16)
                db.execute('INSERT INTO users(name,email,role,salt,password) VALUES(?,?,?,?,?)',
                           (name, email, role, salt, password_hash('TenisDemo2026!', salt)))
            entries = [('level','Iniciación',0),('level','Intermedio',0),('level','Avanzado',0),
                       ('coach','Carlos Medina',0),('coach','Lucía Torres',0),('coach','Pablo Ruiz',0),
                       ('court','Pista 1 · Tierra batida',0),('court','Pista 2 · Tierra batida',0),('court','Pista 3 · Dura',0),
                       ('tariff','Escuela · 2 días',65),('tariff','Competición',95),('tariff','Mini tenis',45)]
            db.executemany('INSERT INTO catalogs(kind,name,value) VALUES(?,?,?)', entries)
            today = dt.date.today()
            start = today.replace(day=1).isoformat()
            end = (today + dt.timedelta(days=300)).isoformat()
            specs = [('Pequeños aces',1,4,7,12,[0,2],'16:00','17:00',7,5,9,180),
                     ('La próxima generación',2,5,8,10,[1,3],'17:00','18:30',7,10,15,220),
                     ('Equipo de competición',3,6,9,11,[0,2,4],'18:00','19:30',7,14,20,420),
                     ('Tenis a tu ritmo',1,4,7,10,[1,3],'19:00','20:00',8,18,80,240),
                     ('Sábado en pista',2,5,8,10,[5],'10:00','11:30',7,10,17,160),
                     ('Primer servicio',1,6,9,12,[1,3],'16:00','17:00',7,5,9,160)]
            for n,l,c,p,t,d,s,e,cap,amin,amax,cost in specs:
                db.execute('INSERT INTO groups(name,level_id,coach_id,court_id,tariff_id,days,start,end,starts_on,ends_on,capacity,min_age,max_age,cost) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                           (n,l,c,p,t,json.dumps(d),s,e,start,end,cap,amin,amax,cost))
            names = ['Lucas García','Sofía García','Mateo López','Valeria Martín','Leo Sánchez','Emma Díaz','Hugo Romero',
                     'Daniela Alonso','Martín Navarro','Julia Moreno','Adrián Muñoz','Paula Ortega','Alejandro Gil','Carla Vega',
                     'Diego Ramos','Alba Castro','Mario Santos','Olivia León','Nicolás Cruz','Lara Molina','Marcos Vidal','Celia Ríos',
                     'Álvaro Costa','Inés Soler','Javier Cano','Clara Peña','David Soto','Elena Blanco','Pablo Flores','Sara Bravo']
            group_assignments = [1,2]+[1]*5+[2]*6+[3]*6+[4]*3+[5]*5+[6]*3
            for i, (name, gid) in enumerate(zip(names,group_assignments),1):
                age = 7 if gid in (1,6) else 12 if gid in (2,5) else 16 if gid==3 else 30
                level = 1 if gid in (1,4,6) else 3 if gid==3 else 2
                db.execute('INSERT INTO students(name,birth,level_id,guardian_id) VALUES(?,?,?,?)',
                           (name,f'{today.year-age}-02-15',level,2 if i<=2 else None))
                db.execute('INSERT INTO memberships VALUES(?,?)',(i,gid))
                db.execute('INSERT INTO payments(student_id,group_id,month,amount,status) SELECT ?,id,?,(SELECT value FROM catalogs WHERE id=tariff_id),? FROM groups WHERE id=?',
                           (i,today.strftime('%Y-%m'),'pending' if i==2 else 'paid',gid))
            for gid in range(1,7):
                audit(db,gid,'Sistema','Grupo creado · temporada actual')


def audit(db, gid, actor, action):
    db.execute('INSERT INTO history(group_id,at,actor,action) VALUES(?,?,?,?)',
               (gid,dt.datetime.now(dt.timezone.utc).isoformat(),actor,action))


def owns(db, user, sid):
    return user['role']=='manager' or bool(db.execute('SELECT 1 FROM students WHERE id=? AND (guardian_id=? OR user_id=?)', (sid,user['id'],user['id'])).fetchone())


def get_group(db, gid):
    g = db.execute('SELECT * FROM groups WHERE id=?',(gid,)).fetchone()
    require(g is not None,'Grupo inexistente')
    return dict(g)


def occurs(g, date):
    return g['starts_on'] <= date.isoformat() <= g['ends_on'] and date.weekday() in json.loads(g['days'])


def overlaps(a,b):
    lo,hi = max(a['starts_on'],b['starts_on']), min(a['ends_on'],b['ends_on'])
    if lo>hi or not (a['start']<b['end'] and b['start']<a['end']):
        return False
    common = set(json.loads(a['days'])) & set(json.loads(b['days']))
    first = dt.date.fromisoformat(lo)
    return any((first+dt.timedelta(days=i)).isoformat()<=hi and (first+dt.timedelta(days=i)).weekday() in common for i in range(7))


def group_conflicts(db, g, exclude=None):
    conflicts=[]
    for other in rows(db,"SELECT * FROM groups WHERE status='active'"):
        if other['id']==exclude or not overlaps(g,other):
            continue
        shared=[]
        if g['coach_id']==other['coach_id']: shared.append('entrenador')
        if g['court_id']==other['court_id']: shared.append('pista')
        if exclude and db.execute('SELECT 1 FROM memberships a JOIN memberships b ON a.student_id=b.student_id WHERE a.group_id=? AND b.group_id=?',(exclude,other['id'])).fetchone():
            shared.append('alumno')
        if shared: conflicts.append(f"{other['name']} ({', '.join(shared)})")
    return conflicts


def check_member(db,sid,gid,source=None):
    student=db.execute('SELECT * FROM students WHERE id=?',(sid,)).fetchone()
    require(student is not None,'Alumno inexistente')
    g=get_group(db,gid)
    require(g['status']=='active','El grupo está cerrado')
    require(not db.execute('SELECT 1 FROM memberships WHERE student_id=? AND group_id=?',(sid,gid)).fetchone(),'El alumno ya pertenece al grupo')
    require(db.execute('SELECT COUNT(*) FROM memberships WHERE group_id=?',(gid,)).fetchone()[0]<g['capacity'],'Grupo completo; la solicitud permanece en lista de espera')
    birth=dt.date.fromisoformat(student['birth']); today=dt.date.today()
    age=today.year-birth.year-((today.month,today.day)<(birth.month,birth.day))
    require(g['min_age']<=age<=g['max_age'],'La edad no corresponde al grupo')
    require(student['level_id']==g['level_id'],'El nivel del alumno no corresponde al grupo')
    for old in rows(db,'SELECT g.* FROM groups g JOIN memberships m ON m.group_id=g.id WHERE m.student_id=? AND g.status=\'active\'',(sid,)):
        require(old['id']==source or not overlaps(g,old),f"Incompatibilidad horaria con {old['name']}")


def enroll(db,sid,gid,actor,source=None):
    check_member(db,sid,gid,source)
    if source:
        require(db.execute('DELETE FROM memberships WHERE student_id=? AND group_id=?',(sid,source)).rowcount==1,'El alumno ya no pertenece al grupo de origen')
        audit(db,source,actor,f'Alumno #{sid} trasladado al grupo #{gid}')
    db.execute('INSERT INTO memberships VALUES(?,?)',(sid,gid))
    audit(db,gid,actor,f'Alumno #{sid} incorporado'+(f' desde grupo #{source}' if source else ''))


def state(db,user):
    manager=user['role']=='manager'
    students=rows(db,'SELECT * FROM students'+('' if manager else ' WHERE guardian_id=? OR user_id=?'),() if manager else (user['id'],user['id']))
    ids=[s['id'] for s in students]
    placeholder=','.join('?' for _ in ids) or 'NULL'
    def scoped(table): return rows(db,f'SELECT * FROM {table}'+('' if manager else f' WHERE student_id IN ({placeholder})'),() if manager else ids)
    groups=rows(db,'SELECT * FROM groups')
    for g in groups:
        g['count']=db.execute('SELECT COUNT(*) FROM memberships WHERE group_id=?',(g['id'],)).fetchone()[0]
        g['days']=json.loads(g['days'])
        if not manager:
            g.pop('cost', None)
    return dict(user={k:user[k] for k in ('id','name','role')}, catalogs=rows(db,'SELECT * FROM catalogs'),students=students,
                tutors=rows(db,"SELECT id,name,email FROM users WHERE role='client'") if manager else [],groups=groups,
                memberships=scoped('memberships'),requests=scoped('requests'),attendance=scoped('attendance'),
                makeups=scoped('makeups'),payments=scoped('payments'),history=rows(db,'SELECT * FROM history ORDER BY id DESC') if manager else [])


def catalog_ref(db, value, kind):
    require(db.execute('SELECT 1 FROM catalogs WHERE id=? AND kind=?',(value,kind)).fetchone(),f'{kind}: selección inválida')
    return int(value)


def mutate(db,user,path,p):
    manager=user['role']=='manager'; actor=user['name']
    require(manager or path=='requests','Acción reservada al gestor')
    if path=='catalog':
        kind=p['kind']; require(kind in ('coach','court','tariff','level'),'Tipo inválido')
        name=p['name'].strip(); value=float(p.get('value',0)); require(name and 0<=value<=100000,'Nombre o importe inválido')
        if p.get('id'):
            db.execute('UPDATE catalogs SET name=?,value=? WHERE id=? AND kind=?',(name,value,p['id'],kind))
        else: db.execute('INSERT INTO catalogs(kind,name,value) VALUES(?,?,?)',(kind,name,value))
    elif path=='tutors':
        salt=secrets.token_hex(16); password=p.get('password','')
        require(p['name'].strip() and '@' in p['email'],'Nombre y correo obligatorios')
        if p.get('id'):
            require(db.execute("SELECT 1 FROM users WHERE id=? AND role='client'",(p['id'],)).fetchone(),'Cuenta inexistente')
            db.execute('UPDATE users SET name=?,email=? WHERE id=?',(p['name'].strip(),p['email'].strip().lower(),p['id']))
            if password:
                require(len(password)>=10,'La contraseña debe tener al menos 10 caracteres')
                db.execute('UPDATE users SET salt=?,password=? WHERE id=?',(salt,password_hash(password,salt),p['id']))
                db.execute('DELETE FROM tokens WHERE user_id=?',(p['id'],))
        else:
            require(len(password)>=10,'La contraseña debe tener al menos 10 caracteres')
            db.execute('INSERT INTO users(name,email,role,salt,password) VALUES(?,?,\'client\',?,?)',(p['name'].strip(),p['email'].strip().lower(),salt,password_hash(password,salt)))
    elif path=='students':
        birth=dt.date.fromisoformat(p['birth']); require(birth<=dt.date.today(),'Fecha de nacimiento futura')
        require(p['name'].strip(),'Nombre obligatorio'); catalog_ref(db,p['level_id'],'level')
        for key in ('guardian_id','user_id'):
            if p.get(key): require(db.execute("SELECT 1 FROM users WHERE id=? AND role='client'",(p[key],)).fetchone(),'Cuenta de cliente inválida')
        values=(p['name'].strip(),birth.isoformat(),p['level_id'],p.get('guardian_id') or None,p.get('user_id') or None)
        if p.get('id'): db.execute('UPDATE students SET name=?,birth=?,level_id=?,guardian_id=?,user_id=? WHERE id=?',values+(p['id'],))
        else: db.execute('INSERT INTO students(name,birth,level_id,guardian_id,user_id) VALUES(?,?,?,?,?)',values)
    elif path=='groups':
        gid=p.get('id'); name=p['name'].strip(); require(name,'Nombre obligatorio')
        g={'name':name}
        for field,kind in [('level_id','level'),('coach_id','coach'),('court_id','court'),('tariff_id','tariff')]: g[field]=catalog_ref(db,p[field],kind)
        days=sorted(set(int(x) for x in p['days'])); require(days and all(0<=x<=6 for x in days),'Selecciona días válidos')
        g.update(days=json.dumps(days),start=p['start'],end=p['end'],starts_on=p['starts_on'],ends_on=p['ends_on'],capacity=int(p['capacity']),min_age=int(p['min_age']),max_age=int(p['max_age']),cost=float(p['cost']))
        dt.time.fromisoformat(g['start']); dt.time.fromisoformat(g['end']); dt.date.fromisoformat(g['starts_on']); dt.date.fromisoformat(g['ends_on'])
        require(g['start']<g['end'] and g['starts_on']<=g['ends_on'],'Intervalo de fechas u horas inválido')
        require(1<=g['capacity']<=100 and 0<=g['min_age']<=g['max_age']<=120 and 0<=g['cost']<=1000000,'Capacidad, edades o coste inválidos')
        old=get_group(db,gid) if gid else None
        if old:
            require(g['capacity']>=db.execute('SELECT COUNT(*) FROM memberships WHERE group_id=?',(gid,)).fetchone()[0],'La capacidad es inferior al número de alumnos')
        conflicts=group_conflicts(db,g,gid) if not old or old['status']=='active' else []
        require(not conflicts,'Incompatibilidad horaria: '+ '; '.join(conflicts))
        fields=list(g)
        if gid:
            db.execute('UPDATE groups SET '+','.join(f'{k}=?' for k in fields)+' WHERE id=?',tuple(g.values())+(gid,))
            audit(db,gid,actor,'Configuración modificada: '+', '.join(k for k in fields if str(old[k])!=str(g[k])))
        else:
            cur=db.execute('INSERT INTO groups('+','.join(fields)+') VALUES('+','.join('?' for _ in fields)+')',tuple(g.values()))
            audit(db,cur.lastrowid,actor,'Grupo recurrente creado'+(f" · duplicado de #{p['duplicate_of']}" if p.get('duplicate_of') else ''))
    elif path=='close':
        get_group(db,p['group_id'])
        db.execute("UPDATE groups SET status='closed' WHERE id=?",(p['group_id'],)); audit(db,p['group_id'],actor,'Grupo cerrado; se conserva el historial')
    elif path=='membership':
        sid,gid=int(p['student_id']),int(p['group_id'])
        if p['action']=='remove':
            require(db.execute('DELETE FROM memberships WHERE student_id=? AND group_id=?',(sid,gid)).rowcount,'El alumno no pertenece al grupo')
            audit(db,gid,actor,f'Alumno #{sid} dado de baja')
        else: enroll(db,sid,gid,actor,p.get('source_id'))
    elif path=='requests':
        sid=int(p['student_id']); require(owns(db,user,sid),'Alumno fuera de tu cuenta')
        kind=p['kind']; require(kind in ('alta','cambio','baja'),'Solicitud inválida')
        source=p.get('source_id') or None; target=p.get('target_id') or None
        if kind=='alta': source=None
        if kind in ('cambio','baja'): require(db.execute('SELECT 1 FROM memberships WHERE student_id=? AND group_id=?',(sid,source)).fetchone(),'Grupo de origen inválido')
        if kind in ('alta','cambio'):
            g=get_group(db,target); require(g['status']=='active','Grupo cerrado'); require(target!=source,'Elige otro grupo')
            require(not db.execute('SELECT 1 FROM memberships WHERE student_id=? AND group_id=?',(sid,target)).fetchone(),'Ya pertenece a este grupo')
        else: target=None
        require(not db.execute("SELECT 1 FROM requests WHERE student_id=? AND status='pending' AND kind=? AND source_id IS ? AND target_id IS ?",(sid,kind,source,target)).fetchone(),'Ya existe una solicitud pendiente')
        db.execute('INSERT INTO requests(student_id,kind,source_id,target_id,note,created) VALUES(?,?,?,?,?,?)',(sid,kind,source,target,str(p.get('note',''))[:1000],dt.datetime.now(dt.timezone.utc).isoformat()))
        audit(db,target or source,actor,f'Solicitud de {kind} para alumno #{sid} pendiente de aprobación')
    elif path=='resolve':
        r=db.execute('SELECT * FROM requests WHERE id=?',(p['id'],)).fetchone(); require(r and r['status']=='pending','Solicitud ya resuelta o inexistente')
        approved=p['decision']=='approved'; require(p['decision'] in ('approved','rejected'),'Decisión inválida')
        if approved:
            if r['kind']=='baja':
                require(db.execute('DELETE FROM memberships WHERE student_id=? AND group_id=?',(r['student_id'],r['source_id'])).rowcount,'El alumno ya no pertenece al grupo')
            else: enroll(db,r['student_id'],r['target_id'],actor,r['source_id'] if r['kind']=='cambio' else None)
        db.execute('UPDATE requests SET status=?,resolved=? WHERE id=?',(p['decision'],dt.datetime.now(dt.timezone.utc).isoformat(),p['id']))
        audit(db,r['target_id'] or r['source_id'],actor,f"Solicitud #{r['id']} de {r['kind']}: {'aprobada' if approved else 'rechazada'}")
    elif path=='attendance':
        sid,gid=int(p['student_id']),int(p['group_id']); date=dt.date.fromisoformat(p['date']); g=get_group(db,gid)
        require(db.execute('SELECT 1 FROM memberships WHERE student_id=? AND group_id=?',(sid,gid)).fetchone(),'Alumno no inscrito')
        require(occurs(g,date) and date<=dt.date.today(),'La fecha debe ser una sesión celebrada del grupo')
        require(p['status'] in ('present','absent','excused'),'Asistencia inválida')
        db.execute('INSERT INTO attendance VALUES(?,?,?,?) ON CONFLICT(student_id,group_id,date) DO UPDATE SET status=excluded.status',(sid,gid,p['date'],p['status']))
        if p['status'] in ('absent','excused'):
            db.execute('INSERT OR IGNORE INTO makeups(student_id,group_id,missed_date) VALUES(?,?,?)',(sid,gid,p['date']))
        else: db.execute("DELETE FROM makeups WHERE student_id=? AND group_id=? AND missed_date=? AND status='pending'",(sid,gid,p['date']))
        audit(db,gid,actor,f"Asistencia alumno #{sid} · {p['date']}: {p['status']}")
    elif path=='makeups':
        r=db.execute('SELECT * FROM makeups WHERE id=?',(p['id'],)).fetchone(); require(r is not None,'Recuperación inexistente')
        date=dt.date.fromisoformat(p['recovery_date']); g=get_group(db,r['group_id'])
        require(g['status']=='active' and occurs(g,date) and date>dt.date.fromisoformat(r['missed_date']),'Selecciona una sesión posterior dentro de la temporada')
        status=p.get('status','scheduled'); require(status in ('scheduled','done'),'Estado inválido')
        require(status!='done' or date<=dt.date.today(),'No se puede completar una recuperación futura')
        db.execute('UPDATE makeups SET recovery_date=?,status=? WHERE id=?',(date.isoformat(),status,p['id']))
        audit(db,r['group_id'],actor,f"Recuperación #{r['id']}: {date.isoformat()} · {status}")
    elif path=='bill':
        month=p['month']; dt.datetime.strptime(month,'%Y-%m'); created=0
        for m in rows(db,"SELECT m.*,c.value,g.starts_on,g.ends_on FROM memberships m JOIN groups g ON g.id=m.group_id JOIN catalogs c ON c.id=g.tariff_id WHERE g.status='active'"):
            if m['starts_on'][:7]<=month<=m['ends_on'][:7]:
                created+=db.execute("INSERT OR IGNORE INTO payments(student_id,group_id,month,amount,status) VALUES(?,?,?,?,'pending')",(m['student_id'],m['group_id'],month,m['value'])).rowcount
        audit(db,None,actor,f'Cuotas de {month}: {created} recibos generados')
    elif path=='payment':
        require(p['status'] in ('paid','pending'),'Estado inválido')
        pay=db.execute('SELECT * FROM payments WHERE id=?',(p['id'],)).fetchone(); require(pay is not None,'Pago inexistente')
        db.execute('UPDATE payments SET status=? WHERE id=?',(p['status'],p['id']))
        audit(db,pay['group_id'],actor,f"Recibo #{p['id']}: {p['status']}")
    else: raise Invalid('Operación desconocida')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def send_json(self, value, status=200, cookie=None):
        data=json.dumps(value,ensure_ascii=False).encode()
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff')
        if cookie: self.send_header('Set-Cookie',cookie)
        self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)

    def user(self, db):
        jar=cookies.SimpleCookie()
        try: jar.load(self.headers.get('Cookie',''))
        except cookies.CookieError: return None
        token=jar.get('tennis_session')
        return db.execute('SELECT u.* FROM users u JOIN tokens t ON t.user_id=u.id WHERE t.token=? AND t.expires>?',
                          (token.value if token else '',dt.datetime.now(dt.timezone.utc).isoformat())).fetchone()

    def do_GET(self):
        if self.path=='/api/state':
            with connect() as db:
                # Every device receives a consistent snapshot, including during a save.
                db.execute('BEGIN')
                user=self.user(db)
                return self.send_json(state(db,user) if user else {'error':'Inicia sesión'},200 if user else 401)
        files={'/':'index.html','/app.js':'app.js','/sync.js':'sync.js','/style.css':'style.css'}
        name=files.get(self.path.split('?')[0])
        if not name: return self.send_json({'error':'No encontrado'},404)
        data=(ROOT/'web'/name).read_bytes(); self.send_response(200)
        self.send_header('Content-Type',{'html':'text/html; charset=utf-8','css':'text/css','js':'text/javascript'}[name.split('.')[-1]])
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Cache-Control','no-cache')
        self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)

    def do_POST(self):
        try:
            # Same-origin JSON requests only. SameSite cookie adds a second CSRF boundary.
            require(self.headers.get('Content-Type','').split(';')[0]=='application/json','Se requiere JSON')
            require(self.headers.get('Sec-Fetch-Site','same-origin') not in ('cross-site',),'Origen no permitido')
            origin=self.headers.get('Origin')
            require(not origin or origin in ('http://'+self.headers.get('Host',''),'https://'+self.headers.get('Host','')),'Origen no permitido')
            length=int(self.headers.get('Content-Length',0)); require(0<length<=65536,'Tamaño de petición inválido')
            p=json.loads(self.rfile.read(length))
            with connect() as db:
                if self.path=='/api/login':
                    u=db.execute('SELECT * FROM users WHERE email=?',(str(p.get('email','')).strip().lower(),)).fetchone()
                    if not u or not hmac.compare_digest(password_hash(str(p.get('password','')),u['salt']),u['password']):
                        return self.send_json({'error':'Correo o contraseña incorrectos'},401)
                    token=secrets.token_urlsafe(32)
                    db.execute('DELETE FROM tokens WHERE expires<?',(dt.datetime.now(dt.timezone.utc).isoformat(),))
                    db.execute('INSERT INTO tokens VALUES(?,?,?)',(token,u['id'],(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=12)).isoformat()))
                    return self.send_json({'ok':True},cookie=f'tennis_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200')
                user=self.user(db)
                if not user: return self.send_json({'error':'Inicia sesión'},401)
                if self.path=='/api/logout':
                    jar=cookies.SimpleCookie(self.headers.get('Cookie','')); db.execute('DELETE FROM tokens WHERE token=?',(jar['tennis_session'].value,))
                    return self.send_json({'ok':True},cookie='tennis_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
                # Serialize capacity checks and their mutations across concurrent requests.
                db.execute('BEGIN IMMEDIATE')
                mutate(db,user,self.path.removeprefix('/api/'),p)
                result=state(db,user)
            self.send_json(result)
        except (Invalid,ValueError,KeyError,TypeError,sqlite3.IntegrityError) as e:
            message='El dato ya existe o está vinculado a otro registro' if isinstance(e,sqlite3.IntegrityError) else str(e)
            self.send_json({'error':message},400)
        except Exception:
            import traceback
            traceback.print_exc()
            self.send_json({'error':'Error interno del servidor'},500)


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=8000); parser.add_argument('--host',default='127.0.0.1'); parser.add_argument('--no-seed',action='store_true')
    args=parser.parse_args(); initialize(not args.no_seed)
    http=ThreadingHTTPServer((args.host,args.port),Handler)
    print(f'Escuela de tenis · puerto {http.server_port}',flush=True)
    http.serve_forever()
