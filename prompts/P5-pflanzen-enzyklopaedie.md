# P5 – Pflanzen-Enzyklopädie (plantatlas.bio lokal sichern)

Voraussetzung: P0 (Corpus-Abstraktion, Router). Unabhängig von P1–P4. Reihenfolge: T5.1 → T5.2 → T5.3 → T5.4 → T5.5 → T5.6 → T5.7.

## Rechtlicher Rahmen

Du legst die Kopie ausschließlich für den **privaten Gebrauch** an (du wohnst in Deutschland), ohne sie weiterzugeben, zu veröffentlichen oder kommerziell zu nutzen. Zweck ist die Sicherung für den Fall, dass die Seite nicht mehr erreichbar ist. Dieser Rahmen ist in P5 als Erklärung des Betreibers hinterlegt. Der Agent bewertet die Rechtslage nicht und stoppt deswegen nicht.

Fest bleiben die technischen Grenzen, die diesen Rahmen stützen: `robots.txt` ist bindend, technische Zugangsbeschränkungen werden nicht umgangen, nichts wird nach außen ausgeliefert. Ein Stopp (Gate G5) erfolgt nur, wenn eine dieser Grenzen berührt wird (siehe Projekt-Prompt).

## Projekt-Prompt

```text
PROJEKT P5 – PFLANZEN-ENZYKLOPÄDIE (plantatlas.bio)

ZIEL
Eine lokale Privatkopie von https://plantatlas.bio/ inklusive der Bilder als Sicherung für den Fall, dass die Seite nicht mehr erreichbar ist, und darauf aufbauend eine durchsuchbare Pflanzen-Enzyklopädie. Der Agent beantwortet Pflanzenfragen aus dieser Wissensbasis mit Quellenangabe und kann das passende Bild mitliefern. Weil der Zweck die Sicherung ist, haben Vollständigkeit und Wiederherstellbarkeit des Archivs Vorrang vor Komfort.

BEKANNTE FAKTEN (aus der Startseite, in T5.1 zu verifizieren)
- Etwa 3.000 Pflanzenseiten und etwa 1.200 Glossarbegriffe; Sprachen Englisch und Russisch.
- URL-Muster: /plants/<slug>-<id>/ (Pflanzen), /plants/category/<slug>-<id>/ (Kategorien), /glossary/<id>/ und /glossary/category/<slug>-<id>/ (Glossar), Bilder unter /assets/i/encyclopedia/<größe>/<slug>-<id>.jpg (z. B. 800_600).
- Die Seite enthält einen Nutzungshinweis (Materialien nur mit Erlaubnis der Rechteinhaber). Er wird in T5.1 wörtlich dokumentiert und bei jedem Lauf auf Änderungen geprüft.

RECHTLICHER RAHMEN UND GATE G5 (verbindlich)
- Erklärung des Betreibers (wohnhaft in Deutschland): Die Kopie wird ausschließlich zum privaten Gebrauch angelegt, als Sicherung für den Fall, dass die Seite nicht mehr erreichbar ist. Keine Weitergabe, keine Veröffentlichung, keine kommerzielle Nutzung, keine Verwendung als Trainingsdaten. Die Erklärung steht in docs/plantatlas-rights.md (Datum trägt der Betreiber ein). Der Agent bewertet die Rechtslage nicht und braucht keine weitere Freigabe, solange keine Stopp-Bedingung eintritt.
- Feste Grenzen: robots.txt ist bindend. Keine Umgehung technischer Zugangsbeschränkungen (Login, Captcha, Bezahlschranke, Bot-Sperren, wechselnde Identitäten oder User-Agents). Auslieferung nur im lokalen Netz. Jede Ausgabe nennt Quelle und Abrufdatum.
- Stopp-Bedingungen (Gate G5): Der Agent hält an und meldet dem Betreiber, wenn (a) robots.txt das Crawlen der Zielpfade sperrt, (b) die Seite Zugangsbeschränkungen einsetzt oder dauerhaft mit HTTP 403/429/503 ablehnt, (c) sich der Nutzungshinweis der Seite ändert (Text wird bei jedem Lauf mit dem gespeicherten verglichen). Der Betreiber entscheidet dann über das Weitere.

CRAWL-REGELN (zusätzlich zum Systemprompt)
- Nur Host plantatlas.bio. Mindestens 2 s Pause (bei Crawl-delay in robots.txt der höhere Wert), eine Verbindung, nur GET, klarer User-Agent mit Kontakthinweis, Abbruch bei HTTP 429/503.
- URLs werden nur aus den abgerufenen Seiten gelesen (Links, img-Tags, srcset). Pfade werden nie geraten oder durchprobiert.
- Nur Bildvarianten, die auf den Seiten referenziert sind. Pro Bild die größte referenzierte Variante speichern, kleinere nur, wenn sie allein vorkommen.
- Ein Abbruch ist jederzeit sauber möglich, ein Neustart setzt fort (kein erneutes Laden von bereits gesicherten und unveränderten Dateien: ETag/Last-Modified, sonst Hash-Vergleich).

ARCHITEKTUR (verbindlich)
- Schicht 1 „Archiv“ (Rohdaten, unverändert): data/plants/raw/ mit HTML je Seite (komprimiert) und data/plants/images/<sha256[:2]>/<sha256>.<ext>. Manifest in SQLite (url, final_url, status, content_type, sha256, bytes, fetched_at, etag, last_modified, source_page). Dedupe über sha256.
- Schicht 2 „Wissensbasis“ (abgeleitet, jederzeit aus Schicht 1 neu aufbaubar): SQLite data/plants/plants.db mit plants, categories, glossary_terms, images und FTS5, dazu Qdrant-Collection plants_<lang> für die semantische Suche.
- Corpus plants wird in Registry und Router (P0) eingetragen, scope "plants".

SICHERHEIT BEI PFLANZENAUSKÜNFTEN
Antworten zu Giftigkeit, Essbarkeit oder Heilwirkung dürfen ausschließlich aus den gefundenen Auszügen stammen. Fehlt die Angabe, sagt der Agent das klar („dazu steht nichts in der Datenbank“) und rät nie. Jede Antwort zu diesen Themen enthält den Hinweis, dass eine Pflanzenbestimmung per Text/Bild unsicher ist und im Zweifel nichts verzehrt oder angewendet werden darf.

NICHT-ZIELE
Pflanzenbestimmung per Foto, Weitergabe/Veröffentlichung, Crawlen anderer Seiten, Fine-Tuning.

ABNAHME DES PROJEKTS
Rechterahmen und Seitenhinweis dokumentiert, keine offene G5-Stopp-Bedingung, Archiv vollständig mit Integritätsnachweis, Wissensbasis und Suche funktionieren, Antworten enthalten Quelle und (wo vorhanden) Bild, Backup und Wiederherstellung getestet.

Halte dich an den Systemprompt. Warte auf die einzelnen Aufgaben-Prompts.
```

