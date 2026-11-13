# Wissensdatenbank anlegen
Schritt für Schritt eine Wissensdatenbank aus einer Webseite oder aus Wikipedia aufbauen.

1. Ziel klären: Welche Quelle, welcher Bereich, wofür? Mit `wissen_vorlagen` die Vorlagen zeigen (w3schools, wikipedia, plantatlas). Das passende Quellen-Skill lesen.
2. Anlegen: `wissen_anlegen` (name, description, preset, parts bzw. config). Es wird noch nichts geladen.
3. Plan: `wissen_plan`. Dem Nutzer in wenigen Sätzen erklären: robots.txt/Erreichbarkeit, gefundene Seiten bzw. Artikel, Obergrenze, höchstens geschätzte Dauer, Lizenz und `notice`.
4. Probelauf: Nach dem Ja des Nutzers `wissen_start` mit `max_pages` 10. Gibt es eine `notice`, den Hinweis vorlesen und nur nach ausdrücklicher Bestätigung `acknowledged=true` setzen.
5. Beobachten: `wissen_status` alle paar Minuten abfragen, nicht dauernd. Danach 2-3 Testfragen mit `wissen_suche` stellen und Treffer samt Quelle gemeinsam ansehen.
6. Vollauf: Wenn es gut aussieht und der Nutzer zustimmt, erneut `wissen_plan` (neue plan_id), dann `wissen_start` ohne kleines max_pages. Unveränderte Seiten werden übersprungen.
7. Abschluss: Kurz berichten (Seiten, Abschnitte, Fehler) und zeigen, wie man fragt.

Regeln:
- Nie `wissen_start` ohne Plan und ausdrückliches Ja.
- Meldet der Plan ein `problem` (robots.txt, Sperre, nicht erreichbar): nicht umgehen, dem Nutzer erklären.
- Es läuft immer nur ein Job. Bei Fehlern `last_error` aus dem Job nennen, nicht raten. Zur Diagnose `service_status`.
- Löschen (`wissen_loeschen`) nur auf ausdrücklichen Wunsch.
