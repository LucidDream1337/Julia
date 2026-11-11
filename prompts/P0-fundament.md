# P0 – Fundament (Mehrquellen-Architektur, Tests, Betrieb)

Voraussetzung für alle weiteren Projekte. Reihenfolge: T0.1 → T0.2 → T0.3 → T0.4.

## Projekt-Prompt

```text
PROJEKT P0 – FUNDAMENT

ZIEL
Das Repository für mehrere Wissensquellen („Corpora“), automatische Tests und sauberen Betrieb vorbereiten, ohne das bestehende Verhalten zu brechen. Danach können W3Schools (P1), Code-Werkstatt (P2), Wikipedia (P3) und Selbstverbesserung (P4) darauf aufbauen.

AUSGANGSLAGE
Genau eine Qdrant-Collection (COLLECTION_NAME), genau eine Quelle (SOURCES = (W3SCHOOLS,)), eine RAG-Pipeline mit festem Prompt, Query-Rewrite immer ins Englische, keine automatischen Tests.

NICHT-ZIELE
Keine neuen Inhalte laden, keine neuen Funktionen für Nutzer außer dem Parameter scope.

ARCHITEKTURENTSCHEIDUNGEN
- „Corpus“ = benannte Wissensquelle mit eigener Qdrant-Collection, eigenem Antwortprompt, Lizenzhinweis und Verfügbarkeitsprüfung. Zunächst: programming (bestehend), wikipedia (angelegt, aber inaktiv bis P3).
- /ask bekommt das optionale Feld scope ("auto" | "programming" | "wikipedia"). Das Standardverhalten bleibt für bestehende Aufrufer identisch.
- Tests laufen ohne Netz und ohne Docker.

ABNAHME DES PROJEKTS
pytest ist grün, docs/ARCHITECTURE.md und docs/FINDINGS.md existieren, /ask liefert für programming dasselbe wie vorher, docker compose config ist gültig (falls Docker vorhanden), Backup-Skript und Smoke-Test sind dokumentiert.

Halte dich an den Systemprompt (Regeln, Gates, Berichtsformat). Warte auf die einzelnen Aufgaben-Prompts.
```

---

## Aufgaben-Prompts

### T0.1 – Baseline und Testfundament

```text
AUFGABE T0.1 – BASELINE UND TESTFUNDAMENT

1. Lies das komplette Repository (agent/app/*, Dockerfile, docker-compose.yaml, setup.sh, README). Lege ein Git-Repository an, falls keines existiert, und prüfe .gitignore (.env, data/ dürfen nie committet werden).
2. Lege requirements-dev.txt an (pytest, ruff). Diese Pakete gehören nicht ins Produktions-Image.
3. Schreibe Charakterisierungstests, die das heutige Verhalten festhalten: normalize_url, Source.accepts, build_chunks, point_id, rag._build_context, require_admin. Ollama und Qdrant werden durch Fakes ersetzt (Qdrant ggf. über QdrantClient(":memory:")).
4. Schreibe docs/ARCHITECTURE.md (Ist-Zustand, Datenfluss als Textdiagramm, Zuständigkeiten je Modul).
5. Schreibe docs/FINDINGS.md: alle Fehler und Risiken, die dir beim Lesen auffallen (mit Datei, Zeile, Auswirkung, Vorschlag). Behebe nur Triviales. Alles andere wird in P1–P4 behoben.

FERTIG, WENN: pytest läuft ohne Netz und ohne Docker grün, ruff meldet nichts Kritisches, FINDINGS.md liegt vor.
```

### T0.2 – Corpus-Abstraktion

```text
AUFGABE T0.2 – CORPUS-ABSTRAKTION

1. Neues Modul agent/app/corpus.py: Dataclass Corpus (name, collection, description, license_note, answer_prompt, available()) und eine Registry. Eingetragen werden programming (Collection aus COLLECTION_NAME) und wikipedia (Collection-Präfix aus WIKI_COLLECTION_PREFIX, available() ist false, solange keine Collection existiert).
2. Store erhält die Collection als Konstruktorparameter (Default = bisheriges Verhalten). rag.ask(question, corpus=...) wählt Prompt und Store je Corpus.
3. Der Query-Rewrite wird je Corpus konfigurierbar: programming übersetzt wie bisher ins Englische, wikipedia nutzt die Sprache der Frage (wird in P3 gebraucht).
4. Verhalten für programming bleibt bitgleich. Alle Tests aus T0.1 bleiben ohne Änderung grün; ergänze Tests für die Registry.

RANDBEDINGUNG: keine Migration, kein Umbenennen der vorhandenen Collection.
FERTIG, WENN: Tests grün und `python -m app.cli ask ...` verhält sich wie vorher.
```

### T0.3 – Router und API

```text
AUFGABE T0.3 – ROUTER UND API

1. POST /ask: neues optionales Feld scope ("auto" | "programming" | "wikipedia", Default "auto"). Die Antwort wird um corpus und attribution (Lizenz-/Quellenhinweis) erweitert. Alle bestehenden Felder bleiben unverändert.
2. Auto-Router: zuerst regelbasiert (Programmiersprachen-Namen, Code-Marker wie "def ", "SELECT", Dateiendungen, Wörter wie "Fehler", "Syntax"), nur bei Unsicherheit ein kurzer LLM-Aufruf mit temperature 0. Ist ein Corpus nicht verfügbar, wird auf programming zurückgefallen und das in der Antwort vermerkt.
3. Formuliere summary und description des OpenAPI-Eintrags so, dass ein 3B-Modell das Tool korrekt wählt: kurz, mit je einem Positiv- und Negativbeispiel pro scope.
4. Ist ein explizit gewählter Corpus leer oder nicht verfügbar: HTTP 503 mit klarer Meldung und nächstem Schritt.
5. Tests: Tabelle mit mindestens 30 Beispielfragen (deutsch und englisch) und erwartetem scope.

FERTIG, WENN: Router-Tests grün, OpenAPI-Schema (/openapi.json) enthält weiterhin nur /ask und /health, Admin-Endpunkte bleiben versteckt.
```

### T0.4 – Betrieb, Backup, Smoke-Test

```text
AUFGABE T0.4 – BETRIEB, BACKUP, SMOKE-TEST

1. docker-compose.yaml und setup.sh: Verzeichnis data/wikipedia anlegen, neue ENV-Variablen aus T0.2/T0.3 aufnehmen, Image-Tag auf 1.1 anheben (setup.sh baut ihn), Ressourcenlimits für programming-agent und learning-worker prüfen. Weiterhin kein build: in der Compose-Datei.
2. scripts/backup.sh: Qdrant-Snapshot über die API und `sqlite3 .backup` für state.db nach data/backups/<Datum>/, Rotation (letzte 5 behalten). Schreibe eine Restore-Anleitung. Qdrant ist nur im Docker-Netz erreichbar – das Skript muss das berücksichtigen (z. B. docker exec).
3. scripts/smoke.sh: /health, ein /ask-Aufruf, /status – mit klaren OK/FEHLER-Zeilen.
4. README aktualisieren (Struktur, neue Variablen, Backup, Smoke-Test) und den Abschnitt „Teststand“ ehrlich pflegen.

FERTIG, WENN: `docker compose --env-file .env config` ist gültig (falls Docker verfügbar, sonst als nicht geprüft markieren), Backup und Restore sind beschrieben, fremde Container werden nirgends referenziert.
```
