# Programming Learning Agent (Ollama + RAG + Qdrant + Open WebUI)

Lokaler Programmier-Lernagent: Lernmaterial von W3Schools wird höflich gecrawlt, in Qdrant
gespeichert und über RAG mit qwen2.5:7b beantwortet. Bedienung über Open WebUI.
Der komplette Stack (inklusive Ollama mit NVIDIA-GPU) läuft in Docker.

```
Open WebUI :3001 ──► Ollama (GPU, qwen2.5:7b)
      │
      └─ Tool (OpenAPI) ──► julia-agent :8090 ──► Qdrant :6333
                                   ▲                      ▲
                      learning-worker (alle 24 h) ────────┘
                      Crawler -> Chunks -> nomic-embed-text -> Qdrant
```

## Inhalt

| Datei/Ordner | Zweck |
|---|---|
| `docker-compose.yaml` | Stack: `ollama` (+ `ollama-models` Modell-Download), `open-webui`, `qdrant`, `julia-agent`, `learning-worker` |
| `setup.sh` | Voraussetzungen prüfen, Verzeichnisse, `.env`, Image bauen, Compose validieren |
| `agent/` | Python-Quellcode + `Dockerfile` des Agenten |
| `data/` | Persistente Daten (`ollama`, `qdrant`, `open-webui`, `agent`) |
| `training/` | Reserviert für späteres Fine-Tuning |
| `.env.example` | Vorlage der Konfiguration |

## Getroffene Annahmen

1. Auf dem Server läuft kein Ollama mehr; der Stack bringt Ollama selbst mit (Container
   `julia-school-ollama`, Modelle unter `data/ollama`). Der Stack legt sein eigenes
   Netzwerk `julia-learning-net` an; ein altes Netzwerk (z. B. `programming-school_internal`)
   wird nicht verwendet.
2. Das Agent-Image wird **auf dem Host** gebaut. Dockhand referenziert nur das fertige Image.
3. Container-Namen sind eindeutig (`julia-school-qdrant`, `-agent`, `-worker`, `-webui`),
   damit nichts mit bestehenden Containern (Jellyfin, Valheim, Dockhand, nginx, …) kollidiert.
   Diese werden nicht angefasst.
4. Der Agent-Container läuft als root im Container, damit der Bind-Mount `data/agent`
   ohne Rechte-Anpassung beschreibbar ist.
5. Für den Crawl sind standardmäßig die Bereiche Python, JavaScript, HTML, CSS, SQL, Java, C++,
   C, C#, PHP freigegeben (`allowed_prefixes` in `agent/app/crawler.py`). Übungen, Quizze,
   Zertifikate und der „Try it"-Editor werden ausgelassen.
6. Fragen dürfen deutsch sein: Die Suchanfrage wird vom Sprachmodell vorab ins Englische
   umformuliert (`RAG_QUERY_REWRITE=true`), weil Quellen und Embedding-Modell überwiegend
   englisch sind. Die Antwort kommt in der Sprache der Frage.

## Voraussetzungen

- Docker + Docker Compose v2
- NVIDIA-Treiber auf dem Host (`nvidia-smi` funktioniert) **und** NVIDIA Container Toolkit, damit
  der `ollama`-Container die GPU nutzen kann. Prüfen: `docker info | grep -i nvidia`.
  Installation siehe NVIDIA-Doku „Container Toolkit Install Guide"; danach
  `sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker`.
  Der Docker-Neustart unterbricht kurz alle Container (Jellyfin, Valheim, …), sofern `live-restore`
  nicht aktiv ist – am besten außerhalb der Spielzeiten.
- Internetzugang des Servers (Modell-Download von Ollama, Crawl von w3schools.com, Images)

## Installation

### 1. Dateien auf den Server bringen

```bash
unzip programming-learning-agent.zip
cp -r programming-learning-agent/. /Projekte/Festplatten/int0SSD0/
cd /Projekte/Festplatten/int0SSD0
```

(Vorhandene Ordner `agent/`, `data/`, `training/` werden dabei zusammengeführt.)

### 2. Setup ausführen

```bash
./setup.sh
```

Das Skript prüft Docker, Compose, NVIDIA-GPU/-Runtime und Namenskollisionen mit fremden
Containern, legt Verzeichnisse an, erzeugt `.env` mit zufälligem `WEBUI_SECRET_KEY` und
`ADMIN_TOKEN`, baut `julia-school-agent:1.0` und validiert die Compose-Datei.
Optionen: `--no-build`, `--up`. Ohne NVIDIA Container Toolkit warnt es nur – dann zuerst
die Voraussetzungen erfüllen.

