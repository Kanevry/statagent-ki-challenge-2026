import { folieAusParam, naechsteFolie, schalterFuerTaste } from "./navigation";

// Fängt ab: Umbruch über das Ende hinaus (Folie 0 oder n + 1), Leertaste ohne Wirkung, eine Taste, die zu Unrecht
// den Browser sperrt (null statt Zahl), und ein ?folie=-Wert, der den Absturz oder eine leere Bühne bringt.

describe("naechsteFolie", () => {
  it("Pfeil rechts, Leertaste und Bild ab gehen vor", () => {
    expect(["ArrowRight", " ", "PageDown"].map((t) => naechsteFolie(2, 5, t))).toEqual([3, 3, 3]);
  });
  it("Pfeil links und Bild auf gehen zurück", () => {
    expect(["ArrowLeft", "PageUp"].map((t) => naechsteFolie(2, 5, t))).toEqual([1, 1]);
  });
  it("bleibt am Anfang und am Ende stehen", () => {
    expect(naechsteFolie(1, 5, "ArrowLeft")).toBe(1);
    expect(naechsteFolie(5, 5, "ArrowRight")).toBe(5);
  });
  it("Pos1 und Ende springen an die Ränder", () => {
    expect([naechsteFolie(3, 5, "Home"), naechsteFolie(3, 5, "End")]).toEqual([1, 5]);
  });
  it("gibt null für Tasten ohne Bedeutung, damit der Browser sie behält", () => {
    expect(naechsteFolie(2, 5, "Tab")).toBeNull();
    expect(naechsteFolie(2, 5, "f")).toBeNull();
  });
});

describe("folieAusParam", () => {
  it("nimmt eine gültige Zahl", () => {
    expect(folieAusParam("2", 3)).toBe(2);
    expect(folieAusParam("3", 3)).toBe(3);
  });
  it.each(["0", "4", "-1", "2.5", "abc", "2abc", "", " 2", "99999999999"])("ergibt Folie 1 für %j", (wert) => {
    expect(folieAusParam(wert, 3)).toBe(1);
  });
  it("ergibt Folie 1 ohne Wert und nimmt bei wiederholtem Parameter den ersten", () => {
    expect(folieAusParam(undefined, 3)).toBe(1);
    expect(folieAusParam(["3", "2"], 3)).toBe(3);
  });
});

it("F und N schalten, groß wie klein, alles andere nicht", () => {
  expect([schalterFuerTaste("f"), schalterFuerTaste("F"), schalterFuerTaste("n"), schalterFuerTaste("N")]).toEqual([
    "vollbild",
    "vollbild",
    "notizen",
    "notizen",
  ]);
  expect(schalterFuerTaste("x")).toBeNull();
});
