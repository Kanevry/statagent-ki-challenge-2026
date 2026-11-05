import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

// Fängt ab: ein Token-Wert oder eine Farbpaarung aus den Pen-Frames, die unter 4,5:1 fällt (WCAG 1.4.3).
// Die Paare sind die Text-auf-Fläche-Kombinationen, die Shell und Bausteine tatsächlich setzen.

// Pfad über eine Variable: Vite würde ein Literal in `new URL(..., import.meta.url)` als Asset umschreiben.
const pfad = "../src/tokens.css";
const css = readFileSync(fileURLToPath(new URL(pfad, import.meta.url)), "utf8");
const farbe = (name: string): string => {
  const treffer = new RegExp(`--color-${name}:\\s*(#[0-9a-f]{6})`, "i").exec(css);
  if (!treffer?.[1]) throw new Error(`Token ${name} fehlt`);
  return treffer[1];
};

function leuchtdichte(hex: string): number {
  const kanaele = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * kanaele[0]! + 0.7152 * kanaele[1]! + 0.0722 * kanaele[2]!;
}

export function kontrast(a: string, b: string): number {
  const [hell, dunkel] = [leuchtdichte(a), leuchtdichte(b)].sort((x, y) => y - x);
  return (hell! + 0.05) / (dunkel! + 0.05);
}

const paare: Array<[string, string, string]> = [
  ["Aktiver Tab: weiß auf Grün", "white", "gruen"],
  ["Hauptknopf beim Überfahren: weiß auf Grün-dunkel", "white", "gruen-dunkel"],
  ["Modell-Pille: Violett auf Violett-hell", "violett", "violett-bg"],
  ["Hinweis „zuletzt“ in der Pille: Navy auf Violett-hell", "navy", "violett-bg"],
  ["Chip bewertet: Ink auf Mint", "ink", "mint"],
  ["Herkunft-Chip: Grün auf Grün-hell", "gruen", "gruen-bg"],
  ["Warn-Chip: Warn-Text auf Warn-hell", "warn-fg", "warn-bg"],
  ["Fehler-Chip: Fehler-Text auf Fehler-hell", "err-fg", "err-bg"],
  ["Diff: entfernt auf Papier", "err-fg", "paper"],
  ["Diff: neu auf Papier", "gruen", "paper"],
  ["Marke: Navy auf Weiß", "navy", "white"],
  ["Nebentext: Slate auf Weiß", "slate", "white"],
];

describe("Kontrast der Frame-Paare", () => {
  it.each(paare)("%s hat mindestens 4,5:1", (_name, vorder, grund) => {
    expect(kontrast(farbe(vorder), farbe(grund))).toBeGreaterThanOrEqual(4.5);
  });
});
