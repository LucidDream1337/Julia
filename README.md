# Julia
Autonomous Self-Learning KI with WebUI

## Setup
1. Den Ordner `aioPack` auf den Server kopieren (z. B. nach `/Projekte/Festplatten/int0SSD0`)
2. `./setup.sh` ausführen (baut das Agent-Image, legt `.env` an)
3. `docker compose --env-file .env up -d`
4. Die WebUI ist unter Port 3001 erreichbar

Modell: `qwen3:14b` (ca. 9 GB; mit Kontext 8192 braucht es etwa 11–12 GB VRAM). Bei weniger VRAM `OLLAMA_MODEL=qwen3:8b` setzen.

## Websuche (einmalig im Admin-Panel)
Die Websuche (DuckDuckGo) wird per Umgebungsvariable vorkonfiguriert, gilt aber nur beim ersten Start von Open WebUI.
Damit sie in jedem neuen Chat automatisch aktiv ist:
1. *Admin-Panel → Einstellungen → Websuche*: prüfen, dass sie aktiv und DuckDuckGo gewählt ist
2. *Admin-Panel → Einstellungen → Modelle → qwen3:14b*: Fähigkeit **Websuche** aktivieren und unter **Standard-Funktionen** **Websuche** anhaken

## Wissens-Tool anbinden
*Admin-Panel → Externe Tools → OpenAPI*: URL `http://julia-agent:8090`, Pfad `openapi.json`. Details in `aioPack/README.md`.

## Projekt mit dem Entwicklungs-Agenten (Hermes) weiterbauen
Im Stack-Ordner liegen `AGENTS.md` (Projektregeln) und `START-HERMES.md` (Reihenfolge der Aufgaben aus `prompts/`).
```bash
cd /Projekte/Festplatten/int0SSD0
hermes
```
Dann sagen: **„Lies START-HERMES.md und führe es aus.“** Hermes arbeitet Projekt für Projekt ab und hält an Freigabe-Gates und am Ende jedes Projekts an.
Wichtig: Hermes braucht dafür ein starkes Modell mit zuverlässigem Tool-Calling (nicht zwingend das lokale `qwen3:14b`).
