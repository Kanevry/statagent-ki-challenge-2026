import { execFile } from "node:child_process";
import { findeRepoWurzel } from "./modell";
import { ergebnisSchema, frageSchema } from "./uc4-ergebnis";

// POST /api/uc4/frage (#98): reicht die Frage an `plattform.router` weiter, als Subprozess mit argv (keine Shell).
// web/ ruft nie ein Modell direkt; welche Adapter antworten, entscheidet der Router. `UC4_ADAPTER=mock` hängt
// `--mock` an (CI, Playwright, Online-Demo ohne Modellschlüssel). Exit 1 heißt „keine Antwort“ (alle fehlend)
// und ist ein gültiges Ergebnis, solange stdout den Vertrag erfüllt.

export const ROUTER_ARGV = ["run", "--frozen", "python", "-m", "plattform.router", "frage", "--json"] as const;
export const TIMEOUT_MS = 60_000;
/** Drei Antworten mit Belegen passen weit hinein; mehr ist ein Fehler, kein Ergebnis. */
export const MAX_BUFFER = 1024 * 1024;

export interface Lauf {
  code: number;
  stdout: string;
}

/** Läuft ein Kommando und liefert Exit-Code und stdout; wirft bei Timeout, Abbruch oder Startfehler. */
export type Ausfuehren = (
  befehl: string,
  argv: readonly string[],
  optionen: { cwd: string; timeout: number; maxBuffer: number },
) => Promise<Lauf>;

export const standardAusfuehren: Ausfuehren = (befehl, argv, { cwd, timeout, maxBuffer }) =>
  new Promise((aufloesen, ablehnen) => {
    execFile(befehl, [...argv], { cwd, timeout, maxBuffer, env: process.env }, (fehler, stdout) => {
      if (!fehler) aufloesen({ code: 0, stdout });
      // Regulärer Exit ≠ 0 (z. B. 1 = keine Antwort): der Aufrufer entscheidet. Timeout und maxBuffer setzen
      // `killed` bzw. einen Text-Code und gelten als Fehler.
      else if (typeof fehler.code === "number" && !fehler.killed) aufloesen({ code: fehler.code, stdout });
      else ablehnen(fehler);
    });
  });

/** argv für eine Frage; `--` davor, damit eine Frage wie „-h“ kein Schalter des Routers wird. */
export function routerArgv(frage: string, mock: boolean): string[] {
  return [...ROUTER_ARGV, ...(mock ? ["--mock"] : []), "--", frage];
}

function fehler(status: 400 | 502, meldung: string): Response {
  return Response.json({ fehler: meldung }, { status, headers: { "cache-control": "no-store" } });
}

export async function frageAntwort(
  anfrage: Request,
  {
    ausfuehren = standardAusfuehren,
    umgebung = process.env,
    wurzel = findeRepoWurzel,
  }: {
    ausfuehren?: Ausfuehren;
    umgebung?: Readonly<Record<string, string | undefined>>;
    wurzel?: () => string;
  } = {},
): Promise<Response> {
  let roh: unknown;
  try {
    roh = await anfrage.json();
  } catch {
    return fehler(400, "Die Anfrage braucht JSON mit dem Feld frage.");
  }
  const eingabe = frageSchema.safeParse(roh);
  if (!eingabe.success) return fehler(400, eingabe.error.issues[0]?.message ?? "Die Frage ist ungültig.");

  const argv = routerArgv(eingabe.data.frage, umgebung.UC4_ADAPTER === "mock");
  let lauf: Lauf;
  try {
    lauf = await ausfuehren("uv", argv, { cwd: wurzel(), timeout: TIMEOUT_MS, maxBuffer: MAX_BUFFER });
  } catch (grund) {
    // Nur die Art des Fehlers loggen: stderr und Meldung können Pfade, Umgebungswerte oder die Frage enthalten.
    console.warn(`[uc4/frage] Router nicht erreichbar (${(grund as Error).name ?? "Fehler"})`);
    return fehler(502, "Die Kette hat nicht geantwortet. Bitte später noch einmal fragen.");
  }
  if (lauf.code !== 0 && lauf.code !== 1) {
    console.warn(`[uc4/frage] Router beendet mit Exit ${lauf.code}`);
    return fehler(502, "Die Kette ist mit einem Fehler abgebrochen.");
  }

  let ergebnis;
  try {
    ergebnis = ergebnisSchema.safeParse(JSON.parse(lauf.stdout));
  } catch {
    ergebnis = null;
  }
  if (!ergebnis?.success) {
    console.warn("[uc4/frage] Router-Ausgabe verletzt den Vertrag");
    return fehler(502, "Die Kette hat in einem unerwarteten Format geantwortet.");
  }
  return Response.json(ergebnis.data, { headers: { "cache-control": "no-store" } });
}
