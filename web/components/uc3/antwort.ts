import { ucAntwortSchema, type UcAntwort } from "@kic/ui/antwortform";
// Nur Typen aus cli.ts: die Seite (Client) nutzt alsCsv und istRueckfrage aus dieser Datei, und cli.ts zieht
// node:child_process, das Turbopack im Client-Bundle ablehnt (gemessen 05.11.). Den Aufruf `uc3` reicht die Route
// herein (`starte`), siehe web/app/api/uc3/frage/route.ts.
import type { Ausfuehren, CliLauf, uc3 } from "./cli";

// Fragen an die Daten (UC3, POST /api/uc3/frage): reicht die Frage an `uc3 frage --json` weiter und, solange #74
// fehlt, an `uc3 antwort --json`. Das Programm rechnet ohne Sprachmodell; web/ prüft nur die Form (UcAntwort,
// strikt) und zeigt Zahl, Beleg und Abfrage. Frage und stderr werden nie geloggt.

export const MAX_BODY_BYTES = 4 * 1024;
export const MAX_FRAGE = 500;
/** Gleichzeitige CLI-Läufe je Prozess; jeder Lauf ist ein Python-Prozess mit Datenbankverbindung. */
export const MAX_LAEUFE = 2;
export const TIMEOUT_MS = 60_000;

/** argv nach `uc3`; `--` vor der Frage, damit eine Frage wie „-h“ kein Schalter wird. */
export function frageArgv(befehl: "frage" | "antwort", frage: string): string[] {
  return [befehl, "--json", "--", frage];
}

/**
 * `uc3 frage` ist noch nicht gebaut (#74): Exit 2 mit „noch nicht umgesetzt“. Heute bricht typer schon vorher mit
 * „No such option: --json“ ab (auch Exit 2), weil der Platzhalter den Schalter nicht kennt; beides heißt „noch
 * nicht da“. Jeder andere Exit 2 (fehlendes Argument, falscher Schalter) ist ein Fehler, kein Rückfall.
 */
export function frageFehlt(lauf: CliLauf): boolean {
  return lauf.code === 2 && (lauf.stderr.includes("noch nicht umgesetzt") || /No such option: --json\b/.test(lauf.stderr));
}

export type Zerlegt =
  | { ok: true; antwort: UcAntwort; definition: string | null; rueckfrage: string | null }
  | { ok: false };

function textOderNull(wert: unknown): string | null | undefined {
  if (wert === undefined || wert === null) return null;
  if (typeof wert !== "string") return undefined;
  return wert.trim() ? wert.trim() : null;
}

/**
 * stdout der CLI (schon als JSON gelesen) → UcAntwort plus `definition` und `rueckfrage` (#74). Die beiden
 * Zusatzfelder werden vor der strikten Prüfung abgetrennt; jedes andere unbekannte Feld oder eine Zahl ohne
 * Beleg macht die Ausgabe ungültig.
 */
export function zerlegeAntwort(json: unknown): Zerlegt {
  if (typeof json !== "object" || json === null || Array.isArray(json)) return { ok: false };
  const { definition, rueckfrage, ...rest } = json as Record<string, unknown>;
  const def = textOderNull(definition);
  const rueck = textOderNull(rueckfrage);
  if (def === undefined || rueck === undefined) return { ok: false };
  const geprueft = ucAntwortSchema.safeParse(rest);
  if (!geprueft.success) return { ok: false };
  return { ok: true, antwort: geprueft.data, definition: def, rueckfrage: rueck };
}

/** Rückfrage statt Zahl: die CLI fragt ausdrücklich nach, oder sie hat keine Zahl geliefert. */
export function istRueckfrage(antwort: UcAntwort, rueckfrage: string | null): boolean {
  return rueckfrage !== null || antwort.zahlen.length === 0;
}

// --- CSV ------------------------------------------------------------------------------------------------------

