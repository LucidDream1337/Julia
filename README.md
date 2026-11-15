# Julia – private, lernende KI

Eine komplett lokale KI-Umgebung auf Basis von Docker Compose. Julia läuft in einem eigenen
Docker-Netzwerk, speichert alle Daten in diesem Ordner und kann selbstständig Wissen
(Knowledge Bases) und Skills anlegen.

Zielordner: `/Projekte/Festplatten/int0SSD0/Julia`

## Bestandteile

| Service | Aufgabe |
|---|---|
| `open-webui` | Chat-Oberfläche (http://localhost:3000) |
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
erreichbar, und zwar standardmäßig nur über `127.0.0.1:3000`. Open WebUI spricht bewusst nicht
direkt mit Ollama, sondern ausschließlich mit dem Agent.

## Voraussetzungen

- Docker mit Docker Compose v2 (`docker compose version`)
- Ca. 6 GB freier Speicherplatz für die Modelle, ca. 8 GB RAM (mehr ist besser)
- Internetzugang beim ersten Start (Modelle und Images laden)
- Optional: NVIDIA-GPU mit `nvidia-container-toolkit`

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
http://localhost:3000 öffnen. Der erste registrierte Account wird Administrator. Als Modell
erscheint **julia**.

## Benutzung

Julia hat Werkzeuge, die sie selbst aufruft, wenn es passt. Du kannst sie auch direkt darum bitten:

- „Leg eine Knowledge Base `heimnetz` an und merk dir: Der NAS hat die IP 192.168.1.20.“
- „Was weißt du über mein Heimnetz?“
- „Lerne den Inhalt von https://example.com/anleitung in der Knowledge Base `anleitungen`.“
  (nur mit `AGENT_ALLOW_WEB=true`)
- „Speichere diesen Ablauf als Skill `wochenbericht`: 1. … 2. … 3. …“
- „Nutze den Skill `wochenbericht`.“

Zusätzlich:

- Zu jeder Frage durchsucht der Agent automatisch alle Knowledge Bases und hängt passende
  Treffer als Kontext an.
- Alle Skills (Name und Beschreibung) kennt Julia in jeder Unterhaltung.
- Hat Julia etwas gespeichert, steht am Ende der Antwort eine Zeile `🧠 Gelernt: …`.

### Werkzeuge des Agents

| Werkzeug | Funktion |
|---|---|
| `list_knowledge_bases` | Vorhandene Knowledge Bases anzeigen |
| `create_knowledge_base` | Neue Knowledge Base anlegen |
| `add_to_knowledge_base` | Text speichern (legt die KB bei Bedarf automatisch an) |
| `search_knowledge` | Semantische Suche in einer oder allen KBs |
| `learn_from_url` | Webseite lesen und in einer KB speichern |
| `save_skill` / `use_skill` | Skill speichern oder laden |

Skills sind reine Text-Anleitungen (`data/agent/skills/*.md`), kein ausführbarer Code. Du kannst
sie von Hand ansehen und bearbeiten.

## Konfiguration (`.env`)

| Variable | Standard | Bedeutung |
|---|---|---|
| `AGENT_API_KEY` | – (Pflicht) | Schlüssel zwischen Open WebUI und Agent |
| `WEBUI_SECRET_KEY` | – (Pflicht) | Geheimnis für Sessions in Open WebUI |
| `CHAT_MODEL` | `qwen3:4b` | Chat-Modell (beliebiges Ollama-Modell mit Tool-Unterstützung) |
| `EMBED_MODEL` | `nomic-embed-text` | Embedding-Modell |
| `AGENT_ALLOW_WEB` | `false` | Erlaubt dem Agent, Webseiten abzurufen |
| `AGENT_THINK` | `false` | Qwen3-„Thinking“: klügere, aber langsamere Antworten |

Wichtig: Nach dem Anlegen von Knowledge Bases `EMBED_MODEL` nicht mehr ändern. Die Vektorgröße
ist pro KB fest, bei einem anderen Embedding-Modell musst du die KBs neu anlegen.

Weitere Einstellungen direkt in `docker-compose.yml`:

- **Zugriff aus dem LAN:** Port bei `open-webui` von `127.0.0.1:3000:8080` auf `3000:8080` ändern.
- **GPU:** Den auskommentierten `deploy`-Block bei `ollama` aktivieren.
- **Kontextlänge:** `OLLAMA_CONTEXT_LENGTH` (Ollama) und `num_ctx` in `agent/main.py`.

## Datenablage

Alles liegt unter `./data` und überlebt `docker compose down`:

```
data/
├── ollama/       Modelle
├── qdrant/       Knowledge Bases (Vektoren)
├── agent/        kbs.json (KB-Verzeichnis) und skills/
└── open-webui/   Accounts, Chats, Einstellungen
```

**Backup:** `docker compose down`, dann den Ordner `Julia/` kopieren (oder `data/` archivieren).
**Komplett zurücksetzen:** `docker compose down && rm -rf data`.

## Betrieb

```bash
docker compose ps                 # Status
docker compose logs -f agent      # Agent-Logs
docker compose restart agent      # Agent neu starten
docker compose pull && docker compose up -d --build   # Updates
docker compose down               # Stoppen (Daten bleiben)
```

## Sicherheit

- Der Agent akzeptiert nur Anfragen mit `AGENT_API_KEY` und ist nicht nach außen veröffentlicht.
- Beim Web-Lernen blockiert der Agent Adressen im lokalen Netz und im Docker-Netz (Schutz vor
  SSRF), auch bei Weiterleitungen.
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
| Antworten sehr langsam | Läuft auf der CPU. GPU aktivieren oder `AGENT_THINK=false` lassen |
| Julia speichert nichts von selbst | Kleine Modelle nutzen Werkzeuge nicht immer. Ausdrücklich darum bitten |
| Port 3000 belegt | Host-Port bei `open-webui` in `docker-compose.yml` ändern |

## Grenzen

- Julia „lernt“, indem sie Wissen und Skills speichert und wiederfindet. Das Modell selbst wird
  nicht trainiert.
- Antworten erscheinen auf einmal und nicht Wort für Wort, weil der Agent zuerst seine
  Werkzeugschritte abschließt.
- Ein 4B-Modell macht Fehler. Wichtige Fakten bitte gegenprüfen.
