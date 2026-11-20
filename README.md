# Julia – private, lernende KI

Eine komplett lokale KI-Umgebung auf Basis von Docker Compose. Julia läuft in einem eigenen
Docker-Netzwerk, speichert alle Daten in diesem Ordner und kann selbstständig Wissen
(Knowledge Bases) und Skills anlegen.

Zielordner: `/Projekte/Festplatten/int0SSD0/Julia`

## Bestandteile

| Service | Aufgabe |
|---|---|
| `open-webui` | Chat-Oberfläche (http://localhost:3001) |
| `agent` | Eigener Agent-Service (FastAPI). Gibt sich als OpenAI-kompatible API aus, steuert das Modell, nutzt Werkzeuge und verwaltet Wissen und Skills |
| `ollama` | Modell-Server mit `qwen3:4b` (Chat) und `nomic-embed-text` (Embeddings) |
| `ollama-init` | Lädt die Modelle einmalig und beendet sich danach |
| `qdrant` | Vektordatenbank, jede Knowledge Base ist eine Collection |

```
Browser ──> Open WebUI ──> Agent ──> Ollama (qwen3:4b, nomic-embed-text)
                             └─────> Qdrant (Knowledge Bases)
                             └─────> data/agent/skills (Skills als Markdown)
```

Alle Container hängen im Netz `julia-net` (172.28.40.0/24). Nach außen ist nur Open WebUI
erreichbar, und zwar standardmäßig nur über `127.0.0.1:3001`. Open WebUI spricht bewusst nicht
direkt mit Ollama, sondern ausschließlich mit dem Agent.

## Voraussetzungen

- Docker mit Docker Compose v2 (`docker compose version`)
- Ca. 6 GB freier Speicherplatz für die Modelle, ca. 8 GB RAM (mehr ist besser)
- Internetzugang beim ersten Start (Modelle und Images laden)
- NVIDIA-GPU mit installiertem `nvidia-container-toolkit` (standardmäßig aktiviert, ohne GPU siehe Konfiguration)

## Installation

```bash
mkdir -p /Projekte/Festplatten/int0SSD0
cd /Projekte/Festplatten/int0SSD0
unzip /pfad/zu/Julia.zip        # legt den Ordner Julia/ an
cd Julia

cp .env.example .env
```

In `.env` zwei Schlüssel setzen (jeweils mit `openssl rand -hex 32` erzeugen):

```
AGENT_API_KEY=...
WEBUI_SECRET_KEY=...
```

Starten:

```bash
docker compose up -d --build
docker compose logs -f ollama-init    # Fortschritt des Modell-Downloads
```

Sobald `ollama-init` mit Exit 0 beendet ist, startet der Agent. Danach
http://localhost:3001 öffnen. Der erste registrierte Account wird Administrator. Als Modell
erscheint **julia**.

## Benutzung

Julia hat Werkzeuge, die sie selbst aufruft, wenn es passt. Du kannst sie auch direkt darum bitten:

- „Leg eine Knowledge Base `heimnetz` an und merk dir: Der NAS hat die IP 192.168.1.20.“
- „Was weißt du über mein Heimnetz?“
- „Lerne den Inhalt von https://example.com/anleitung in der Knowledge Base `anleitungen`.“
  (nur mit `AGENT_ALLOW_WEB=true`)
- „Speichere diesen Ablauf als Skill `wochenbericht`: 1. … 2. … 3. …“
- „Nutze den Skill `wochenbericht`.“
- „Die NAS-IP hat sich geändert, sie ist jetzt 192.168.1.30.“ (Julia korrigiert den Eintrag)
- „Räum die Knowledge Base `heimnetz` auf.“ (Dubletten und Veraltetes, Skill `kb-pflege`)
- „Lösch die Knowledge Base `testen`.“ (landet im Papierkorb) und „Hol `testen` zurück.“
- „Verbessere den Skill `wochenbericht`, Schritt 3 fehlt der Hinweis auf …“
- „Was hast du zuletzt geändert?“ (Changelog)

Zusätzlich:

- Zu jeder Frage durchsucht der Agent automatisch alle Knowledge Bases und hängt passende
  Treffer als Kontext an.
- Alle Skills (Name und Beschreibung) kennt Julia in jeder Unterhaltung.
- Hat Julia etwas gespeichert, steht am Ende der Antwort eine Zeile `🧠 Aktionen: …`.

### Werkzeuge des Agents

| Bereich | Werkzeug | Funktion |
|---|---|---|
| Knowledge Bases | `list_knowledge_bases` | Alle KBs mit Beschreibung und Anzahl Einträge |
| | `create_knowledge_base` | Neue KB anlegen |
| | `update_knowledge_base` | Beschreibung ändern |
| | `rename_knowledge_base` | KB umbenennen (Inhalt wird übernommen) |
| | `delete_knowledge_base` | KB in den Papierkorb legen; mit `permanent=true` endgültig löschen (nur wenn sie schon im Papierkorb liegt) |
| | `restore_knowledge_base` | KB aus dem Papierkorb zurückholen |
| | `merge_knowledge_bases` | Einträge einer KB in eine andere verschieben, Quelle kommt in den Papierkorb |
| | `export_knowledge_base` | Einträge als JSON nach `data/agent/exports/` sichern |
| Einträge | `add_to_knowledge_base` | Text speichern (legt die KB bei Bedarf an, überspringt nahezu identische Einträge) |
| | `list_entries` | Einträge einer KB mit IDs anzeigen |
| | `search_knowledge` | Semantische Suche, Treffer als `[KB#ID]` |
| | `update_entry` / `delete_entry` | Einzelnen Eintrag korrigieren / löschen |
| | `learn_from_url` | Webseite lesen und speichern (nur mit `AGENT_ALLOW_WEB=true`) |
| Skills | `list_skills`, `use_skill` | Skills auflisten / laden |
| | `save_skill` | Skill anlegen oder überschreiben (alte Version wird gesichert) |
| | `delete_skill` / `restore_skill` | Skill in den Papierkorb legen / zurückholen |
| Selbstprüfung | `status` | Version, Modelle, Qdrant, GPU/CPU, Einstellungen, Werkzeuge |
| | `empty_trash` | Papierkorb (KBs und Skills) endgültig leeren, nur auf ausdrücklichen Wunsch |
| Protokoll | `show_changelog` | Letzte eigene Änderungen ansehen |

### Selbstverwaltung

Julia pflegt Wissen und Skills selbst. Damit das sicher bleibt:

- **Papierkorb:** Ganze KBs und Skills werden zuerst nur in den Papierkorb gelegt und nach
  `AGENT_TRASH_DAYS` Tagen (Standard 14) endgültig entfernt. Bis dahin kann Julia sie wiederherstellen.
- **Changelog:** Jede Änderung steht in `data/agent/changelog.md`. Bei geänderten oder gelöschten
  Einträgen auch mit dem alten Inhalt, sodass sich Fehler von Hand oder durch Julia korrigieren lassen.
- **Skill-Historie:** Beim Überschreiben eines Skills bleiben die letzten 5 Versionen in `data/agent/skills/.history/`.
- **Spielregeln:** Ergänzen und Korrigieren darf Julia selbstständig. Ganze KBs oder Skills löschen
  und mehr als 3 Einträge auf einmal entfernen soll sie nur auf Wunsch oder nach Rückfrage.
  Inhalte aus Webseiten, Dokumenten und KBs behandelt sie als Daten, nicht als Anweisungen.
- **Schalter:** Mit `AGENT_ALLOW_DELETE=false` kann Julia gar nichts mehr löschen (Anlegen, Ergänzen
  und Korrigieren bleiben möglich).
- **Start-Skills:** Beim ersten Start legt Julia sechs Skills an, die diese Abläufe beschreiben:
  `werkzeugkasten`, `selbstverwaltung`, `kb-pflege`, `skill-pflege`, `wissen-ablegen` und `wissen-recherchieren`.
  Sie lassen sich wie jeder andere Skill bearbeiten. Gelöschte kommen nicht zurück.

Skills sind reine Text-Anleitungen (`data/agent/skills/*.md`), kein ausführbarer Code. Du kannst
sie von Hand ansehen und bearbeiten.

### Befehle (Starter-Kit, ohne Sprachmodell)

Beginnt eine Nachricht mit `/` oder `!` und ist ein bekannter Befehl, führt der Agent ihn direkt aus.
Das funktioniert zuverlässig, auch wenn das kleine Modell ein Werkzeug nicht von selbst wählt.

| Befehl | Wirkung |
|---|---|
| `/hilfe` | Befehlsübersicht |
| `/status` | Selbsttest: Version, Modelle, Qdrant, GPU/CPU, Einstellungen, Werkzeuge |
| `/kb` | Alle Knowledge Bases |
| `/kb einträge NAME` | Einträge mit IDs |
| `/kb beschreibung NAME TEXT` | Beschreibung ändern |
| `/kb umbenennen ALT NEU` | Umbenennen |
| `/kb löschen NAME [endgültig]` | In den Papierkorb legen, mit `endgültig` sofort und unwiderruflich löschen |
| `/kb wiederherstellen NAME` | Aus dem Papierkorb holen |
| `/kb zusammenführen QUELLE ZIEL` | Einträge verschieben, Quelle kommt in den Papierkorb |
| `/kb export NAME` | Einträge als JSON nach `data/agent/exports/` |
| `/skills`, `/skill anzeigen NAME` | Skills auflisten / lesen |
| `/skill löschen NAME [endgültig]`, `/skill wiederherstellen NAME` | Skill löschen / zurückholen |
| `/papierkorb`, `/papierkorb leeren` | Papierkorb ansehen / endgültig leeren |
| `/log [ANZAHL]` | Änderungsprotokoll |

## Konfiguration (`.env`)

| Variable | Standard | Bedeutung |
|---|---|---|
| `AGENT_API_KEY` | – (Pflicht) | Schlüssel zwischen Open WebUI und Agent |
| `WEBUI_SECRET_KEY` | – (Pflicht) | Geheimnis für Sessions in Open WebUI |
| `CHAT_MODEL` | `qwen3:4b` | Chat-Modell (beliebiges Ollama-Modell mit Tool-Unterstützung) |
| `EMBED_MODEL` | `nomic-embed-text` | Embedding-Modell |
| `AGENT_ALLOW_WEB` | `false` | Erlaubt dem Agent, Webseiten abzurufen |
| `AGENT_THINK` | `false` | Qwen3-„Thinking“: klügere, aber langsamere Antworten |
| `AGENT_ALLOW_DELETE` | `true` | Darf Julia löschen (Einträge, KBs, Skills)? |
| `AGENT_TRASH_DAYS` | `14` | Tage bis der Papierkorb endgültig geleert wird |
| `AGENT_NUM_CTX` | `12288` | Kontextgröße des Modells (mehr = mehr RAM) |

Wichtig: Nach dem Anlegen von Knowledge Bases `EMBED_MODEL` nicht mehr ändern. Die Vektorgröße
ist pro KB fest, bei einem anderen Embedding-Modell musst du die KBs neu anlegen.

Weitere Einstellungen direkt in `docker-compose.yml`:

- **Zugriff aus dem LAN:** Port bei `open-webui` von `127.0.0.1:3001:8080` auf `3001:8080` ändern.
- **GPU:** NVIDIA ist standardmäßig aktiv (`deploy`-Block und `NVIDIA_*`-Variablen bei `ollama`). Ohne NVIDIA-GPU diese entfernen.
- **Kontextlänge:** `AGENT_NUM_CTX` in `.env` (und `OLLAMA_CONTEXT_LENGTH` bei `ollama`).

## Datenablage

Alles liegt unter `./data` und überlebt `docker compose down`:

```
data/
├── ollama/        Modelle
├── qdrant/        Knowledge Bases (Vektoren)
├── agent/
│   ├── kbs.json       KB-Verzeichnis (inkl. Papierkorb-Status)
│   ├── changelog.md   Protokoll aller Änderungen durch Julia
│   ├── exports/       KB-Backups als JSON
│   └── skills/        Skills (*.md), .history/ (alte Versionen), .trash/ (gelöschte)
└── open-webui/    Accounts, Chats, Einstellungen
```

**Backup:** `docker compose down`, dann den Ordner `Julia/` kopieren (oder `data/` archivieren).
**Komplett zurücksetzen:** `docker compose down && rm -rf data`.

## Betrieb

```bash
docker compose ps                 # Status
docker compose logs -f agent      # Agent-Logs
docker compose restart agent      # Agent neu starten
docker compose pull && docker compose up -d --build   # Updates (nach Änderungen am Agent immer mit --build)
docker compose down               # Stoppen (Daten bleiben)
```

## Sicherheit

- Der Agent akzeptiert nur Anfragen mit `AGENT_API_KEY` und ist nicht nach außen veröffentlicht.
- Beim Web-Lernen blockiert der Agent Adressen im lokalen Netz und im Docker-Netz (Schutz vor
  SSRF), auch bei Weiterleitungen.
- Löschen ist abgesichert: Papierkorb, Changelog und Skill-Historie. Mit `AGENT_ALLOW_DELETE=false` ist es ganz abgeschaltet.
- Julia soll keine Passwörter oder Schlüssel speichern, außer du verlangst es ausdrücklich.
  Behandle `data/` trotzdem wie vertrauliche Daten.
- Öffnest du Open WebUI im LAN, lege starke Passwörter fest und stelle bei Bedarf in Open WebUI
  die Registrierung ab.

## Fehlersuche

| Problem | Lösung |
|---|---|
| `compose` meldet „bitte in .env setzen“ | `.env` anlegen und beide Schlüssel eintragen |
| Agent startet nicht | `ollama-init` noch nicht fertig oder Download fehlgeschlagen: `docker compose logs ollama-init` |
| Modell „julia“ fehlt in Open WebUI | Admin-Einstellungen → Verbindungen: URL `http://agent:8000/v1`, Key = `AGENT_API_KEY` |
| Fehler 401 im Agent-Log | `AGENT_API_KEY` in Open WebUI und Agent stimmen nicht überein, danach `docker compose up -d` |
| Antworten sehr langsam | Läuft vermutlich auf der CPU: `/status` zeigt bei geladenen Modellen GPU oder CPU. `AGENT_THINK=false` lassen |
| `could not select device driver "nvidia"` beim Start | `nvidia-container-toolkit` installieren und Docker neu starten, oder ohne GPU den `deploy`-Block bei `ollama` entfernen |
| Julia kann nichts löschen | `/status` senden: Zeigt es keine Version 3 oder reagiert Julia nur wie im Chat, läuft noch das alte Image (`docker compose up -d --build`). Steht dort „Löschen erlaubt: NEIN“, `AGENT_ALLOW_DELETE` in `.env` prüfen. Zum Testen `/kb löschen NAME` nutzen |
| Julia speichert nichts von selbst | Kleine Modelle nutzen Werkzeuge nicht immer. Ausdrücklich darum bitten |
| Port 3001 belegt | Host-Port bei `open-webui` in `docker-compose.yml` ändern |
| `ollama list` ist leer, Fehler 404 „model not found“ | Der Modell-Download ist fehlgeschlagen (z. B. keine Internetverbindung im Container). Von Hand laden: `docker compose exec ollama ollama pull qwen3:4b` und `docker compose exec ollama ollama pull nomic-embed-text`. `ollama-init` versucht es jetzt selbst alle 15 Sekunden erneut (`docker compose logs -f ollama-init`) |
| Open WebUI meldet „HTTP 500“ vom Agent | Die Ursache steht im Agent-Log: `docker compose logs --tail=60 agent`. Seit Version 4 erscheint sie auch direkt im Chat. Häufig sind Ollama-Fehler (Modell fehlt, zu wenig GPU-Speicher: `AGENT_NUM_CTX` und `OLLAMA_CONTEXT_LENGTH` senken, GPU-Treiber), siehe `docker compose logs --tail=60 ollama` |

## Grenzen

- Julia „lernt“, indem sie Wissen und Skills speichert und wiederfindet. Das Modell selbst wird
  nicht trainiert.
- Antworten erscheinen auf einmal und nicht Wort für Wort, weil der Agent zuerst seine
  Werkzeugschritte abschließt.
- Ein 4B-Modell macht Fehler. Wichtige Fakten bitte gegenprüfen.