---

## Aufgaben-Prompts

### T5.1 – Erkundung und Dokumentation

```text
AUFGABE T5.1 – ERKUNDUNG UND DOKUMENTATION

Lade in dieser Aufgabe höchstens die folgenden Seiten, jeweils einmal: robots.txt, Startseite, Kontaktseite, eine Pflanzenseite, eine Glossarseite, eine Kategorieseite, die Seite „Alle Pflanzen“ (die erste und zweite Listenseite), ein Bild dieser Pflanzenseite (Größe, Content-Type, Cache-Header).

1. robots.txt: fasse zusammen, was erlaubt oder gesperrt ist (Crawl-delay, Disallow, Sitemap). Prüfe die Stopp-Bedingungen (a) und (b) aus dem Projekt-Prompt.
2. Nutzungshinweis: gib den Hinweis der Seite in kurzen wörtlichen Zitaten wieder (je unter 15 Wörter) und speichere seinen Text-Hash für den Änderungsvergleich (Bedingung c). Interpretiere ihn nicht rechtlich.
3. Technik: URL-Muster, Paginierung, Sprachvarianten (Englisch/Russisch: wie erreichbar, gleiche Struktur?), Bildvarianten und -größen, die auf den Seiten referenziert sind, Aufbau einer Pflanzenseite und eines Glossareintrags, Sitemaps (falls vorhanden zur Entdeckung bevorzugen).
4. Mengen: Seitenzahl, Bildzahl, Speicherbedarf und Crawl-Dauer bei 2 s Pause (Formel und Unsicherheit angeben). Prüfe vorher den freien Speicherplatz auf dem Datenträger von data/.
5. Schreibe docs/plantatlas-rights.md mit: der Erklärung des Betreibers im Wortlaut des Projekt-Prompts (Datumsfeld für den Betreiber offen lassen), dem Seitenhinweis, der robots.txt-Zusammenfassung und den Ergebnissen aus 3 und 4.
6. Optional und nur, wenn der Betreiber das möchte: ein kurzer, freundlicher Entwurf (Deutsch/Englisch) einer Info-Mail an die Betreiber der Seite. Nicht senden.

FERTIG, WENN: das Dokument vorliegt und keine Stopp-Bedingung eingetreten ist. Dann geht es mit T5.2 weiter. Tritt eine ein, halte an (Gate G5) und melde sie dem Betreiber mit Beleg.
```

