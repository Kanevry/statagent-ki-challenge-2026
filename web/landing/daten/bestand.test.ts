import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { BESTAND_JE_MONAT, EINBRUCH, LIEFERUNGEN, zahl } from "./fakten";

const berichte = join(__dirname, "../../../abgabe/qualitaetsberichte");
const bericht = (monat: string) => readFileSync(join(berichte, `${monat}.md`), "utf8");

describe("Kurve der Startseite gegen die Qualitätsberichte", () => {
  it("hat je Lieferung genau einen Wert", () => {
    expect(BESTAND_JE_MONAT).toHaveLength(LIEFERUNGEN.length);
  });

  it.each(LIEFERUNGEN.map((l, i) => [l.lieferung, BESTAND_JE_MONAT[i]] as const))(
    "%s steht mit %i im Bericht",
    (monat, wert) => {
      const zeile =
        monat === EINBRUCH.lieferung ? "davon geliefert gezählt (ohne fortgeschriebene)" : "Beschäftigungsverhältnisse am Stichtag";
      const treffer = bericht(monat)
        .split("\n")
        .find((z) => z.startsWith(`| ${zeile}`));
      expect(treffer, monat).toContain(`| ${zahl(wert)} |`);
    },
  );

  it("die vorläufige Oktober-Zahl ist Lieferung plus Übernommenes", () => {
    expect(EINBRUCH.geliefert + EINBRUCH.uebernommen).toBe(EINBRUCH.vorlaeufig);
    expect(bericht(EINBRUCH.lieferung)).toContain(`| ${zahl(EINBRUCH.vorlaeufig)} |`);
  });
});
