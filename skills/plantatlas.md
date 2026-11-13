# Pflanzenatlas (plantatlas.bio)
Pflanzen- und Glossarseiten von plantatlas.bio als lokale Privatkopie lernen (nur Text, keine Bilder).

1. Lege die Wissensdatenbank mit `preset` "plantatlas" an (z. B. name "pflanzenatlas"). Laut Startseite sind es ca. 3.000 Pflanzenseiten und 1.200 Glossarbegriffe.
2. Weiter nach dem Skill "wissensdatenbank-anlegen". Im Plan prüfen: Ist `robots_ok` wahr? Passen die `sample_urls`? Bei einem `problem` anhalten und es dem Nutzer erklären.
3. Der Plan enthält eine `notice` zum Nutzungshinweis der Seite. Vorlesen und nur mit ausdrücklicher Bestätigung des Nutzers `acknowledged=true` setzen. Du bewertest die Rechtslage nicht.
4. Probelauf mit 10 Seiten, Treffer ansehen, dann der Vollauf (mehrere Stunden, jederzeit mit `wissen_stopp` unterbrechbar und später fortsetzbar).

Sicherheit bei Antworten:
- Zu Giftigkeit, Essbarkeit und Heilwirkung antwortest du nur aus den gefundenen Auszügen. Fehlt die Angabe, sagst du "dazu steht nichts in der Datenbank".
- Hänge dann immer an: Pflanzenbestimmung per Text ist unsicher, im Zweifel nichts essen oder anwenden.
- Nenne bei jeder Antwort die Quelle (URL).

Hinweise:
- Die Seite hat Englisch und Russisch. Mit englischen Begriffen suchen, auf Deutsch antworten.
- Bricht die Seite mit HTTP 429/503/403 ab, hört der Lauf von selbst auf. Nicht erneut erzwingen, sondern dem Nutzer berichten.
