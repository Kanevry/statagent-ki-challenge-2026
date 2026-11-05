import { render } from "@testing-library/react";
import path from "node:path";
import { leseFolien, parseFolie } from "../../../lib/praesentation/folien";
import { taktZahl } from "../schau";
import { szeneFuer } from "./index";
import { ZahlenSzene } from "./zahlen";

// Fängt ab: die Management-Fassung mit fehlender Folie oder unbekannter Szene, eine Zahl oder ein Satz aus dem Markdown,
// den die Szene verliert, ein Takt-Wert im Frontmatter, der mehr Takte erzeugt, als die Szene zeichnen kann.

const management = leseFolien(path.join(process.cwd(), "content", "slides-management"));

it("die Management-Fassung hat 11 Folien, alle als bekannte Szene, zusammen 10 Minuten", () => {
  expect(management).toHaveLength(11);
  for (const f of management) expect(szeneFuer(f.szene), f.id).toBeDefined();
  expect(management.reduce((s, f) => s + Number(f.daten.dauer_s), 0)).toBe(600);
});

it("zahlen zeigt Titel, Zahl mit Text, Absatz und Herkunft aus dem Markdown", () => {
  const folie = parseFolie(
    "t.md",
    "---\ntitel: T\nszene: zahlen\n---\n\n# Ein Satz als Titel.\n\n| Zahl | Text |\n|---|---|\n| 2.880 | Zahlen |\n| 0 | Abweichungen |\n\nDer Satz unten.\n\nHerkunft: Quelle\n",
  );
  const { container } = render(<ZahlenSzene folie={folie} nr={1} aktiv={false} takt={0} />);
  for (const text of ["Ein Satz als Titel.", "2.880", "Zahlen", "Abweichungen", "Der Satz unten.", "Herkunft: Quelle"]) {
    expect(container.textContent).toContain(text);
  }
});

it("zahlen zeigt ohne Tabelle die Liste als Sätze", () => {
  const folie = parseFolie("t.md", "---\ntitel: T\nszene: zahlen\n---\n\n# Titel\n\n1. Erster Satz.\n2. Zweiter Satz.\n");
  const { container } = render(<ZahlenSzene folie={folie} nr={1} aktiv={false} takt={0} />);
  expect(container.querySelectorAll("li")).toHaveLength(2);
  expect(container.textContent).toContain("Zweiter Satz.");
});

it("takte im Frontmatter kann die Takte der Szene senken, aber nie erhöhen", () => {
  expect(taktZahl(3, undefined)).toBe(3);
  expect(taktZahl(3, "2")).toBe(2);
  expect(taktZahl(3, "9")).toBe(3);
  expect(taktZahl(3, "abc")).toBe(3);
});

const folieNr = (nr: number) => {
  const f = management[nr - 1];
  if (!f) throw new Error(`Folie ${nr} fehlt`);
  return f;
};

it("Regie Management: Folie 11 ohne Kreis 4, Folie 4 ohne Zählzeile, Folie 9 ohne Etikett, Folie 2 ohne Rechenfalle", () => {
  const zeige = (nr: number) => {
    const f = folieNr(nr);
    const Szene = szeneFuer(f.szene)?.Komponente;
    if (!Szene) throw new Error(`Szene zu Folie ${nr} fehlt`);
    return render(<Szene folie={f} nr={nr} aktiv={false} takt={9} />).container;
  };
  expect(zeige(11).querySelector('[data-k="4"]')).toBeNull();
  expect(zeige(4).textContent).not.toContain("2.880 von 2.880 gleich");
  expect(zeige(9).textContent).not.toContain("Use Case 3");
  const zwei = zeige(2).textContent ?? "";
  expect(zwei).toContain("von 394.200 im September");
  expect(zwei).not.toContain("313.154");
});
