# Julia

Eine kleine, freundliche KI für den Alltag, die schrittweise Wissensdatenbanken aufbaut (W3Schools, Wikipedia, Pflanzenatlas) und dich bei Projekten unterstützt.

```
Open WebUI  ──►  Ollama-Modell "julia" (qwen3:4b + kurzer Systemprompt)
     │
     └─ Werkzeuge ──►  julia-service (FastAPI)  ──►  Qdrant (eine Collection je Wissensdatenbank)
                         ├─ skills/    kurze Arbeitsanleitungen, die Julia bei Bedarf liest
                         └─ presets/   Quellen-Vorlagen (w3schools, wikipedia, plantatlas)
```

Der Service erledigt das Deterministische (crawlen, zerlegen, einbetten, suchen). Julia entscheidet, fragt dich und führt dich Schritt für Schritt. Skills sind Rezepte von 20 bis 30 Zeilen statt langer Prompts.

## Installation

Voraussetzungen: Linux-Server mit Docker, NVIDIA-GPU mit NVIDIA Container Toolkit. Das Standardmodell `qwen3:4b` passt komplett in 6 GB VRAM (z. B. RTX 2060).

1. ZIP entpacken (z. B. nach `/Projekte/Festplatten/int0SSD0`) und in den Ordner wechseln.
2. `./setup.sh` ausführen. Es legt `.env` an, fragt nach einem Crawler-Kontakt (E-Mail oder URL) und baut das Image `julia-service:1.0`.
3. `docker compose --env-file .env up -d` (oder in Dockhand: Compose-Inhalt einfügen, Inhalt der `.env` als Umgebungsvariablen eintragen).
4. `docker logs -f julia-init` abwarten, bis dort „Fertig: Modell julia ist bereit.“ steht (Download rund 3 GB).

Open WebUI: `http://<server-ip>:3001`

## Open WebUI einrichten (einmalig)

1. **Konto anlegen.** Das erste Konto wird Admin. Danach in `.env` `WEBUI_ENABLE_SIGNUP=false` setzen und den Stack neu starten.
2. **Tool-Server verbinden:** Admin-Bereich → Einstellungen → Externe Tools → „+“. URL `http://julia-service:8090`, Pfad `openapi.json`, Authentifizierung keine. Speichern. Es erscheint „Julia Wissen“.
3. **Modell `julia` einstellen:** Admin-Bereich → Modelle → julia:
   - Werkzeuge: „Julia Wissen“ anhaken (damit es in jedem Chat aktiv ist)
   - Fähigkeiten: Websuche aktivieren, und unter Standard-Funktionen ebenfalls Websuche anhaken
   - Erweiterte Parameter: Funktionsaufruf auf **Nativ** stellen (Bezeichnung kann je nach Version leicht abweichen)
4. Im Chat das Modell **julia** wählen.

Die Websuche (DuckDuckGo) ist in der Compose-Datei vorkonfiguriert, Open WebUI übernimmt solche Werte aber nur beim ersten Start. Was du im Admin-Panel speicherst, hat danach Vorrang.

## Erste Schritte mit Julia

Schreib ihr zum Beispiel:

- „Welche Skills hast du?“
- „Lege eine Wissensdatenbank für W3Schools Python an.“
- „Lerne Wikipedia-Artikel zur Kategorie Heilpflanze (deutsch).“
- „Sichere den Pflanzenatlas.“

Sie liest das passende Skill, legt die Datenbank an und macht einen **Plan** (robots.txt, Umfang, Dauer). Erst nach deinem Ja startet sie einen Probelauf mit 10 Seiten, dann den Vollauf. Bei W3Schools und Plantatlas liest sie dir vorher den Nutzungshinweis vor und braucht deine ausdrückliche Bestätigung.

## Was fest eingebaut ist

- `robots.txt` ist bindend, mindestens 2 Sekunden Pause, eine Verbindung, nur GET, User-Agent mit deinem Kontakt.
- Abbruch bei HTTP 429/503 und bei gehäuftem 403. Keine Umgehung von Sperren.
- Ein Lauf gleichzeitig, harte Obergrenze `HARD_MAX_PAGES` (5000). Läufe sind jederzeit stoppbar und später fortsetzbar (unveränderte Seiten werden übersprungen).
- Wikipedia läuft über die offizielle API (nicht über Crawling der normalen Seiten), nur ausgewählte Themen.

## Eigene Quellen und Skills

- Neue Vorlage: JSON-Datei in `presets/` (Beispiele dort). Eine Web-Quelle braucht `seeds`, optional `allowed_prefixes`, `content_selector` und `exclude_pattern`.
- Neues Skill: Markdown-Datei in `skills/` (erste Zeile Titel, zweite Zeile Beschreibung). Kein Neubau nötig, es gilt sofort.
- Systemprompt ändern: `julia/system-prompt.md`, dann `docker start -a julia-init` (baut das Modell `julia` neu).

## Modell wechseln

Passende Modelle je nach VRAM: 6 GB `qwen3:4b` (Standard, komplett auf der GPU), 8 GB `qwen3:8b`, ab 12 GB `qwen3:14b`. `qwen3:8b` läuft auf 6 GB nur teilweise auf der GPU und ist deutlich langsamer. In `.env` `OLLAMA_MODEL` ändern, dann `docker compose --env-file .env up -d --force-recreate julia-init`. Nach einem Wechsel von `EMBED_MODEL` müssen Wissensdatenbanken neu angelegt werden (andere Vektorgröße).

## Fehlersuche

- Julia fragen: „Ruf service_status auf.“ (prüft Ollama, Qdrant, Embedding-Modell, Crawler-Kontakt)
- `docker logs julia-service`, `docker logs julia-init`
- `docker exec julia-ollama ollama ps` zeigt, ob das Modell komplett auf der GPU läuft. Steht dort nicht „100% GPU“, `NUM_CTX=4096` setzen oder ein kleineres Modell wählen.
- Ruft Julia keine Werkzeuge auf: Funktionsaufruf auf „Nativ“ prüfen und ob „Julia Wissen“ beim Modell angehakt ist.

## Entwickeln

`AGENTS.md` enthält die Hinweise für Entwicklungs-Agenten (z. B. Hermes). Tests: `cd service && pip install -r requirements-dev.txt && pytest` (laufen ohne Netz und Docker).

## Ehrliche Grenzen

- Julia mit einem kleinen Modell (4B bis 14B) führt Schritt für Schritt durch Aufgaben, arbeitet aber nicht vollständig allein. Bei Unklarem fragt sie nach.
- Dateien ändern oder Programme ausführen kann sie nur mit zusätzlichen Werkzeugen. Das Skill „Projekt leiten“ arbeitet im Chat.
- Der Pflanzenatlas wird nur als Text gesichert (keine Bilder). Die Vorlage ist nach den Angaben der Startseite aufgebaut und wurde nicht gegen die echte Seite getestet. Der Plan zeigt vorher, was gefunden wird.
- Antworten zu Giftigkeit oder Essbarkeit von Pflanzen immer selbst gegenprüfen.
