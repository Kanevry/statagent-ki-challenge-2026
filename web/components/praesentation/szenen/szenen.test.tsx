import { render } from "@testing-library/react";
import { FOLIEN_ORDNER, leseFolien, type Folie } from "../../../lib/praesentation/folien";
import { inlineText } from "../../../lib/praesentation/markdown";
import {
  absatzTexte,
  frontmatterListe,
  herkunft,
  listenPunkte,
  screenshotKennung,
  tabellen,
  ueberschrift,
  uebergaenge,
  zahlWert,
} from "../../../lib/praesentation/szenen-daten";
import { bildFuer } from "../bilder";
import { monatText } from "./falsche-zahl";
import { szeneFuer, SZENEN } from "./index";

// Fängt ab: eine Szene, die Inhalt aus dem Markdown verliert (Überschrift, Absatz, Liste, Tabelle, Herkunft), eine
// szene im Frontmatter ohne Komponente, ein Bild ohne echte Aufnahme in bilder.ts, Elemente eines Takts, die vor
// ihrem Takt schon sichtbar geschaltet sind, Zeitmarken auf der Bühne, Gedankenstriche und Monate als JJJJ-MM.

const folien = leseFolien(FOLIEN_ORDNER);
const mitSzene = folien.flatMap((f, i) => (szeneFuer(f.szene) ? [[f.szene ?? "", f, i + 1] as const] : []));
const MONAT_ALS_ZIFFERN = /\b20\d\d-\d\d\b|\b\d\d\/20\d\d\b/;

function zeige(id: string, folie: Folie, nr: number, takt = 0) {
  const { Komponente } = szeneFuer(id)!;
  return render(<Komponente folie={folie} nr={nr} aktiv takt={takt} />).container;
}
const folieMit = (id: string) => {
  const e = mitSzene.find(([s]) => s === id);
  expect(e, `keine Folie mit szene: ${id}`).toBeDefined();
  return e!;
};

describe("Hilfen", () => {
  it("liest deutsche Zahlen, Bildkennungen und Übergänge", () => {
    expect([zahlWert("392.236"), zahlWert("2.880"), zahlWert("−0,067 %"), zahlWert("keine")]).toEqual([392236, 2880, -0.067, Number.NaN]);
    const f = folien[0]!;
    expect(screenshotKennung({ ...f, daten: { screenshot: "SC7" } })).toBe("SC07");
    expect(screenshotKennung({ ...f, daten: { screenshot: "freigabe-echt" } })).toBe("freigabe-echt");
    expect(screenshotKennung({ ...f, daten: { screenshot: "../x.png" } })).toBeUndefined();
    expect(screenshotKennung({ ...f, daten: {} })).toBeUndefined();
    expect(uebergaenge("C-C J-J Q-R J-K x")).toEqual([["C", "C"], ["J", "J"], ["Q", "R"], ["J", "K"]]);
    expect([monatText("2024-08"), monatText("2025-10"), monatText("2026-07"), monatText("2025-10", true)]).toEqual([
      "Aug 2024",
      "Okt 2025",
      "Jul 2026",
      "Oktober 2025",
    ]);
  });
});

it("die zehn Folien laufen alle als Szene; Takte in falsche-zahl, kern, beleg, fehler, annahme und einstieg", () => {
  expect(folien.map((f) => f.szene)).toEqual(Object.keys(SZENEN));
  expect(Object.entries(SZENEN).filter(([, e]) => e.takte > 0).map(([id, e]) => [id, e.takte])).toEqual([
    ["falsche-zahl", 3],
    ["kern", 3],
    ["beleg", 1],
    ["fehler", 3],
    ["annahme", 3],
    ["einstieg", 3],
  ]);
  expect(szeneFuer("gibt-es-nicht")).toBeUndefined();
});

