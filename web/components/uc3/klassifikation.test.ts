import { describe, expect, it } from "vitest";
import {
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
