import { describe, expect, it } from "vitest";
import {
  abschnitteNachName,
  kategorieSaetze,
  uebergangsWorte,
  vergleicheAbschnitte,
  wechselSatz,
  wechselzahlen,
  zaehleUebergangsWorte,
} from "./klassifikation";

const alt = [
  { code: "A", bezeichnung: "Land- und Forstwirtschaft, Fischerei" },
  { code: "J", bezeichnung: "Information und Kommunikation" },
  { code: "K", bezeichnung: "Erbringung von Finanz- und Versicherungsdienstleistungen" },
  { code: "UNB", bezeichnung: "Wirtschaftszweig unbekannt" },
];
const neu = [
  { code: "A", bezeichnung: "Land- und Forstwirtschaft, Fischerei" },
  { code: "J", bezeichnung: "Verlagswesen, Rundfunk" },
  { code: "K", bezeichnung: "Telekommunikation, Softwareentwicklung" },
  { code: "L", bezeichnung: "Erbringung von Finanz- und Versicherungsdienstleistungen" },
  { code: "UNB", bezeichnung: "Wirtschaftszweig unbekannt" },
];

describe("vergleicheAbschnitte", () => {
  // Fehler, den das fängt: Vergleich über den Buchstaben statt über den Namen; dann hieße K 2025 „gleich“,
  // obwohl K 2008 Finanzdienstleistungen und K 2025 IT ist, und L wäre „neu“ statt „verschoben von K“.
  it("vergleicht über den Namen, nicht über den Buchstaben", () => {
    const zeilen = vergleicheAbschnitte(alt, neu);
    const nach = (code: string) => zeilen.find((z) => z.code === code)?.vergleich;
    expect(nach("A")).toEqual({ art: "gleich" });
    expect(nach("K")).toEqual({ art: "neu" });
    expect(nach("L")).toEqual({ art: "verschoben", vonCode: "K" });
    expect(zeilen.map((z) => z.code)).toEqual(["A", "J", "K", "L", "UNB"]);
  });

  // Fehler, den das fängt: „Wirtschaftszweig unbekannt“ als Abschnitt mitgezählt (22 statt 21 Abschnitte 2008).
  it("zählt UNB nicht als Abschnitt und bildet den Satz aus den Zahlen", () => {
    const zahlen = wechselzahlen(vergleicheAbschnitte(alt, neu));
    expect(zahlen).toEqual({ abschnitteAlt: 3, abschnitteNeu: 4, gleich: 1, verschoben: 1, neu: 2 });
    expect(wechselSatz(zahlen)).toBe(
      "Ab Jänner 2025 zählen wir Branchen nach ÖNACE 2025 mit 4 statt 3 Abschnitten; nur 1 behalten Buchstabe und Namen.",
    );
  });
});

describe("uebergangsWorte", () => {
  // Fehler, den das fängt: Zählen der Zeilen statt der alten Codes (DE stünde zweimal da) oder ein Wort aus dem
  // Feld `beziehung` („m:n“), obwohl DE laut Umsteiger auf C und J aufgeteilt ist.
  it("nennt einen Code mit zwei Zielen aufgeteilt und zählt ihn einmal", () => {
    const zeilen = [
      { versionAlt: "2003", codeAlt: "DA", versionNeu: "2008", codeNeu: "C" },
      { versionAlt: "2003", codeAlt: "DB", versionNeu: "2008", codeNeu: "C" },
      { versionAlt: "2003", codeAlt: "DE", versionNeu: "2008", codeNeu: "C" },
      { versionAlt: "2003", codeAlt: "DE", versionNeu: "2008", codeNeu: "J" },
      { versionAlt: "2003", codeAlt: "X", versionNeu: "2008", codeNeu: "Y" },
    ];
    const worte = uebergangsWorte(zeilen);
    expect(worte.find((w) => w.codeAlt === "DE")).toEqual({ codeAlt: "DE", ziele: ["C", "J"], wort: "aufgeteilt" });
    expect(zaehleUebergangsWorte(worte)).toEqual({ gleich: 1, aufgeteilt: 1, zusammengelegt: 2 });
  });
});

