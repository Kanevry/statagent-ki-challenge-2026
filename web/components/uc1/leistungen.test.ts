// @vitest-environment node
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { findeRepoWurzel } from "../../lib/plattform/modell";
import { LEISTUNGEN, leistungName } from "./leistungen";

const DATEI = path.join(findeRepoWurzel(), "uc1", "daten", "leistungen.yaml");

/** `name: {de: "…"}` je Leistung im Abschnitt `leistungen:` (zwei Leerzeichen Einzug für die ID). */
function namenAusYaml(text: string): Record<string, string> {
  const abschnitt = text.split(/^leistungen:\s*$/m)[1] ?? "";
  const namen: Record<string, string> = {};
  for (const treffer of abschnitt.matchAll(/^ {2}([a-z_]+):\s*\n {4}name:\s*\{de:\s*"([^"]+)"/gm)) {
    if (treffer[1] && treffer[2]) namen[treffer[1]] = treffer[2];
  }
  return namen;
}

describe("Leistungsnamen", () => {
  // Fängt: ein im Kern umbenannter oder neuer Leistungsname, der auf der Seite veraltet oder als ID steht.
  it.skipIf(!existsSync(DATEI))("stimmen mit uc1/daten/leistungen.yaml überein", () => {
    const namen = namenAusYaml(readFileSync(DATEI, "utf8"));
    expect(Object.keys(namen).length).toBeGreaterThan(0);
    expect(LEISTUNGEN).toEqual(namen);
  });

  // Fängt: eine unbekannte ID als „zahn_spange“ statt lesbar.
  it("macht unbekannte IDs lesbar", () => {
    expect(leistungName("pflegegeld")).toBe("Pflegegeld");
    expect(leistungName("zahn_spange")).toBe("Zahn spange");
  });
});
