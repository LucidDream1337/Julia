# P4 – Selbstverbesserung (kontrolliert, messbar, rückholbar)

Voraussetzung: P0, P1; sinnvoll nach P2 und P3 (liefern Kompetenzmatrix und zweiten Corpus). Reihenfolge: T4.1 → T4.2 → T4.3 → T4.4 → T4.5 (optional) → T4.6.

## Projekt-Prompt

```text
PROJEKT P4 – SELBSTVERBESSERUNG

ZIEL
In regelmäßigen Abständen soll sich das System messbar verbessern, ohne sich selbst zu gefährden.

WAS „BESSER WERDEN“ HIER HEISST (ehrlich)
Die Modellgewichte bleiben unverändert (kein Fine-Tuning). Verbessert werden: (1) Daten, indem Lücken erkannt und gezielt gefüllt werden, (2) Retrieval-Parameter und Prompts, (3) Glossar und Synonyme, (4) Übungsschwerpunkte, (5) optional und nur als Vorschlag: Code. Bei einem 14B-Modell kommt der größte Gewinn aus Datenabdeckung und Retrieval, nicht aus „klügerem Denken“.

AUTONOMIESTUFEN
- Stufe A (autonom innerhalb Leitplanken, mit automatischem Rollback): Retrieval-Parameter (Whitelist), Prompt-Varianten aus einem versionierten Katalog, Crawl-/Embedding-Priorisierung, Glossar, Übungsschwerpunkte.
- Stufe B (nur Vorschlag, Freigabe G4): Code-Patches. Der Agent wendet sie nie selbst an.
- Stufe C (verboten): Sicherheits-, Höflichkeits- und Sandbox-Grenzen, Admin-Token, Compose-Datei, Netzwerkfreigaben, neue Domains als Quellen, Löschen von Daten, Änderungen an Modellgewichten.

EVAL-FIRST-PRINZIP
Keine Änderung ohne Messung vorher/nachher. Golden-Set mit Dev/Test-Split. Eine Änderung wird nur übernommen, wenn sie auf Dev und Test besser ist (Mindestabstand), Sicherheitsfälle nicht schlechter werden und die Latenz im Rahmen bleibt. Bei Regression sofortiger Rollback. Jede Änderung ist eine versionierte Konfiguration mit Changelog.

PRIVATSPHÄRE
Telemetrie nur lokal, ohne Nutzerkennung, mit begrenzter Aufbewahrung (Default 90 Tage), abschaltbar.

KILL-SWITCH UND BUDGET
SELF_IMPROVE_ENABLED=false und SELF_IMPROVE_MODE=dry-run als Standard. Stopp-Datei data/agent/STOP beendet alles sofort. Zeit- und GPU-Budget pro Nacht. Jobs laufen nie parallel zu Wikipedia-Embedding und lassen Chat-Anfragen Vorrang.

GATE
G3: Erste Aktivierung (und der Wechsel von dry-run auf apply) nur nach ausdrücklicher Freigabe, frühestens nach einer Woche dry-run-Berichten.

ABNAHME DES PROJEKTS
Eval-Harness mit eingefrorener Baseline, Telemetrie und Lückenliste, Experiment-Runner mit Promotion und Rollback, Wochenbericht, Kill-Switch getestet, Abnahmeprotokoll.

Halte dich an den Systemprompt. Warte auf die einzelnen Aufgaben-Prompts.
```

---

## Aufgaben-Prompts

### T4.1 – Golden-Set und Eval-Harness

```text
AUFGABE T4.1 – GOLDEN-SET UND EVAL-HARNESS

1. Verzeichnis eval/golden/*.jsonl, Schema: id, corpus, language, question, question_language, expected_urls oder expected_titles, must_contain_keywords, type (retrieval | answer | code | safety), split (dev | test), origin (manual | synthetic).
2. Lege ein Seed-Set an: eigene Formulierungen, nicht aus W3Schools-Texten abgeschrieben. Mindestens 20 Fragen je Kernsprache (Python, JavaScript, SQL, Java, C/C++/C# gemischt, HTML/CSS), 30 Wikipedia-Fragen, 10 Sicherheitsfälle (Prompt-Injection in Auszügen, Fragen außerhalb des Wissens -> ehrliche Absage). Kennzeichne synthetische Fragen und weise darauf hin, dass der Betreiber das Set mit eigenen Fragen ergänzen sollte.
3. Metriken: Hit@k, MRR, Keyword-Abdeckung der Antwort, Latenz, Code-pass-rate (aus P2, falls aktiv). LLM-als-Richter höchstens als Zusatzsignal, nie allein (ein 14B-Modell ist ein schwacher Richter).
4. `cli eval --corpus programming --split dev` erzeugt JSON- und Markdown-Report. Deterministisch: temperature 0, feste Reihenfolge, feste Seeds.
5. Baseline einfrieren unter eval/baselines/<datum>.json und Vergleichsbefehl `cli eval --compare <baseline>`.
6. Tests mit Fake-Retriever für die Metrikberechnung.

FERTIG, WENN: Baseline-Report für programming liegt vor, Metrik-Tests grün.
```

