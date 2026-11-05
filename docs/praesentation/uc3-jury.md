# Use Case 3: die zwei Termine

Dieses Blatt ist der Ablauf für beide Termine. Pfad A ist die Fachjury, Pfad B das Management. Sprechtext, Befehle und Sollzahlen stehen in den Dateien, auf die jede Zeile zeigt. Zahlen tragen ihre Kennung aus dem Belegregister (`belegregister.md`).

Gehört zu GitLab #20 (Kriterium AC3) und Epic #26. Vorgaben des Owners vom 05.11.2026: Vorführung online über Hotspot, kein Lauf ohne Netz.

**Die eine Aussage, in beiden Terminen gleich:** Jede Zahl lässt sich nachrechnen, jede Änderung hat einen Namen. Die KI versteht den Auftrag, ein Mensch gibt frei, das Programm rechnet.

- **Termine:** Probe Fr 06.11.2026 06:00 bis 07:00, Freeze 07:00, Fachjury ab 09:00 (Europe/Vienna).
- **Wer spricht:** Bernhard Götzendorfer.
- **Vorführung:** eigene Adresse mit Passwort, Modell Azure, Datenbank ist eine Kopie der Abgabe. Die Abgabezahlen bleiben davon unberührt. Details: `docs/betrieb/vorfuehrung.md`.

## Pfad A: Fachjury, zwei Personen, 15 bis 20 Minuten

Gefragt ist die echte Live-Demo. Am Anfang keine Folien: Der Laptop steht offen auf `/uc3`, die Kriterien-Karte (`kriterien-karte.md`) liegt ausgedruckt daneben, der Fragenkatalog (`fragenkatalog.md`) griffbereit. Die Aufgabe verlangt fünf Dinge, alle kommen vor: Lösung, Fehler, eine Annahme im Detail, die Live-Änderung, die Datenanfragen.

| Zeit | Was die Aufgabe verlangt | Was die Jury sieht | Wo es steht |
|---|---|---|---|
| 0:00–1:00 | Lösung | `/uc3`: 24 Monate, zwei davon angehalten. Dazu die eine Aussage | Skript Abschnitt 3 |
| 1:00–3:00 | Gefundene Fehler | Bericht Oktober 2025: 78.949 fehlen, der Monat steht still, nichts ist gelöscht. Kurz die acht Arten | Drehbuch D1 |
| 3:00–4:00 | Lösung, Beleg | Bericht August 2024: 2.880 von 2.880 Zahlen stimmen | Drehbuch D1 |
| 4:00–5:00 | Eine Annahme im Detail | Geburtsmonat 13, drei Rechenwege gegen 576 Zahlen | Folie 8 (`/praesentation?folie=8`), Skript Abschnitt 3 |
| 5:00–6:00 | Live-Änderung, Vorlauf | Die drei Aufträge der Aufgabe, freigegeben mit Namen | Drehbuch D2 Teil 1 |
| **6:00–9:30** | **Live-Änderung** | **Bernhard fragt nach einer Regel. Die Jury nennt sie. Satz tippen, Vorschlag, vorher und nachher, Freigabe, Protokoll** | **Drehbuch D2 Teil 2** |
| 9:30–12:00 | Datenanfragen | Zeitreihe, Männer und Frauen, Fluktuation je Wirtschaftsbereich | Drehbuch D3 |
| 12:00–13:00 | Zusatz | Eine ehrliche Absage: „Entwicklung im Bau seit August 2024“ | Drehbuch D3 |
| 13:00–14:00 | Zusatz | Die Wien-Frage durch alle drei Räume. Nur wenn sie um 06:45 echt läuft | Drehbuch D4 |
| bis 20:00 | Fragen der Jury | Weitere Änderungen und Fragen, Karte und Katalog | `fragenkatalog.md`, Teil B und C |

Wird die Zeit knapp, entfällt zuerst der Zusatz, dann Teil 1 von D2. Die Änderung der Jury, die Datenanfragen und die Annahme bleiben immer drin, denn die Aufgabe verlangt sie.

**Die Änderung kommt vor den Datenfragen,** weil sie das Modell braucht. Hakt Azure, bleibt danach Zeit. Rückfall: Drehbuch D2.

Die Aufgabe sagt „per Sprache“. Bei uns tippt Bernhard den Wunsch der Jury als einen Satz. Das sagt er, wenn die Jury fragt (FAQ Frage 16).

**Datenanfragen:**

| Art | Frage im Drehbuch D3 | Sollzahl | Kennung |
|---|---|---|---|
| Zeitreihe | Frage 1 | 24 Werte, August 2024 392.236, Juli 2026 399.027 | F14, F21 |
| Männer und Frauen | Frage 2 (August 2024, je Bundesland) | Männer 211.603, Frauen 180.633 | F14 |
| Fluktuation je Wirtschaftsbereich | Frage 4 (Oktober 2024) | 3,42 %, 12.215 Zugänge, 14.557 Abgänge | F23 |