Optional startet `./setup.sh --up` den Stack direkt.

### 3. Stack starten

**Mit Dockhand:** Neuen Stack anlegen, den Inhalt von `docker-compose.yaml` einfügen, den Inhalt
von `.env` als Umgebungsvariablen des Stacks eintragen, deployen.

**Per Kommandozeile:**

```bash
docker compose --env-file .env up -d
docker compose --env-file .env ps
```

Beim ersten Start lädt der Hilfscontainer `julia-school-ollama-models` die Modelle
`qwen2.5:7b` und `nomic-embed-text` (ca. 2,3 GB) und beendet sich danach mit Status
`Exited (0)` – das ist normal. Fortschritt:

```bash
docker logs -f julia-school-ollama-models
docker exec julia-school-ollama ollama list
```

GPU-Nutzung prüfen (nach der ersten Anfrage): `docker exec julia-school-ollama ollama ps`
zeigt bei GPU-Betrieb `100% GPU`.

### 4. Prüfen (erst nachdem die Modelle geladen sind)

```bash
docker exec julia-school-agent python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8090/health').read().decode())"
```

`"status": "ok"` heißt: Ollama erreichbar, beide Modelle da, Qdrant erreichbar. Direkt nach dem
ersten Start ist die Collection noch nicht vorhanden (`collection_exists: false`) – das ist normal.

### 5. Ersten Lernlauf starten

Der Worker startet automatisch (erster Lauf ca. 60 s nach Start, danach alle 24 h). Manuell:

```bash
docker exec julia-school-agent python -m app.cli learn --max-pages 10
docker exec julia-school-agent python -m app.cli status
docker exec julia-school-agent python -m app.cli ask "Wie funktionieren Variablen in Python?"
```

Gezielt einzelne Seiten (neu) indexieren:

```bash
docker exec julia-school-agent python -m app.cli crawl https://www.w3schools.com/python/python_lists.asp
```

## Open WebUI einrichten

**Websuche:** Der Stack setzt `ENABLE_WEB_SEARCH`, `WEB_SEARCH_ENGINE` (DuckDuckGo) usw. per Umgebungsvariable.
Diese Werte gelten nur beim *ersten* Start von Open WebUI; danach hat das Admin-Panel Vorrang. Damit die Suche in
neuen Chats automatisch angeschaltet ist, einmalig unter *Admin-Panel → Einstellungen → Modelle → qwen2.5:7b*
die Fähigkeit **Websuche** aktivieren und unter **Standard-Funktionen** ebenfalls **Websuche** anhaken
(dafür gibt es keine Umgebungsvariable).

1. `http://<server-ip>:3001` öffnen, ersten Benutzer registrieren (wird Administrator).
2. **Admin-Einstellungen → Externe Tools** (je nach Version „Tools"/„Tool-Server"): Verbindung
   hinzufügen, Typ **OpenAPI**, URL `http://julia-agent:8090`, OpenAPI-Pfad `openapi.json`,
   speichern. Die Anfragen kommen vom Open-WebUI-Container, daher gilt der Docker-Hostname.
3. Im Chat das Modell `qwen2.5:7b` wählen und das Tool **ask_programming_question**
   aktivieren (Werkzeug-Symbol unter dem Eingabefeld).
4. Empfehlung: Unter *Arbeitsbereich → Modelle* ein eigenes Modell „Programmier-Lehrer" auf Basis
   von `qwen2.5:7b` anlegen, mit Systemprompt wie:
   *„Rufe bei jeder Frage zu Programmierung zuerst das Tool ask_programming_question auf und gib
   dessen Antwort samt Quellen wieder."*

Hinweise: Die Menübezeichnungen unterscheiden sich zwischen Open-WebUI-Versionen und müssen
ggf. angepasst werden. Auch ein 7B-Modell ruft Tools nicht immer zuverlässig auf – ein expliziter
Systemprompt (siehe oben) hilft; gegebenenfalls in den erweiterten Parametern des Modells den
Funktionsaufruf-Modus „Nativ" bzw. „Standard" ausprobieren.

**Sicherheit:** Im OpenAPI-Schema stehen nur `/ask` und `/health`. `/crawl`, `/learn` und
`/status` sind aus dem Schema ausgeblendet und nur mit Header `X-Admin-Token` erreichbar. Das
Sprachmodell kann Crawls daher nicht von selbst auslösen. Der Agent hat standardmäßig keinen
Host-Port; zum Debuggen in der Compose-Datei `127.0.0.1:8090:8090` freischalten:

