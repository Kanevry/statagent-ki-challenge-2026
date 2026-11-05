# Design: Anti-Schablonen-Gate

Owner-Vorgabe: „alles was ai schreit oder ai slop ist muss identifiziert und entfernt werden“. Das Gate macht daraus
einen Test, der in der CI läuft und die Abgabe blockiert, solange die Oberfläche generische KI-Muster zeigt.

## Warum es das Gate gibt

Die Jury sieht in Sekunden, ob eine Oberfläche nach Vorlage aussieht. Ein Satz im Styleguide verhindert das nicht,
eine Messung schon. `measureSlop` (`web/tests/lib/slop-measure.js`) zählt die Erkennungsmuster in der gerendert
dargestellten Seite. Die Zahlen entstehen durch Code, nicht durch ein Sprachmodell.

Bezug auf die drei Räume: In StatAgent (UC3) tragen Kennzahl, Herkunft-Chip und Freigabe-Karte die Aussage, im
KI-Lotsen (UC1) die Antwort mit Beleg, im HealthPolicy Simulator (UC2) die Positionen des Panels. Jedes Muster unten
lenkt den Blick von diesem Inhalt weg auf Deko, deshalb zählt es als Treffer.

## Der Katalog (zwölf Schlüssel, alle müssen 0 sein)

| Schlüssel | Erkennt | Behebung |
|---|---|---|
| `kickersMono` | Kleines Label in Großbuchstaben und Monospace über einer Überschrift | Label streichen oder in die Überschrift einbauen; Monospace nur für Daten |
| `kickersCaps` | Kleines Versal-Label (≤ 14 px, gesperrt) über einer Überschrift | Label streichen; die Überschrift trägt die Aussage allein |
| `iconTiles` | Getönte quadratische Kachel mit Icon neben oder über einer Überschrift | Kachel entfernen oder Icon ohne Kachel direkt am Text setzen |
| `shadowCards` | Karte mit Radius ≥ 12 px, gefülltem Grund und weichem Schatten (Blur ≥ 8 px) | Schatten entfernen, Fläche über Abstand und Linie gliedern |
| `ghostCards` | Karte mit Haarlinie und gleichzeitig großem weichem Schatten | Entweder Linie oder Fläche, nie beides mit Schatten |
| `gradientText` | Text mit Farbverlauf (`background-clip: text`) | Volltonfarbe aus den Tokens |
| `glassBlur` | Milchglas durch `backdrop-filter: blur(≥ 4px)` | Deckender Grund |
| `lightOrbs` | Große, runde, stark verwischte Lichtkugeln als Dekor | Dekor streichen |
| `pulsingDecor` | Leeres Element mit `pulse`- oder `ping`-Animation | Statische Statusanzeige mit Text |
| `sparklesNonAi` | Funkel-Icon (lucide Sparkles), das nicht an KI-Inhalt hängt | Anderes Icon oder entfernen; nur bei echter KI-Funktion erlaubt |
| `emDashes` | Gedankenstrich (U+2014) im sichtbaren Text | Punkt, Komma oder Doppelpunkt setzen |
| `questionHeadings` | Überschrift (h1 bis h3), die mit Fragezeichen endet | Aussage als Überschrift formulieren |

Die Werte stehen je Route und Viewport als Anhang im Playwright-Bericht. `measureSlop` liefert weitere Zahlen
(`italicSerifLines`, `sideStripes`, `pureWhiteBg`, `pureBlackText`, `dotLines`); sie gehören nicht zu den zwölf
und lassen den Test nicht fehlschlagen.

## Ausnahme: `genericFontShare`

`genericFontShare` (Anteil von Inter, Roboto, Arial und Ähnlichem am Text) wird nicht geprüft. Inter ist als
Schrift für Fließtext und Oberfläche Vertrag (Tokens in `shared/ui`). Die Wiedererkennbarkeit kommt aus Layout,
Sprache und Daten, nicht aus einer Exotenschrift.

## Wie das Gate misst

- `web/tests/slop.spec.ts` ruft je Route `measureSlop({ root: "body" })` auf. Der Standard `root: "main"` ließe
  Kopfzeile und Navigation aus, und genau dort sitzen viele Muster.
- Der Test prüft zuerst, dass alle zwölf Schlüssel im Ergebnis vorkommen. Ein fehlender Schlüssel wäre sonst
  als 0 lesbar und ließe den Test still bestehen.
- Routen: `/`, `/uc1`, `/uc2`, `/uc3` (aus der Registry `shared/ui/src/ucs.ts`), `/praesentation`, `/_bausteine`.
  Je Route Desktop (1440×900) und Mobil (390×844), nur Chromium. Erwartet werden HTTP 200 und 0 Treffer.
- Beleg, dass das Gate misst: `web/tests/fixtures/slop-positive.html` ist eine absichtlich schlechte Seite und muss
  in jedem der zwölf Schlüssel mindestens 1 liefern. Wer die Messfunktion austauscht, sieht hier sofort, wenn ein
  Schlüssel stumm geworden ist.

## Lokal starten

```bash
pnpm --filter web exec playwright install chromium   # einmalig, falls der Browser fehlt
pnpm --filter web run test:slop
```

Playwright startet den Dev-Server selbst (Port 3210, `LLM_PROVIDER=mock`, `KIC_BAUSTEINE=1`) und beendet ihn
danach. Ein bereits laufender Server auf Port 3210 wird lokal wiederverwendet. Berichte: `web/playwright-report/`
(HTML) und `web/test-results/slop-report.json`.

## Regel zu `NOCH_OFFEN`

Routen, die noch nicht gebaut sind, stehen in der Liste `NOCH_OFFEN` in `web/tests/slop.spec.ts`, mit Begründung.
Die Liste ist der einzige Weg, eine Route auszunehmen, und sie reinigt sich selbst: Eine Route in `NOCH_OFFEN`
muss 404 liefern. Ist sie gebaut, wird der Test rot („Route gebaut, aus NOCH_OFFEN streichen“). Mit `ABGABE=1`
verlangt ein eigener Test eine leere Liste; vor der Abgabe (Fr 06.11.2026 09:00) läuft das Gate so.

Unterseiten eines UC (z. B. `/uc3/lauf`) misst das Gate über die Links der UC-Seite mit. Gemessen wird nach
`document.fonts.ready` mit `reducedMotion: reduce`; der Bericht enthält je Seite Werte und Beispiele (`samples`).
In der CI läuft der Produktions-Build (`next build && next start`), lokal der Dev-Server.
