# Sprache: jeder Text, den ein Mensch sieht (#31, #32, #81, #107)

Owner-Vorgabe: Bürgersprache, kurze Sätze, keine KI-Schablonen, keine Gedankenstriche, jede Leistung mit Quelle
im Halbsatz. Je Screen eine Hauptaussage, dann die nächste Handlung. Zitat und Stand stehen hinter „Beleg
anzeigen“ (`aussagen`, `belege`), nicht im Fließtext.

## Was der Code tut

`uc1/uc1/sprache.py` mit Regeln in `uc1/daten/sprache.yaml`, ohne Modell:

- `glaette(text)`: Em-Dash und Gedankenstrich („ – “, „ - “) werden Komma, vor einem kurzen Schluss Doppelpunkt.
  Bindestriche in Wörtern und Bereiche („7-9“, „7 – 9“ → „7–9“) bleiben. Reine Floskeln („Gerne helfe ich“,
  „Ich hoffe, das hilft“, „Zögern Sie nicht“) fallen als Satz weg; „Bitte beachten Sie:“, „Wichtig:“ und
  „umfassende“ vor einem Nomen fallen als Wort weg. Emojis fallen weg.
- `pruefe(text)`: meldet Gedankenstriche, Schablonen, Emojis, Kaskaden (ab 2 × „zudem“, „darüber hinaus“ …),
  Sätze über 25 Wörter und ein Mittel ab 15 Wörtern. Was sich ohne Grammatik nicht sicher umstellen lässt
  („Es ist wichtig zu beachten, dass …“, „Als KI …“), wird gemeldet, nicht umgeschrieben. Wörtliche Zitate in
  „…“ zählen nicht mit.
- `kurze_quelle()`: „Anträge und Formulare/PAL080_0125_Mpfl_052026.pdf, S. 2“ → „Antrag PAL080, S. 2“.

`glaette` läuft auf jedem Antworttext vor der Nachprüfung: Kern (`frage`, auch Abstinenz und Sprechtext), Grenzantwort,
UC4 (Text und Grenztext), Antrag-Zusammenfassung, Termin-Dialog und ICS-Beschreibung. Die Belegregeln
(Zitat wörtlich, Deckung, Betrag nur im Zitat, Grenzprüfung, Träger aus der Tabelle) sind unverändert.

## Textaufbau im Kern

Vorher: Einleitung, je Aussage ein Listenpunkt mit „Quelle: BPGG § 4, Stand: Fassung ab 01.01.2015:“ und Zitat.
Nachher: ein Absatz, je Aussage ein Satz mit Halbsatz „(BPGG § 4)“; Beträge mit Stand kurz:
„200,80 Euro (BPGG § 5, Stand 2020, heute vielleicht höher).“ und einmal „Den aktuellen Betrag nennt Ihnen der
Träger.“ Dann „Zuständig: …“, „So geht es weiter:“ mit Handlungen in Sie-Form. Fehlende Angaben heißen jetzt
„wer die Pension zahlt“ statt `status`.

## Messung (2026-11-05, M4, Azure `gpt-5-4-mini`, je ein Lauf)

Gespräche: Pflege in 2 Wechseln (Rückfrage, dann Antwort), Case-Managerin Reha, Grenzfrage Tabletten,
englische Pflegefrage; dazu `lotse antrag pflegegeld`, `lotse termin --fall termin-wien`, ein UC4-Lauf
(Demo-Kontext Wartezeiten, erfunden). Mittel und längster Satz nach `sprache.saetze` (Zeilen getrennt).

