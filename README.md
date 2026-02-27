# Vikunja + MCP PoC

Lokaler Proof of Concept für:

- Vikunja (Self-hosted Kanban)
- PostgreSQL
- MCP-Adapter für Codex

## Voraussetzungen

- Docker + Docker Compose
- Python 3.12+

## Schnellstart

1. `.env` erstellen:

```bash
cp .env.example .env
```

2. Stack starten:

```bash
docker compose up -d --build
```

3. Admin-User und API-Token erzeugen:

```bash
python3 scripts/bootstrap_admin_and_token.py
```

4. MCP-Adapter mit Token neu starten:

```bash
docker compose up -d --build mcp-adapter
```

5. PoC verifizieren:

```bash
python3 scripts/verify_poc.py
```

6. MCP-Transport direkt testen:

```bash
python3 scripts/test_mcp_adapter.py
```

### Alternativ mit Makefile

```bash
make up
make bootstrap
make full-check
```

## MCP-Tools

Implementierte Tools im Adapter:

- `health`
- `list_projects`
- `create_project`
- `list_tasks`
- `create_task`
- `move_task`

## Codex MCP-Anbindung

MCP-Server in Codex registrieren:

```bash
codex mcp add vikunja --url http://localhost:8000/mcp
codex mcp list
```

Details prüfen:

```bash
codex mcp get vikunja
```

Hinweis: `http://localhost:8000/mcp` ist ein Streamable-HTTP-Endpunkt. Direkte Browser-GETs sind kein valider MCP-Test.

## GitHub Publish Readiness

Vor dem Publish:

```bash
make publish-check
```

Repo enthält für GitHub:

- CI Workflow: `.github/workflows/ci.yml`
- License: `LICENSE` (MIT)
- Contribution Guide: `CONTRIBUTING.md`
- Secrets-Schutz: `.env` ist in `.gitignore`

Optionaler schneller Ablauf:

```bash
git add .
git commit -m "Prepare release"
git push origin main
```

## Skill für andere Codex-Instanzen

Dieses Repo enthält ein Skill zum schnellen Setup:

- `skills/vikunja-poc-deploy`

Das Skill nutzen, wenn ein anderer Codex diese Umgebung in einem frischen Checkout schnell starten und validieren soll.

Lokale Installation in eine andere Codex-Instanz:

```bash
mkdir -p "$HOME/.codex/skills"
cp -r skills/vikunja-poc-deploy "$HOME/.codex/skills/"
```

Danach kann die andere Instanz das Skill über den Namen `vikunja-poc-deploy` verwenden.

## Nützliche Befehle

Logs:

```bash
docker compose logs -f vikunja mcp-adapter
```

Services stoppen:

```bash
docker compose down
```

Services inkl. Volumes entfernen:

```bash
docker compose down -v
```

## Sicherheit

- API-Token ist in `.env` und `.gitignore` ausgeschlossen.
- Keine Hardcoded Secrets im Code.
- `VIKUNJA_ENABLE_REGISTRATION=false` ist Standard.
