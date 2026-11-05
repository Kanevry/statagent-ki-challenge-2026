import { render } from "@testing-library/react";
import { FOLIEN_ORDNER, leseFolien, type Folie } from "../../../lib/praesentation/folien";
import { inlineText } from "../../../lib/praesentation/markdown";
import {
  absatzTexte,
  herkunft,
  listenPunkte,
  screenshotKennung,
  tabelle,
  ueberschrift,
  zahlWert,
  zeitZeile,
} from "../../../lib/praesentation/szenen-daten";
import { BILDER } from "../bilder";
import { monatText } from "./falsche-zahl";
import { szeneFuer, SZENEN } from "./index";

// Fängt ab: eine Szene, die Inhalt aus dem Markdown verliert (Überschrift, Absatz, Liste, Tabelle, Herkunft), eine
// szene im Frontmatter ohne Komponente, ein Fenster ohne echtes Bild, ein Link auf eine nicht freigegebene Route,
// Gedankenstriche auf der Bühne und falsche Zahlen aus deutscher Schreibweise.

const folien = leseFolien(FOLIEN_ORDNER);
const mitSzene = folien.flatMap((f, i) => (szeneFuer(f.szene) ? [[f.szene ?? "", f, i + 1] as const] : []));

function zeige(id: string, folie: Folie, nr: number, takt = 0) {
  const { Komponente } = szeneFuer(id)!;
  return render(<Komponente folie={folie} nr={nr} aktiv takt={takt} />).container;
}

describe("Hilfen", () => {
  it("liest deutsche Zahlen, schreibt Zeiten ohne Strich und Kennungen zweistellig", () => {
    expect([zahlWert("392.236"), zahlWert("2.880"), zahlWert("−0,067 %"), zahlWert("keine")]).toEqual([392236, 2880, -0.067, Number.NaN]);
    const f = folien[0]!;
    expect(zeitZeile({ ...f, zeit: "1:00–2:00" }, 3)).toBe("3 · 1:00 bis 2:00");
    expect(screenshotKennung({ ...f, daten: { screenshot: "SC7" } })).toBe("SC07");
    expect(screenshotKennung({ ...f, daten: {} })).toBeUndefined();
  });
});

it("die neun Folien laufen alle als Szene, Takte hat nur falsche-zahl", () => {
  expect(folien.map((f) => f.szene)).toEqual(Object.keys(SZENEN));
  expect(Object.entries(SZENEN).filter(([, e]) => e.takte > 0).map(([id, e]) => [id, e.takte])).toEqual([["falsche-zahl", 3]]);
  expect(szeneFuer("gibt-es-nicht")).toBeUndefined();
});

describe.each(mitSzene)("Szene %s", (id, folie, nr) => {
  it("zeigt Überschrift, Absätze, Listen, Tabellenwerte, Herkunft und Zeit aus dem Markdown", () => {
    const text = zeige(id, folie, nr, 3).textContent ?? "";
    const kopf = ueberschrift(folie);
    if (kopf) expect(text).toContain(kopf);
    for (const a of absatzTexte(folie)) expect(text).toContain(a);
    for (const p of listenPunkte(folie)) expect(text).toContain(id === "einstieg" ? inlineText(p).replace(/^UC\d:\s*/, "") : inlineText(p));
    const t = tabelle(folie);
    if (t && id !== "falsche-zahl") for (const zeile of t.zeilen) expect(text).toContain(zeile.at(-1) ?? "");
    const quelle = herkunft(folie);
    if (quelle) expect(text).toContain(quelle);
    expect(text).toContain(zeitZeile(folie, nr));
    expect(text).not.toMatch(/ [–—] /);
  });

  it("zeigt kein Fenster, solange bilder.ts kein Bild zur Kennung hat", () => {
    const kennung = screenshotKennung(folie);
    if (kennung && Object.hasOwn(BILDER, kennung)) return;
    expect(zeige(id, folie, nr, 3).querySelector("figure, img")).toBeNull();
  });
});

it("falsche-zahl baut eine Säule je Tabellenzeile und zeigt die Takt-Sätze aus der Liste", () => {
  const eintrag = mitSzene.find(([id]) => id === "falsche-zahl");
  expect(eintrag).toBeDefined();
  const [, folie, nr] = eintrag!;
  const ansicht = zeige("falsche-zahl", folie, nr, 3);
  expect(ansicht.querySelectorAll('[style*="--h:"]')).toHaveLength(tabelle(folie)?.zeilen.length ?? 0);
  expect(ansicht.querySelectorAll("ol li")).toHaveLength(3);
  // Achse kurz aus der Tabelle (JJJJ-MM), Stempel aus dem Frontmatter, keine Monatsangabe als JJJJ-MM sichtbar.
  const zeilen = tabelle(folie)?.zeilen ?? [];
  const text = ansicht.textContent ?? "";
  for (const i of [0, zeilen.length - 1]) expect(text).toContain(monatText(zeilen[i]?.[0] ?? ""));
  expect(text).toContain(folie.daten.stempel);
  expect(text).not.toMatch(/\b20\d\d-\d\d\b/);
  expect([monatText("2024-08"), monatText("2025-10"), monatText("2026-07"), monatText("2025-10", true)]).toEqual([
    "Aug 2024",
    "Okt 2025",
    "Jul 2026",
    "Oktober 2025",
  ]);
});

it("sichtbare Monatsangaben stehen ausgeschrieben, nie als JJJJ-MM oder MM/JJJJ (außer Tabellen und Datenmustern)", () => {
  for (const f of folien) {
    for (const t of [...absatzTexte(f), ...listenPunkte(f).map(inlineText), herkunft(f) ?? "", ueberschrift(f) ?? ""]) {
      expect(t, f.id).not.toMatch(/\b20\d\d-\d\d\b|\b\d\d\/20\d\d\b/);
    }
  }
});

it("annahme nimmt den Treffer-Satz aus dem Frontmatter", () => {
  const eintrag = mitSzene.find(([id]) => id === "annahme");
  expect(eintrag).toBeDefined();
  const [, folie, nr] = eintrag!;
  expect(zeige("annahme", folie, nr).textContent).toContain(folie.daten.treffer);
});

it("schluss verlinkt nur eine freigegebene Route", () => {
  const eintrag = mitSzene.find(([id]) => id === "schluss");
  expect(eintrag).toBeDefined();
  const [, folie, nr] = eintrag!;
  expect(zeige("schluss", folie, nr).querySelector("a")?.getAttribute("href")).toBe(folie.daten.route);
  const fremd = { ...folie, daten: { ...folie.daten, route: "/gibt-es-nicht" } };
  expect(zeige("schluss", fremd, nr).querySelector("a")).toBeNull();
});