Die Antwort zeigt Zahl oder Tabelle und die Abfrage, unter „Details“ den ganzen Satz und die Definition. Bei Männern und Frauen stehen die Summen dort, also „Details“ aufklappen. Ein Sprachmodell rechnet hier nichts. Freie Fragen der Jury nur, wenn der Stand um 06:45 sie trägt (Eintrag in `probe.md`).

## Pfad B: Management, 10 Minuten Folien, 5 Minuten Fragen

Die Runde will die Geschichte, den Mehrwert und die Zahlen. Eine Live-Demo gibt es danach nur vielleicht. Folien: Seite `/praesentation/management`, als fertige PDF-Datei auf dem USB-Stick. Sprechtext: `skript-management.md`.

| Zeit | Folie | Was hängen bleibt |
|---|---|---|
| 0:00 | Drei Menschen brauchen eine Antwort, der sie trauen können. | Worum es geht |
| 1:00 | Im Oktober 2025 fehlte jedes fünfte Beschäftigungsverhältnis. | Wer einfach zählt, meldet einen Einbruch, den es nie gab |
| 2:30 | StatAgent veröffentlicht nicht, er hält an und fragt nach. | Das ist der Mehrwert |
| 3:15 | Den offiziellen Bericht nachgerechnet: 2.880 von 2.880 Zahlen stimmen. | Warum man der Zahl traut |
| 4:15 | Acht Arten von Fehlern gefunden, nichts gelöscht. | Die Daten sind nicht sauber, das Programm weiß das |
| 5:15 | Die KI versteht, ein Mensch gibt frei, das Programm rechnet. | Die eine Idee |
| 6:15 | Drei Aufträge in Alltagssprache, am selben Tag umgesetzt. | Änderungen kosten wenig |
| 7:15 | Gerechnet wird ohne KI. | Unsere gemessene Dauer und die offene Frage nach Ihrer |
| 8:15 | Eine Frage, drei Antworten: Statistik, Simulator, Lotse. | Ein Kern für alle drei. Nur wenn die Wien-Frage um 06:45 echt läuft |
| 9:00 | Die Verantwortung bleibt beim Menschen. | Name, Zeit, keine Einzeldaten |
| 9:45 | Jede Zahl nachrechenbar. | Danke, Ihre Fragen |

**Die 5 Minuten Fragen:** `management-faq.md`, die fünf wichtigsten Antworten stehen oben, Kosten und Dauer gleich danach. Die Kriterien-Karte bleibt hier weg, das Raster interessiert in dieser Runde nicht.

**Falls Zeit für einen kurzen Blick live bleibt (60 s), nur mit stehendem Hotspot:** `/uc3/fragen`, Frage 2 tippen, Tabelle zeigen, „Abfrage ansehen“ klicken. „Das ist keine KI-Antwort. Das ist die Rechnung, die Sie prüfen können.“ Kein Modell nötig, kein Risiko.

## Ehrliche Grenzen

Bernhard nennt sie von sich aus oder auf Nachfrage und versteckt sie nicht.

- Die Live-Änderung ist ein getippter Satz, keine gesprochene Eingabe.
- Gezählt wird nach ÖNACE-Abschnitt und Bundesland (Kriterien-Karte, Bereich 2).
- Die Pensionsmeldungen der Träger sind nicht eingelesen (Bereich 1).
- Wo Daten fehlen, gilt eine begründete Annahme mit Beleg, die Rückfrage ist dokumentiert (`abgabe/rueckfragen/`).
- Zeitersparnis: nicht gemessen. Wir fragen zurück: „Wie lange dauert das bei Ihnen heute?“
- Alle gesammelt: Fragenkatalog C14, `management-faq.md` Frage 13.

## Probe und Backup-Video

- **Probe:** Fr 06:00 nach `probe.md`, Pfad A und Pfad B je einmal mit Uhr. Entscheide um 06:45: Teil 2 von D2, freie Datenfragen, Wien-Frage.
- **Rückfall:** Hotspot wechseln, dann Terminal, dann Video (`demo-drehbuch.md`, Abschnitt „Rückfall“).
- **Backup-Video:** Probelauf vom 05.11. 21:25 auf `main`, 2:34 Minuten. Das Endvideo entsteht bis 05:45 auf dem Stand des Freeze, Datei, Dauer und SHA-256 in `backup-video.md`. Es wird immer angesagt: „Das ist eine Aufzeichnung von heute früh.“
- **USB-Stick:** beide Folien-PDFs und das Video (`docs/praesentation/werkzeug/README.md`).