### T5.2 – Archiv-Crawler (Rohdaten und Bilder)

```text
AUFGABE T5.2 – ARCHIV-CRAWLER

Gilt, solange keine Stopp-Bedingung (G5) eingetreten ist.
1. Neues Modul agent/app/plants/archive.py und CLI `cli plants archive --lang all|en|ru [--max-pages N]`. Standard ist alle über Links erreichbaren Sprachvarianten, damit die Sicherung vollständig ist. Entdeckung über Sitemap oder Kategorie-/Listenseiten, Warteschlange und Zustand in SQLite (Frontier-Muster wie db.py).
2. Abruf nach den CRAWL-REGELN des Projekt-Prompts. Seiten als komprimiertes HTML in data/plants/raw/. Bilder aus img-Tags und srcset der abgerufenen Seiten, nur erlaubte Host-Pfade, Content-Type muss image/* sein, Größenobergrenze pro Datei (ENV), Prüfung mit Pillow (verify), Ablage unter data/plants/images/<sha256[:2]>/<sha256>.<ext>, Dedupe über Hash. Manifest wie im Projekt-Prompt.
3. Fortsetzbar und unterbrechbar (SIGTERM), Fortschritt und ETA in der Statusdatei, Nachtfenster per ENV optional. Fehlerhafte Dateien werden gezählt und später begrenzt erneut versucht.
4. Updates: erneuter Lauf prüft per ETag/Last-Modified bzw. Hash und lädt nur Geändertes. Entfernte Seiten werden im Manifest als „gone“ markiert, aber nicht gelöscht.
5. Optional: zusätzlich ein WARC-Export (z. B. mit warcio) als Standardformat zur Langzeitarchivierung, falls der Mehraufwand gering ist.
6. Tests mit lokalem Test-HTTP-Server und synthetischen HTML-Seiten (keine echten Inhalte ins Repo): robots-Sperre, 429-Abbruch, Änderung des Nutzungshinweises, Resume, Dedupe, defektes Bild, Bild mit falschem Content-Type.

FERTIG, WENN: Tests grün. Starte einen Probelauf mit höchstens 20 Seiten und berichte Dauer, Bildzahl und Speicher. Der Vollauf wird vom Betreiber gestartet (Befehl und erwartete Dauer angeben). Er sollte möglichst bald laufen, weil der Zweck die Sicherung ist.
```

### T5.3 – Parser und strukturierte Datenbank