| Text | Mittel vorher | Mittel nachher | längster Satz vorher → nachher | Zeichen vorher → nachher | Befunde vorher → nachher |
|---|---:|---:|---:|---:|---|
| Pflege W1 (Rückfrage) | 8,0 | 6,3 | 13 → 7 | 138 → 112 | 0 → 0 |
| Pflege W2 | 9,6 | 8,5 | 26 → 16 | 1.100 → 901 | 0 → 0 |
| Reha Case-Managerin | 14,4 | 8,2 | 43 → 18 | 2.265 → 764 | 0 → 0 |
| Grenzfrage | 12,6 | 7,6 | 16 → 11 | 382 → 372 | 0 → 0 |
| Englisch | 12,8 | 9,6 | 36 → 16 | 1.608 → 944 | 0 → 0 |
| UC4 | 8,3 | 8,5 | 11 → 11 | 140 → 187 | 0 → 0 |
| Antrag (CLI-Text) | 19,6 | 11,0 | 34 → 23 | 4.407 → 2.561 | 5 Sätze > 25, Mittel → 0 |

Em-Dashes und Schablonen: in keinem Lauf, weder vorher noch nachher. Das Modell schrieb hier keine; die Glättung
ist die Sicherung dafür, nicht die Ursache der Verbesserung. Die Verbesserung kommt aus dem Textaufbau
(Zitat und Stand aus dem Fließtext) und den neuen festen Texten. Termin: `lotse termin --pruefen termin-wien`
bestanden, Fixture und ICS neu aufgezeichnet.

## Karl, 55, kümmert sich um seine Mutter

| Text | Was geändert wurde |
|---|---|
| Rückfrage Status | Eine Frage, dann ein Beispiel, dann „Sie können auch sagen: keine Pension.“ statt einer Doppelfrage. |
| Pflege-Antwort | Kein „Das habe ich in den Quellen gefunden:“, kein Zitat mitten im Satz; Quelle nur als „(BPGG § 4)“. |
| Nächste Schritte | Handlungen in Sie-Form („Stellen Sie den Antrag …“, „Legen Sie … bei“), Dateinamen als Kurznamen. |
| Vorbehalt | „Mir fehlen noch Angaben: Bundesland.“ statt Feld-IDs. |
| Grenze, Notfall | Ein Gedanke je Satz; Notfall nennt zuerst 144, dann wer der Lotse ist, dann 1450. |
| Antrag | „Ihr Antrag ist als Entwurf fertig. Abgeschickt wird nichts.“, „Bitte noch selbst ausfüllen“, Quellen kurz. |
| Termin | „Wann passt es Ihnen besser: vormittags oder nachmittags?“ statt Gedankenstrich; Datum als 17.11.2026. |
| UC4 | Prompt verlangt Bürgersprache; das Modell erklärte „Median“ von sich aus („Die Hälfte wartet kürzer …“). |

Was Karl weiter stolpern lässt: Das Modell bleibt nahe am Gesetzeswortlaut („Pflegegeld gebührt bei ständigen
Betreuungs- und Hilfsbedarf“, „beim zuständigen Entscheidungsträger“), manchmal mit Grammatikfehler.

## Grenzen

- **Deckung gegen Bürgersprache.** Die Deckungsprüfung verlangt die Wörter des Zitats. Eine erste Prompt-Fassung
  („gebührt“ → „gibt es“, Sie-Form) ließ das Modell Personen und Umschreibungen ergänzen; in der Pflege-Antwort
  fielen dann 2 von 4 Aussagen durch (Deckung 0,11 und 0,33), und die Hauptaussage fehlte. Die Fassung jetzt sagt
  „einfach, aber mit den Wörtern des Zitats“ und „Zitat genau zu dem Teil, den die Aussage sagt“: 4 von 4
  Aussagen gedeckt, aber Amtsdeutsch bleibt teils stehen. Mehr Bürgersprache verlangt eine Deckung, die
  Umschreibungen kennt (Gleichwerte in `deckung.yaml`), nicht mehr Prompt.
- **Englisch** behält deutsche Begriffe aus dem Zitat („zuständigen Entscheidungsträger“), und Formular- und
  Unterlagentexte sind nur deutsch.
- `eval.mittlere_satzlaenge` zählt Zeilen ohne Satzpunkt mit der nächsten Zeile zusammen (Listen); für den Antrag
  ergibt es 36,2 statt 11,0. `sprache.mittlere_laenge` trennt Zeilen.
- Ein Lauf je Gespräch; Modellantworten schwanken. Das Lotse-Set ist nicht gemessen.
