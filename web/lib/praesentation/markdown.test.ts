import { inlineText, parseBlocks, parseInline } from "./markdown";

// Fängt ab: Fett und Code, die als Rohzeichen auf der Folie stehen, ein nicht geschlossenes `**`, das den Rest
// verschluckt, HTML, das unverändert durchgereicht wird, und Listen, die zu Absätzen zerfallen.

it("zerlegt fett und code, lässt nicht geschlossene Zeichen als Text stehen", () => {
  expect(parseInline("Das **gilt** für `uc3 lauf` immer")).toEqual([
    { art: "text", text: "Das " },
    { art: "fett", text: "gilt" },
    { art: "text", text: " für " },
    { art: "code", text: "uc3 lauf" },
    { art: "text", text: " immer" },
  ]);
  expect(inlineText(parseInline("offen **nie zu"))).toBe("offen **nie zu");
});

it("macht HTML nie zu Markup: ein script-Tag bleibt Text", () => {
  expect(parseInline("<script>alert(1)</script>")).toEqual([{ art: "text", text: "<script>alert(1)</script>" }]);
});

it("erkennt Überschriften, Absätze über mehrere Zeilen, beide Listenarten und übergeht Kommentare", () => {
  const blocks = parseBlocks(
    ["# Titel", "", "erste Zeile", "zweite Zeile", "", "- a", "- b", "  weiter", "", "1. eins", "2. zwei", "<!-- weg -->", "## Unter"].join("\n"),
  );
  expect(blocks.map((b) => b.art)).toEqual(["ueberschrift", "absatz", "liste", "liste", "ueberschrift"]);
  expect(blocks[1]).toMatchObject({ inline: [{ art: "text", text: "erste Zeile zweite Zeile" }] });
  expect(blocks[2]).toMatchObject({ geordnet: false });
  expect(blocks[2]?.art === "liste" && blocks[2].punkte.map(inlineText)).toEqual(["a", "b weiter"]);
  expect(blocks[3]).toMatchObject({ geordnet: true });
  expect(blocks[4]).toMatchObject({ stufe: 2 });
});

it("liest eine Tabelle mit Kopf und Trennzeile, die Zeile danach ist wieder ein Absatz", () => {
  const blocks = parseBlocks(["| A | B |", "|---|---|", "| 1 | **2** |", "", "danach"].join("\n"));
  expect(blocks.map((b) => b.art)).toEqual(["tabelle", "absatz"]);
  const tabelle = blocks[0];
  expect(tabelle?.art === "tabelle" && tabelle.kopf.map(inlineText)).toEqual(["A", "B"]);
  expect(tabelle?.art === "tabelle" && tabelle.zeilen[0]?.map(inlineText)).toEqual(["1", "2"]);
});
