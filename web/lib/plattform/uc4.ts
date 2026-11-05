import { execFile } from "node:child_process";
import { findeRepoWurzel } from "./modell";
import { erstelleRatenlimit, grenzeAus, type PruefeRatenlimit } from "./ratenlimit";
import { BUDGET_MELDUNG, ergebnisSchema, frageSchema, KETTE, type KettenUc, type Modellwahl } from "./uc4-ergebnis";

export { BUDGET_MELDUNG };

// POST /api/uc4/frage (#98): reicht die Frage an `plattform.router` weiter, als Subprozess mit argv (keine Shell).
// web/ ruft nie ein Modell direkt; welche Adapter antworten, entscheidet der Router. `UC4_ADAPTER=mock` hängt
// `--mock` an (CI, Playwright, Online-Demo ohne Modellschlüssel). Exit 1 heißt „keine Antwort“ (alle fehlend)
// und ist ein gültiges Ergebnis, solange stdout den Vertrag erfüllt. Vor dem Subprozess greift das Ratenlimit je IP
// (#100); Exit 3 heißt „Tagesbudget von plattform.llm verbraucht“ und wird wie das Ratenlimit ein 429.

export const ROUTER_ARGV = ["run", "--frozen", "python", "-m", "plattform.router", "frage", "--json"] as const;
// 180 s: Die Kette ruft nacheinander bis zu drei Adapter mit Modell auf. Gemessen am 05.11. mit Azure: UC3 1 s,
// UC2 98 s (vier Akteure, zwei Runden), UC1 1 s. Mit 60 s brach die Route ab und die Seite zeigte gar keine Antwort.
export const TIMEOUT_MS = 180_000;
/** Drei Antworten mit Belegen passen weit hinein; mehr ist ein Fehler, kein Ergebnis. */
export const MAX_BUFFER = 1024 * 1024;
/** Exit-Code von `plattform.router frage`, wenn das Tagesbudget erschöpft ist (`router.BUDGET_ERSCHOEPFT`). */
export const EXIT_BUDGET = 3;

export interface Lauf {
  code: number;
  stdout: string;
}

/** Läuft ein Kommando und liefert Exit-Code und stdout; wirft bei Timeout, Abbruch oder Startfehler. */
export type Ausfuehren = (
  befehl: string,
  argv: readonly string[],
  optionen: { cwd: string; timeout: number; maxBuffer: number; zusatz?: Readonly<Record<string, string>> },
) => Promise<Lauf>;

export const standardAusfuehren: Ausfuehren = (befehl, argv, { cwd, timeout, maxBuffer, zusatz = {} }) =>
  new Promise((aufloesen, ablehnen) => {
    execFile(befehl, [...argv], { cwd, timeout, maxBuffer, env: { ...process.env, ...zusatz } }, (fehler, stdout) => {
      if (!fehler) aufloesen({ code: 0, stdout });
      // Regulärer Exit ≠ 0 (z. B. 1 = keine Antwort): der Aufrufer entscheidet. Timeout und maxBuffer setzen
      // `killed` bzw. einen Text-Code und gelten als Fehler.
      else if (typeof fehler.code === "number" && !fehler.killed) aufloesen({ code: fehler.code, stdout });
      else ablehnen(fehler);
    });
  });

/** argv für eine Frage; `--` davor, damit eine Frage wie „-h“ kein Schalter des Routers wird. */
export function routerArgv(frage: string, mock: boolean, kette?: readonly KettenUc[]): string[] {
  return [...ROUTER_ARGV, ...(mock ? ["--mock"] : []), ...(kette ? ["--kette", kette.join(",")] : []), "--", frage];
}

/** Volle Kette, wie `plattform.router.STANDARD_KETTE`. */
export const STANDARD_KETTE = KETTE;
/** UCs ohne Sprachmodell (UC3 rechnet nur mit SQL); wie `OHNE_MODELL` in `plattform.router`. */
const OHNE_MODELL: ReadonlySet<KettenUc> = new Set(["uc3"]);

type Umgebung = Readonly<Record<string, string | undefined>>;

/**
 * Kette aus `UC4_KETTE` (Komma-Liste, Teilmenge von uc3,uc2,uc1, Reihenfolge der Standardkette). Leer: alle drei.
 * Ein ungültiger Wert fällt auf „nur uc3“ zurück: ohne Modell, also ohne Kosten (fail-closed).
 */
export function ketteAus(umgebung: Umgebung): readonly KettenUc[] {
  const roh = (umgebung.UC4_KETTE ?? "").trim();
  if (roh === "") return STANDARD_KETTE;
  const teile = roh.split(",").map((teil) => teil.trim());
  const gueltig =
    teile.length > 0 &&
    new Set(teile).size === teile.length &&
    teile.every((teil): teil is KettenUc => (STANDARD_KETTE as readonly string[]).includes(teil));
  if (!gueltig) {
    console.warn("[uc4/frage] UC4_KETTE ungültig, es fragt nur UC3");
    return ["uc3"];
  }
  return STANDARD_KETTE.filter((uc) => teile.includes(uc));
}

/** Ruft die Kette ein Sprachmodell auf? Nein, wenn sie nur aus UCs ohne Modell besteht (Online-Stufe A). */
export function ketteMitModell(kette: readonly KettenUc[]): boolean {
  return kette.some((uc) => !OHNE_MODELL.has(uc));
}

