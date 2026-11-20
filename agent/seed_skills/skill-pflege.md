---
description: Skills anlegen, verbessern, zusammenführen und aufräumen; Aufbau eines guten Skills
---
# Skill-Pflege

## Wann einen Skill anlegen?
- Der Nutzer bringt dir einen Ablauf bei.
- Du hast dieselbe Art Aufgabe schon zweimal gelöst und es gibt einen festen Weg.

## Aufbau eines Skills (save_skill)
- name: kurz, klein, mit Bindestrich (z. B. wochenbericht).
- description: genau eine Zeile, die sagt, wann der Skill nützt.
- instructions: Ziel, Voraussetzungen, nummerierte Schritte, Beispiele, typische Stolperfallen.
  Nenne konkrete Werkzeuge (z. B. search_knowledge, add_to_knowledge_base), wenn sie gebraucht werden.

## Verbessern
1. Skill mit use_skill lesen.
2. Den kompletten, verbesserten Text mit save_skill unter demselben Namen speichern. Die alte Version wird automatisch gesichert.
3. Passte ein Skill nicht oder fehlte ein Schritt: direkt nach der Aufgabe verbessern.

## Aufräumen
- list_skills: ähnliche Skills zusammenführen, veraltete löschen (delete_skill nur nach Rückfrage, er landet im Papierkorb).
- Skills sind reiner Text. Behaupte in Skills nichts, was deine Werkzeuge nicht können.
