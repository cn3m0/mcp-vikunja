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

## MCP-Tools

Implementierte Tools im Adapter:

- `health`
- `list_projects`
- `create_project`
- `list_tasks`
- `create_task`
- `move_task`

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

