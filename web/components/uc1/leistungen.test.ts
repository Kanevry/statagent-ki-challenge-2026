// @vitest-environment node
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { findeRepoWurzel } from "../../lib/plattform/modell";
import { LEISTUNGEN, leistungenTitel, leistungName } from "./leistungen";

const DATEI = path.join(findeRepoWurzel(), "uc1", "daten", "leistungen.yaml");

/**
 * `name: {de: "…"}` je Leistung im Abschnitt `leistungen:`. Ein Block beginnt mit `  <id>:` (zwei Leerzeichen) und
 * endet vor dem nächsten Block; darin zählt die erste `name:`-Zeile mit vier Leerzeichen Einzug, egal an welcher
 * Stelle sie im Block steht.
 */
function namenAusYaml(text: string): Record<string, string> {
  const abschnitt = (text.split(/^leistungen:\s*$/m)[1] ?? "").split(/^\S/m)[0] ?? "";
  const namen: Record<string, string> = {};
  const bloecke = abschnitt.split(/^(?= {2}[a-z_]+:\s*$)/m);
  for (const block of bloecke) {
    const id = /^ {2}([a-z_]+):\s*$/m.exec(block)?.[1];
    const name = /^ {4}name:\s*\{\s*de:\s*"([^"]+)"/m.exec(block)?.[1];
    if (id && name) namen[id] = name;
  }
  return namen;
}

describe("Leistungsnamen", () => {
  // Fängt: ein neuer oder umbenannter Leistungsname im Kern, der auf der Seite als ID oder veraltet steht.
  it.skipIf(!existsSync(DATEI))("jede Leistung aus uc1/daten/leistungen.yaml steht mit gleichem Namen in LEISTUNGEN", () => {
    const namen = namenAusYaml(readFileSync(DATEI, "utf8"));
    expect(Object.keys(namen).length).toBeGreaterThan(0);
    expect(LEISTUNGEN).toMatchObject(namen);
  });

  // Fängt: einen Leser, der an der Zeilenreihenfolge hängt (Kommentar oder Feld vor `name:`) und Leistungen verliert.
  it("liest den Namen je Block, auch wenn er nicht direkt unter der ID steht", () => {
    const yaml = [
      "traeger:",
      "  pva:",
      '    name: {de: "Pensionsversicherungsanstalt"}',
      "leistungen:",
      "  pflegegeld:",
      "    # Kommentar",
      "    alltagshilfe: true",
      '    name: {de: "Pflegegeld", en: "care allowance"}',
      "    stelle:",
      '      name: {de: "nicht dieser"}',
      "  unfallversicherung:",
      '    name: {de: "Unfallversicherung"}',
      "regeln:",
      "  x:",
      '    name: {de: "fremd"}',
    ].join("\n");
    expect(namenAusYaml(yaml)).toEqual({ pflegegeld: "Pflegegeld", unfallversicherung: "Unfallversicherung" });
  });

  // Fängt: eine unbekannte ID als „zahn_spange“ statt lesbar.
  it("macht unbekannte IDs lesbar", () => {
    expect(leistungName("pflegegeld")).toBe("Pflegegeld");
    expect(leistungName("unfallversicherung")).toBe("Unfallversicherung");
    expect(leistungName("zahn_spange")).toBe("Zahn spange");
  });
});

describe("leistungenTitel", () => {
  // Fängt: Namensliste in der Überschrift bei mehreren Leistungen (Urteil ui-regie-32) oder falsche Einzahl.
  it("nennt eine Leistung beim Namen und zählt mehrere als Zahlwort", () => {
    expect(leistungenTitel(["pflegegeld"])).toBe(`${leistungName("pflegegeld")} kommt für Sie in Frage`);
    expect(leistungenTitel(["pflegegeld", "rehabilitation"])).toBe("Zwei Leistungen kommen für Sie in Frage");
    expect(leistungenTitel(["a", "b", "c"])).toBe("Drei Leistungen kommen für Sie in Frage");
  });
});
