# Prompt-Paket: Programming Learning Agent erweitern

Dieses Paket erweitert dein Projekt (`programming-learning-agent.zip`) um:

1. **Programmieren lernen und anwenden** (W3Schools, alle dort angebotenen Sprachen, plus Code-Ausführung in einer Sandbox)
2. **Lokale Wikipedia-Wissensbasis** aus den offiziellen Dumps
3. **Kontrollierte Selbstverbesserung** in regelmäßigen Abständen

## Aufbau

| Datei | Inhalt |
|---|---|
| `00-system-prompt.md` | Teil A: dauerhafter Systemprompt für den Entwicklungs-Agenten. Teil B: Systemprompt für das Laufzeitmodell in Open WebUI |
| `P0-fundament.md` | Mehrquellen-Architektur, Tests, Betrieb (4 Aufgaben) |
| `P1-w3schools-curriculum.md` | Alle W3Schools-Bereiche, Coverage, Sprachfilter (5 Aufgaben) |
| `P2-code-werkstatt.md` | Sandbox, Sprach-Runner, Übungen, Kompetenzmatrix (6 Aufgaben) |
| `P3-wikipedia-wissensdatenbank.md` | Dump-Download, SQLite + FTS5, Vektorindex, Hybridsuche, Updates (7 Aufgaben) |
| `P4-selbstverbesserung.md` | Eval, Telemetrie, Experimente mit Rollback, Berichte, Kill-Switch (6 Aufgaben) |

Jede Projektdatei enthält zuerst den **Projekt-Prompt** und danach die **Aufgaben-Prompts** in Ausführungsreihenfolge. Jeder Prompt steht in einem `text`-Block und kann direkt kopiert werden.

## So verwendest du es

1. Entwicklungs-Agenten (z. B. Claude Code) im Repo-Root starten. Teil A aus `00-system-prompt.md` als `CLAUDE.md` bzw. `AGENTS.md` ablegen.
2. Pro Projekt zuerst den Projekt-Prompt senden, dann die Aufgaben-Prompts nacheinander. Erst zur nächsten Aufgabe, wenn der Bericht (Geändert / Geprüft / Nicht geprüft / Annahmen / Offene Fragen) für dich plausibel ist.
3. Die Befehle, die der Agent nur „dokumentiert“, führst du auf dem Server aus (Docker, GPU, Internet). Nur dort lässt sich prüfen, ob es wirklich läuft.

## Empfohlene Reihenfolge

```
P0 -> P1 -> P2 ->  P4
        \-> P3 -/
```

P2 und P3 sind voneinander unabhängig. Vermeide aber, beide gleichzeitig GPU-lastig laufen zu lassen. P4 kommt zuletzt, weil es Messwerte aus den anderen Projekten braucht.

## Freigabe-Gates (der Agent stoppt hier und wartet auf dich)

| Gate | Wo | Entscheidung |
|---|---|---|
| G1 | P3 / T3.1 | Kapazitätsplan für Wikipedia (Platz, Dauer, welche Sprachausgaben und Tiers) |
| G2 | P2 / T2.4 | Sandbox-Sicherheit ist abgenommen, `run_code` darf aktiviert werden |
| G3 | P4 / T4.6 | Selbstverbesserung von `dry-run` auf `apply` schalten |
| G4 | P4 / T4.5 | Ein vom System vorgeschlagener Code-Patch wird übernommen |

## Was du wissen solltest (ehrliche Grenzen)

- **„Jede Programmiersprache über W3Schools“**: W3Schools deckt nur die Sprachen ab, für die es Tutorials gibt. P1 (T1.1) ermittelt diese Liste verbindlich. Für alles andere braucht es andere Quellen.
- **Lernen heißt hier Wissen im Index plus Üben mit Rückmeldung.** Ein 3B-Modell wird dadurch kein Senior-Entwickler. P2 macht das messbar (Kompetenzmatrix), statt es zu behaupten.
- **Wikipedia komplett** ist groß. Die deutsche Ausgabe hat etwa 3 Mio., die englische etwa 7 Mio. Artikel. Deshalb Phasen (simplewiki als Test, dann dewiki, dann enwiki), Stufen beim Embedding und ein Kapazitätsplan vor dem ersten großen Download.
- **Selbstverbesserung** bedeutet hier: Daten, Parameter und Prompts verbessern, mit Messung, Rollback und Kill-Switch. Das Modell selbst wird nicht trainiert, und das System ändert weder seinen eigenen Code noch seine Sicherheitsgrenzen.
- **Bereits im Projekt auffällig** (in P1/T1.1 zu verifizieren): Für C# und PHP gibt es keine Seeds, und die Endungsprüfung im Crawler lässt `.php`-Seiten (z. B. das C-Tutorial) vermutlich nicht durch.
- **Rechtliches**: W3Schools-Inhalte nur privat und höflich nutzen, die Nutzungsbedingungen prüfst du. Wikipedia-Text steht unter CC BY-SA 4.0, die Antworten nennen deshalb Quelle und Lizenz. Fine-Tuning mit W3Schools-Texten ist ausgeschlossen.

## Annahmen

- Die Prompts richten sich an einen leistungsfähigen Coding-Agenten, der in deinem Repository arbeiten darf. Das Laufzeitmodell (Llama 3.2 3B) bekommt nur den kurzen Systemprompt aus Teil B.
- Das Basismodell, das Embedding-Modell und die GPU bleiben wie in deinem Setup. Ein größeres Modell ist nicht vorausgesetzt.
- Den ZIP-Inhalt habe ich gelesen, aber nicht ausgeführt. Die Verdachtsmomente zum Crawler sind aus dem Quellcode abgeleitet und noch nicht am laufenden System bestätigt.