```bash
curl -X POST http://127.0.0.1:8090/learn -H "X-Admin-Token: $(grep ^ADMIN_TOKEN .env | cut -d= -f2)"
curl http://127.0.0.1:8090/status -H "X-Admin-Token: ..."
```

## Konfiguration (`.env`)

| Variable | Standard | Bedeutung |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama-Container im Stack |
| `OLLAMA_KEEP_ALIVE` / `OLLAMA_HOST_PORT` | `30m` / `11434` | Wie lange Modelle im VRAM bleiben / lokaler Host-Port von Ollama (nur 127.0.0.1) |
| `OLLAMA_MODEL` | `qwen2.5:7b` | Antwortmodell |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding-Modell |
| `OLLAMA_NUM_CTX` | `8192` | Kontextfenster (Agent **und** Ollama-Standard via `OLLAMA_CONTEXT_LENGTH`) |
| `QDRANT_URL` / `COLLECTION_NAME` | `http://qdrant:6333` / `programming_knowledge` | Vektordatenbank |
| `CRAWL_DELAY_SECONDS` | `2` | Pause zwischen Anfragen (Minimum 2; `Crawl-delay` aus robots.txt hat Vorrang, falls höher) |
| `MAX_PAGES_PER_RUN` | `25` | Seiten pro Lernlauf |
| `CRAWL_INTERVAL_HOURS` | `24` | Intervall des Workers |
| `RECRAWL_AFTER_DAYS` | `30` | Wann bereits indexierte Seiten erneut geprüft werden |
| `RAG_TOP_K` / `RAG_MIN_SCORE` | `4` / `0.35` | Anzahl Treffer / Mindest-Ähnlichkeit |
| `RAG_QUERY_REWRITE` | `true` | Suchanfrage vorab ins Englische umformulieren |
| `ADMIN_TOKEN`, `WEBUI_SECRET_KEY` | zufällig | Von `setup.sh` erzeugt |
| `WEBUI_PORT` | `3001` | Host-Port von Open WebUI |

Nach Änderungen: Stack in Dockhand neu deployen bzw. `docker compose --env-file .env up -d`.

## Crawler-Verhalten

- Nur `www.w3schools.com`, nur freigegebene Pfade; `robots.txt` wird geladen und beachtet.
  Ist sie nicht eindeutig prüfbar (Netzwerkfehler, HTTP 5xx), bricht der Lauf ab. Bei HTTP 429/503
  der Seite ebenfalls.
- Mindestens 2 s Pause, maximal 25 Seiten pro Lauf, Seitenabruf nur per GET mit klarem User-Agent.
- Die Warteschlange füllt sich aus den Links der Seiten (Seitenmenü). Neue Seiten kommen vor
  Wiederholungen; fehlgeschlagene Seiten werden nach 24 h bis zu 3-mal erneut versucht.
- Inhalte werden anhand von Überschriften in Chunks (ca. 300–1200 Zeichen) zerlegt. Pro Chunk
  werden URL, Titel, Abschnitt, Thema, Zeitstempel und Inhalts-Hash gespeichert.
- Chunk-IDs sind deterministisch (URL + Index): Aktualisierte Seiten überschreiben, veraltete
  Chunks werden entfernt. Unveränderte Seiten (gleicher Hash) werden nicht neu eingebettet.
- Die Embedding-Dimension wird aus dem ersten echten Embedding bestimmt; die Collection wird
  entsprechend angelegt. Weicht die Dimension später ab (anderes Embedding-Modell), bricht der
  Lauf mit einer klaren Meldung ab.

**Hinweis zu Urheberrecht und Nutzungsbedingungen:** Die Inhalte gehören W3Schools. Prüfe vor
dem Betrieb die aktuellen Nutzungsbedingungen. Das System ist als privates Lernwerkzeug mit
kleinem Tempo gedacht; es gibt Quellen-URLs aus, ersetzt aber nicht die Originalseite. Die
Inhalte sollten nicht weiterveröffentlicht oder als Trainingsdaten für Fine-Tuning verwendet werden.
Bei Beanstandung: `CRAWL_INTERVAL_HOURS` hoch setzen oder den Worker stoppen.

Mit dem Standardlimit dauert das vollständige Lernen aller freigegebenen Bereiche viele
Wochen. Zum Fokussieren `allowed_prefixes`/`seeds` in `agent/app/crawler.py` einschränken
(Image neu bauen) oder `MAX_PAGES_PER_RUN` erhöhen.

