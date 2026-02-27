# PLAN.md

## Dokumentstatus

- Erstellt am: 2026-02-27
- Letzte Aktualisierung: 2026-02-27
- Quelle: `PROJECT.md`
- Zweck: Ausgangslage dokumentieren und entscheidungsfertigen Umsetzungsplan bereitstellen

## 0. Ausgangspunkt (Baseline aus PROJECT.md)

- Ziel: Self-hosted Kanban mit AI-Integration (Codex) als PoC.
- Zielsystem:
- Vikunja (Kanban)
- PostgreSQL (Persistenz)
- MCP-Server (Model Context Protocol Adapter)
- Lokale Codex-Integration
- Betriebsmodell: lokal via Docker Compose.
- Gewünschte Fähigkeiten für Codex:
- Boards lesen
- Tasks erstellen
- Tasks verschieben
- Status auswerten
- Zusammenfassungen generieren
- Startstatus:
- Anforderungen sind definiert.
- Umsetzung ist noch nicht begonnen.

## 1. Ziel und Scope

### In Scope

- Docker-Compose-Setup mit `postgres:16-alpine` und `vikunja/vikunja:latest`
- Konfiguration über `.env` (DB, JWT Secret, Public URL, Token)
- Initialisierung mit Admin-User und API-Token
- Lokaler MCP-Adapter mit den vereinbarten Tools
- Verifikation der Kern-Use-Cases Ende-zu-Ende

### Out of Scope (vorerst)

- Nginx Reverse Proxy
- HTTPS via Let's Encrypt
- OAuth Integration
- Webhook-Automatisierung
- Task Digest Generator als separates Produktfeature

## 2. Architektur und Komponenten

### Komponenten

- PostgreSQL:
- Persistente Speicherung aller Vikunja-Daten
- Healthcheck muss aktiv sein
- Vikunja Backend/API:
- Zugriff für UI und MCP-Adapter
- Authentifizierung via Bearer-Token
- Vikunja Web UI:
- Manuelle Sichtprüfung und Betriebsoberfläche
- MCP-Adapter-Service:
- Kapselt Vikunja-API als MCP-Tools
- Minimales, nachvollziehbares Logging
- Codex:
- Nutzt MCP-Tools für Lese-/Schreibzugriffe und Zusammenfassungen

### Netzwerk und Erreichbarkeit

- Alle Container im selben Docker-Netz
- UI/API erreichbar unter `http://localhost:3456`
- MCP-Service greift intern über Docker-Netz auf Vikunja zu

## 3. Umsetzungsphasen mit Deliverables

### Phase 1: Infrastruktur

- Aufgaben:
- Docker Compose definieren
- PostgreSQL und Vikunja anbinden
- Persistente Volumes konfigurieren
- Restart-Policies setzen
- DB-Healthcheck erzwingen
- Deliverables:
- `docker-compose.yml`
- `.env.example` oder dokumentierte `.env`-Variablen
- Akzeptanzkriterien:
- `docker compose up` startet ohne Konfigurationsfehler
- PostgreSQL wird als healthy gemeldet
- Vikunja verbindet sich mit DB

### Phase 2: Initialisierung

- Aufgaben:
- Dienste starten und auf Port `3456` prüfen
- Admin-User anlegen
- API-Token erzeugen
- Token-Handling dokumentieren (nur ENV)
- Deliverables:
- Initialisierungsanleitung im Repo
- Definierte ENV-Variable für Token
- Akzeptanzkriterien:
- Login mit Admin möglich
- API-Aufruf mit Token funktioniert

### Phase 3: MCP-Adapter

- Aufgaben:
- Lokalen MCP-Service anlegen
- Tools implementieren: `health`, `list_projects`, `create_project`, `list_tasks`, `create_task`, `move_task`
- Robuste Fehlerbehandlung umsetzen
- Minimales Logging einbauen
- Deliverables:
- MCP-Service-Code
- Tool-Definitionen und Startanleitung
- Akzeptanzkriterien:
- Alle Tools antworten in konsistenter Struktur
- Fehlerfälle liefern aussagekräftige Fehlercodes

### Phase 4: Verifikation

- Aufgaben:
- Automatisierte oder skriptbasierte End-to-End-Prüfung ausführen
- Ergebnisse dokumentieren
- Deliverables:
- Verifikationsskript oder reproduzierbare Testbefehle
- Testprotokoll
- Akzeptanzkriterien:
- API erreichbar
- Projekt erstellbar
- Task erstellbar
- Task verschiebbar

