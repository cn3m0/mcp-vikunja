# PROJECT.md

## Vikunja + MCP Proof of Concept

### Ziel: Self-hosted Kanban mit AI-Integration (Codex)

---

## 1. Projektziel

Dieses Projekt soll eine lokal gehostete Kanban-Infrastruktur aufbauen, bestehend aus:

* Vikunja (Self-hosted Kanban-System)
* PostgreSQL Datenbank
* MCP-Server (Model Context Protocol Adapter)
* API-Integration für Codex

Ziel ist es, dass Codex:

* Boards lesen kann
* Tasks erstellen kann
* Tasks verschieben kann
* Status auswerten kann
* Zusammenfassungen generieren kann

Die gesamte Umgebung soll lokal via Docker Compose betrieben werden.

---

## 2. Architekturübersicht

Systemkomponenten:

1. PostgreSQL (Persistenz)
2. Vikunja Backend
3. Vikunja Web UI
4. MCP-Adapter-Service (Node oder Python)
5. Lokale Codex-Integration

Netzwerk:

* Alle Container im selben Docker-Netz
* Vikunja erreichbar unter [http://localhost:3456](http://localhost:3456)
* MCP-Service greift über internes Docker-Netz auf Vikunja zu

---

## 3. Anforderungen

### Funktional

* Vikunja startet fehlerfrei
* Admin-User existiert
* API-Token kann erzeugt werden
* MCP kann:

  * Projekte listen
  * Tasks listen
  * Tasks erstellen
  * Tasks verschieben

### Nicht-Funktional

* Kein Cloud-Zwang
* Keine externen Abhängigkeiten
* Reproduzierbar via `docker compose up`
* Konfiguration via `.env`

---

## 4. Implementierungsaufgaben (für Codex)

### Phase 1 – Infrastruktur

1. Erstelle Docker Compose Setup:

   * postgres:16-alpine
   * vikunja/vikunja:latest
2. Konfiguriere ENV:

   * DB Credentials
   * JWT Secret
   * Public URL
3. Stelle sicher:

   * DB Healthcheck aktiv
   * Restart Policy gesetzt
   * Volumes persistent

### Phase 2 – Initialisierung

1. Starte Container
2. Prüfe:

   * Port 3456 erreichbar
3. Erstelle Admin User
4. Generiere API Token
5. Dokumentiere Token Handling (ENV Variable)

### Phase 3 – MCP Adapter

1. Erstelle lokalen MCP-Service
2. Implementiere folgende Tools:

* health
* list_projects
* create_project
* list_tasks
* create_task
* move_task

3. API Auth via Bearer Token
4. Fehlerbehandlung robust implementieren
5. Logging minimal aber nachvollziehbar

### Phase 4 – Verifikation

Codex soll automatisiert prüfen:

* Ist Vikunja API erreichbar?
* Kann Projekt erzeugt werden?
* Kann Task erzeugt werden?
* Kann Task verschoben werden?

Wenn alle Tests erfolgreich:
→ PoC erfolgreich.

---

## 5. Sicherheitsanforderungen

* API Token niemals hardcoded
* Nutzung von ENV Variablen
* Kein offenes Registration Flag im Produktivmodus
* Keine Public Exposure ohne Reverse Proxy

---

## 6. Erweiterung (optional)

* Nginx Reverse Proxy
* HTTPS via Let’s Encrypt
* OAuth Integration
* Webhook für AI Automatisierung
* Task Digest Generator

---

## 7. Erfolgsdefinition

Das Projekt gilt als erfolgreich, wenn:

* `docker compose up` startet das System vollständig
* Ein Projekt namens "CN3M0 PoC" kann erstellt werden
* Ein Task kann via MCP erzeugt werden
* Der Task kann zwischen Kanban-Spalten verschoben werden
* Codex kann Board-Zustand zusammenfassen

---

## 8. Motivation

Dieses Setup dient als:

* AI-augmentiertes Projektmanagement-System
* Experimentelle Infrastruktur für CN3M0
* Grundlage für autonome Task-Orchestrierung

---

## 9. Arbeitsweise

Codex darf:

* Dateien anlegen
* Compose anpassen
* MCP Code generieren
* Testscripte schreiben
* Logs auswerten

Codex soll:

* deterministisch arbeiten
* keine unnötigen Abhängigkeiten einführen
* System minimal halten


