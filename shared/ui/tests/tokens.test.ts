import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// Fängt eine Farbe, Schrift oder Textgröße ab, die in tokens.css geändert wurde, ohne den
// Pencil-Snapshot neu zu ziehen (und umgekehrt), sowie jede zusätzliche --text-*-Stufe.

type Snapshot = {
  kopf: { quelle: string; zeitstempel: string; werkzeug: string };
  farben: Record<string, string>;
  schriften: Record<string, string>;
  textgroessen: number[];
};

const lies = (pfad: string) => readFileSync(fileURLToPath(new URL(pfad, import.meta.url)), "utf8");
const snapshot = JSON.parse(lies("../tokens.snapshot.json")) as Snapshot;

function themeVariablen(css: string): Map<string, string> {
  const block = /@theme\s*\{([\s\S]*?)\n\}/.exec(css.replace(/\/\*[\s\S]*?\*\//g, ""));
  if (!block?.[1]) throw new Error("kein @theme-Block in tokens.css");
  const variablen = new Map<string, string>();
  for (const [, name, wert] of block[1].matchAll(/(--[\w*-]+)\s*:\s*([^;]+);/g)) {
    if (name && wert) variablen.set(name, wert.trim());
  }
  return variablen;
}

const theme = themeVariablen(lies("../src/tokens.css"));
const mitPraefix = (praefix: string) =>
  [...theme].filter(([name]) => name.startsWith(praefix) && !name.endsWith("*"));

// Pen-Variable -> Tailwind-Variable für Schriften (Farben: Präfix l- entfällt).
const schriftZuordnung: Record<string, string> = {
  "font-head": "--font-display",
  "font-body": "--font-sans",
  "font-mono": "--font-mono",
};

describe("Design-Tokens gegen Pencil-Snapshot", () => {
  it("Snapshot stammt aus der Pen-Datei", () => {
    expect(snapshot.kopf.quelle).toBe("ki-challenge.pen");
    expect(snapshot.kopf.werkzeug).toMatch(/Pencil/);
    expect(Number.isNaN(Date.parse(snapshot.kopf.zeitstempel))).toBe(false);
  });

  it("schaltet Tailwinds Standardpalette, -schriften und -größen ab", () => {
    for (const ns of ["--color-*", "--font-*", "--text-*"]) expect(theme.get(ns)).toBe("initial");
  });

  it("Farben stimmen genau mit dem Snapshot überein", () => {
    const erwartet = Object.fromEntries(
      Object.entries(snapshot.farben).map(([name, wert]) => [`--color-${name.replace(/^l-/, "")}`, wert.toLowerCase()]),
    );
    const ist = Object.fromEntries(mitPraefix("--color-").map(([name, wert]) => [name, wert.toLowerCase()]));
    expect(ist).toEqual(erwartet);
  });

  it("genau drei Schriften, je die Pencil-Familie als Fontsource-Variable", () => {
    expect(mitPraefix("--font-").map(([name]) => name).sort()).toEqual(Object.values(schriftZuordnung).sort());
    for (const [penName, familie] of Object.entries(snapshot.schriften)) {
      const variable = schriftZuordnung[penName];
      expect(variable, `keine Zuordnung für ${penName}`).toBeDefined();
      const stapel = (theme.get(variable ?? "") ?? "").split(",").map((f) => f.trim().replace(/^"|"$/g, ""));
      expect(stapel.slice(0, 2)).toEqual([`${familie} Variable`, familie]);
    }
  });

  it("Skala genau 56/32/28/20/16/14/13/12/11 px, keine weitere --text-*", () => {
    const groessen = mitPraefix("--text-").filter(([name]) => !name.endsWith("--line-height"));
    const px = Object.fromEntries(
      groessen.map(([name, wert]) => {
        const rem = /^([\d.]+)rem$/.exec(wert);
        if (!rem?.[1]) throw new Error(`${name} ist nicht in rem: ${wert}`);
        return [name, Number(rem[1]) * 16];
      }),
    );
    expect(px).toEqual(Object.fromEntries(snapshot.textgroessen.map((g) => [`--text-${g}`, g])));
    const zeilen = mitPraefix("--text-").filter(([name]) => name.endsWith("--line-height"));
    expect(zeilen.map(([name]) => name).sort()).toEqual(
      snapshot.textgroessen.map((g) => `--text-${g}--line-height`).sort(),
    );
  });
});
