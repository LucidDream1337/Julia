# Julia
Autonomous Self-Learning KI with WebUI

## ACHTUNG: Dieser Schritt muss in OpenUI Manuell gemacht werden
1. Einstellungen öffnen
2. Den Toggle "Websuche" und "Embedding und Retrieval umgehen" aktivieren und dann die entsprechenden engines einstellen (Ich verwende persönlich DuckDuckGo)

How-To Setup:
1. Das AiOPack in einen Ordner entpacken
2. In den entpackten Ordner navigieren
3. Das Script `setup.sh` ausführen
4. Den Container-Stack mit `docker compose --env-file .env up -d` starten
5. Die WebUI ist dann unter Port 3001 verfügbar

## Websuche (einmalig im Admin-Panel)
Die Websuche (DuckDuckGo) wird per Umgebungsvariable vorkonfiguriert, gilt aber nur beim ersten Start von Open WebUI.
Damit sie in jedem neuen Chat automatisch aktiv ist:
1. *Admin-Panel → Einstellungen → Websuche*: prüfen, dass sie aktiv und DuckDuckGo gewählt ist
2. *Admin-Panel → Einstellungen → Modelle → qwen2.5:7b*: Fähigkeit **Websuche** aktivieren und unter **Standard-Funktionen** **Websuche** anhaken

## Wissens-Tool anbinden
*Admin-Panel → Externe Tools → OpenAPI*: URL `http://julia-agent:8090`, Pfad `openapi.json`. Details in `aioPack/README.md`.
