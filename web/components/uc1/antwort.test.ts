import { describe, expect, it } from "vitest";
import { abbilden, ersterSatz, formatStand, quelleAnzeige, telefonTeile } from "./antwort";

describe("quelleAnzeige", () => {
  // Fängt: ein roher Dateipfad des Kerns („Anträge und Formulare/….pdf“) auf der Seite.
  it("macht aus einem Pfad den Dateinamen ohne Endung und lange Ziffern, Seite bleibt", () => {
    expect(quelleAnzeige("Anträge und Formulare/PAL080_2026.pdf, S. 5")).toBe("PAL080, S. 5");
    expect(quelleAnzeige("a/b/Serviceratgeber.pdf")).toBe("Serviceratgeber");
    expect(quelleAnzeige("BPGG § 22 Abs. 1 Z 1")).toBe("BPGG § 22 Abs. 1 Z 1");
  });
});

describe("ersterSatz", () => {
  // Fängt: die ganze Erklärung der Rückfrage als Überschrift über den Antwortknöpfen.
  it("nimmt nur den ersten Satz, Abkürzungen ohne Leerzeichen danach bleiben", () => {
    expect(ersterSatz("Wer zahlt die Pension? Meist ist das die PVA. Sie können auch sagen: keine Pension.")).toBe("Wer zahlt die Pension?");
    expect(ersterSatz("Wohnt sie in Wien")).toBe("Wohnt sie in Wien");
  });
});

describe("abbilden: rueckfrage_optionen", () => {
  const roh = { text: "t", verhalten: "rueckfrage", sitzung_id: "s", aussagen: [], rueckfrage: "Wer zahlt die Pension?" };
  // Fängt: ältere Kern-Ausgaben ohne das Feld würden sonst als unerwartetes Format abgelehnt.
  it("fehlt das Feld, ist es leer; vorhandene Knöpfe kommen durch", () => {
    expect(abbilden(roh)?.rueckfrage_optionen).toEqual([]);
    const knopf = { text: "Pensionsversicherung (PVA)", antwort: "Die Pension kommt von der PVA." };
    expect(abbilden({ ...roh, rueckfrage_optionen: [knopf] })?.rueckfrage_optionen).toEqual([knopf]);
  });
});

describe("formatStand und telefonTeile", () => {
  // Fängt: „01.01.2015“ oder „Januar“ statt der österreichischen Form „1. Jänner 2015“.
  it("schreibt das Datum mit österreichischem Monatsnamen", () => {
    expect(formatStand("2015-01-01")).toBe("1. Jänner 2015");
    expect(formatStand("2026-11-05")).toBe("5. November 2026");
    expect(formatStand("unbekannt")).toBe("unbekannt");
  });

  // Fängt: Notrufnummern ohne Link, doppelte Links, und Ziffern in Paragrafen oder Beträgen („§ 1450a“, „1.144“).
  it("macht 1450 und 144 zu tel-Teilen, sonst nichts", () => {
    expect(telefonTeile("Rufen Sie 1450 an, im Notfall 144.")).toEqual([
      { text: "Rufen Sie " },
      { text: "1450", tel: "1450" },
      { text: " an, im Notfall " },
      { text: "144", tel: "144" },
      { text: "." },
    ]);
    expect(telefonTeile("Betrag 1.144 Euro, Zeile 14450").every((t) => !t.tel)).toBe(true);
  });
});
