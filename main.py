from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path
import sqlite3, hashlib, secrets, json, os
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / 'instance'
INSTANCE_DIR.mkdir(exist_ok=True)
DB_PATH = Path(os.getenv('DATABASE_PATH', INSTANCE_DIR / 'bauantrag_v8_live.db'))
SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_hex(32))
APP_NAME = os.getenv('APP_NAME', 'Bauantrag OS V8 Live')
DEFAULT_ADMIN_USERNAME = os.getenv('DEFAULT_ADMIN_USERNAME', 'admin')
DEFAULT_ADMIN_PASSWORD = os.getenv('DEFAULT_ADMIN_PASSWORD', 'admin123!')
SESSION_HOURS = int(os.getenv('SESSION_HOURS', '12'))

app = FastAPI(title=APP_NAME)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=60*60*SESSION_HOURS, same_site='lax', https_only=False)
app.mount('/static', StaticFiles(directory=str(BASE_DIR / 'static')), name='static')
templates = Jinja2Templates(directory=str(BASE_DIR / 'templates'))


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def init_db():
    conn = db()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin'
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            client_name TEXT,
            state TEXT,
            city TEXT,
            procedure_type TEXT,
            project_type TEXT,
            status TEXT,
            total_site_area REAL DEFAULT 0,
            grz REAL DEFAULT 0,
            gfz REAL DEFAULT 0,
            bri REAL DEFAULT 0,
            required_parking INTEGER DEFAULT 0,
            provided_parking INTEGER DEFAULT 0,
            description_text TEXT DEFAULT '',
            operation_text TEXT DEFAULT '',
            change_text TEXT DEFAULT '',
            documents_json TEXT DEFAULT '[]',
            area_rows_json TEXT DEFAULT '[]',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    existing = cur.execute('SELECT id FROM users WHERE username = ?', (DEFAULT_ADMIN_USERNAME,)).fetchone()
    if not existing:
        cur.execute(
            'INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
            (DEFAULT_ADMIN_USERNAME, hash_password(DEFAULT_ADMIN_PASSWORD), 'admin')
        )
    conn.commit()
    conn.close()


def current_user(request: Request):
    user = request.session.get('user')
    return user


def require_user(request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401)
    return user


def parse_json(value: Optional[str], fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


def area_summary(rows):
    total = 0.0
    woflv_a = 0.0
    woflv_b = 0.0
    nutz_a = 0.0
    nutz_b = 0.0
    nutz_c = 0.0
    for row in rows:
        area = float(row.get('area') or 0)
        total += area
        model = row.get('model')
        subtype = row.get('subtype')
        if model == 'woflv':
            if subtype == 'a':
                woflv_a += area
            elif subtype == 'b':
                woflv_b += area
        elif model == 'nutz':
            if subtype == 'a':
                nutz_a += area
            elif subtype == 'b':
                nutz_b += area
            elif subtype == 'c':
                nutz_c += area
    return {
        'gesamtflaeche': total,
        'woflv_a': woflv_a,
        'woflv_b': woflv_b,
        'woflv_summe': woflv_a + woflv_b,
        'nutz_a': nutz_a,
        'nutz_b': nutz_b,
        'nutz_c': nutz_c,
        'nutz_summe': nutz_a + nutz_b + nutz_c,
    }


def project_with_meta(row):
    rows = parse_json(row['area_rows_json'], [])
    return {
        'project': dict(row),
        'areas': area_summary(rows),
        'documents': parse_json(row['documents_json'], []),
        'area_rows': rows,
    }


@app.on_event('startup')
def startup():
    init_db()


@app.get('/health')
def health():
    return JSONResponse({'ok': True, 'app': APP_NAME})


@app.get('/', response_class=HTMLResponse)
def root(request: Request):
    if current_user(request):
        return RedirectResponse('/dashboard', status_code=303)
    return RedirectResponse('/login', status_code=303)


@app.get('/login', response_class=HTMLResponse)
def login_page(request: Request):
    if current_user(request):
        return RedirectResponse('/dashboard', status_code=303)
    return templates.TemplateResponse('login.html', {'request': request, 'error': None, 'app_name': APP_NAME})


@app.post('/login', response_class=HTMLResponse)
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    conn = db()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    if not user or user['password_hash'] != hash_password(password):
        return templates.TemplateResponse('login.html', {'request': request, 'error': 'Zugangsdaten ungültig.', 'app_name': APP_NAME}, status_code=400)
    request.session['user'] = {'id': user['id'], 'username': user['username'], 'role': user['role']}
    return RedirectResponse('/dashboard', status_code=303)


@app.get('/logout')
def logout(request: Request):
    request.session.clear()
    return RedirectResponse('/login', status_code=303)


@app.get('/dashboard', response_class=HTMLResponse)
def dashboard(request: Request):
    user = require_user(request)
    conn = db()
    rows = conn.execute('SELECT * FROM projects ORDER BY updated_at DESC LIMIT 8').fetchall()
    all_rows = conn.execute('SELECT * FROM projects').fetchall()
    conn.close()
    projects = [project_with_meta(r) for r in rows]
    stats = {
        'gesamt': len(all_rows),
        'offen': len([r for r in all_rows if r['status'] in ('Entwurf', 'In Bearbeitung')]),
        'fertig': len([r for r in all_rows if r['status'] == 'Abgabereif']),
    }
    return templates.TemplateResponse('dashboard.html', {'request': request, 'user': user, 'projects': projects, 'stats': stats, 'app_name': APP_NAME})


@app.get('/projects', response_class=HTMLResponse)
def projects_page(request: Request):
    user = require_user(request)
    conn = db()
    rows = conn.execute('SELECT * FROM projects ORDER BY updated_at DESC').fetchall()
    conn.close()
    projects = [project_with_meta(r) for r in rows]
    return templates.TemplateResponse('projects.html', {'request': request, 'user': user, 'projects': projects, 'app_name': APP_NAME})


@app.get('/projects/new', response_class=HTMLResponse)
def projects_new(request: Request):
    user = require_user(request)
    project = {
        'id': '', 'name': '', 'client_name': '', 'state': 'NRW', 'city': '',
        'procedure_type': 'Bauantrag', 'project_type': 'Nutzungsänderung', 'status': 'Entwurf',
        'total_site_area': 0, 'grz': 0, 'gfz': 0, 'bri': 0, 'required_parking': 0, 'provided_parking': 0,
        'description_text': '', 'operation_text': '', 'change_text': ''
    }
    return templates.TemplateResponse('project_form.html', {
        'request': request, 'user': user, 'project': project,
        'documents': [], 'area_rows': [], 'app_name': APP_NAME
    })


@app.get('/projects/{project_id}', response_class=HTMLResponse)
def projects_edit(project_id: int, request: Request):
    user = require_user(request)
    conn = db()
    row = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404)
    meta = project_with_meta(row)
    return templates.TemplateResponse('project_form.html', {
        'request': request, 'user': user, 'project': dict(row),
        'documents': meta['documents'], 'area_rows': meta['area_rows'], 'app_name': APP_NAME
    })