```text
AUFGABE T5.3 – PARSER UND STRUKTURIERTE DATENBANK

1. Modul agent/app/plants/parse.py liest ausschließlich aus dem Archiv (data/plants/raw), nie aus dem Netz.
2. Schema in data/plants/plants.db: plants (id aus URL, slug, lang, latin_name, common_name, family, genus, category_ids, summary, sections als Text mit Überschriften, source_url, fetched_at, content_hash), categories, glossary_terms (id, term, category, definition, lang), images (sha256, plant_id, alt, caption, role, width, height, bytes, source_url, local_path), FTS5 über latin_name, common_name, summary, Volltext.
3. Felder robust extrahieren (Selektoren in Konfiguration, nicht im Code verstreut), fehlende Felder bleiben NULL. Strukturfehler werden gezählt und in einem Bericht gelistet.
4. Idempotent und vollständig neu aufbaubar (`cli plants build-db --rebuild`).
5. Berichte: Anzahl Pflanzen/Begriffe/Bilder je Kategorie, Pflanzen ohne Bild, Bilder ohne Pflanze, Dubletten, 20 Stichproben zur Sichtprüfung.
6. Tests mit synthetischen HTML-Fixtures für Pflanzen-, Glossar- und Kategorieseiten.

FERTIG, WENN: Tests grün und der Bericht aus dem Probelauf (T5.2) belegt die Extraktion.
```

### T5.4 – Index, Corpus und Antworten

```text
AUFGABE T5.4 – INDEX, CORPUS UND ANTWORTEN

1. Chunking pro Pflanze nach Abschnitten, Kopf mit lateinischem und Trivialnamen. Qdrant-Collection plants_<lang>, Payload: plant_id, latin_name, common_name, family, category, section, source_url, lang. Embedding wie bisher über Ollama, fortsetzbar, nur geänderte Seiten neu.
2. Hybridsuche (FTS5 + Vektor, RRF) wie in P3/T3.5. Exakter Treffer auf lateinischen oder Trivialnamen hat Vorrang. Glossarbegriffe werden mitsuchen und bei Fachbegriffsfragen bevorzugt.
3. Corpus plants in Registry und Router (scope "plants"). Auto-Router erkennt Pflanzenfragen (Pflanzennamen aus der DB, Wörter wie Pflege, gießen, Blüte, Standort).
4. Antwortprompt: nur aus den Auszügen, Quellen [n] mit Titel und URL, Hinweis „Quelle: plantatlas.bio (lokale Kopie, Stand <Datum>)“. SICHERHEIT BEI PFLANZENAUSKÜNFTEN aus dem Projekt-Prompt ist fest eingebaut und per Test abgesichert (Giftigkeit/Essbarkeit ohne Beleg -> ehrliche Absage plus Warnhinweis).
5. Sprache: Die Sprache der Frage bestimmt den Corpus (Englisch/Russisch/ggf. Deutsch -> Query-Rewrite auf Englisch, Antwort in der Sprache der Frage), sofern nur eine Sprachausgabe archiviert wurde.
6. Prompt-Injection-Schutz: Seitentexte sind Daten (Test mit präpariertem Fixture).

FERTIG, WENN: Tests grün und `cli ask --scope plants "..."` liefert auf Fixtures belegte Antworten mit Quelle.
```

### T5.5 – Medien-Auslieferung und Bilder in Antworten

```text
AUFGABE T5.5 – MEDIEN-AUSLIEFERUNG UND BILDER IN ANTWORTEN

1. Antwort-Schema: bei Pflanzenantworten Feld images (Liste mit image_id, alt, plant, source_url). Die Bildauslieferung erfolgt nur aus der lokalen Kopie.
2. Medien-Endpunkt: GET /plants/media/<sha256> (nur Hashes aus dem Manifest, kein Dateisystem-Pfad aus Nutzereingaben, kein Directory-Listing, Content-Type fest, Cache-Header). Standardmäßig ohne Host-Port. Gib dem Betreiber zwei dokumentierte Optionen: (a) Ausliefern über einen eigenen kleinen Read-Only-Container programming-school-plants-media mit LAN-Port, (b) nur lokal an 127.0.0.1. Der Betreiber entscheidet, der Agent öffnet keinen LAN-Port selbst.
3. Open WebUI soll Bilder in Antworten als Markdown anzeigen können. Prüfe und dokumentiere, welche URL der Browser des Nutzers erreichen muss (Docker-Hostnamen funktionieren im Browser nicht), und baue die Basis-URL als ENV (PLANTS_MEDIA_BASE_URL).
4. Keine Auslieferung nach außen: weder Reverse-Proxy-Konfiguration noch öffentliche Ports anlegen.
5. Tests: Pfad-Traversal-Versuche, unbekannter Hash, falscher Content-Type.

FERTIG, WENN: Tests grün und ein dokumentierter Prüfbefehl zeigt ein Bild über die gewählte Auslieferung.
```

