# Sprech-Skript Management: 10 Minuten

Erzeugt aus den Sprechernotizen in `web/content/slides-management/` mit `docs/praesentation/werkzeug/skript_management.py`. Änderungen gehören in die Folien, nicht hierher. Folien: `/praesentation/management`, Antworten für die 5 Minuten danach: `management-faq.md`.

Das Zeichen „→“ steht vor dem Satz, der mit dem Klick kommt. Kennungen wie F11 stehen im Belegregister und werden nicht mitgesprochen.

## Folie 1 · Drei Menschen brauchen eine Antwort · 0:00–1:00

> Guten Tag, ich bin Bernhard Götzendorfer, Team OneShotAndy. Die Challenge stellt drei Aufgaben, und hinter jeder steht ein Mensch mit einer Frage. Versicherte wollen wissen, was ihnen zusteht. Entscheider wollen wissen, was eine Entscheidung bewirkt. Und das Statistik-Team will sicher sein, dass jede veröffentlichte Zahl stimmt. Drei Fragen, aber alle drei brauchen dasselbe: eine Antwort, der sie trauen können. Bewertet wird die Statistik, deshalb zeige ich es Ihnen dort. An einem Fall aus den Daten der Challenge.

Belege: keine Zahl.

## Folie 2 · Im Oktober 2025 fehlte jedes fünfte Beschäftigungsverhältnis. · 1:00–2:30

> Jeden Monat kommt eine Lieferung mit allen Beschäftigungsverhältnissen. Daraus wird eine Zahl, und die geht weiter. Hier sehen Sie 24 Monate, die Säulen sind fast gleich hoch. So sollte es auch sein.
>
> → Im Oktober 2025 fehlen in der Lieferung 78.949 Beschäftigungsverhältnisse. Jedes fünfte.
>
> → Wer einfach zählt, meldet 313.154 statt 394.200 im September. Das wäre ein Einbruch um ein Fünftel, in einem einzigen Monat. Einen Einbruch, den es nie gab.

Belege: F11, F17.

## Folie 3 · StatAgent veröffentlicht nicht, er hält an und fragt nach. · 2:30–3:15

> Und jetzt der Unterschied, um den es uns geht. StatAgent veröffentlicht diesen Monat nicht. Er hält an und schreibt eine Rückfrage an die Fachabteilung. Bis zur Antwort schreibt er 77.746 fehlende Verhältnisse aus dem September fort und kennzeichnet den Monat als vorläufig. Gelöscht wird nichts, überschrieben wird nichts. Im November sind 78.733 der fehlenden wieder da. Das Programm hat nichts entschieden. Es hat gemerkt, dass etwas nicht stimmt, und einem Menschen die Frage gestellt.

Belege: F11.

## Folie 4 · Den offiziellen Bericht nachgerechnet: 2.880 von 2.880 Zahlen stimmen. · 3:15–4:15

> Woher wissen wir, dass das Programm richtig rechnet? Das ist die Frage, die ich an Ihrer Stelle stellen würde. Der Veranstalter hat einen offiziellen Bericht für August 2024 mitgegeben: 13 Tabellen, 2.880 Zahlen. StatAgent rechnet ihn aus den Rohdaten selbst nach, und eine zweite Rechnung ohne unseren Code prüft das gegen. Alle 2.880 stimmen, null Abweichungen.
>
> → Das ist ein Monat. Für die anderen 23 gibt es keinen Vergleich, das sage ich Ihnen offen. Dort wachen 24 Prüfregeln, und zwei Monate haben sie angehalten: März und Oktober 2025.

Belege: F1, F15.

## Folie 5 · Acht Arten von Fehlern gefunden, nichts gelöscht. · 4:15–5:15

> In den Daten stecken Fehler.
>
> → 370 Beschäftigungsverhältnisse sind laut Lieferung im 13. Monat geboren.
>
> → Sieben Datensätze haben 117 bis 153 Jahre.
>
> → Im März 2025 sind 1.663 Zeilen doppelt. Dazu fünf weitere Arten, acht insgesamt. Gelöscht haben wir nichts. Jeder Fehler hat eine Regel oder einen Halt, jede Annahme ist begründet und mit Beleg dokumentiert. Und wo wir nachfragen wollten, steht die Rückfrage im Bericht.

Belege: F4, F5, F7, F8, F9.

## Folie 6 · Die KI versteht, ein Mensch gibt frei, das Programm rechnet. · 5:15–6:15

