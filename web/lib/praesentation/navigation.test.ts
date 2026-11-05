import { folieAusParam, naechsteFolie, naechsterStand, schalterFuerTaste } from "./navigation";

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

describe("naechsterStand mit Takten", () => {
  // Folie 2 hat drei Takte wie die Szene „falsche-zahl“, alle anderen keine.
  const takte = [0, 3, 0, 0];
  const weiter = (folie: number, takt: number, alle = false) => naechsterStand({ folie, takt }, takte, "ArrowRight", alle);
  const zurueck = (folie: number, takt: number) => naechsterStand({ folie, takt }, takte, "ArrowLeft");

  it("schaltet in Folie 2 erst drei Takte, dann Folie 3 mit Takt 0", () => {
    let stand = { folie: 1, takt: 0 };
    const weg: string[] = [];
    for (let i = 0; i < 5; i++) {
      stand = naechsterStand(stand, takte, " ") ?? stand;
      weg.push(`${stand.folie}.${stand.takt}`);
    }
    expect(weg).toEqual(["2.0", "2.1", "2.2", "2.3", "3.0"]);
  });
  it("geht zurück erst durch die Takte, und von hinten betreten zeigt alle Takte", () => {
    expect(zurueck(3, 0)).toEqual({ folie: 2, takt: 3 });
    expect(zurueck(2, 2)).toEqual({ folie: 2, takt: 1 });
    expect(zurueck(2, 0)).toEqual({ folie: 1, takt: 0 });
  });
  it("zeigt bei reduzierter Bewegung beim Betreten sofort alle Takte", () => {
    expect(weiter(1, 0, true)).toEqual({ folie: 2, takt: 3 });
    expect(naechsterStand({ folie: 4, takt: 0 }, takte, "Home", true)).toEqual({ folie: 1, takt: 0 });
  });
  it("bleibt an den Rändern stehen, Pos1 und Ende setzen Takt 0, fremde Tasten ergeben null", () => {
    expect(weiter(4, 0)).toEqual({ folie: 4, takt: 0 });
    expect(zurueck(1, 0)).toEqual({ folie: 1, takt: 0 });
    expect(naechsterStand({ folie: 3, takt: 0 }, takte, "End")).toEqual({ folie: 4, takt: 0 });
    expect(naechsterStand({ folie: 3, takt: 0 }, takte, "PageUp")).toEqual({ folie: 2, takt: 3 });
    expect(naechsterStand({ folie: 2, takt: 1 }, takte, "f")).toBeNull();
  });
  it("korrigiert einen Takt über dem Maximum, statt ihn stehen zu lassen", () => {
    expect(weiter(2, 9)).toEqual({ folie: 3, takt: 0 });
  });
});
