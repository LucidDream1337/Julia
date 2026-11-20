---
description: Knowledge Bases aufräumen und pflegen: Dubletten, Widersprüche, veraltete Einträge, Beschreibungen, Namen
---
# KB-Pflege

Nutze diesen Skill, wenn der Nutzer um Aufräumen bittet oder du merkst, dass eine KB unordentlich ist.

1. list_knowledge_bases: Überblick. Auffällig sind leere KBs und unklare Beschreibungen.
2. Pro KB list_entries (bei mehr Einträgen seitenweise mit offset). Achte auf:
   - Dubletten oder fast gleiche Einträge
   - Widersprüche und veraltete Angaben
   - Einträge, die mehrere Themen mischen oder nicht für sich verständlich sind
3. Dubletten: den besseren Eintrag behalten (bei Bedarf mit update_entry um fehlende Details ergänzen), den anderen mit delete_entry entfernen.
4. Widersprüche: gilt der neuere Stand? Wenn unklar, den Nutzer fragen, bevor du etwas löschst.
5. Zu lange Mischeinträge: in einzelne, kurze Einträge aufteilen (add_to_knowledge_base) und den alten löschen.
6. Beschreibung der KB mit update_knowledge_base aktuell halten. Umbenennen (rename_knowledge_base) nur nach Rückfrage; danach Skills prüfen, die den alten Namen nennen.
7. Zum Schluss kurz berichten: was geprüft, geändert und gelöscht wurde.

Gute Einträge: ein Gedanke oder Fakt, 200 bis 800 Zeichen, ohne Bezug auf "oben" oder "wie besprochen", mit Quelle, wenn bekannt.
Gute KB-Namen: kurz, klein geschrieben, thematisch (z. B. heimnetz, rezepte, projekt-alpha).
Ganze KBs nie ohne Wunsch des Nutzers löschen.
