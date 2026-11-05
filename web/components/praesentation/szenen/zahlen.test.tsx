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
