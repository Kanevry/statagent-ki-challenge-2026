# Fragen des Managements: Antworten mit Beleg

Für die 5 Minuten nach den Folien und für Nachfragen der Fachjury. Jede Antwort ist zum Sagen geschrieben, darunter steht der Beleg. Steht kein Beleg zur Verfügung, steht dort „nicht gemessen“. Kennungen wie F1 stehen im Belegregister (`belegregister.md`).

**Stand:** 05.11.2026. Vor dem Freeze mit `main` abgleichen, dann gilt dieser Text.

## Die fünf wichtigsten Antworten

**1. Was bringt das dem Haus?**
„Eine falsche veröffentlichte Zahl kostet Vertrauen. Hier hält das Programm an, statt sie zu melden, und jeder Schritt hat einen Namen.“
Beleg: Oktober 2025, 78.949 fehlende Verhältnisse, Monat angehalten (F11, F17). Eine Zeit- oder Geldersparnis nennen wir nicht, siehe Frage 7.

**2. Ist das sicher mit den Daten?**
„Ans Modell gehen nur Schema, Regeln und Summen. Einzeldaten verweigert das Lese-Werkzeug der Agenten. Die Daten der Challenge sind außerdem synthetisch.“
Beleg: `abgabe/modelle.md`, Abschnitt „Im Betrieb“.

**3. Ersetzt das Mitarbeiter?**
„Nein. Es nimmt das Suchen und Rechnen ab. Freigeben darf nur ein Mensch mit Vor- und Nachnamen.“
Beleg: Prüfung des Namens in `shared/py/plattform/freigabe.py`, „Team“ wird abgelehnt.

**4. Warum Microsoft und nicht Europa?**
„Das Modell gibt die Challenge vor: Azure, Standort West Europe. Es ist ein Schalter. Mistral aus der EU und ein Modell im eigenen Haus laufen am selben Code.“
Beleg: `abgabe/modelle.md`. Mistral gerufen am 05.11.2026 laut Modell-Protokoll, einmal, Koordinator.

**5. Wie schnell geht das in den Echtbetrieb?**
„Das kann ich Ihnen nicht sagen, das haben wir nicht gemessen. Die Technik ist eine normale PostgreSQL-Datenbank. Der nächste Schritt wäre die echte Lieferung statt der synthetischen. Der Code steht unter MIT-Lizenz, und die Ergebnisse stehen dem Dachverband uneingeschränkt zur Verfügung.“
Beleg: `README.md`, Abschnitt Lizenzen. Dauer einer Einführung: nicht gemessen.

## Kosten und Dauer

**6. Was kostet eine Anfrage?**
„Eine Frage an die Daten kostet keinen Modellaufruf, denn dort rechnet das Programm. Ein Änderungsvorschlag kostet rund einen Cent und dauert rund drei Minuten, weil das Programm den Monat zweimal rechnet.“

| Was | Modellaufrufe | Tokens hinein und heraus | Dauer beim Modell | Kosten zum Listenpreis |
|---|---|---|---|---|
| Monatslauf, Qualitätsbericht, Frage an die Daten | 0 | 0 | 0 | 0 |
| Auftrag 1 (Vorschlag uc3/24) | 2 | 13.447 und 273 | 3,3 s | 1,0 bis 1,1 Cent |
| Auftrag 2 (Vorschlag uc3/25) | 2 | 13.604 und 510 | 5,2 s | 1,1 bis 1,2 Cent |
| Auftrag 3 (Vorschlag uc3/26) | 2 | 13.789 und 802 | 8,8 s | 1,3 bis 1,4 Cent |
| Alle Anläufe rund um die drei Aufträge (05.11.2026) | 50 | 457.462 und 19.342 | | 39 bis 42 Cent |
| Typischer Lauf (Median) aus 246 Läufen in den Proben | 2 | 15.380 und 320 | 3,0 s | 1,2 bis 1,3 Cent |

- **Preis:** Azure-Preisliste (`prices.azure.com`, Region West Europe, abgerufen 05.11.2026): GPT 5.4 mini, je Million Tokens, Global 0,6733 € hinein und 4,0397 € heraus, Data Zone 0,7406 € und 4,4436 €. Die Spanne oben kommt aus diesen zwei Preisen, welcher für unsere Bereitstellung gilt, wissen wir nicht. Den Zugang stellt der Veranstalter.
- **Tokens:** Protokoll der Modellaufrufe `var/protokoll/modellaufrufe.jsonl`, je Aufruf eine Zeile ohne Inhalt. Die Datei liegt je Arbeitsstand getrennt und nicht im Repo. Ausgewertet wurden drei davon.
- **Nicht jeder Satz sitzt beim ersten Mal:** Auftrag 1 kam im ersten Anlauf, die Aufträge 2 und 3 brauchten mehrere. Die Zuordnung folgt aus den Zeitstempeln im Protokoll.
- **Monatliche Betriebskosten:** nicht gemessen.

**7. Wie viel Zeit spart das Statistik-Team?**
„Das wissen wir nicht, wir kennen die Dauer Ihres Prozesses nicht. Wie lange dauert das bei Ihnen heute? Von uns kann ich Ihnen die gemessene Dauer sagen: Alle 24 Lieferungen dauern bei uns 8,4 Minuten nach den alten Regeln und knapp 13 Minuten nach den neuen, gemessen auf einer frischen Datenbank ohne Netz. Unter Last waren es rund 13 und knapp 20 Minuten.“
Beleg: frische Datenbank ohne Netz, Stand `f7b985e`: Regelsatz v1 504 s, v2 770 s; frischer Klon unter Last, main `87de2b0`: 793 s und 1169 s (F28). Zeitersparnis: nicht gemessen. Keine Schätzung nennen.