## 4. Öffentliche Schnittstellen (MCP Tools/API)

### Gemeinsame Antwortstruktur

- Erfolg:
- `success: true`
- `data: object`
- Fehler:
- `success: false`
- `error.code: string`
- `error.message: string`
- `error.details: object|null`

### Tool-Verträge

- `health`
- Input: keiner
- Output: API-Erreichbarkeit, Service-Status
- `list_projects`
- Input: optional `limit`, `page`
- Output: Liste mit `id`, `title`, `description`
- `create_project`
- Input: `title` (pflicht), `description` (optional)
- Output: erzeugtes Projekt mit `id`
- `list_tasks`
- Input: `project_id` (pflicht), optional `bucket_id`, `limit`, `page`
- Output: Liste mit `id`, `title`, `status/bucket`, `project_id`
- `create_task`
- Input: `project_id` (pflicht), `title` (pflicht), `description` (optional), `bucket_id` (optional)
- Output: erzeugter Task mit `id`
- `move_task`
- Input: `task_id` (pflicht), `target_bucket_id` (pflicht)
- Output: aktualisierter Task inkl. neuem Bucket

## 5. Verifikation und Testfälle

### Kernszenarien

- API Reachability:
- Erwartung: `health` meldet `success: true`
- Projekterstellung:
- Aktion: `create_project` mit Name `CN3M0 PoC`
- Erwartung: Projekt-ID wird zurückgegeben
- Task-Erstellung:
- Aktion: `create_task` im Projekt `CN3M0 PoC`
- Erwartung: Task-ID wird zurückgegeben
- Task-Verschiebung:
- Aktion: `move_task` in andere Kanban-Spalte
- Erwartung: Bucket/Status ist aktualisiert
- Zusammenfassung:
- Aktion: Boarddaten über MCP lesen und Statuszusammenfassung erzeugen
- Erwartung: konsistente, nachvollziehbare Zusammenfassung

### Negative Tests

- Ungültiger Token
- Erwartung: Auth-Fehler mit klarer Meldung
- Fehlende Pflichtfelder
- Erwartung: Validierungsfehler mit klarer Feldangabe
- Nicht existierende IDs
- Erwartung: 404-nahe Fehlerabbildung im Tool-Fehlerobjekt

## 6. Sicherheits- und Betriebsanforderungen

- API-Token niemals im Code hardcoden
- Secrets nur über ENV-Variablen
- Registrierung in produktionsnahem Betrieb deaktivieren
- Keine öffentliche Exponierung ohne Reverse Proxy
- Reproduzierbarkeit sicherstellen: Start über `docker compose up`

## 7. Risiken, Annahmen, offene Punkte

### Annahmen

- Docker und Docker Compose sind lokal verfügbar
- Port `3456` ist frei
- Vikunja-Image `latest` ist für PoC akzeptabel

### Defaults

- Sprache und Dokumentation in Deutsch
- MCP-Implementierung darf Node oder Python sein
- Entscheidung Node/Python erfolgt erst bei Implementierung

### Risiken

- Breaking Changes bei `vikunja/vikunja:latest`
- Unklare Fehlerabbildung ohne einheitliches Fehlerschema
- Token-Leakage bei unvorsichtigem Logging

## 8. Definition of Done

- [x] `docker compose up` startet alle Kernservices vollständig
- [x] Admin-User ist angelegt und nutzbar
- [x] API-Token ist erzeugt und ausschließlich via ENV konfiguriert
- [x] Projekt `CN3M0 PoC` kann angelegt werden
- [x] Task kann via MCP erzeugt werden
- [x] Task kann via MCP zwischen Spalten verschoben werden
- [x] Codex kann den Board-Zustand zusammenfassen
- [x] Reproduzierbare Verifikation ist dokumentiert

## 9. Start-zu-Ist Tracking (Checkliste)

| Bereich | Startstatus (2026-02-27) | Aktueller Status | Nachweis |
|---|---|---|---|
| Infrastruktur (Compose, DB, Vikunja) | Geplant | DONE | docker compose + Healthchecks aktiv |
| Initialisierung (Admin, Token) | Geplant | DONE | `scripts/bootstrap_admin_and_token.py` |
| MCP-Adapter (Tools) | Geplant | DONE | `mcp_adapter/vikunja_mcp/server.py` |
| Verifikation (E2E) | Geplant | DONE | `scripts/verify_poc.py` erfolgreich |
| Sicherheit/Secrets | Anforderungen definiert | DONE | Token nur in `.env`, `.gitignore` aktiv |
