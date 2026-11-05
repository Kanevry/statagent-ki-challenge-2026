# Backup-Video: Plan und Metadatenbericht

Gehört zu GitLab #90, Epic #26. Das Video ist Stufe 3 der Rückfallstufen im `docs/praesentation/demo-drehbuch.md`.

## Zweck

Fällt Netz, Modell oder Rechner aus, zeigt das Video die Demo trotzdem. Es läuft lokal und braucht kein Netz. Es ist eine Aufzeichnung und wird immer so benannt: „Das ist eine Aufzeichnung von heute früh.“ Dieses Issue lädt nichts hoch und versendet nichts.

## Inhalt

Das Video zeigt D1 bis D3 aus dem Drehbuch, in dieser Reihenfolge:

1. D1 Lauf 2025-03 und Qualitätsbericht: Volldubletten (F8) und fehlende freie Dienstverträge (F9), Monat angehalten und vorläufig.
2. D2 Änderung per Sprache: Auftrag, Vorschlag mit Regel-Diff und Zahlen vorher/nachher, Freigabe mit Vor- und Nachname, Protokoll.
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
- Texte folgen der Sprachregel: kurze Sätze, keine Gedankenstriche als Stilmittel, jede Zahl mit Kennung aus dem Faktenblatt.

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
| Datei (Pfad) | |
| Ablage (Repo oder lokal außerhalb) | |
| Dauer (Minuten:Sekunden, aus `ffprobe`) | |
| Größe in Byte (> 0) | |
| SHA-256 (`shasum -a 256`) | |
| Auflösung (`ffprobe`, Soll 1920 × 1080) | |
| Aufgenommen am (Datum, Uhr) | |
| Stand (Commit) der aufgenommenen App | |
| Abspieltest offline: Datum | |
| Abspieltest offline: Uhrzeit | |
| Abspieltest offline: Ergebnis | bestanden / nicht bestanden |
| Kennzeichnung „Aufzeichnung“ im Bild von Sekunde 0 | ja / nein |
| Anmerkungen | |

### Sichtprüfung

| Prüfpunkt | Ergebnis |
|---|---|
| Ergebniszahl sichtbar | ja / nein |
| Protokoll sichtbar | ja / nein |
| Eingeblendete Texte lesbar | ja / nein |
| Sichtbare Secrets | 0 / Anzahl |

| Feld | Wert |
|---|---|
| Prüfer | |
| Datum | |
| Uhrzeit | |