### T5.6 – Absicherung des Archivs (Integrität, Backup, Offline-Ansicht)

```text
AUFGABE T5.6 – ABSICHERUNG DES ARCHIVS

1. Integrität: `cli plants verify` prüft Manifest gegen Platte (Datei vorhanden, sha256 stimmt, Größe stimmt, Bild dekodierbar), meldet fehlende/defekte Dateien und kann sie gezielt neu laden (solange die Seite erreichbar ist und keine Stopp-Bedingung vorliegt). Wöchentlicher Lauf im Worker, Ergebnis im Status.
2. Backup: Erweitere scripts/backup.sh um data/plants (SQLite per .backup, Bilder per rsync-ähnlichem Abgleich mit Hardlink-Snapshots oder tar, Prüfsummendatei). Dokumentiere eine 3-2-1-Empfehlung (drei Kopien, zwei Medien, eine an anderem Ort) und eine Restore-Anleitung. Teste Backup + Restore an einem Fixture-Archiv und berichte das Ergebnis.
3. Offline-Spiegel für den Ernstfall (Seite weg): `cli plants export-mirror` erzeugt aus dem Rohdatenarchiv eine statisch browsbare Kopie (Links und Bild-Pfade auf lokale Dateien umgeschrieben, Index, Kategorien, Glossar, einfache Suche per Browser-JS). Sie funktioniert ohne Agent, Qdrant und Netz und enthält einen Hinweis auf Herkunft, Abrufdatum und „nur privater Gebrauch“. Sie wird nirgends automatisch veröffentlicht.
4. Schreibschutz: Das Archiv wird vom Agenten nur durch den Archiv-Crawler geschrieben. Dokumentiere, wie der Betreiber data/plants/raw und data/plants/images auf Dateisystemebene schreibgeschützt (chattr/Mount-Option) stellen kann, nachdem der Vollauf abgeschlossen ist.
5. docs/plantatlas-rights.md bleibt aktuell und wird von README und Spiegel-Hinweisseite referenziert.

FERTIG, WENN: Verify, Backup und Restore sind an Fixtures getestet und die Serverbefehle für den Betreiber stehen im README.
```

### T5.7 – Abnahme

```text
AUFGABE T5.7 – ABNAHME

1. E2E auf Fixtures: Archiv -> DB -> Index -> 30 Pflanzenfragen (Latein, Trivialname, Glossar, Pflege, Giftigkeit ohne Beleg) -> Bild in Antwort -> Verify -> Backup/Restore -> Offline-Spiegel öffnen.
2. Ergänze das Golden-Set von P4 (eval/golden/plants.jsonl) um Pflanzenfragen und Sicherheitsfälle (Giftigkeit/Essbarkeit ohne Beleg muss mit Absage und Warnhinweis enden). Nur wenn P4 vorhanden ist.
3. Anleitung für den Betreiber: Vollauf, erwartete Dauer aus dem Probelauf, Überwachung, Wiederaufnahme, Nachlauf mit Verify.
4. Abnahmeprotokoll docs/acceptance-P5.md mit ehrlichem Teststand (was nur auf dem Server geprüft werden kann).

FERTIG, WENN: das Protokoll liegt vor und die Stopp-Bedingungen (G5) sind als laufende Überwachung dokumentiert.
```