### T4.2 – Telemetrie und Lückenliste

```text
AUFGABE T4.2 – TELEMETRIE UND LÜCKENLISTE

1. SQLite data/agent/telemetry.db: Zeitpunkt, Corpus, erkannte Sprache, Frage (gekürzt), bester Score, knowledge_found, Anzahl Quellen, Dauer, Fehler. Keine Nutzerkennung, keine IP-Adressen. Aufbewahrung per ENV (TELEMETRY_RETENTION_DAYS, Default 90), tägliches Aufräumen. Abschaltbar (TELEMETRY_ENABLED).
2. `cli gaps`: häufige Fragen ohne Treffer oder mit niedrigem Score, nach Thema und Sprache gruppiert (einfaches Clustering, z. B. über Embeddings oder Schlüsselwörter), mit Zählern und Beispielfragen.
3. Die Telemetrie darf Antworten nie verlangsamen (asynchron oder Batch-Schreiben, Fehler werden verschluckt und geloggt).
4. Dokumentiere Datenschutz im README (was gespeichert wird, wie man es abschaltet, wie man es löscht).

FERTIG, WENN: Tests (Retention, Abschaltung, Fehlerfall) grün und `cli gaps` liefert mit Testdaten eine sinnvolle Liste.
```

### T4.3 – Konfigurationsversionierung und Experiment-Runner

```text
AUFGABE T4.3 – KONFIGURATIONSVERSIONIERUNG UND EXPERIMENT-RUNNER

1. Tunable-Whitelist (nur diese darf der Runner verändern): RAG_TOP_K, RAG_MIN_SCORE, Query-Rewrite an/aus, Gewichte der Hybridsuche, RAG_MAX_CONTEXT_CHARS, Auswahl einer Prompt-Variante aus data/agent/prompts/*.txt (versionierter Katalog). Chunk-Größen ändern erfordern Re-Embedding und sind deshalb nur ein Vorschlag mit Kostenabschätzung, nie automatisch.
2. active_config.json (versioniert, mit Changelog). Der Agent liest sie beim Start und mit kurzem Cache je Anfrage; ENV-Werte bleiben Fallback und Obergrenze. `cli config show|history|rollback <version>`.
3. Runner: Kandidaten (kleines Grid oder Zufallssuche mit Obergrenze an Läufen) -> eval auf dev -> bester Kandidat -> eval auf test plus Sicherheitsfälle -> Promotion nur bei Mindestverbesserung (Parameter, Vorschlag: +2 Prozentpunkte Hit@4 oder MRR) bei Latenz höchstens 120 % der Baseline und ohne Verschlechterung der Sicherheitsfälle. Sonst verwerfen. Jede Entscheidung wird begründet protokolliert.
4. Automatischer Rollback: Nach Promotion läuft eine Kontrollmessung. Bei Regression Rückkehr zur Vorversion.
5. Im Modus dry-run werden Kandidaten gemessen und berichtet, aber nicht aktiviert.
6. Tests: Promotion, Ablehnung, Rollback, Whitelist-Verletzung (muss hart abgelehnt werden).

FERTIG, WENN: Tests grün und ein vollständiger dry-run auf Fixtures ist dokumentiert.
```

### T4.4 – Lückengetriebenes Lernen

