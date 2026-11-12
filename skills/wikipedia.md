# Wikipedia-Wissensdatenbank
Ausgewählte Wikipedia-Themen über die offizielle API lernen. Keine Komplettkopie der Wikipedia.

1. Frag nach Sprache (de, en, simple, ...) und Thema. Mögliche Auswahl: eine Titelliste, eine Kategorie (z. B. "Kategorie:Heilpflanze", mit depth 0-2 für Unterkategorien) oder ein Suchbegriff.
2. Lege die Wissensdatenbank an: `preset` "wikipedia" und `config`, z. B. {"lang": "de", "categories": [{"name": "Kategorie:Heilpflanze", "depth": 1}], "max_pages": 200}. Alternativ "titles": [...] oder "search": "...".
3. Weiter nach dem Skill "wissensdatenbank-anlegen". Im Plan zeigt `sample_titles`, was gefunden wurde: gemeinsam prüfen, ob das Thema passt.
4. Beim Antworten die Artikel-URL als Quelle nennen. Der Text steht unter CC BY-SA 4.0.

Hinweise:
- Voraussetzung ist `CRAWLER_CONTACT` in der .env. Fehlt er, meldet der Plan das, und der Nutzer muss ihn eintragen.
- Die ganze deutsche oder englische Wikipedia ist für diesen Rechner zu groß. Lieber Themenbereiche wählen.
- Für ganz Aktuelles ist die Websuche besser als die lokale Kopie.
