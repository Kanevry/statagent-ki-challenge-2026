import { execFile } from "node:child_process";
import { findeRepoWurzel } from "./modell";
import { erstelleRatenlimit, grenzeAus, type PruefeRatenlimit } from "./ratenlimit";
import { ergebnisSchema, frageSchema } from "./uc4-ergebnis";

// POST /api/uc4/frage (#98): reicht die Frage an `plattform.router` weiter, als Subprozess mit argv (keine Shell).
// web/ ruft nie ein Modell direkt; welche Adapter antworten, entscheidet der Router. `UC4_ADAPTER=mock` hängt
// `--mock` an (CI, Playwright, Online-Demo ohne Modellschlüssel). Exit 1 heißt „keine Antwort“ (alle fehlend)
// und ist ein gültiges Ergebnis, solange stdout den Vertrag erfüllt. Vor dem Subprozess greift das Ratenlimit je IP
// (#100); Exit 3 heißt „Tagesbudget von plattform.llm verbraucht“ und wird wie das Ratenlimit ein 429.

export const ROUTER_ARGV = ["run", "--frozen", "python", "-m", "plattform.router", "frage", "--json"] as const;
export const TIMEOUT_MS = 60_000;
/** Drei Antworten mit Belegen passen weit hinein; mehr ist ein Fehler, kein Ergebnis. */
export const MAX_BUFFER = 1024 * 1024;
/** Exit-Code von `plattform.router frage`, wenn das Tagesbudget erschöpft ist (`router.BUDGET_ERSCHOEPFT`). */
export const EXIT_BUDGET = 3;
export const BUDGET_MELDUNG = "Das Tageskontingent für Modellaufrufe ist aufgebraucht.";

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

/** Größter Request-Body; eine Frage mit 500 Zeichen braucht als JSON höchstens rund 3 KiB (UTF-8, Escapes). */
export const MAX_BODY_BYTES = 4 * 1024;
/** Router-Läufe, die ein Prozess gleichzeitig startet; jeder Lauf ist ein Python-Prozess. */
export const MAX_LAEUFE = 2;

const UNGUELTIG = "Die Anfrage braucht JSON mit dem Feld frage als Text.";

type Status = 400 | 403 | 413 | 429 | 502;

function fehler(status: Status, meldung: string): Response {
  return Response.json({ fehler: meldung }, { status, headers: { "cache-control": "no-store" } });
}

/** Sekunden bis zur nächsten UTC-Mitternacht: dann zählt plattform.llm das Budget neu. */
function bisMitternachtUtc(jetzt: number): number {
  const morgen = new Date(jetzt);
  morgen.setUTCHours(24, 0, 0, 0);
  return Math.max(1, Math.ceil((morgen.getTime() - jetzt) / 1000));
}

function budgetErschoepft(stdout: string): boolean {
  try {
    const daten: unknown = JSON.parse(stdout);
    return typeof daten === "object" && daten !== null && "fehler" in daten && daten.fehler === "budget_erschoepft";
  } catch {
    return false;
  }
}

class ZuGross extends Error {}

/** Liest den Body als Text und bricht ab, sobald er `grenze` Bytes überschreitet (auch ohne Content-Length). */
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

/** Frage aus dem Body oder eine feste deutsche Meldung (keine zod-Texte an den Client). */
function leseFrage(text: string): { frage: string } | { meldung: string } {
  let roh: unknown;
  try {
    roh = JSON.parse(text);
  } catch {
    return { meldung: UNGUELTIG };
  }
  if (typeof roh !== "object" || roh === null || typeof (roh as { frage?: unknown }).frage !== "string") {
    return { meldung: UNGUELTIG };
  }
  // Ab hier tragen nur noch die eigenen deutschen Meldungen aus frageSchema (leer, zu lang).
  const eingabe = frageSchema.safeParse(roh);
  return eingabe.success ? { frage: eingabe.data.frage } : { meldung: eingabe.error.issues[0]?.message ?? UNGUELTIG };
}