**8. Wie schnell kommt die Antwort auf eine Datenfrage?**
„Innerhalb von Sekunden, mit der Abfrage dazu.“
Beleg: Testserver am 05.11.2026, vier geprüfte Fragen: 0,4 bis 3,8 Sekunden (F29). Am Ort der Vorführung: nicht gemessen.

## Zahlen und Verantwortung

**9. Stimmen Ihre Zahlen?**
„Für August 2024 gibt es einen offiziellen Vergleichsbericht. Dort stimmen 2.880 von 2.880 Zahlen. Für die anderen 23 Monate gibt es keinen Vergleich, dort wachen 24 Prüfregeln.“
Beleg: F1, F15.

**10. Rechnet die KI?**
„Nein. Gerechnet wird mit SQL und Python, ohne Modell. Zwei Läufe mit denselben Daten ergeben dieselben Zahlen.“
Beleg: `abgabe/modelle.md`; 72 Wiederholungsläufe, 72-mal derselbe Hash (`abgabe/uc3-abnahme.md`, Abschnitt 3; F16).

**11. Wer hat freigegeben, Mensch oder KI?**
*Wortlaut stimmt Bernhard um 07:00 ab. Bis dahin nicht verwenden.* Der Entwurf folgt dem Protokoll:
„Regelsatz v1 und die 22 veröffentlichten Monate habe ich selbst freigegeben. Die Freigaben der Vorschläge 24 bis 26 und des Regelsatzes v2 hat in meinem Auftrag eine KI-Sitzung eingegeben, das habe ich um 18:22 bestätigt, mit meinem Namen. Das steht offen im Protokoll. Die Ministeriums-Lieferung habe ich selbst freigegeben.“
Beleg: `abgabe/protokoll.md`, Abschnitt „Hinweise zu den Freigaben“ und Abschnitt 1; Commit `2ba95e5`.

**12. Was haben Sie an den Daten korrigiert?**
„Gelöscht haben wir nichts. Acht Arten von Fehlern, jede mit einer Regel oder einem Halt. März und Oktober 2025 bleiben vorläufig. Wo Daten fehlen, gilt eine begründete Annahme mit Beleg, und die Rückfrage ist dokumentiert.“
Beleg: F4 bis F11; `abgabe/protokoll.md`; `abgabe/rueckfragen/` (R1 bis R10); `docs/plan/uc3/annahmen.md`.

**13. Was fehlt noch?**
„Bei den Pensionen fehlen die öffentlich Bediensteten, die frühere BVA meldet keine. Wir zählen nach Abschnitt und Bundesland, weil die Lieferungen nur das haben. Die tiefen Klassifikationen kann man online nachschlagen, gezählt wird nicht tiefer. Die Live-Änderung ist getippt, nicht gesprochen. Das steht alles offen auf unserer Karte.“
Beleg: `kriterien-karte.md`, Fragenkatalog C14. Vor dem Freeze mit `main` abgleichen.

## Betrieb und Regeln

**14. Muss das nicht lokal und offline laufen?**
„Es läuft lokal wie gefordert, und zusätzlich auf einem Server, den wir selbst betreiben. Sie können es selbst nachbauen. Die Abgabezahlen sind auf der eigenen Datenbank gerechnet, online läuft nur die Vorführung.“
Dazu, wenn gefragt: „Der ganze Weg ab einem frischen Klon dauerte einmal 36 und einmal 55 Minuten, je nach Rechner und Last, auf einer frischen Datenbank im vorhandenen Klon 24 Minuten, jeweils mit den Datentests.“
Beleg: Messung des Jury-Wegs durch die Review-Bank, 05.11.2026 auf main `87de2b0` ohne Netz, Pakete und Docker-Image lagen vorab da, 06.11.2026 auf main `809da6d` auf Linux, Netz nicht gesperrt, Datenbank auf 4 Kerne begrenzt, Rechner unter anderer Last. Hash und Regelstand 24 von 24 je Regelsatz, 2.880 Zellen ohne Abweichung, Ministerium 32.741, `pruefe-abgabe` Exit 0 (F30).
Nur wenn gefragt: Neu erzeugte Sheets und Berichte weichen byteweise ab (Status, Lauf-IDs, Kommentare), die Zellwerte nicht.

**15. Was passiert, wenn das Modell ausfällt?**
„Rechnen, Berichte und Fragen an die Daten laufen ohne Modell weiter. Nur neue Änderungsvorschläge warten, bis das Modell wieder da ist.“
Beleg: `abgabe/modelle.md`, `docs/plan/uc3/vertragsnutzung.md`.

**16. Warum getippt und nicht gesprochen?**
Nur auf Nachfrage. „Getippt. Eine gesprochene Eingabe zeigen wir nicht, deshalb steht die Zeile bei uns auf teilweise.“
Beleg: Owner-Entscheid 05.11.2026, `kriterien-karte.md`, Bereich 5.

**17. Was war schon vorher da?**
„Für die Sprache ein Konzept, kein Code. Der Rest ist hier entstanden, und die Fremdteile sind genannt.“
Beleg: `docs/abgabe/herkunft.md`, `README.md`, Abschnitt Vorab Entstandenes. Paketlizenzen einzeln: nicht gemessen.

**18. Ist das mit dem AI Act vereinbar? Ist das Hochrisiko?**
„StatAgent entscheidet über keine Person und keine Leistung, es rechnet eine Statistik aus synthetischen Daten. Wir halten das deshalb nicht für Hochrisiko. Das ist unsere Einschätzung, eine rechtliche Prüfung haben wir nicht gemacht.“
Einordnung: Hochrisiko nach Anhang III Nr. 5(a) käme erst in Frage, wenn ein System über Leistungen entscheidet. Beleg: keiner, eigene Einschätzung. Geprüft hat das niemand von außen.