/** Ein Feld für CSV mit Semikolon: Anführungszeichen verdoppelt, Feld in Anführungszeichen bei ; " oder Umbruch. */
function feld(wert: string, alsText = true): string {
  // Tabellenprogramme rechnen Felder, die mit = + @ beginnen, als Formel; ein Apostroph davor hält sie als Text.
  const sicher = alsText && /^[=+@\t\r-]/.test(wert) ? `'${wert}` : wert;
  return /[;"\r\n]/.test(sicher) ? `"${sicher.replaceAll('"', '""')}"` : sicher;
}

/** Zahlen der Antwort als CSV (Spalten bezeichnung;wert;einheit;lieferung;sql), Dezimalkomma, Zeilenende CRLF. */
export function alsCsv(antwort: UcAntwort): string {
  const zeilen = [["bezeichnung", "wert", "einheit", "lieferung", "sql"].join(";")];
  for (const zahl of antwort.zahlen) {
    const beleg = antwort.belege[zahl.beleg];
    zeilen.push(
      [
        feld(zahl.bezeichnung),
        feld(String(zahl.wert).replace(".", ","), false),
        feld(zahl.einheit ?? ""),
        feld(beleg?.lieferung ?? ""),
        feld(beleg?.sql ?? ""),
      ].join(";"),
    );
  }
  return `${zeilen.join("\r\n")}\r\n`;
}

// --- POST /api/uc3/frage --------------------------------------------------------------------------------------

const UNGUELTIG = "Die Anfrage braucht JSON mit dem Feld frage als Text.";

type FehlerStatus = 400 | 403 | 413 | 429 | 502;

function fehler(status: FehlerStatus, meldung: string): Response {
  return Response.json({ fehler: meldung }, { status, headers: { "cache-control": "no-store" } });
}

class ZuGross extends Error {}

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

/** Body → Frage oder feste deutsche Meldung. */
export function leseFrage(text: string): { frage: string } | { meldung: string } {
  let roh: unknown;
  try {
    roh = JSON.parse(text);
  } catch {
    return { meldung: UNGUELTIG };
  }
  const frage = (roh as { frage?: unknown } | null)?.frage;
  if (typeof frage !== "string") return { meldung: UNGUELTIG };
  const sauber = frage.trim();
  if (!sauber) return { meldung: "Bitte eine Frage eingeben." };
  if (sauber.length > MAX_FRAGE) return { meldung: `Die Frage ist länger als ${MAX_FRAGE} Zeichen.` };
  return { frage: sauber };
}

export interface FrageAntwortOptionen {
  /** `uc3` aus cli.ts; baut argv (`uv run … uc3`) und startet den Prozess. */
  starte: typeof uc3;
  ausfuehren?: Ausfuehren;
  umgebung?: Readonly<Record<string, string | undefined>>;
  wurzel?: () => string;
  maxLaeufe?: number;
}

export interface FrageErgebnis {
  antwort: UcAntwort;
  definition: string | null;
  rueckfrage: string | null;
  quelle: "frage" | "antwort";
}

/**
 * Handler für POST /api/uc3/frage. Sperren in dieser Reihenfolge, alle vor dem Subprozess: `KIC_ONLINE_LESEND=1`
 * → 403, Body > 4 KiB → 413, ungültige Frage → 400, schon `maxLaeufe` Läufe offen → 429. Dann `uc3 frage`, bei
 * „noch nicht umgesetzt“ `uc3 antwort`; Timeout, Startfehler, Exit ≠ 0 oder eine Ausgabe außerhalb des Vertrags
 * → 502. Erfolg: {antwort, definition, rueckfrage, quelle}.
 */
export function erstelleFrageAntwort({
  starte,
  ausfuehren,
  umgebung = process.env,
  wurzel,
  maxLaeufe = MAX_LAEUFE,
}: FrageAntwortOptionen): (anfrage: Request) => Promise<Response> {
  let offen = 0;
  const optionen = { timeout: TIMEOUT_MS, ...(ausfuehren ? { ausfuehren } : {}), ...(wurzel ? { wurzel } : {}) };

  async function fuehreAus(frage: string): Promise<Response> {
    let quelle: FrageErgebnis["quelle"] = "frage";
    let lauf: CliLauf;
    try {
      lauf = await starte(frageArgv("frage", frage), optionen);
      if (frageFehlt(lauf)) {
        quelle = "antwort";
        lauf = await starte(frageArgv("antwort", frage), optionen);
      }
    } catch (grund) {
      // Nur die Art des Fehlers: Meldung und stderr können Pfade, Umgebungswerte oder die Frage enthalten.
      console.warn(`[uc3/frage] CLI nicht erreichbar (${(grund as Error).name ?? "Fehler"})`);
      return fehler(502, "Das Programm hat nicht rechtzeitig geantwortet. Bitte gleich noch einmal fragen.");
    }
    if (lauf.code !== 0) {
      console.warn(`[uc3/frage] CLI ${quelle} beendet mit Exit ${lauf.code}`);
      return fehler(502, "Das Programm konnte die Frage nicht beantworten. Bitte gleich noch einmal fragen.");
    }
    let json: unknown;
    try {
      json = JSON.parse(lauf.stdout);
    } catch {
      json = null;
    }
    const zerlegt = zerlegeAntwort(json);
    if (!zerlegt.ok) {
      console.warn(`[uc3/frage] Ausgabe von ${quelle} verletzt den Vertrag`);
      return fehler(502, "Das Programm hat in einer unerwarteten Form geantwortet.");
    }
    const ergebnis: FrageErgebnis = {
      antwort: zerlegt.antwort,
      definition: zerlegt.definition,
      rueckfrage: zerlegt.rueckfrage,
      quelle,
    };
    return Response.json(ergebnis, { headers: { "cache-control": "no-store" } });
  }

  return async function frageAntwort(anfrage: Request): Promise<Response> {
    // Gleiche Bedingung wie fragenGesperrt in cli.ts; hier ausgeschrieben, weil diese Datei nur Typen aus cli.ts
    // importiert (die Fragen-Seite lädt sie im Browser).
    if (umgebung.KIC_ONLINE_LESEND === "1" && umgebung.KIC_ONLINE_FRAGEN !== "1") {
      return fehler(403, "Fragen an die Daten sind in der Online-Demo gesperrt.");
    }

    let text: string;
    try {
      text = await leseBody(anfrage, MAX_BODY_BYTES);
    } catch (grund) {
      if (grund instanceof ZuGross) return fehler(413, `Die Anfrage ist größer als ${MAX_BODY_BYTES / 1024} KiB.`);
      return fehler(400, UNGUELTIG);
    }
    const eingabe = leseFrage(text);
    if ("meldung" in eingabe) return fehler(400, eingabe.meldung);

    if (offen >= maxLaeufe) return fehler(429, "Gerade rechnet das Programm schon zwei Fragen. Bitte gleich noch einmal.");
    offen += 1;
    try {
      return await fuehreAus(eingabe.frage);
    } finally {
      offen -= 1;
    }
  };
}