export interface FrageOptionen {
  ausfuehren?: Ausfuehren;
  umgebung?: Readonly<Record<string, string | undefined>>;
  wurzel?: () => string;
  maxLaeufe?: number;
  /** Ratenlimit je Client-IP (#100); Standard: eigenes Limit dieses Handlers mit `RATENLIMIT_PRO_MINUTE`. */
  ratenlimit?: PruefeRatenlimit;
  jetzt?: () => number;
}

/**
 * Baut den Handler für POST /api/uc4/frage mit eigener Lauf-Zählung. Sperren in dieser Reihenfolge, alle vor dem
 * Subprozess: `KIC_ONLINE_LESEND=1` → 403 (Online-Demo, zweite Sperre hinter dem Proxy, #100), Ratenlimit je IP
 * → 429 mit `Retry-After`, Body > 4 KiB → 413, ungültige Frage → 400, schon `maxLaeufe` Läufe offen → 429. Der Slot
 * wird in `finally` frei, auch nach Fehlern. Nach dem Lauf: Exit 3 (Tagesbudget erschöpft) → 429.
 */
export function erstelleFrageAntwort({
  ausfuehren = standardAusfuehren,
  umgebung = process.env,
  wurzel = findeRepoWurzel,
  maxLaeufe = MAX_LAEUFE,
  ratenlimit = erstelleRatenlimit({ proMinute: grenzeAus(umgebung) }),
  jetzt = Date.now,
}: FrageOptionen = {}): (anfrage: Request) => Promise<Response> {
  let offen = 0;

  async function fuehreAus(frage: string): Promise<Response> {
    const argv = routerArgv(frage, umgebung.UC4_ADAPTER === "mock");
    let lauf: Lauf;
    try {
      lauf = await ausfuehren("uv", argv, { cwd: wurzel(), timeout: TIMEOUT_MS, maxBuffer: MAX_BUFFER });
    } catch (grund) {
      // Nur die Art des Fehlers loggen: stderr und Meldung können Pfade, Umgebungswerte oder die Frage enthalten.
      console.warn(`[uc4/frage] Router nicht erreichbar (${(grund as Error).name ?? "Fehler"})`);
      return fehler(502, "Die Kette hat nicht geantwortet. Bitte später noch einmal fragen.");
    }
    if (lauf.code === EXIT_BUDGET && budgetErschoepft(lauf.stdout)) {
      console.warn("[uc4/frage] Tagesbudget erschöpft");
      return Response.json(
        { fehler: BUDGET_MELDUNG },
        { status: 429, headers: { "retry-after": String(bisMitternachtUtc(jetzt())), "cache-control": "no-store" } },
      );
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

  return async function frageAntwort(anfrage: Request): Promise<Response> {
    if (umgebung.KIC_ONLINE_LESEND === "1") return fehler(403, "Fragen sind in der Online-Demo noch gesperrt.");
    const gedrosselt = ratenlimit(anfrage, jetzt());
    if (gedrosselt) return gedrosselt;

    let text: string;
    try {
      text = await leseBody(anfrage, MAX_BODY_BYTES);
    } catch (grund) {
      if (grund instanceof ZuGross) return fehler(413, `Die Anfrage ist größer als ${MAX_BODY_BYTES / 1024} KiB.`);
      return fehler(400, UNGUELTIG);
    }
    const eingabe = leseFrage(text);
    if ("meldung" in eingabe) return fehler(400, eingabe.meldung);

    if (offen >= maxLaeufe) return fehler(429, "Gerade laufen schon genug Fragen. Bitte gleich noch einmal fragen.");
    offen += 1;
    try {
      return await fuehreAus(eingabe.frage);
    } finally {
      offen -= 1;
    }
  };
}

/** Prozessweiter Handler für die Route: ein Ratenlimit je IP, höchstens `MAX_LAEUFE` Router-Läufe gleichzeitig. */
export const frageAntwort = erstelleFrageAntwort();
