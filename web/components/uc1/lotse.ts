import { execFile } from "node:child_process";
// Relativ statt "@/…": vitest.config.ts (E0) kennt den Alias nicht, so bleibt die Datei in Tests ladbar.
import { findeRepoWurzel } from "../../lib/plattform/modell";
import { abbilden, frageSchema, type FrageEingabe } from "./antwort";

// POST /api/uc1/frage (#35): reicht die Situation an `lotse frage --json` weiter, als Subprozess mit argv (keine
// Shell). web/ ruft nie ein Modell direkt. Nur für den Server: die Seite importiert antwort.ts, nie diese Datei.
// `UC1_CLI_WURZEL` lenkt den Aufruf auf einen anderen Checkout, in dem uc1/ mit dem Kern liegt (Entwicklung).

export const LOTSE_ARGV = ["run", "--frozen", "--package", "uc1", "lotse", "frage", "--json"] as const;
export const TIMEOUT_MS = 60_000;
export const MAX_BUFFER = 2 * 1024 * 1024;
/** 1000 Zeichen als JSON mit Escapes und Umlauten passen weit unter 4 KiB. */
export const MAX_BODY_BYTES = 4 * 1024;
/** Lotse-Läufe, die ein Prozess gleichzeitig startet; jeder Lauf ist ein Python-Prozess. */
export const MAX_LAEUFE = 2;

export const NICHT_ERREICHBAR = "Der Lotse ist gerade nicht erreichbar.";
const UNGUELTIG = "Die Anfrage braucht JSON mit dem Feld text.";

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
      else if (typeof fehler.code === "number" && !fehler.killed) aufloesen({ code: fehler.code, stdout });
      else ablehnen(fehler);
    });
  });

export function cliWurzel(umgebung: Readonly<Record<string, string | undefined>> = process.env): string {
  return umgebung.UC1_CLI_WURZEL?.trim() || findeRepoWurzel();
}

/** argv für `uv`; `--` vor dem Text, damit eine Eingabe wie „-h“ kein Schalter der CLI wird. */
export function lotseArgv({ text, sitzung, stil, sprache }: FrageEingabe): string[] {
  return [
    ...LOTSE_ARGV,
    ...(sitzung ? ["--sitzung", sitzung] : []),
    "--stil",
    stil,
    ...(sprache ? ["--sprache", sprache] : []),
    "--",
    text,
  ];
}

type Status = 400 | 403 | 413 | 429 | 503;

function fehler(status: Status, meldung: string, replay = false): Response {
  return Response.json(replay ? { fehler: meldung, replay: true } : { fehler: meldung }, {
    status,
    headers: { "cache-control": "no-store" },
  });
}

class ZuGross extends Error {}

/** Liest den Body und bricht ab, sobald er `grenze` Bytes überschreitet (auch ohne Content-Length). */
async function leseBody(anfrage: Request, grenze: number): Promise<string> {
  const laenge = Number(anfrage.headers.get("content-length") ?? "");
  if (Number.isFinite(laenge) && laenge > grenze) throw new ZuGross();
  if (!anfrage.body) return "";
  const leser = anfrage.body.getReader();
  const stuecke: Uint8Array[] = [];
  let gelesen = 0;
  for (;;) {
    const { done, value } = await leser.read();
    if (done) break;
    gelesen += value.byteLength;
    if (gelesen > grenze) {
      await leser.cancel();
      throw new ZuGross();
    }
    stuecke.push(value);
  }
  return new TextDecoder().decode(Buffer.concat(stuecke));
}

/** Eingabe aus dem Body oder eine feste deutsche Meldung (keine zod-Texte an den Client). */
function leseEingabe(text: string): FrageEingabe | { meldung: string } {
  let roh: unknown;
  try {
    roh = JSON.parse(text);
  } catch {
    return { meldung: UNGUELTIG };
  }
  if (typeof roh !== "object" || roh === null || typeof (roh as { text?: unknown }).text !== "string") {
    return { meldung: UNGUELTIG };
  }
  const eingabe = frageSchema.safeParse(roh);
  return eingabe.success ? eingabe.data : { meldung: eingabe.error.issues[0]?.message ?? UNGUELTIG };
}

export interface LotseOptionen {
  ausfuehren?: Ausfuehren;
  umgebung?: Readonly<Record<string, string | undefined>>;
  wurzel?: () => string;
  maxLaeufe?: number;
}

/**
 * Handler für POST /api/uc1/frage mit eigener Lauf-Zählung. Vor dem Subprozess: `KIC_ONLINE_LESEND=1` → 403,
 * Body über 4 KiB → 413, ungültige Eingabe → 400, schon `maxLaeufe` offen → 429. Danach: Exit ≠ 0 (auf main
 * meldet `lotse frage` Exit 2, solange der Kern fehlt), Timeout oder kaputtes JSON → 503. 403 und 503 tragen
 * `replay: true`, damit die Seite das aufgezeichnete Beispiel anbietet. Frage und stderr werden nie geloggt.
 */
export function erstelleLotseAntwort({
  ausfuehren = standardAusfuehren,
  umgebung = process.env,
  wurzel = () => cliWurzel(umgebung),
  maxLaeufe = MAX_LAEUFE,
}: LotseOptionen = {}): (anfrage: Request) => Promise<Response> {
  let offen = 0;

  async function fuehreAus(eingabe: FrageEingabe): Promise<Response> {
    let lauf: Lauf;
    try {
      lauf = await ausfuehren("uv", lotseArgv(eingabe), { cwd: wurzel(), timeout: TIMEOUT_MS, maxBuffer: MAX_BUFFER });
    } catch (grund) {
      console.warn(`[uc1/frage] Lotse nicht erreichbar (${(grund as Error).name ?? "Fehler"})`);
      return fehler(503, NICHT_ERREICHBAR, true);
    }
    if (lauf.code !== 0) {
      console.warn(`[uc1/frage] Lotse beendet mit Exit ${lauf.code}`);
      return fehler(503, NICHT_ERREICHBAR, true);
    }
    let antwort;
    try {
      antwort = abbilden(JSON.parse(lauf.stdout));
    } catch {
      antwort = null;
    }
    if (!antwort) {
      console.warn("[uc1/frage] Lotse-Ausgabe verletzt den Vertrag");
      return fehler(503, NICHT_ERREICHBAR, true);
    }
    return Response.json(antwort, { headers: { "cache-control": "no-store" } });
  }

  return async function lotseAntwort(anfrage: Request): Promise<Response> {
    if (umgebung.KIC_ONLINE_LESEND === "1") {
      return fehler(403, "In der Online-Demo antwortet der Lotse nicht live.", true);
    }
    let body: string;
    try {
      body = await leseBody(anfrage, MAX_BODY_BYTES);
    } catch (grund) {
      if (grund instanceof ZuGross) return fehler(413, "Die Anfrage ist zu groß.");
      return fehler(400, UNGUELTIG);
    }
    const eingabe = leseEingabe(body);
    if ("meldung" in eingabe) return fehler(400, eingabe.meldung);

    if (offen >= maxLaeufe) return fehler(429, "Gerade sind viele Anfragen unterwegs. Bitte gleich noch einmal.");
    offen += 1;
    try {
      return await fuehreAus(eingabe);
    } finally {
      offen -= 1;
    }
  };
}

/** Prozessweiter Handler für die Route: höchstens `MAX_LAEUFE` Lotse-Läufe gleichzeitig. */
export const lotseAntwort = erstelleLotseAntwort();
