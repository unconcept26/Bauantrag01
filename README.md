# Bauantrag OS V8 Live Ready

Diese Version ist für echtes Hosting vorbereitet. Sie ist nicht mehr als lokale HTML-Spielerei gedacht, sondern als deploy-fähige WebApp mit:

- serverseitigem Login
- SQLite-Datenbank
- Projektverwaltung
- Flächenmodul mit WoFlV / Nutzfläche
- Passwort ändern
- TXT-Export
- Health-Endpoint
- vorbereiteten Dateien für Docker und Render

## Standard-Zugang
- Benutzername: `admin`
- Passwort: `admin123!`

Nach dem ersten Login direkt unter **Einstellungen** ändern.

## Lokaler Test
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```
Dann öffnen:
`http://127.0.0.1:8000`

## Umgebungsvariablen
Siehe `.env.example`

Wichtig für Produktion:
- `SECRET_KEY` setzen
- `DEFAULT_ADMIN_PASSWORD` ändern
- Domain später über dein Hosting verbinden, z. B. `bauantrag.unconcept.de`

## Render / Railway / VPS
Du kannst die App auf einem Python-Host oder per Docker deployen.

### Startkommando ohne Docker
```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Healthcheck
`/health`

## Datenbank
Standardmäßig nutzt die App SQLite in:
`instance/bauantrag_v8_live.db`

Für den ersten Produktivstart ist das okay. Für ein Team-Setup später besser auf PostgreSQL wechseln.
