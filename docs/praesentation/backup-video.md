# Backup-Video: Plan und Metadatenbericht

Gehört zu GitLab #90, Epic #26. Das Video ist Stufe 3 der Rückfallstufen im `docs/praesentation/demo-drehbuch.md`.

## Zweck

Fällt Netz, Modell oder Rechner aus, zeigt das Video die Demo trotzdem. Es läuft lokal und braucht kein Netz. Es ist eine Aufzeichnung und wird immer so benannt: „Das ist eine Aufzeichnung von heute früh.“ Dieses Issue lädt nichts hoch und versendet nichts.

## Inhalt

Das Video zeigt D1 bis D3 aus dem Drehbuch, in dieser Reihenfolge:

1. D1 Lauf 2025-03 und Qualitätsbericht: Volldubletten (F8) und fehlende freie Dienstverträge (F9), Monat angehalten und vorläufig.
2. D2 Rückblick: die drei Aufträge der Aufgabe in der Liste der Freigaben, jeder mit Vor- und Nachnamen freigegeben. Dann Vorschlag 24 mit Regel-Unterschied und Zahlen vorher und nachher.
3. D3 Datenanfrage Männer und Frauen je Bundesland mit sichtbarer SQL.

Optional D4 kommt nicht ins Video. Eine Einblendung „Aufzeichnung vom [Datum]“ steht von der ersten bis zur letzten Sekunde im Bild.

## Aufnahme

- Zeitpunkt: vor der Probe, spätestens Fr 06.11.2026 05:45 (Europe/Vienna), auf dem Stand, der um 07:00 eingefroren wird. Eine erste Aufnahme entsteht, sobald D1 bis D3 in der Oberfläche laufen.
- In der Probe ab 06:00 folgen Abspieltest und Ausfallprobe mit dieser Datei. Nach dem Freeze wird nur noch der SHA-256 abgeglichen.
- Ändert sich die Demo nach der Aufnahme noch, bleibt die Aufzeichnung gültig. Bernhard sagt sie mit ihrer Uhrzeit an.
- Werkzeug: `browser-kit record` (dev-browser). Siehe Skill `browser`.
- Auflösung: 1920 × 1080.
- Der Terminal-Teil (D2) wird als Bildschirmaufnahme eingebunden oder als Web-Terminal gezeigt. Die Wahl steht im Bericht unter „Anmerkungen“.
- Vor der Aufnahme: keine Secrets im Bild. Umgebungsvariablen nicht anzeigen, keine `.env.local` öffnen, keine Tokens in Adresszeile oder Tabs.
- Beispiel-Kennungen einzelner Verhältnisse (VVH_ID) und Einzeldaten kommen nicht ins Bild.

## Render und Schnitt

- Render und Schnitt laufen auf dem Zweitrechner, nicht auf dem Vortragsrechner. Der Vortragsrechner bleibt frei für die Probe und die Demo.
- Der fertige Export wird auf den Vortragsrechner kopiert und dort geöffnet.

## Ton und Texte

- Keine Stimme. Eingeblendete Texte erklären jeden Schritt, kurz und gut lesbar.
- Es wird keine Klonstimme und kein Avatar verwendet.
- Falls doch Stimme oder Avatar zum Einsatz kommen: sichtbare Kennzeichnung „KI-generiert“ ab Sekunde 0 bis zum letzten Bild, wie es Art. 50 Abs. 4 AI Act verlangt. Dann den Text vorher freigeben lassen und im Bericht vermerken.
- Texte folgen der Sprachregel: kurze Sätze, keine Gedankenstriche als Stilmittel, jede Zahl mit Kennung aus dem Belegregister.

## Ablage

- Ziel: `docs/praesentation/backup-demo.mp4` (oder `.webm`), nur wenn die Datei kleiner als 25 MB ist.
- Ist sie größer: lokal außerhalb des Repos ablegen und den Pfad im Bericht eintragen. Die Datei kommt nicht ins Repo.
- Der Metadatenbericht unten kommt in jedem Fall ins Repo.

## Abspieltest

- Netz sperren (WLAN und Kabel aus).
- Datei lokal im Player öffnen und ganz abspielen.
- Datum und Uhrzeit aus `TZ=Europe/Vienna date` im Bericht eintragen.
- Danach das Netz wieder einschalten.

## Befehle für den Bericht

```
ls -l <datei>                      # Größe in Byte
shasum -a 256 <datei>              # SHA-256
ffprobe -v error -show_entries stream=width,height -show_entries format=duration -of default=nw=1 <datei>
TZ=Europe/Vienna date              # Datum und Uhrzeit
```

## Metadatenbericht

Alle Werte bleiben leer, bis die Datei fertig ist. Nie schätzen.

| Feld | Wert |
|---|---|
| Datei (Pfad) | `docs/praesentation/backup-demo.mp4`, Kopie in `~/Movies/ki-challenge/` auf dem Rechner der Aufnahme |
| Ablage (Repo oder lokal außerhalb) | Repo, kleiner als 25 MB |
| Dauer (Minuten:Sekunden, aus `ffprobe`) | 2:45 |
| Größe in Byte (> 0) | 4141777 |
| SHA-256 (`shasum -a 256`) | `8ff01e63913c3854b10e9854e99aff9399f633b595bb93742160e8a6f0faa972` |
| Auflösung (`ffprobe`, Soll 1920 × 1080) | 1920 × 1080 |
| Aufgenommen am (Datum, Uhr) | 06.11.2026, 03:21 |
| Stand (Commit) der aufgenommenen App | `809da6d`, Vorführ-Instanz `93a491d`, gleicher Inhalt laut Lane Vorführung |
| Abspieltest offline: Datum | 06.11.2026 |
| Abspieltest offline: Uhrzeit | 06:21 bis 06:24 |
| Abspieltest offline: Ergebnis | bestanden, bis zum Ende, nur der Browser ohne Netz, der Rechner nicht |
| Kennzeichnung „Aufzeichnung“ im Bild von Sekunde 0 | ja |
| Anmerkungen | Aufnahme gegen die Vorführ-Adresse, nur lesend. Render auf dem Rechner der Session statt auf dem Zweitrechner, der seit 00:35 ausgefallen ist (Auftrag des Leads; 184 s, 834 MB). Geschnitten: 1,7 s Anfang und 11,4 s Wartezeit bei der Zeitreihe, im Bild genannt. Zeigt D1, D2 Rückblick, Vorschlag 24 und D3, nicht die Live-Änderung und nicht D4. Kein Terminal im Bild. Nach der Aufnahme änderten sich bis main `a6dd221` nur `frage.py`, `woerter.py` und Tests; die drei gezeigten Fragen um 04:17 auf der Instanz nachgeprüft, gleiche Zahlen. Zeigt in D1 die alten Regeln (313.154 + 77.746 = 390.900), „Rechnen“ rechnet live nach den Änderungsaufträgen (397.514). |

### Sichtprüfung

| Prüfpunkt | Ergebnis |
|---|---|
| Ergebniszahl sichtbar | ja |
| Protokoll sichtbar | ja, als Hinweis auf den Protokoll-Commit bei Vorschlag 24 |
| Eingeblendete Texte lesbar | ja |
| Sichtbare Secrets | 0 |

| Feld | Wert |
|---|---|
| Prüfer | Agent UI-Regie, nicht Mensch |
| Datum | 06.11.2026 |
| Uhrzeit | 03:25 |
