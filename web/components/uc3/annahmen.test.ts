import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { annahmenKopf, geltungLinks, HERLEITUNG, SQL_ANNAHMEN } from "./annahmen";

describe("Annahmen als Bereich", () => {
  // Fehler, den das fängt: Die Seite nennt eine Annahme, die es im Dokument nicht (mehr) gibt.
  it("hält A1 bis A13 mit dem Dokument gleich", () => {
    const dokument = readFileSync(resolve(__dirname, "../../../docs/plan/uc3/annahmen.md"), "utf8");
    expect(HERLEITUNG.map((a) => a.nr)).toEqual(Array.from({ length: 13 }, (_, i) => `A${i + 1}`));
    for (const { nr } of HERLEITUNG) expect(dokument).toMatch(new RegExp(`^\\| ${nr} \\|`, "m"));
    for (const { nr, name } of HERLEITUNG.slice(0, 10)) {
      const zeile = dokument.split("\n").find((z) => z.startsWith(`| ${nr} |`))!;
      // Anführungszeichen schreibt die Seite typografisch, das Dokument gerade.
      const gerade = (t: string) => t.replace(/[„“"]/g, "");
      expect(gerade(zeile)).toContain(gerade(name));
    }
  });

  // Fehler, den das fängt: Die Seite ist eine Sackgasse (Audit 06.11.: 0 Links) oder zeigt JJJJ-MM statt des Monats.
  it("führt von jeder Annahme zu den Monaten, in denen sie gilt", () => {
    expect(geltungLinks(["2025-05", "2026-02"])).toEqual([
      { text: "Mai 2025", pfad: "/uc3/berichte/2025-05#annahmen" },
      { text: "Februar 2026", pfad: "/uc3/berichte/2026-02#annahmen" },
    ]);
    for (const leer of [null, []]) expect(geltungLinks(leer)).toEqual([{ text: "alle Monate", pfad: "/uc3/berichte" }]);
  });

  // Fehler, den das fängt: Die Abfrage verliert die Spalte, und die Seite zeigt „Warum:“ ohne Text.
  it("liest die Begründung aus der Datenbank", () => {
    expect(SQL_ANNAHMEN).toContain("a.begruendung");
  });

  // Fehler, den das fängt: „10 Annahmen sind offen“, obwohl zwei keine Rückfrage haben (Review, F5 und F10).
  it("nennt nur Annahmen mit offener Rückfrage als offen", () => {
    expect(annahmenKopf(10, 8)).toBe("10 Annahmen, jede begründet. Zu 8 sind Rückfragen an die Fachabteilung offen.");
    expect(annahmenKopf(10, 1)).toBe("10 Annahmen, jede begründet. Zu 1 ist eine Rückfrage an die Fachabteilung offen.");
    expect(annahmenKopf(10, 0)).toBe("10 Annahmen, jede begründet.");
    expect(annahmenKopf(1, 1)).toBe("1 Annahme, begründet. Zu 1 ist eine Rückfrage an die Fachabteilung offen.");
  });
});
