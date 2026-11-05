# @kic/ui

Gemeinsame Oberfläche der Plattform: Design-Tokens „Klarton+“ und ruhige Basis-Elemente (#56).
Einstieg per Subpath, ohne gemeinsamen Barrel: `@kic/ui/tokens.css`, `@kic/ui/basis`.

## Tokens

`src/tokens.css` ist ein Tailwind-4-`@theme`. Tailwinds Standardpalette, -schriften und -größen sind
abgeschaltet: `bg-blue-500`, `text-lg` oder `font-serif` erzeugen nichts.

| Gruppe | Tokens | Klassen |
|---|---|---|
| Farben | `paper` `white` `ink` `slate` `line` `gruen` `gruen-bg` `mint` `navy` `violett` `violett-bg` `gelb` `gelb-bg` `warn-fg` `warn-bg` `err-fg` `err-bg` | `bg-paper`, `text-ink`, `border-line`, `border-violett` |
| Schriften | `display` (Space Grotesk), `sans` (Inter, Standard), `mono` (JetBrains Mono) | `font-display`, `font-sans`, `font-mono` |
| Größen | `56` `32` `28` `20` `16` `14` `13` `12` `11` (px, mit eigener Zeilenhöhe) | `text-56` … `text-11` |
| Abstände | Tailwind-Standard `--spacing` = 4 px; Stufen 4/8/16/24/32/48/64 | `p-1` `p-2` `p-4` `p-6` `p-8` `p-12` `p-16` (ebenso `gap-*`, `m-*`) |

Regeln: Violett nur für KI-Label und 2-px-Linie, Gelb nur als Fläche, nie als Schrift. Hell, kein Dark Mode.
Die Schriften kommen offline aus `@fontsource-variable/*` (OFL-1.1), ohne CDN.

Einbinden in einer App (`web/app/globals.css`):

```css
@import "tailwindcss";
@import "@kic/ui/tokens.css";
@source "../../shared/ui/src";
```

Beispiel: `<main className="bg-paper text-ink">` und `<h1 className="font-display text-56 font-bold">`.

## Basis-Elemente

`import { Ueberschrift, Fliesstext, Zahl, Knopf, knopfKlassen, Feld, Tabelle, Status, Leerzustand, Akzent } from "@kic/ui/basis";`

- `Knopf` ist standardmäßig `type="button"` und verwirft `autoFocus`. Je Screen höchstens ein primärer Knopf.
- `Status` zeigt immer Symbol und Wort (`ok`, `warnung`, `fehler`, `info`).
- `Akzent` ist eine linke Farblinie: `beleg` grün, `ki` violett, `warnung` gelb, `fehler` rot.
- Alle Elemente sind auf `/_bausteine` zu sehen (in Produktion nur mit `KIC_BAUSTEINE=1`).

## Herkunft und Snapshot erneuern

Quelle ist die Pen-Datei `design/ki-challenge.pen`, Variablen `l-*` (Farben, Präfix entfällt) und
`font-head`/`font-body`/`font-mono`. Die Pen-Datei hat keine Größen-Variablen; die Skala steht im
PRD (Vertrag D) und kommt in den Klarton+-Frames vor. `tokens.snapshot.json` hält den Stand fest,
`tests/tokens.test.ts` vergleicht ihn mit `tokens.css`.

Snapshot erneuern, wenn sich in Pencil etwas ändert:

1. In Pen die Datei `ki-challenge.pen` öffnen, über Pencil-MCP `execute` lesend `Print(GetVariables())` ausführen.
2. Die `l-*`-Farben und die drei `font-*`-Werte 1:1 nach `tokens.snapshot.json` übernehmen, `kopf.zeitstempel` setzen.
3. `src/tokens.css` angleichen, dann `pnpm --filter @kic/ui test`.

Eine Änderung nur in `tokens.css` lässt den Test fehlschlagen. Das ist so gewollt.