```text
AUFGABE T4.4 – LÜCKENGETRIEBENES LERNEN

Leite aus Lückenliste (T4.2) und Kompetenzmatrix (P2) konkrete Lernziele ab und setze sie innerhalb der Budgets um:
a) W3Schools: fehlende oder veraltete Seiten der betroffenen Sprache im Frontier vorziehen (nur bereits erlaubte Quellen und Pfade, Höflichkeitsregeln unverändert).
b) Wikipedia: Artikel, nach denen gefragt wurde und die nur als Lead vorliegen, für Tier-2-Volltext-Embedding vormerken (nur wenn P3 aktiv ist).
c) Glossar/Synonyme: Begriffs-Zuordnungen (deutsch -> englisch, Alias-Begriffe) in data/agent/glossary.json pflegen und im Query-Rewrite nutzen. Einträge müssen belegt sein (Quelle) und werden per Eval geprüft.
d) Übungen: für schwache Themen der Kompetenzmatrix zusätzliche Aufgaben generieren (P2, nur wenn aktiv).
Jede Maßnahme wird mit Anlass, Umfang und Ergebnis protokolliert. Keine neuen Domains, keine Änderung der Crawler-Grenzen.

FERTIG, WENN: Tests mit Fake-Telemetrie belegen Ableitung und Priorisierung; Protokolleinträge sind nachvollziehbar.
```

### T4.5 – Code-Verbesserungsvorschläge (optional, Stufe B)

```text
AUFGABE T4.5 – CODE-VERBESSERUNGSVORSCHLÄGE (OPTIONAL, STANDARD: AUS)

Hinweis: Ein 14B-Modell schreibt nur eingeschränkt brauchbare Patches. Baue diese Funktion deshalb als Vorschlags-Pipeline mit harter Qualitätsprüfung und standardmäßig deaktiviert (PROPOSALS_ENABLED=false). Wenn du während der Umsetzung feststellst, dass der Nutzen fehlt, dokumentiere das und empfiehl, die Aufgabe zu streichen.

1. Arbeit ausschließlich auf einer Kopie des Quellcodes (data/agent/workspace/), nie am laufenden Code.
2. Eingaben: Telemetrie-Fehler, Fehlerlogs, Eval-Schwächen. Ausgabe je Vorschlag: data/agent/proposals/<id>/{patch.diff, report.md, eval-diff.json}.
3. Ein Vorschlag wird nur behalten, wenn Tests grün sind und die Eval nicht schlechter wird. Sonst verwerfen mit Grund.
4. Denylist (niemals ändern): Sicherheits- und Höflichkeitsgrenzen in config.py/crawler.py, sandbox/, docker-compose.yaml, setup.sh, .env*, Admin-Authentifizierung, diese Denylist selbst. Verletzungen führen zum Verwerfen.
5. `cli proposals list|show <id>`. Anwenden macht ausschließlich der Betreiber manuell (Git-Branch, Review, Gate G4). Es gibt keinen automatischen Apply-Befehl für das System selbst.

FERTIG, WENN: Tests belegen Denylist, Qualitätsprüfung und dass nie automatisch angewendet wird.
```

### T4.6 – Scheduler, Berichte, Kill-Switch und Abnahme

```text
AUFGABE T4.6 – SCHEDULER, BERICHTE, KILL-SWITCH UND ABNAHME

1. Worker-Zyklus: learn (P1) -> practice (P2, falls aktiv) -> eval -> experiment (T4.3) -> gap-learning (T4.4) -> report. Erweitere RunLock so, dass die Reihenfolge und das Ausschließen paralleler GPU-Jobs (Wikipedia-Embedding, Übungen) gewährleistet sind. Zeit- und GPU-Budget pro Nacht (SELF_IMPROVE_BUDGET_MINUTES), Chat hat Vorrang.
2. Modi: SELF_IMPROVE_ENABLED (Default false), SELF_IMPROVE_MODE=dry-run|apply (Default dry-run). Stopp-Datei data/agent/STOP wird vor jedem Teilschritt geprüft und beendet den Zyklus sauber.
3. Wochenbericht data/agent/reports/<Jahr>-W<Woche>.md: Coverage je Sprache, Kompetenzmatrix, Eval-Trend gegenüber Baseline, durchgeführte und verworfene Änderungen, Rollbacks, offene Vorschläge, Budgetverbrauch. Kurzfassung in /status.
4. Sicherheitstests: Stopp-Datei wirkt, Whitelist wird durchgesetzt, Rollback funktioniert, Telemetrie-Ausfall legt den Betrieb nicht lahm.
5. Abnahmeprotokoll docs/acceptance-P4.md inkl. Betreiber-Checkliste für Gate G3: mindestens eine Woche dry-run-Berichte prüfen, Baseline und Trend ansehen, dann erst SELF_IMPROVE_MODE=apply. Aktiviere nichts selbst.

FERTIG, WENN: Protokoll vorliegt und G3 klar als Entscheidung des Betreibers benannt ist.
```