describe("kategorieSaetze", () => {
  const liste = [
    { code: "AngestellteDV", bezeichnung: "Angestellte (Dienstvertrag)", kategorie: "Angestellte", freierDienstvertrag: false },
    { code: "AngestellteFD", bezeichnung: "Angestellte (freier Dienstvertrag)", kategorie: "Angestellte", freierDienstvertrag: true },
    { code: "ArbeiterDV", bezeichnung: "Arbeiter (Dienstvertrag)", kategorie: "Arbeiter", freierDienstvertrag: false },
    { code: "ArbeiterFD", bezeichnung: "Arbeiter (freier Dienstvertrag)", kategorie: "Arbeiter", freierDienstvertrag: true },
    { code: "Beamte", bezeichnung: "Beamte", kategorie: "Beamte", freierDienstvertrag: false },
    { code: "UNB", bezeichnung: "Qualifikation unbekannt", kategorie: "Unbekannt", freierDienstvertrag: null },
  ];
  const auftrag = {
    vorschlagId: 24,
    titel: "Auftrag 1, Dienstvertrag und freier Dienstvertrag zusammen",
    regelsatzZiel: "v2",
    zielSpalte: "beschaeftigungskategorie",
  };
  const stand = { regelsatz: "v1", regelId: 13, regelName: "R6_beschaeftigungskategorie", spalte: "code" };

  // Fehler, den das fängt: ein fester Satz „5 Qualifikationen zu 3 Kategorien“, obwohl Regelsatz v1 die fünf Codes
  // einzeln zählt und der Auftrag noch offen sein kann.
  it("sagt bei offenem Auftrag, dass weiter mit Regelsatz v1 gezählt wird", () => {
    const s = kategorieSaetze({ ...stand, auftrag: { ...auftrag, status: "offen", von: null, am: null } }, liste, "v1");
    expect(s.regel).toContain("zählen wir die 5 gelieferten Qualifikationen einzeln");
    expect(s.auftrag).toContain("Gezählt wird mit Regelsatz v1, bis Auftrag 1 freigegeben ist.");
    expect(s.zahlen).toBe("Die Zahlen auf dieser Seite sind mit Regelsatz v1 gerechnet.");
  });

  it("nennt bei Freigabe Name und Wiener Zeit und die drei Kategorien", () => {
    const s = kategorieSaetze(
      {
        ...stand,
        auftrag: { ...auftrag, status: "freigegeben", von: "Bernhard Götzendorfer", am: "2026-11-05T15:53:49.778Z" },
      },
      liste,
      "v1",
    );
    expect(s.auftrag).toContain("von Bernhard Götzendorfer am 5. November 2026 um 16:53 Uhr");
    expect(s.auftrag).toContain("zu 3 Beschäftigungskategorien zusammen: Angestellte, Arbeiter und Beamte");
  });
});

describe("abschnitteNachName", () => {
  // Fehler, den das fängt: Zeilen je Buchstabe stellen K 2008 (Finanz) neben K 2025 (IT); nach Namen steht
  // Finanz einmal da, 2008 unter K und 2025 unter L.
  it("stellt dieselbe Branche in eine Zeile, auch wenn der Buchstabe wechselt", () => {
    const zeilen = abschnitteNachName(vergleicheAbschnitte(alt, neu));
    const finanz = zeilen.find((z) => z.bezeichnung.startsWith("Erbringung von Finanz"));
    expect(finanz).toMatchObject({ codeAlt: "K", codeNeu: "L", vergleich: "gewechselt" });
    expect(zeilen.find((z) => z.bezeichnung.startsWith("Information"))?.vergleich).toBe("entfaellt");
    expect(zeilen.find((z) => z.bezeichnung.startsWith("Telekommunikation"))?.vergleich).toBe("neu");
    expect(zeilen.at(-1)?.codeAlt).toBe("UNB");
  });
});