@app.post('/projects/save')
def projects_save(
    request: Request,
    project_id: Optional[int] = Form(None),
    name: str = Form(...),
    client_name: str = Form(''),
    state: str = Form('NRW'),
    city: str = Form(''),
    procedure_type: str = Form('Bauantrag'),
    project_type: str = Form('Nutzungsänderung'),
    status: str = Form('Entwurf'),
    total_site_area: float = Form(0),
    grz: float = Form(0),
    gfz: float = Form(0),
    bri: float = Form(0),
    required_parking: int = Form(0),
    provided_parking: int = Form(0),
    description_text: str = Form(''),
    operation_text: str = Form(''),
    change_text: str = Form(''),
    documents_json: str = Form('[]'),
    area_rows_json: str = Form('[]')
):
    require_user(request)
    conn = db()
    cur = conn.cursor()
    if project_id:
        cur.execute('''
            UPDATE projects SET
                name=?, client_name=?, state=?, city=?, procedure_type=?, project_type=?, status=?,
                total_site_area=?, grz=?, gfz=?, bri=?, required_parking=?, provided_parking=?,
                description_text=?, operation_text=?, change_text=?, documents_json=?, area_rows_json=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        ''', (
            name, client_name, state, city, procedure_type, project_type, status,
            total_site_area, grz, gfz, bri, required_parking, provided_parking,
            description_text, operation_text, change_text, documents_json, area_rows_json,
            project_id
        ))
        target_id = project_id
    else:
        cur.execute('''
            INSERT INTO projects (
                name, client_name, state, city, procedure_type, project_type, status,
                total_site_area, grz, gfz, bri, required_parking, provided_parking,
                description_text, operation_text, change_text, documents_json, area_rows_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            name, client_name, state, city, procedure_type, project_type, status,
            total_site_area, grz, gfz, bri, required_parking, provided_parking,
            description_text, operation_text, change_text, documents_json, area_rows_json
        ))
        target_id = cur.lastrowid
    conn.commit()
    conn.close()
    return RedirectResponse(f'/projects/{target_id}', status_code=303)


@app.get('/projects/{project_id}/delete')
def projects_delete(project_id: int, request: Request):
    require_user(request)
    conn = db()
    conn.execute('DELETE FROM projects WHERE id = ?', (project_id,))
    conn.commit()
    conn.close()
    return RedirectResponse('/projects', status_code=303)


@app.get('/projects/{project_id}/export.txt')
def export_project(project_id: int, request: Request):
    require_user(request)
    conn = db()
    row = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404)
    meta = project_with_meta(row)
    p = dict(row)
    a = meta['areas']
    docs = meta['documents']
    area_rows = meta['area_rows']

    lines = []
    lines.append(f"{APP_NAME} – Projekt-Export")
    lines.append('=' * 58)
    lines.append(f"Projekt: {p['name']}")
    lines.append(f"Bauherr: {p['client_name']}")
    lines.append(f"Ort: {p['city']} / {p['state']}")
    lines.append(f"Verfahren: {p['procedure_type']}")
    lines.append(f"Vorhaben: {p['project_type']}")
    lines.append(f"Status: {p['status']}")
    lines.append('')
    lines.append('KENNZAHLEN')
    lines.append('-' * 58)
    lines.append(f"Grundstücksfläche: {p['total_site_area']:.2f} m²")
    lines.append(f"GRZ: {p['grz']:.2f}")
    lines.append(f"GFZ: {p['gfz']:.2f}")
    lines.append(f"BRI: {p['bri']:.2f} m³")
    lines.append(f"Stellplätze Soll/Ist: {p['required_parking']} / {p['provided_parking']}")
    lines.append('')
    lines.append('FLÄCHEN')
    lines.append('-' * 58)
    lines.append(f"Gesamtfläche: {a['gesamtflaeche']:.2f} m²")
    lines.append(f"WoFlV gesamt: {a['woflv_summe']:.2f} m²")
    lines.append(f"  Wohnfläche (a): {a['woflv_a']:.2f} m²")
    lines.append(f"  Nicht-Wohnfläche (b): {a['woflv_b']:.2f} m²")
    lines.append(f"Nutzfläche gesamt: {a['nutz_summe']:.2f} m²")
    lines.append(f"  Nutzfläche (a): {a['nutz_a']:.2f} m²")
    lines.append(f"  Verkehrsfläche (b): {a['nutz_b']:.2f} m²")
    lines.append(f"  Technikfläche (c): {a['nutz_c']:.2f} m²")
    lines.append('')
    lines.append('FLÄCHENLISTE')
    lines.append('-' * 58)
    for row in area_rows:
        lines.append(f"{row.get('level','')} | {row.get('name','')} | {row.get('area',0)} m² | {row.get('model','')} | {row.get('subtype','')}")
    lines.append('')
    lines.append('UNTERLAGEN')
    lines.append('-' * 58)
    for doc in docs:
        lines.append(f"- {doc.get('name','')} [{doc.get('status','offen')}]")
    lines.append('')
    lines.append('BAUBESCHREIBUNG')
    lines.append('-' * 58)
    lines.append(p['description_text'] or '-')
    lines.append('')
    lines.append('BETRIEBSBESCHREIBUNG')
    lines.append('-' * 58)
    lines.append(p['operation_text'] or '-')
    lines.append('')
    lines.append('NUTZUNGSÄNDERUNG')
    lines.append('-' * 58)
    lines.append(p['change_text'] or '-')

    return PlainTextResponse('\n'.join(lines), media_type='text/plain; charset=utf-8', headers={
        'Content-Disposition': f'attachment; filename="projekt_{project_id}.txt"'
    })


@app.get('/settings', response_class=HTMLResponse)
def settings_page(request: Request):
    user = require_user(request)
    return templates.TemplateResponse('settings.html', {'request': request, 'user': user, 'message': None, 'error': None, 'app_name': APP_NAME})


@app.post('/settings/password', response_class=HTMLResponse)
def settings_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...)
):
    user = require_user(request)
    conn = db()
    row = conn.execute('SELECT * FROM users WHERE id = ?', (user['id'],)).fetchone()
    if not row or row['password_hash'] != hash_password(current_password):
        conn.close()
        return templates.TemplateResponse('settings.html', {'request': request, 'user': user, 'message': None, 'error': 'Aktuelles Passwort ist nicht korrekt.', 'app_name': APP_NAME}, status_code=400)
    if new_password != confirm_password:
        conn.close()
        return templates.TemplateResponse('settings.html', {'request': request, 'user': user, 'message': None, 'error': 'Neue Passwörter stimmen nicht überein.', 'app_name': APP_NAME}, status_code=400)
    conn.execute('UPDATE users SET password_hash = ? WHERE id = ?', (hash_password(new_password), user['id']))
    conn.commit()
    conn.close()
    return templates.TemplateResponse('settings.html', {'request': request, 'user': user, 'message': 'Passwort erfolgreich geändert.', 'error': None, 'app_name': APP_NAME})
