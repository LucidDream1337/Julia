---
description: So speichert Julia neues Wissen sauber in Knowledge Bases, ohne Dubletten
---
# Wissen ablegen

1. Lohnt es sich? Speichere, was später nützlich ist: Fakten, Präferenzen, Entscheidungen, Anleitungen. Keine Smalltalk-Inhalte, keine Passwörter.
2. list_knowledge_bases ansehen und die passende KB wählen. Nur wenn keine passt, eine neue anlegen (kurzer thematischer Name, Beschreibung mitgeben).
3. Mit search_knowledge prüfen, ob es das schon gibt:
   - Gleicher Inhalt: nichts speichern.
   - Ältere oder falsche Fassung: update_entry mit der ID aus dem Treffer.
   - Neu: add_to_knowledge_base.
4. Formuliere den Text so, dass er allein verständlich ist (Namen und Zusammenhang ausschreiben) und nur einen Fakt oder Gedanken enthält. Gib die Quelle an, wenn bekannt.
5. Dem Nutzer kurz mitteilen, was in welcher KB gelandet ist.