> Das ist die eine Idee dahinter, und sie gilt für alle drei Aufgaben. Drei Rollen, sauber getrennt.
>
> → Die KI versteht, was jemand in einem Satz will, und schreibt daraus einen Vorschlag. Mehr darf sie nicht.
>
> → Wirksam wird ein Vorschlag erst mit dem Vor- und Nachnamen eines Menschen. Das steht mit Uhrzeit im Protokoll. „Team“ als Name lehnt das Programm ab.
>
> → Und gerechnet wird ohne KI. Zwei Läufe mit denselben Daten ergeben dieselben Zahlen. Eine Zahl, die jedes Mal anders herauskommt, wäre für eine Statistik wertlos.

Belege: F3, F26.

## Folie 7 · Drei Aufträge in Alltagssprache, am selben Tag umgesetzt. · 6:15–7:15

> Die Aufgabe stellt drei Änderungsaufträge, zum Beispiel: Dienstvertrag und freien Dienstvertrag zusammenfassen. Die habe ich der Maschine in Sätzen gegeben. Sie schrieb Vorschläge, mit den Zahlen vorher und nachher. Wirksam wurden sie erst nach Prüfung und mit Namen. Ein Vorschlag braucht beim Modell drei bis neun Sekunden und kostet zum Listenpreis rund einen Cent. Ehrlich dazu: Nicht jeder Satz sitzt beim ersten Mal. Zwei der drei Aufträge haben mehrere Anläufe gebraucht. Alle Versuche rund um die drei Aufträge zusammen haben rund 40 Cent gekostet. Die Kosten sind also nicht das Problem. Die Arbeit ist die Prüfung durch den Menschen.

Belege: F19, F26, F27.

## Folie 8 · Gerechnet wird ohne KI, und das Ergebnis ist jedes Mal gleich. · 7:15–8:15

> Jetzt zu den Zahlen, nach denen Sie vermutlich fragen wollen. Alle 24 Monatslieferungen, zusammen gut zehn Millionen Zeilen, rechnet das Programm in rund 13 Minuten, gemessen auf unserem Rechner, der dabei auch anderes zu tun hatte. Dabei fällt kein einziger Modellaufruf an, auch nicht bei einer Frage an die Daten. Und wir haben das 72-mal wiederholt: 72-mal genau dasselbe Ergebnis. Was ich Ihnen nicht sagen kann, ist die Ersparnis. Wir wissen nicht, wie lange der Prozess bisher dauert. Darum frage ich Sie: Wie lange dauert das bei Ihnen heute?

Belege: F16, F28.

## Folie 9 · Eine Frage, drei Antworten: Statistik, Simulator, Lotse. · 8:15–9:00

> Und was für die Statistik gilt, trägt auch die anderen zwei Aufgaben. Eine Frage läuft durch alle drei.
>
> → StatAgent liefert die geprüfte Zahl: 7.498 Beschäftigungsverhältnisse.
>
> → Der Simulator wägt ab, was mehr oder weniger Personal für Wartezeiten bedeutet.
>
> → Der Lotse erklärt es in einfachen Worten. Drei Aufgaben, ein Kern, ein Einstieg.

Belege: F18.

## Folie 10 · Die Verantwortung bleibt beim Menschen. · 9:00–9:45

> Drei Sätze zur Verantwortung, weil das am Ende der Punkt ist. Jede Regeländerung und jede Lieferung trägt einen Vor- und Nachnamen und einen Zeitpunkt. Ist ein Monat veröffentlicht, bleibt seine Zahl, und Abweichungen stehen im Bericht, statt dass wir etwas überschreiben. Und das Modell sieht keine Einzeldaten, nur Regeln und Summen. Die Verantwortung für jede Zahl bleibt bei Menschen.

Belege: keine Zahl.

## Folie 11 · Jede Zahl nachrechenbar. · 9:45–10:00

> Jede Zahl lässt sich nachrechnen, jede Änderung hat einen Namen. Danke. Ich freue mich auf Ihre Fragen.

Belege: keine Zahl.

## Zeittabelle

Geschätzt mit 130 Wörtern je Minute. Gemessen wird in der Probe (`probe.md`).

| Folie | Soll (s) | Wörter | Schätzung (s) |
|---|---|---|---|
| 1 | 60 | 77 | 36 |
| 2 | 90 | 69 | 32 |
| 3 | 45 | 74 | 34 |
| 4 | 60 | 87 | 40 |
| 5 | 60 | 64 | 30 |
| 6 | 60 | 85 | 39 |
| 7 | 60 | 99 | 46 |
| 8 | 60 | 89 | 41 |
| 9 | 45 | 50 | 23 |
| 10 | 45 | 59 | 27 |
| 11 | 15 | 17 | 8 |
| **Summe** | **600** | **770** | **356** |
