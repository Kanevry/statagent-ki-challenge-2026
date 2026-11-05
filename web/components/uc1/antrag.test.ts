// @vitest-environment node
import { describe, expect, it } from "vitest";
import { abbildenAntrag, antragUnterzeile, formularKurz, offenNachSeite, parseQuelle } from "./antrag";
import pflege from "./fixtures/pflege.json";

const ROH = { ...pflege.antrag, pdf: "/Users/irgendwer/repo/uc1/laufzeit/antraege/pflegegeld-x-entwurf.pdf" };

describe("abbildenAntrag", () => {
  // Fängt: absoluter PDF-Pfad, Formulardatei mit Ordner oder Hash des Formulars im Browser.
  it("lässt pdf, datei, sha256 und jeden Pfad weg", () => {
    const antrag = abbildenAntrag(ROH);
    expect(antrag).not.toBeNull();
    const text = JSON.stringify(antrag);
    expect(text).not.toMatch(/\.pdf|Anträge und Formulare|\/Users|"pdf"|"datei"|"sha256"/);
    expect(text).not.toContain(pflege.antrag.formular.sha256);
  });

  // Fängt: falsche Seite oder ein Wortlaut mit Pfad oder Anführungszeichen; und PDF-Kürzel statt Feldnamen.
  it("parst Quellen zu Seite und Wortlaut und benennt Felder", () => {
    const antrag = abbildenAntrag(ROH);
    const gruende = antrag?.noch_offen.find((p) => p.id === "gruende");
    expect(gruende?.beleg).toEqual({ seite: 2, wortlaut: "Gründe Ihrer Pflegebedürftigkeit:" });
    expect(gruende?.text).toMatch(/^Gründe der Pflegebedürftigkeit .*\.$/);
    expect(antrag?.unterlagen[0]?.beleg?.seite).toBe(2);
    expect(antrag?.befuellt).toContainEqual({ feld: "Familienname", wert: "Beispiel" });
    expect(antrag).toMatchObject({ kurz: "Antrag PAL080", code: "PAL080", eingereicht: false });
    expect(antrag?.stelle?.name).toBe("Pensionsversicherungsanstalt (PVA)");
  });

  // Fängt: eine Ausgabe ohne Pflichtfeld (z. B. befuellt), die als leerer Antrag angezeigt würde.
  it("lehnt eine Ausgabe ohne befuellt ab", () => {
    const { befuellt: _weg, ...ohne } = ROH;
    expect(abbildenAntrag(ohne)).toBeNull();
  });
});

describe("parseQuelle und formularKurz", () => {
  // Fängt: Wortlaut mit inneren Anführungszeichen wird abgeschnitten; eine Quelle ohne Seite wird erfunden.
  it("behält innere Anführungszeichen und gibt ohne Seite null", () => {
    expect(parseQuelle("A/B.pdf, S. 4: „Antrag „bar“ oder Konto“")).toEqual({ seite: 4, wortlaut: "Antrag „bar“ oder Konto" });
    expect(parseQuelle("A/B.pdf")).toBeNull();
    expect(parseQuelle(null)).toBeNull();
  });

  // Fängt: lange Bezeichnung oder Dateiname vor jeder Seitenangabe; Klammern ohne Code („(BPGG)“) als Code.
  it("leitet den Kurznamen aus Klammer oder Version ab", () => {
    expect(formularKurz("Antrag auf Pflegegeld nach dem Bundespflegegeldgesetz (PAL080) der PVA")).toBe("Antrag PAL080");
    expect(formularKurz("Antrag nach dem Gesetz (BPGG)", "PAL 080 (01. 2025)")).toBe("Antrag PAL080");
    expect(formularKurz("Irgendein Antrag")).toBe("Antrag");
  });

  // Fängt: Zahlen in der Unterzeile, die nicht aus der Ausgabe kommen, und Punkt-Aufzählungen.
  it("zählt befüllte und offene Punkte in der Unterzeile", () => {
    const antrag = abbildenAntrag(ROH);
    if (!antrag) throw new Error("Abbildung fehlgeschlagen");
    expect(antragUnterzeile(antrag)).toBe("Im Formular (PAL080): 7 Angaben stehen schon drin, 11 Punkte ergänzen Sie selbst.");
  });
});

describe("offenNachSeite", () => {
  const beleg = (seite: number, wortlaut: string) => ({ seite, wortlaut });
  // Fängt: ein Chip je Punkt (Pillen-Kette), Nummern, die je Seite neu bei 1 beginnen, oder Punkte ohne Beleg vorn.
  it("gruppiert nach Seite, zählt durch und legt Punkte ohne Beleg ans Ende", () => {
    const gruppen = offenNachSeite([
      { id: "a", text: "A", beleg: beleg(2, "„X“") },
      { id: "b", text: "B", beleg: null },
      { id: "c", text: "C", beleg: beleg(1, "„Y“") },
      { id: "d", text: "D", beleg: beleg(2, "„Z“") },
      { id: "e", text: "E", beleg: beleg(2, "„X“") },
    ]);
    expect(gruppen.map((g) => [g.seite, g.start, g.punkte.map((p) => p.id), g.wortlaut])).toEqual([
      [1, 1, ["c"], "„Y“"],
      [2, 2, ["a", "d", "e"], "„X“\n„Z“"],
      [null, 5, ["b"], null],
    ]);
  });

  it("hält die Aufnahme bei vier Seitengruppen und elf Punkten", () => {
    const antrag = abbildenAntrag(ROH);
    const gruppen = offenNachSeite(antrag?.noch_offen ?? []);
    expect(gruppen.map((g) => g.seite)).toEqual([1, 2, 3, 4]);
    expect(gruppen.reduce((n, g) => n + g.punkte.length, 0)).toBe(antrag?.noch_offen.length);
  });
});
