import { describe, expect, it } from "vitest";
import {
  abschnitteNachName,
  aenderungsSatz,
  datumLang,
  gegenueberSaetze,
  gegenueberstellung,
  qualifikationsStaende,
  regelKlartext,
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

describe("gegenueberstellung", () => {
  const alt08 = [
    { code: "A", bezeichnung: "Land- und Forstwirtschaft, Fischerei" },
    { code: "J", bezeichnung: "Information und Kommunikation" },
    { code: "K", bezeichnung: "Erbringung von Finanz- und Versicherungsdienstleistungen" },
    { code: "M", bezeichnung: "Erbringung von freiberuflichen, wissenschaftlichen und technischen Dienstleistungen" },
    { code: "UNB", bezeichnung: "Wirtschaftszweig unbekannt" },
  ];
  const neu25 = [
    { code: "A", bezeichnung: "Land- und Forstwirtschaft, Fischerei" },
    { code: "J", bezeichnung: "Verlagswesen, Rundfunk" },
    { code: "K", bezeichnung: "Telekommunikation, Softwareentwicklung" },
    { code: "L", bezeichnung: "Erbringung von Finanz- und Versicherungsdienstleistungen" },
    { code: "N", bezeichnung: "Erbringung von wissenschaftlichen und technischen Dienstleistungen" },
    { code: "UNB", bezeichnung: "Wirtschaftszweig unbekannt" },
  ];
  // Unterklassen je Abschnittspaar wie im Umsteigeschlüssel: J geht großteils nach J und K, ein Rest nach N.
  const uebergaenge = [
    { alt: "A", neu: "A", unterklassen: 41 },
    { alt: "J", neu: "J", unterklassen: 19 },
    { alt: "J", neu: "K", unterklassen: 12 },
    { alt: "J", neu: "N", unterklassen: 3 },
    { alt: "K", neu: "L", unterklassen: 20 },
    { alt: "M", neu: "N", unterklassen: 21 },
    { alt: "M", neu: "M", unterklassen: 2 },
  ];

  // Fehler, den das fängt: ohne Umsteigeschlüssel stünde „Information und Kommunikation“ als weggefallen da und
  // J/K 2025 als neu; ein Rest von 3 Unterklassen nach N würde J fälschlich in drei Abschnitte teilen.
  it("zeigt J als Teilung in J und K und M als Umbenennung nach N", () => {
    const zeilen = gegenueberstellung(vergleicheAbschnitte(alt08, neu25), uebergaenge);
    const nach = (code: string) => zeilen.find((z) => z.alt?.code === code);
    expect(nach("J")?.art).toBe("geteilt");
    expect(nach("J")?.neu.map((n) => n.code)).toEqual(["J", "K"]);
    expect(nach("M")).toMatchObject({ art: "umbenannt", neu: [{ code: "N" }] });
    expect(nach("K")).toMatchObject({ art: "gewechselt", neu: [{ code: "L" }] });
    expect(zeilen.some((z) => z.art === "neu")).toBe(false);
    expect(zeilen.at(-1)?.alt?.code).toBe("UNB");
    expect(aenderungsSatz(nach("J")!)).toBe(
      "Teilt sich ab Jänner 2025 in zwei Abschnitte: J „Verlagswesen, Rundfunk“ und K „Telekommunikation, Softwareentwicklung“.",
    );
    expect(gegenueberSaetze(zeilen)).toEqual({
      haupt: "Ab Jänner 2025 gilt ÖNACE 2025 mit 5 statt 4 Abschnitten. Wir vergleichen die Branchen über ihren Namen.",
      unter: "1 Branche behält Buchstabe und Namen, 1 steht unter einem anderen Buchstaben, 1 heißt anders und eine teilt sich.",
    });
  });

  it("lässt ohne Umsteigeschlüssel weggefallene und neue Abschnitte getrennt stehen", () => {
    const zeilen = gegenueberstellung(vergleicheAbschnitte(alt08, neu25), []);
    expect(zeilen.find((z) => z.alt?.code === "J")?.art).toBe("entfaellt");
    expect(zeilen.filter((z) => z.art === "neu").map((z) => z.neu[0]?.code)).toEqual(["N", "K", "J"]);
  });
});

describe("regelKlartext", () => {
  // Fehler, den das fängt: Regelcodes und Tabellennamen im Fließtext („Einleseregel E01“, „stat.…“).
  it("nimmt Codes, Tabellen und Spaltennamen aus dem ersten Satz", () => {
    expect(regelKlartext("Sätze, bei denen die Einleseregel E01 BEGINN und ENDE getauscht hat. Rest.")).toBe(
      "Zeilen, bei denen die Einleseregel BEGINN und ENDE getauscht hat.",
    );
    expect(
      regelKlartext("Der Wirtschaftszweig wird nach der ÖNACE-Version ausgewiesen (Gültigkeit in stat.klass_oenace): bis 12/2024 ÖNACE 2008."),
    ).toBe("Der Wirtschaftszweig wird nach der ÖNACE-Version ausgewiesen: bis Dezember 2024 ÖNACE 2008.");
    expect(regelKlartext("Zeilen, die zu einem Satz verdichtet wurden (Summe roh_zeilen − 1).")).toBe(
      "Zeilen, die zu einer Zeile verdichtet wurden.",
    );
  });

  it("schreibt das Datum mit Monatsnamen", () => {
    expect(datumLang("05.11.2026")).toBe("5. November 2026");
    expect(datumLang("")).toBe("");
  });
});

describe("qualifikationsStaende", () => {
  const liste = [
    { code: "AngestellteDV", bezeichnung: "Angestellte (Dienstvertrag)", kategorie: "Angestellte", freierDienstvertrag: false },
    { code: "ArbeiterDV", bezeichnung: "Arbeiter (Dienstvertrag)", kategorie: "Arbeiter", freierDienstvertrag: false },
    { code: "UNB", bezeichnung: "Qualifikation unbekannt", kategorie: "Unbekannt", freierDienstvertrag: null },
  ];
  // Fehler, den das fängt: der Regelsatz aus dem Auftrag fehlt oder trägt die Freigabe ohne Wiener Zeit.
  it("nennt je Regelsatz einen Satz und die Freigabe mit Name und Wiener Zeit", () => {
    const staende = qualifikationsStaende(
      {
        regelsatz: "v1",
        regelId: 13,
        regelName: "R6_beschaeftigungskategorie",
        spalte: "code",
        regelVon: "Bernhard Götzendorfer",
        regelAm: "2026-11-05T15:12:58.688Z",
        auftrag: {
          vorschlagId: 24,
          titel: "Auftrag 1, Dienstvertrag und freier Dienstvertrag zusammen",
          status: "freigegeben",
          regelsatzZiel: "v2",
          zielSpalte: "beschaeftigungskategorie",
          von: "Bernhard Götzendorfer",
          am: "2026-11-05T15:53:49.778Z",
        },
      },
      liste,
    );
    expect(staende.map((s) => s.regelsatz)).toEqual(["v1", "v2"]);
    expect(staende[0]?.satz).toBe("Regelsatz v1 zählt die 2 Qualifikationen einzeln, so wie sie geliefert werden.");
    expect(staende[1]?.freigabe).toBe("freigegeben von Bernhard Götzendorfer am 5. November 2026 um 16:53 Uhr");
    expect(staende[1]?.auftrag).toEqual({ titel: "Auftrag 1", vorschlagId: 24 });
  });
});
