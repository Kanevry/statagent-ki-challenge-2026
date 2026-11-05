import { render } from "@testing-library/react";
import { FOLIEN_ORDNER, leseFolien } from "../../../lib/praesentation/folien";
import { herkunft, kopfzeile, letzterTeil, saetze, tabelle, zahlWert, zeitZeile } from "../../../lib/praesentation/szenen-daten";
import { szeneFuer, SZENEN } from "./index";

// Fängt ab: eine Szene, die Inhalt aus dem Markdown verliert (Tabelle, Herkunft, Titel), eine szene im Frontmatter
// ohne Komponente, Zeitangaben mit Gedankenstrich auf der Bühne und falsche Zahlen aus deutscher Schreibweise.

const folien = leseFolien(FOLIEN_ORDNER);
const mitSzene = folien.flatMap((f, i) => (szeneFuer(f.szene) ? [[f.szene ?? "", f, i + 1] as const] : []));

describe("Hilfen", () => {
  it("liest deutsche Zahlen und schreibt Zeiten ohne Strich", () => {
    expect([zahlWert("392.236"), zahlWert("2.880 von 2.880"), zahlWert("−0,067 %"), zahlWert("keine")]).toEqual([
      392236,
      2880,
      -0.067,
      Number.NaN,
    ]);
    expect(zeitZeile({ ...folien[0]!, zeit: "0:20–1:20" }, 2)).toBe("2 · 0:20 bis 1:20");
    expect(saetze("Eins. Zwei! Drei?")).toEqual(["Eins.", "Zwei!", "Drei?"]);
    expect(letzterTeil("Sehen Regeln, keine Daten.")).toEqual(["Sehen Regeln, ", "keine Daten."]);
  });
});

it("die Registry kennt nur die freigegebenen Szenen, Takte hat nur falsche-zahl", () => {
  expect(Object.keys(SZENEN).sort()).toEqual(["annahme", "beleg", "einstieg", "falsche-zahl", "schluss", "titel"]);
  expect(Object.entries(SZENEN).filter(([, e]) => e.takte > 0).map(([id, e]) => [id, e.takte])).toEqual([["falsche-zahl", 3]]);
  expect(szeneFuer("gibt-es-nicht")).toBeUndefined();
  expect(szeneFuer(undefined)).toBeUndefined();
});

describe.each(mitSzene)("Szene %s", (id, folie, nr) => {
  it("zeigt Titel bzw. Inhalt, Herkunft und Zeit aus dem Markdown", () => {
    const { Komponente } = szeneFuer(id)!;
    const { container } = render(<Komponente folie={folie} nr={nr} aktiv takt={0} />);
    const text = container.textContent ?? "";
    if (id !== "beleg" && id !== "einstieg") expect(text).toContain(kopfzeile(folie));
    const quelle = herkunft(folie);
    if (quelle) expect(text).toContain(quelle);
    expect(text).toContain(zeitZeile(folie, nr));
    expect(text).not.toMatch(/ [–—] /);
    for (const zeile of tabelle(folie)?.zeilen ?? []) {
      if (id === "falsche-zahl") continue; // Werte stecken als Säulenhöhe, nicht als Text
      expect(text).toContain(zeile[1] ?? "");
    }
  });
});

it("falsche-zahl baut eine Säule je Tabellenzeile und markiert den Bruchmonat", () => {
  const eintrag = mitSzene.find(([id]) => id === "falsche-zahl");
  if (!eintrag) return;
  const [, folie, nr] = eintrag;
  const { Komponente } = szeneFuer("falsche-zahl")!;
  const ansicht = render(<Komponente folie={folie} nr={nr} aktiv takt={3} />);
  const saeulen = ansicht.container.querySelectorAll('[style*="--h:"]');
  expect(saeulen).toHaveLength(tabelle(folie)?.zeilen.length ?? 0);
  expect(ansicht.container.textContent).toContain(`${folie.daten.zahl_geliefert} so geliefert`);
});
