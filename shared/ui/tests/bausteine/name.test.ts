import sperrnamen from "../../../py/tests/protokoll/sperrnamen.json";
import { pruefeName } from "../../src/bausteine";

// Fängt ab: die UI-Regel driftet von der Server-Regel weg. Die Sperrnamen sind dieselbe Datei, die
// `plattform.freigabe` testet; ein Name, den der Server ablehnt, darf den Knopf nie aktivieren.
describe("pruefeName spiegelt Vertrag P", () => {
  it.each(sperrnamen as string[])("lehnt %j ab", (name) => {
    expect(pruefeName(name).gueltig).toBe(false);
  });

  it.each([
    ["  Bernhard   Götzendorfer ", "Bernhard Götzendorfer"],
    ["Anna-Lena O'Brien", "Anna-Lena O'Brien"],
    ["Anna O’Brien", "Anna O’Brien"],
    ["J. Huber", "J. Huber"],
    ["Bernhard Go\u0308tzendorfer", "Bernhard Götzendorfer"],
  ])("nimmt %j an und normalisiert Leerraum und Unicode (NFC)", (eingabe, erwartet) => {
    expect(pruefeName(eingabe)).toEqual({ gueltig: true, name: erwartet });
  });
});