## Weitere Wissensquellen ergänzen

In `agent/app/crawler.py` ein weiteres `Source(...)` anlegen (Host, Startseiten, erlaubte Pfade,
CSS-Selektor des Hauptinhalts, Ausschlussmuster) und in `SOURCES` eintragen. Danach Image neu
bauen. Parser, Chunking, robots.txt-Prüfung, Qdrant-Ablage und Worker laufen unverändert.
Neues Image bauen und Stack neu deployen:

```bash
docker build -t julia-school-agent:1.0 /Projekte/Festplatten/int0SSD0/agent
docker compose --env-file .env up -d --force-recreate julia-agent learning-worker
```

## Fine-Tuning (später)

Zuerst das RAG-System stabil betreiben. `training/` ist vorbereitet (siehe `training/README.md`).
Vor einem Training: eigene Trainingsdaten, GPU-Speicher und Modelllizenz prüfen.

## Fehlerbehebung

| Symptom | Ursache / Lösung |
|---|---|
| `ollama` startet nicht: „could not select device driver nvidia" | NVIDIA Container Toolkit fehlt oder Docker wurde nicht neu gestartet (siehe Voraussetzungen) |
| Notbehelf ohne GPU | Im Block `ollama:` der Compose-Datei `deploy:` und die beiden `NVIDIA_*`-Variablen entfernen – Ollama läuft dann auf der CPU (deutlich langsamer) |
| `/health` zeigt `ollama.reachable: false` | `docker ps` prüfen, `docker logs julia-school-ollama`; Modelle noch beim Laden? |
| Modell fehlt | `docker logs julia-school-ollama-models`; manuell: `docker exec julia-school-ollama ollama pull `qwen2.5:7b` bzw. `nomic-embed-text` |
| Port 11434 belegt | `OLLAMA_HOST_PORT` in `.env` ändern |
| „container name already in use" | Alter Container mit gleichem Namen: `docker rm -f <name>` |
| Dockhand: „unable to prepare context" | Es darf kein `build:` im Stack stehen – diese Compose-Datei nutzt nur das Image. Image zuvor per `setup.sh` bauen |
| „pull access denied for julia-school-agent" | Image existiert nicht auf dem Host: `./setup.sh` bzw. `docker build -t julia-school-agent:1.0 agent` |
| `ADMIN_TOKEN fehlt` beim Deploy | `.env` nicht an Dockhand übergeben bzw. `setup.sh` nicht gelaufen |
| Port 3001 belegt | `WEBUI_PORT` in `.env` ändern |
| Lernlauf „aborted": robots.txt | Netzwerkfehler oder Sperre – Internetzugang des Servers prüfen: `docker exec julia-school-agent python -c "import urllib.request;print(urllib.request.urlopen('https://www.w3schools.com/robots.txt').status)"` |
| Lernlauf „aborted": Dimension abweichend | Embedding-Modell gewechselt: neue `COLLECTION_NAME` setzen oder Collection löschen |
| „keine passenden Lerninhalte" | Lernlauf noch nicht gelaufen (`app.cli status`) oder `RAG_MIN_SCORE` senken (z. B. 0.25) |
| Open WebUI lädt beim Start lange / Fehler beim Modell-Download | Interne Embeddings laufen über Ollama (`RAG_EMBEDDING_ENGINE=ollama`); ohne Internet erscheinen einzelne Warnungen, die Chat-Funktion bleibt nutzbar |
| Tool wird vom Modell nicht aufgerufen | Systemprompt wie oben verwenden; alternativ `app.cli ask` zum Test der Pipeline |
| Logs ansehen | `docker logs -f julia-school-agent` / `julia-school-worker` |

## Wartung

```bash
docker exec julia-school-agent python -m app.cli status      # letzter Lauf, Statistik
docker logs --tail 100 julia-school-worker
tar czf backup-$(date +%F).tgz data/qdrant data/agent data/open-webui   # Backup (Stack vorher stoppen)
```

## Teststand

Parser, Chunking und die Shell-Logik (`.env`-Erzeugung, Syntax von `setup.sh`, Gültigkeit der
Compose-Datei) wurden lokal geprüft. Das Zusammenspiel mit echtem Docker, NVIDIA-Runtime, Ollama, Qdrant,
W3Schools und Open WebUI konnte hier nicht getestet werden – führe nach der Installation
die Schritte unter „Prüfen" und „Ersten Lernlauf starten" aus.
