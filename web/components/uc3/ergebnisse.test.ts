// @vitest-environment node
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { EXCEL_DATEIEN, excelAntwort, leseMinisteriumBeleg, ministeriumBelegAus } from "./ergebnisse";

const WURZEL = path.resolve(process.cwd(), "..");

describe("Download der Excel-Dateien", () => {
  it.each(EXCEL_DATEIEN.map((d) => [d.fassung, d.datei]))("%s liefert genau die Datei %s", async (fassung, datei) => {
    const antwort = await excelAntwort(fassung, WURZEL);
    expect(antwort.status).toBe(200);
    expect(antwort.headers.get("Content-Disposition")).toBe(`attachment; filename="${datei}"`);
    expect(Buffer.from(await antwort.arrayBuffer()).equals(readFileSync(path.join(WURZEL, "abgabe", datei)))).toBe(true);
  });

  it.each(["../abgabe/ministerium_2026-07.csv", "ministerium_2026-07.csv", "aggregationen_v1.xlsx", "__proto__", "v3", ""])(
    "%j ist nicht auf der Liste und ergibt 404",
    async (eingabe) => {
      expect((await excelAntwort(eingabe, WURZEL)).status).toBe(404);
    },
  );

  it("ohne Datei 404 statt Absturz", async () => {
    expect((await excelAntwort("v1", path.join(WURZEL, "gibt-es-nicht"))).status).toBe(404);
  });
});

describe("Beleg der Ministeriums-Liste", () => {
  it("nimmt Personen, Spalten und sha256 aus dem Beleg im Repo", async () => {
    const beleg = await leseMinisteriumBeleg(WURZEL);
    expect(beleg).toMatchObject({
      datei: "ministerium_2026-07.csv",
      personen: 32741,
      spalten: ["PERSON_ID", "GESCHLECHT", "GEBURTSJAHR", "TAGE"],
      sha256: "d8492f46dd5f21fcd391e82d3eb671d437e46de2bda96f4237fd1d5972e86379",
    });
    expect(beleg?.zeilen.map((z) => z.angabe)).toContain("Abgabeweg");
    expect(beleg?.zeilen.map((z) => z.angabe)).not.toContain("---");
    expect(beleg?.zeilen.find((z) => z.angabe === "Datei")?.wert).toBe("ministerium_2026-07.csv");
  });

  it("ein Beleg ohne Angaben ergibt null, nie eine geratene Zahl", () => {
    expect(ministeriumBelegAus("# leer")).toBeNull();
  });
});

describe("App-Image", () => {
  it("nimmt aus abgabe/ nur die beiden Excel und den Beleg auf, nie die Ministeriums-Lieferung", () => {
    const liste = readFileSync(path.join(WURZEL, "deploy", "app.Dockerfile.dockerignore"), "utf8").split("\n");
    expect(liste.filter((z) => z.includes("abgabe") && !z.startsWith("#"))).toEqual([
      "!abgabe/aggregationen_v1.xlsx",
      "!abgabe/aggregationen_v2.xlsx",
      "!abgabe/ministerium_2026-07.beleg.md",
    ]);
  });
});