it("nur Folien mit einer echten Aufnahme in bilder.ts nennen ein Bild", () => {
  for (const f of folien) {
    const kennung = screenshotKennung(f);
    if (kennung) expect(bildFuer(kennung), `${f.id}: ${kennung} fehlt in bilder.ts`).toBeDefined();
  }
  // Auf dem Projektor nicht lesbar: keine Szene zeigt mehr ein verkleinertes Bild (UI-Regie, Szene 4).
  expect(folien.filter((f) => screenshotKennung(f)).map((f) => f.szene)).toEqual([]);
});

it("sichtbare Monatsangaben stehen ausgeschrieben (außer Tabellen der Monatswerte und Datenmustern)", () => {
  for (const f of folien) {
    const texte = [...absatzTexte(f), ...listenPunkte(f).map(inlineText), herkunft(f) ?? "", ueberschrift(f) ?? ""];
    for (const t of texte) expect(t, f.id).not.toMatch(MONAT_ALS_ZIFFERN);
  }
});

describe.each(mitSzene)("Szene %s", (id, folie, nr) => {
  const takte = szeneFuer(id)?.takte ?? 0;

  it("zeigt mit allen Takten Überschrift, Absätze, Listen, Tabellenwerte und Herkunft, aber keine Zeitmarke", () => {
    const roh = zeige(id, folie, nr, takte).textContent ?? "";
    // Ohne Leerraum verglichen: Zeilenumbrüche (<br>) zwischen Sätzen sind Gestaltung, kein anderer Text.
    const ohne = (s: string) => s.replace(/\s+/g, "");
    const zeigt = (s: string) => expect(ohne(roh)).toContain(ohne(s));
    const kopf = ueberschrift(folie);
    if (kopf) zeigt(kopf);
    for (const a of absatzTexte(folie)) zeigt(id === "beleg" ? a.replace(/^[\d.]+/, "") : a);
    for (const p of listenPunkte(folie)) zeigt(inlineText(p));
    for (const t of tabellen(folie)) {
      if (id === "falsche-zahl") continue; // Werte stecken als Säulenhöhe, Monate als Achsen-Kurzform
      for (const zeile of t.zeilen) for (const zelle of zeile) zeigt(zelle);
    }
    const quelle = herkunft(folie);
    if (quelle) zeigt(quelle);
    if (folie.zeit) expect(roh).not.toContain(folie.zeit);
    expect(roh).not.toMatch(/ [–—] /);
  });

  it.runIf(takte > 0)("schaltet Takt-Elemente erst mit ihrem Takt an", () => {
    for (let t = 0; t <= takte; t++) {
      const el = zeige(id, folie, nr, t);
      for (const e of el.querySelectorAll<HTMLElement>("[data-takt]")) {
        const ab = Number(e.dataset.takt);
        const klassen = (e.getAttribute("class") ?? "").split(" ");
        expect(klassen.some((c) => c === "an" || /(^|_)an(_|$)/.test(c)), `Takt ${t}, ab ${ab}`).toBe(t >= ab);
      }
    }
  });
});

it("falsche-zahl: eine Säule je Monatswert, Achse in Kurzform, rechts große Zahl, geliefert, Vergleich und vorläufig", () => {
  const [, folie, nr] = folieMit("falsche-zahl");
  const el = zeige("falsche-zahl", folie, nr, 3);
  const zeilen = tabellen(folie)[0]?.zeilen ?? [];
  expect(el.querySelectorAll('[style*="--h:"]')).toHaveLength(zeilen.length);
  const text = el.textContent ?? "";
  for (const i of [0, zeilen.length - 1]) expect(text).toContain(monatText(zeilen[i]?.[0] ?? ""));
  for (const s of [folie.daten.zahl_gross, folie.daten.zahl_geliefert, folie.daten.vergleich, folie.daten.vorlaeufig]) expect(text).toContain(s);
  expect(text).not.toMatch(MONAT_ALS_ZIFFERN);
});

