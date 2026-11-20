---
description: Übersicht aller Verwaltungs-Werkzeuge und Befehle von Julia und wann man welches nutzt
---
# Werkzeugkasten

## Wissen (Knowledge Bases, auch "Wissensdatenbanken" genannt)
- Überblick: list_knowledge_bases, list_entries (mit IDs), search_knowledge.
- Speichern: add_to_knowledge_base (vorher suchen, um Dubletten zu vermeiden).
- Korrigieren: update_entry (ID aus Suche oder Liste). Einzelnes entfernen: delete_entry.
- Umbauen: update_knowledge_base (Beschreibung), rename_knowledge_base, merge_knowledge_bases (verschiebt Einträge, Quelle kommt in den Papierkorb).
- Sichern: export_knowledge_base schreibt eine JSON-Datei nach data/agent/exports/. Vor größeren Aufräumaktionen sinnvoll.

## Löschen ist zweistufig
1. delete_knowledge_base oder delete_skill: Papierkorb, einige Tage wiederherstellbar (restore_knowledge_base, restore_skill).
2. Endgültig nur auf ausdrücklichen Wunsch: delete_knowledge_base mit permanent=true (KB muss schon im Papierkorb liegen) oder empty_trash.
Dem Nutzer immer sagen, welche Stufe ausgeführt wurde.

## Skills
- list_skills, use_skill, save_skill (überschreibt = verbessert, alte Version wird gesichert), delete_skill, restore_skill.

## Selbstprüfung
- status zeigt Version, Modelle, Qdrant, GPU oder CPU, Einstellungen und alle Werkzeuge.
- show_changelog zeigt, was du zuletzt verändert hast. Daraus lassen sich Fehler korrigieren.
- Meldet ein Werkzeug einen Fehler: Meldung lesen, Angaben korrigieren, erneut versuchen. Meldet status "Löschen erlaubt: NEIN", dem Nutzer sagen, dass er AGENT_ALLOW_DELETE in der .env ändern muss.

## Befehle des Nutzers
Der Nutzer kann Verwaltung auch direkt per Befehl auslösen (/hilfe zeigt alle), zum Beispiel /status, /kb löschen NAME, /papierkorb leeren. Diese Befehle laufen ohne dich.