/**
 * Dürfen Fragen gestellt werden? Online-Demo lesend (`KIC_ONLINE_LESEND=1`) sperrt sie, außer `KIC_ONLINE_FRAGEN=1`
 * gibt Fragen frei (Stufe A); Freigaben und alles andere Schreibende bleiben dann gesperrt.
 */
export function fragenOffen(umgebung: Umgebung): boolean {
  return umgebung.KIC_ONLINE_LESEND !== "1" || umgebung.KIC_ONLINE_FRAGEN === "1";
}

export interface Uc4Einstellung {
  /** Stationen in Kettenreihenfolge; online in Stufe A nur ["uc3"]. */
  kette: readonly KettenUc[];
  fragenOffen: boolean;
  /** Ruft eine Frage ein Modell auf? Nein: Modellwahl ausblenden, sie wirkt dann nicht. */
  mitModell: boolean;
}

/** Für die Seite /uc4 (serverseitig): was die Route mit der aktuellen Umgebung tut. */
export function uc4Einstellung(umgebung: Umgebung = process.env): Uc4Einstellung {
  const kette = ketteAus(umgebung);
  return { kette, fragenOffen: fragenOffen(umgebung), mitModell: ketteMitModell(kette) };
}

/** Größter Request-Body; eine Frage mit 500 Zeichen braucht als JSON höchstens rund 3 KiB (UTF-8, Escapes). */
export const MAX_BODY_BYTES = 4 * 1024;
/** Router-Läufe, die ein Prozess gleichzeitig startet; jeder Lauf ist ein Python-Prozess. */
export const MAX_LAEUFE = 2;

const UNGUELTIG = "Die Anfrage braucht JSON mit dem Feld frage als Text.";
const NICHT_FREIGEGEBEN = "Dieses Modell ist hier nicht freigegeben.";

/**
 * Online (KIC_ONLINE=1, nur das Prod-Compose setzt es) darf die Wahl kein Geld kosten, das niemand freigegeben hat:
 * erlaubt sind dann nur Testbetrieb und die Anbieter aus UC4_MODELLWAHL (Komma-Liste). Lokal ist jede Wahl offen.
 * Review !72: sonst hebelte die Wahl LLM_PROVIDER=mock und „claude online aus“ des Compose aus.
 */
export function modellErlaubt(modell: Modellwahl, umgebung: Readonly<Record<string, string | undefined>>): boolean {
  if (umgebung.KIC_ONLINE !== "1" || modell === "mock") return true;
  const liste = (umgebung.UC4_MODELLWAHL ?? "").split(",").map((teil) => teil.trim());
  return liste.includes(modell);
}

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
function leseFrage(text: string): { frage: string; modell?: Modellwahl } | { meldung: string } {
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
  return eingabe.success
    ? { frage: eingabe.data.frage, modell: eingabe.data.modell }
    : { meldung: eingabe.error.issues[0]?.message ?? UNGUELTIG };
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
 * Subprozess: `KIC_ONLINE_LESEND=1` ohne `KIC_ONLINE_FRAGEN=1` → 403 (Online-Demo, zweite Sperre hinter dem Proxy), Ratenlimit je IP
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

  const kette = ketteAus(umgebung);
  const mitModell = ketteMitModell(kette);

  async function fuehreAus(frage: string, gewaehlt: Modellwahl | undefined): Promise<Response> {
    // Ohne Modell in der Kette (Stufe A, nur UC3) wirkt keine Modellwahl: auch „Testbetrieb“ darf die echte Zahl
    // nicht durch die Mock-Zahl ersetzen.
    const modell = mitModell ? gewaehlt : undefined;
    // „Testbetrieb“ nimmt die festen Antworten des Routers (wie die Online-Demo), sonst fehlten Vorlagen je Zweck.
    const argv = routerArgv(
      frage,
      umgebung.UC4_ADAPTER === "mock" || modell === "mock",
      kette === STANDARD_KETTE ? undefined : kette,
    );
    // Gewähltes Modell als LLM_PROVIDER nur für diesen Lauf; ohne Wahl gilt die Einstellung der App.
    const zusatz = modell ? { LLM_PROVIDER: modell } : undefined;
    let lauf: Lauf;
    try {
      lauf = await ausfuehren("uv", argv, { cwd: wurzel(), timeout: TIMEOUT_MS, maxBuffer: MAX_BUFFER, zusatz });
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
    if (!fragenOffen(umgebung)) return fehler(403, "Fragen sind in der Online-Demo noch gesperrt.");
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
    if (mitModell && eingabe.modell && !modellErlaubt(eingabe.modell, umgebung)) return fehler(400, NICHT_FREIGEGEBEN);

    if (offen >= maxLaeufe) return fehler(429, "Gerade laufen schon genug Fragen. Bitte gleich noch einmal fragen.");
    offen += 1;
    try {
      return await fuehreAus(eingabe.frage, eingabe.modell);
    } finally {
      offen -= 1;
    }
  };
}

/** Prozessweiter Handler für die Route: ein Ratenlimit je IP, höchstens `MAX_LAEUFE` Router-Läufe gleichzeitig. */
export const frageAntwort = erstelleFrageAntwort();