it("falsche-zahl: der angehaltene Monat trägt das Pause-Zeichen, nie einen Haken", () => {
  const [, folie, nr] = folieMit("falsche-zahl");
  const el = zeige("falsche-zahl", folie, nr, 3);
  const okt = el.querySelector<HTMLElement>('[style*="--hg:"]');
  expect(okt?.querySelector('svg[class*="pause"]')).not.toBeNull();
  expect(el.querySelector('svg[class*="haken"]')).toBeNull();
});

it("kern: ohne Bild, die Freigabe-Karte mit Name, Datum und Regel aus dem Frontmatter hängt am zweiten Takt", () => {
  const [, folie, nr] = folieMit("kern");
  const el = zeige("kern", folie, nr, 3);
  expect(el.querySelector("figure, img")).toBeNull();
  const { freigabe_name: name, freigabe_datum: datum, freigabe_regel: regel } = folie.daten;
  expect(name).toBeDefined();
  const karte = [...el.querySelectorAll<HTMLElement>('[data-takt="2"]')].find((e) => e.textContent?.includes(name ?? ""));
  expect(karte?.textContent).toBe(`${name}${datum}${regel}`);
});

it("woerterbuecher: eine Linie je Übergang, ein geteilter Code läuft gelb", () => {
  const [, folie, nr] = folieMit("woerterbuecher");
  const el = zeige("woerterbuecher", folie, nr);
  expect(el.querySelectorAll("svg path")).toHaveLength(uebergaenge(folie.daten.uebergang).length);
});

it("beleg: Monate ab September 2024, angehaltene Monate tragen Pause statt Haken", () => {
  const [, folie, nr] = folieMit("beleg");
  const el = zeige("beleg", folie, nr);
  const angehalten = frontmatterListe(folie.daten.angehalten);
  expect(angehalten.length).toBeGreaterThan(0);
  const monate = [...el.querySelectorAll("li")].filter((li) => li.querySelector("svg"));
  expect(monate[0]?.textContent).toBe("September 2024");
  const halt = monate.filter((li) => li.dataset.angehalten === "ja");
  expect(halt.map((li) => li.textContent)).toEqual(angehalten.map((m) => `${m}, angehalten`));
  for (const li of halt) expect(li.querySelector('svg[class*="haken"]')).toBeNull();
  expect(monate.filter((li) => li.querySelector('svg[class*="haken"]'))).toHaveLength(monate.length - halt.length);
  // Beim Betreten nur Vorlage = StatAgent; das Raster der Monate kommt erst mit Takt 1.
  expect(monate[0]?.closest<HTMLElement>("[data-takt]")?.dataset.takt).toBe("1");
});

it("einstieg: Haken nur für Antworten, deren Name in belegt steht", () => {
  const [, folie, nr] = folieMit("einstieg");
  const el = zeige("einstieg", folie, nr, 3);
  const antworten = [...el.querySelectorAll<HTMLElement>("[data-belegt]")];
  expect(antworten).toHaveLength(3);
  const belegt = frontmatterListe(folie.daten.belegt);
  for (const a of antworten) {
    const name = a.querySelector("strong")?.textContent?.replace(/[:.]\s*$/, "") ?? "";
    const ja = belegt.includes(name);
    expect(a.dataset.belegt, name).toBe(ja ? "ja" : "nein");
    expect(a.querySelector('svg[class*="haken"]') !== null, name).toBe(ja);
  }
  expect(antworten.filter((a) => a.dataset.belegt === "ja")).toHaveLength(belegt.length);
  // Nur ein Name in belegt: genau eine Antwort mit Haken, die anderen offen.
  const teil = { ...folie, daten: { ...folie.daten, belegt: "[StatAgent]" } };
  const el2 = zeige("einstieg", teil, nr, 3);
  const ja = [...el2.querySelectorAll<HTMLElement>('[data-belegt="ja"]')];
  expect(ja).toHaveLength(1);
  expect(el2.querySelectorAll('[data-belegt="nein"]')).toHaveLength(2);
});

it("schluss: kein Knopf und kein Link", () => {
  const [, folie, nr] = folieMit("schluss");
  expect(zeige("schluss", folie, nr).querySelector("a, button")).toBeNull();
});
