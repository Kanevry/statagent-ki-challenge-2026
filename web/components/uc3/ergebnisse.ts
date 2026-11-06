import { readFile, stat } from "node:fs/promises";
import path from "node:path";
// Relativ statt "@/…": so bleibt die Datei in Tests ladbar (wie cli.ts).
import { findeRepoWurzel } from "../../lib/plattform/modell";

/**
 * Die Abgabe-Dateien für die Seite /uc3/ergebnisse. Ausgeliefert wird nur, was in dieser festen Liste steht: Die
 * Eingabe wählt einen Eintrag aus, ein Pfad aus der Eingabe kommt nie vor. Die Ministeriums-Lieferung fehlt hier mit
 * Absicht: Sie enthält Einzeldaten und liegt nur im SV-Box-Teamordner (Entscheid #16). Ins App-Image kommen die Dateien
 * über die Positivliste deploy/app.Dockerfile.dockerignore.
 */
export const EXCEL_DATEIEN = [
  {
    fassung: "v1",
    datei: "aggregationen_v1.xlsx",
    titel: "Excel mit den Regeln vom Start (Regelsatz v1)",
    inhalt: "24 Berichtsmonate, August 2024 bis Juli 2026.",
  },
  {
    fassung: "v2",
    datei: "aggregationen_v2.xlsx",
    titel: "Excel nach den Änderungsaufträgen 1 und 2 (Regelsatz v2)",
    inhalt: "Gezählt über das ganze Monat, mit den Kategorien Arbeiter, Angestellte und Beamte.",
  },
] as const;

const EXCEL_TYP = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
const BELEG_DATEI = "ministerium_2026-07.beleg.md";

export function excelPfad(fassung: string): string {
  return `/api/uc3/ergebnisse/${fassung}`;
}

function abgabePfad(datei: string, wurzel: string): string {
  return path.join(wurzel, "abgabe", datei);
}

/** Antwort der Download-Route: unbekannte Fassung oder fehlende Datei ergibt 404. */
export async function excelAntwort(fassung: string, wurzel: string = findeRepoWurzel()): Promise<Response> {
  const eintrag = EXCEL_DATEIEN.find((d) => d.fassung === fassung);
  if (!eintrag) return new Response("Diese Datei gibt es hier nicht.", { status: 404 });
  let inhalt: Uint8Array<ArrayBuffer>;
  try {
    inhalt = new Uint8Array(await readFile(abgabePfad(eintrag.datei, wurzel)));
  } catch {
    return new Response("Diese Datei fehlt in dieser Installation.", { status: 404 });
  }
  return new Response(inhalt, {
    headers: {
      "Content-Type": EXCEL_TYP,
      "Content-Disposition": `attachment; filename="${eintrag.datei}"`,
      "Content-Length": String(inhalt.byteLength),
      "X-Content-Type-Options": "nosniff",
    },
  });
}

/** Größe je Excel-Datei in KB für die Seite, null wenn die Datei fehlt. */
export async function excelGroesseKb(datei: string, wurzel: string = findeRepoWurzel()): Promise<number | null> {
  try {
    return Math.ceil((await stat(abgabePfad(datei, wurzel))).size / 1000);
  } catch {
    return null;
  }
}

export interface MinisteriumBeleg {
  datei: string;
  sha256: string;
  personen: number;
  spalten: string[];
  /** Die Tabelle des Belegs im Wortlaut, für „Beleg ansehen“. */
  zeilen: { angabe: string; wert: string }[];
}

/** Liest die Angaben aus dem Beleg, damit keine Zahl doppelt von Hand steht. Fehlt eine Angabe: null. */
export function ministeriumBelegAus(text: string): MinisteriumBeleg | null {
  const datei = /^\| Datei \| `([^`]+)` \|$/m.exec(text)?.[1];
  const sha256 = /^\| sha256 \| `([0-9a-f]{64})` \|$/m.exec(text)?.[1];
  const personen = /^\| Zeilen \| (\d+) Personen /m.exec(text)?.[1];
  const parameter = /^\| Parameter \| `(\{.*\})` \|$/m.exec(text)?.[1];
  if (!datei || !sha256 || !personen || !parameter) return null;
  try {
    const { felder } = JSON.parse(parameter) as { felder?: unknown };
    if (!Array.isArray(felder) || felder.length === 0) return null;
    const zeilen = [...text.matchAll(/^\| (.+?) \| (.+) \|$/gm)]
      .map(([, angabe, wert]) => ({ angabe: angabe ?? "", wert: (wert ?? "").replaceAll("`", "") }))
      .filter((z) => z.angabe !== "Angabe" && z.angabe !== "---");
    return { datei, sha256, personen: Number(personen), spalten: felder.map(String), zeilen };
  } catch {
    return null;
  }
}

export async function leseMinisteriumBeleg(wurzel: string = findeRepoWurzel()): Promise<MinisteriumBeleg | null> {
  try {
    return ministeriumBelegAus(await readFile(abgabePfad(BELEG_DATEI, wurzel), "utf8"));
  } catch {
    return null;
  }
}
