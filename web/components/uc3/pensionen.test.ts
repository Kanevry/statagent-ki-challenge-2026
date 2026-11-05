import { describe, expect, it } from "vitest";
import { pensionsdaten } from "./pensionen";

describe("pensionsdaten", () => {
  it("macht aus den Texten des Treibers Zahlen und merkt sich den Stand", () => {
    // Fängt: bigint-Summen kommen als Text; ein Vergleich oder eine Formatierung würde sonst still den Text nehmen.
    const daten = pensionsdaten([
      { jahr: 2019, insgesamt: "2379509", unselbstaendige: "2015224", selbstaendige: "364285", vorzeitig: "74906", vorlaeufig: false },
      { jahr: 2020, insgesamt: "2419281", unselbstaendige: "2050966", selbstaendige: "368315", vorzeitig: "79726", vorlaeufig: true },
    ]);
    expect(daten.vorlaeufig).toBe(true);
    expect(daten.jahre[0]).toEqual({
      jahr: 2019,
      insgesamt: 2379509,
      unselbstaendige: 2015224,
      selbstaendige: 364285,
      vorzeitig: 74906,
    });
  });

  it("bleibt ohne Zeilen leer und gilt nicht als vorläufig", () => {
    // Fängt: der Leerzustand vor dem Laden kippt in eine Tabelle aus lauter Nullen.
    expect(pensionsdaten([])).toEqual({ jahre: [], vorlaeufig: false });
  });
});
