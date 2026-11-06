import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { findeRepoWurzel } from "./modell";
import { erstelleRatenlimit, grenzeAus, type PruefeRatenlimit } from "./ratenlimit";
import {
  BUDGET_MELDUNG,
  ergebnisSchema,
  frageSchema,
  KETTE,
  STROM_TYP,
  stromEreignisSchema,
  type KettenUc,
  MODELLWAHL,
  type Modellwahl,
  type StromEreignis,
} from "./uc4-ergebnis";

export { BUDGET_MELDUNG };

// POST /api/uc4/frage (#98): reicht die Frage an `plattform.router` weiter, als Subprozess mit argv (keine Shell).
// web/ ruft nie ein Modell direkt; welche Adapter antworten, entscheidet der Router. `UC4_ADAPTER=mock` hängt
// `--mock` an (CI, Playwright, Online-Demo ohne Modellschlüssel). Exit 1 heißt „keine Antwort“ (alle fehlend)
// und ist ein gültiges Ergebnis, solange stdout den Vertrag erfüllt. Vor dem Subprozess greift das Ratenlimit je IP
// (#100); Exit 3 heißt „Tagesbudget von plattform.llm verbraucht“ und wird wie das Ratenlimit ein 429.

export const ROUTER_ARGV = ["run", "--frozen", "python", "-m", "plattform.router", "frage", "--json"] as const;
// 180 s ist die Obergrenze, nicht die übliche Dauer. Gemessen am 05.11. mit Azure: zuerst UC2 98 s (alter Adapter,
// vier Akteure, zwei Runden; mit 60 s brach die Route ab und die Seite zeigte gar keine Antwort), mit dem heutigen
// Adapter (drei Akteure parallel, eine Runde) die ganze Kette 5 bis 7 s: UC3 1 s, UC2 3 bis 5 s, UC1 1 s.
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
  optionen: {
    cwd: string;
    timeout: number;
    maxBuffer: number;
    zusatz?: Readonly<Record<string, string>>;
    /** Abbruch des Clients: beendet die Prozessgruppe sofort statt erst am Timeout (#150). */
    signal?: AbortSignal;
  },
) => Promise<Lauf>;

/** Nach SIGTERM an die Prozessgruppe so lange warten, dann SIGKILL. */
export const NACHFRIST_MS = 2_000;

/**
 * Startet den Router in einer eigenen Prozessgruppe (detached). `uv run` startet Python als Kind; ein Signal nur an
 * uv ließe Python als Waise weiterrechnen und stdout offen halten, dann käme „close“ nie und der Lauf-Slot bliebe
 * belegt (Review !96). `beenden` schickt SIGTERM an die Gruppe und nach `NACHFRIST_MS` SIGKILL.
 */
function starteGruppe(befehl: string, argv: readonly string[], cwd: string, zusatz: Readonly<Record<string, string>>) {
  // stderr verworfen: es kann Pfade, Umgebungswerte oder die Frage enthalten; nach außen gehen nur Exit-Codes.
  const kind = spawn(befehl, [...argv], {
    cwd,
    env: { ...process.env, ...zusatz },
    stdio: ["ignore", "pipe", "ignore"],
    detached: true,
  });
  let beendet = false;
  let abgebrochen = false;
  kind.once("close", () => (beendet = true));
  const gruppe = (signal: NodeJS.Signals) => {
    if (kind.pid === undefined) return;
    try {
      process.kill(-kind.pid, signal);
    } catch {
      // Gruppe schon leer (ESRCH): nichts mehr zu beenden
    }
  };
  const beenden = () => {
    // Nach „close“ ist die Gruppe leer; ein Signal an eine später neu vergebene Gruppen-ID wäre falsch.
    if (abgebrochen || beendet) return;
    abgebrochen = true;
    gruppe("SIGTERM");
    // Ein Enkel, der SIGTERM ignoriert, bekommt SIGKILL, auch wenn uv schon weg ist.
    setTimeout(() => gruppe("SIGKILL"), NACHFRIST_MS).unref();
  };
  return { kind, beenden, abgebrochen: () => abgebrochen };
}

export const standardAusfuehren: Ausfuehren = (befehl, argv, { cwd, timeout, maxBuffer, zusatz = {}, signal }) =>
  new Promise((aufloesen, ablehnen) => {
    const { kind, beenden } = starteGruppe(befehl, argv, cwd, zusatz);
    const stuecke: Buffer[] = [];
    let groesse = 0;
    let grund: Error | null = null;
    const abbruch = (name: string) => {
      if (grund) return;
      grund = Object.assign(new Error(name), { name });
      beenden();
    };
    kind.stdout.on("data", (stueck: Buffer) => {
      groesse += stueck.length;
      if (groesse > maxBuffer) abbruch("MaxBufferError");
      else stuecke.push(stueck);
    });
    const uhr = setTimeout(() => abbruch("TimeoutError"), timeout);
    const beiAbbruch = () => abbruch("AbortError");
    if (signal?.aborted) beiAbbruch();
    else signal?.addEventListener("abort", beiAbbruch, { once: true });
    kind.once("error", (fehler) => {
      clearTimeout(uhr);
      signal?.removeEventListener("abort", beiAbbruch);
      ablehnen(fehler);
    });
    kind.once("close", (code) => {
      clearTimeout(uhr);
      signal?.removeEventListener("abort", beiAbbruch);
      // Regulärer Exit ≠ 0 (z. B. 1 = keine Antwort): der Aufrufer entscheidet. Timeout, maxBuffer und ein Ende
      // durch Signal gelten als Fehler.
      if (grund) ablehnen(grund);
      else if (code === null) ablehnen(Object.assign(new Error("Signal"), { name: "SignalError" }));
      else aufloesen({ code, stdout: Buffer.concat(stuecke).toString("utf8") });
    });
  });

/** Ein laufender Router im Strom-Modus: stdout Zeile für Zeile, Exit-Code am Ende, Abbruch von außen. */
export interface StromLauf {
  zeilen: AsyncIterable<string>;
  /** Exit-Code; null nach Timeout, Abbruch oder Startfehler. */
  ende: Promise<number | null>;
  abbrechen: () => void;
}

export type StromStarten = (
  befehl: string,
  argv: readonly string[],
  optionen: { cwd: string; timeout: number; zusatz?: Readonly<Record<string, string>> },
) => StromLauf;

export const standardStromStarten: StromStarten = (befehl, argv, { cwd, timeout, zusatz = {} }) => {
  const { kind, beenden, abgebrochen } = starteGruppe(befehl, argv, cwd, zusatz);
  const uhr = setTimeout(beenden, timeout);
  const ende = new Promise<number | null>((aufloesen) => {
    kind.once("error", () => aufloesen(null));
    kind.once("close", (code) => aufloesen(abgebrochen() ? null : code));
  }).finally(() => clearTimeout(uhr));
  return { zeilen: createInterface({ input: kind.stdout, crlfDelay: Infinity }), ende, abbrechen: beenden };
};

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
 * Kette aus `UC4_KETTE` (Komma-Liste, Teilmenge von uc3,uc2,uc1, Reihenfolge der Standardkette). Leer: lokal alle
 * drei, online (`KIC_ONLINE=1`) nur uc3. Ein ungültiger Wert fällt auf „nur uc3“ zurück: ohne Modell, also ohne
 * Kosten (fail-closed, Review !94).
 */
export function ketteAus(umgebung: Umgebung): readonly KettenUc[] {
  const roh = (umgebung.UC4_KETTE ?? "").trim();
  if (roh === "") return umgebung.KIC_ONLINE === "1" ? ["uc3"] : STANDARD_KETTE;
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
  /** Was man wählen darf: Online nicht freigegebene Anbieter stehen gar nicht erst zur Wahl (sonst Fehler 400). */
  modellwahl: readonly Modellwahl[];
}

/** Für die Seite /uc4 (serverseitig): was die Route mit der aktuellen Umgebung tut. */
export function uc4Einstellung(umgebung: Umgebung = process.env): Uc4Einstellung {
  const kette = ketteAus(umgebung);
  return {
    kette,
    fragenOffen: fragenOffen(umgebung),
    mitModell: ketteMitModell(kette),
    modellwahl: MODELLWAHL.filter((modell) => modellErlaubt(modell, umgebung)),
  };
}

/** Deckel der Probierseite /uc2/frage: rund 100 Modellaufrufe am Tag, eine Frage kostet in der Regel 4 bis 5. */
export const STATION_FRAGEN_PRO_TAG = 20;
export const STATION_PRO_MINUTE = 5;
export const STATION_LAEUFE = 1;
export const DECKEL_MELDUNG = "Für heute sind die Probierfragen aufgebraucht. Morgen geht es wieder. Die aufgezeichnete Verhandlung bleibt offen.";

/** Station aus der URL (`?station=uc2`), damit das richtige Limit greift, bevor der Body gelesen wird. */
function stationAus(anfrage: Request): KettenUc | "ungueltig" | undefined {
  const wert = new URL(anfrage.url).searchParams.get("station");
  if (wert === null) return undefined;
  return wert === "uc2" ? wert : "ungueltig";
}

/** Für /uc2 und /uc2/frage: Nimmt die Route gerade Fragen an diese eine Station an? */
export function stationOffen(station: KettenUc, umgebung: Umgebung = process.env): boolean {
  return fragenOffen(umgebung) && ketteAus(umgebung).includes(station);
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
  /** Startet den Router im Strom-Modus (`--strom`); Standard: Subprozess mit zeilenweisem stdout. */
  stromStarten?: StromStarten;
  umgebung?: Readonly<Record<string, string | undefined>>;
  wurzel?: () => string;
  maxLaeufe?: number;
  /** Ratenlimit je Client-IP (#100); Standard: eigenes Limit dieses Handlers mit `RATENLIMIT_PRO_MINUTE`. */
  ratenlimit?: PruefeRatenlimit;
  /** Eigenes Limit der Probierseite, getrennt von `ratenlimit`. */
  stationRatenlimit?: PruefeRatenlimit;
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
  stromStarten = standardStromStarten,
  umgebung = process.env,
  wurzel = findeRepoWurzel,
  maxLaeufe = MAX_LAEUFE,
  ratenlimit = erstelleRatenlimit({ proMinute: grenzeAus(umgebung) }),
  stationRatenlimit = erstelleRatenlimit({ proMinute: STATION_PRO_MINUTE }),
  jetzt = Date.now,
}: FrageOptionen = {}): (anfrage: Request) => Promise<Response> {
  let offen = 0;
  // Eigener Deckel der Probierseite (/uc2/frage), getrennt von Lauf-Zählung und Limit der Kette. Im Speicher, wie das
  // Ratenlimit: Je Container läuft ein Next-Prozess. Ein Neustart setzt ihn zurück; das Tagesbudget von plattform.llm bleibt.
  let stationLaeuft = 0;
  let deckelTag = "";
  let deckelFragen = 0;

  const kette = ketteAus(umgebung);
  const mitModell = ketteMitModell(kette);

  function laufParameter(frage: string, gewaehlt: Modellwahl | undefined, station?: KettenUc) {
    // Ohne Modell in der Kette (Stufe A, nur UC3) wirkt keine Modellwahl: auch „Testbetrieb“ darf die echte Zahl
    // nicht durch die Mock-Zahl ersetzen.
    const modell = mitModell ? gewaehlt : undefined;
    // „Testbetrieb“ nimmt die festen Antworten des Routers (wie die Online-Demo), sonst fehlten Vorlagen je Zweck.
    const argv = routerArgv(
      frage,
      umgebung.UC4_ADAPTER === "mock" || modell === "mock",
      station ? [station] : kette === STANDARD_KETTE ? undefined : kette,
    );
    // Gewähltes Modell als LLM_PROVIDER nur für diesen Lauf; ohne Wahl gilt die Einstellung der App.
    const zusatz = modell ? { LLM_PROVIDER: modell } : undefined;
    return { modell, argv, zusatz };
  }

  function budgetAntwort(): Response {
    console.warn("[uc4/frage] Tagesbudget erschöpft");
    return Response.json(
      { fehler: BUDGET_MELDUNG },
      { status: 429, headers: { "retry-after": String(bisMitternachtUtc(jetzt())), "cache-control": "no-store" } },
    );
  }

  /**
   * Strom (`Accept: application/x-ndjson`): Die erste Zeile entscheidet den Status. Budget erschöpft → 429, keine
   * oder kaputte Zeile → 502, sonst 200 und jede weitere Zeile geprüft, sobald sie kommt. Eine Zeile außerhalb des
   * Vertrags oder ein Abbruch ohne „ende“ endet mit einer „fehler“-Zeile. `freigeben` gibt den Lauf-Slot genau
   * einmal frei: am Ende des Stroms, bei Abbruch durch den Client oder vor einer Fehlerantwort.
   */
  async function fuehreStromAus(
    frage: string,
    gewaehlt: Modellwahl | undefined,
    freigeben: () => void,
    signal: AbortSignal,
  ): Promise<Response> {
    const { modell, argv, zusatz } = laufParameter(frage, gewaehlt);
    const startArgv = [...argv.slice(0, ROUTER_ARGV.length), "--strom", ...argv.slice(ROUTER_ARGV.length)];
    let lauf: StromLauf;
    try {
      lauf = stromStarten("uv", startArgv, { cwd: wurzel(), timeout: TIMEOUT_MS, zusatz });
    } catch (grund) {
      freigeben();
      console.warn(`[uc4/frage] Router nicht startbar (${(grund as Error).name ?? "Fehler"})`);
      return fehler(502, "Die Kette hat nicht geantwortet. Bitte später noch einmal fragen.");
    }
    // Bricht der Client ab, endet der Router sofort, auch schon vor der ersten Zeile (Review !96).
    const beiAbbruch = () => lauf.abbrechen();
    if (signal.aborted) beiAbbruch();
    else signal.addEventListener("abort", beiAbbruch, { once: true });
    const loesen = () => signal.removeEventListener("abort", beiAbbruch);
    const leser = lauf.zeilen[Symbol.asyncIterator]();
    const naechstes = async (): Promise<StromEreignis | "kaputt" | null> => {
      for (;;) {
        const { done, value } = await leser.next();
        if (done) return null;
        if (value.trim() === "") continue;
        try {
          const roh: unknown = JSON.parse(value);
          if (typeof roh === "object" && roh !== null && (roh as { fehler?: unknown }).fehler === "budget_erschoepft") {
            return { art: "fehler", fehler: BUDGET_MELDUNG };
          }
          const geprueft = stromEreignisSchema.safeParse(roh);
          return geprueft.success ? geprueft.data : "kaputt";
        } catch {
          return "kaputt";
        }
      }
    };

    const erstes = await naechstes();
    if (erstes === null || erstes === "kaputt" || erstes.art !== "start") {
      // Nur eine kaputte Zeile bricht ab; sonst endet der Router gerade selbst (Budget, Startfehler).
      if (erstes === "kaputt") lauf.abbrechen();
      const code = await lauf.ende;
      loesen();
      freigeben();
      if (erstes !== null && erstes !== "kaputt" && erstes.art === "fehler" && erstes.fehler === BUDGET_MELDUNG) {
        return budgetAntwort();
      }
      console.warn(`[uc4/frage] Strom ohne gültigen Start (Exit ${code ?? "abgebrochen"})`);
      return fehler(502, "Die Kette hat in einem unerwarteten Format geantwortet.");
    }

    const kodierer = new TextEncoder();
    const zeile = (ereignis: StromEreignis) => kodierer.encode(`${JSON.stringify(ereignis)}\n`);
    let fertig = false;
    let endeGesehen = false;
    const schliessen = () => {
      if (fertig) return;
      fertig = true;
      loesen();
      freigeben();
    };
    const strom = new ReadableStream<Uint8Array>({
      start(steuerung) {
        steuerung.enqueue(zeile({ ...erstes, modell: modell ?? null }));
      },
      async pull(steuerung) {
        let ereignis: Awaited<ReturnType<typeof naechstes>>;
        try {
          ereignis = await naechstes();
        } catch (grund) {
          // Lesefehler der Pipe: Router beenden, Seite bekommt einen Abschluss, Slot wird frei (Review !96).
          console.warn(`[uc4/frage] Strom nicht lesbar (${(grund as Error).name ?? "Fehler"})`);
          lauf.abbrechen();
          steuerung.enqueue(zeile({ art: "fehler", fehler: "Die Kette ist mit einem Fehler abgebrochen." }));
          steuerung.close();
          schliessen();
          return;
        }
        if (ereignis === "kaputt") {
          console.warn("[uc4/frage] Strom-Zeile verletzt den Vertrag");
          lauf.abbrechen();
          steuerung.enqueue(zeile({ art: "fehler", fehler: "Die Kette hat in einem unerwarteten Format geantwortet." }));
          steuerung.close();
          schliessen();
          return;
        }
        if (ereignis === null) {
          const code = await lauf.ende;
          // Ohne „ende“-Zeile bliebe die Seite auf „läuft“, auch bei Exit 0 oder 1 (Review !96). Nach „ende“ zählt
          // trotzdem der Exit-Code: ein Absturz beim Aufräumen oder ein Signal ist ein Fehler (#150).
          if (!endeGesehen || (code !== 0 && code !== 1)) {
            console.warn(`[uc4/frage] Strom endet ohne Abschluss (Exit ${code ?? "abgebrochen"})`);
            const meldung =
              code === null ? "Die Kette hat nicht rechtzeitig geantwortet." : "Die Kette ist mit einem Fehler abgebrochen.";
            steuerung.enqueue(zeile({ art: "fehler", fehler: meldung }));
          }
          steuerung.close();
          schliessen();
          return;
        }
        if (ereignis.art === "ende") endeGesehen = true;
        steuerung.enqueue(zeile(ereignis));
      },
      cancel() {
        lauf.abbrechen();
        schliessen();
      },
    });
    return new Response(strom, {
      headers: { "content-type": `${STROM_TYP}; charset=utf-8`, "cache-control": "no-store", "x-accel-buffering": "no" },
    });
  }

  async function fuehreAus(
    frage: string,
    gewaehlt: Modellwahl | undefined,
    signal: AbortSignal,
    station?: KettenUc,
  ): Promise<Response> {
    const { argv, zusatz } = laufParameter(frage, gewaehlt, station);
    let lauf: Lauf;
    try {
      lauf = await ausfuehren("uv", argv, { cwd: wurzel(), timeout: TIMEOUT_MS, maxBuffer: MAX_BUFFER, zusatz, signal });
    } catch (grund) {
      // Nur die Art des Fehlers loggen: stderr und Meldung können Pfade, Umgebungswerte oder die Frage enthalten.
      console.warn(`[uc4/frage] Router nicht erreichbar (${(grund as Error).name ?? "Fehler"})`);
      return fehler(502, "Die Kette hat nicht geantwortet. Bitte später noch einmal fragen.");
    }
    if (lauf.code === EXIT_BUDGET && budgetErschoepft(lauf.stdout)) return budgetAntwort();
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

  async function stationFrage(
    frage: string,
    gewaehlt: Modellwahl | undefined,
    station: KettenUc,
    signal: AbortSignal,
  ): Promise<Response> {
    const tag = new Date(jetzt()).toISOString().slice(0, 10);
    if (deckelTag !== tag) {
      deckelTag = tag;
      deckelFragen = 0;
    }
    if (deckelFragen >= STATION_FRAGEN_PRO_TAG) {
      return Response.json(
        { fehler: DECKEL_MELDUNG },
        { status: 429, headers: { "retry-after": String(bisMitternachtUtc(jetzt())), "cache-control": "no-store" } },
      );
    }
    if (stationLaeuft >= STATION_LAEUFE) return fehler(429, "Gerade läuft schon eine Frage. Bitte gleich noch einmal.");
    deckelFragen += 1;
    stationLaeuft += 1;
    try {
      const antwort = await fuehreAus(frage, gewaehlt, signal, station);
      // Eine Absage ohne Modell kostet nichts und zählt nicht; ein Fehler zählt, er kann schon Aufrufe gekostet haben.
      if (antwort.ok) {
        const daten = ergebnisSchema.safeParse(await antwort.clone().json());
        if (daten.success && daten.data.antworten.every((a) => a.modell === null)) deckelFragen -= 1;
      }
      return antwort;
    } finally {
      stationLaeuft -= 1;
    }
  }

  return async function frageAntwort(anfrage: Request): Promise<Response> {
    if (!fragenOffen(umgebung)) return fehler(403, "Fragen sind in der Online-Demo noch gesperrt.");
    const station = stationAus(anfrage);
    if (station === "ungueltig") return fehler(400, "Diese Station gibt es hier nicht.");
    // Eine einzelne Station gibt es nur, wenn sie in der eingestellten Kette steht: Mit UC4_KETTE=uc3 öffnet sie kein Modell.
    if (station && !kette.includes(station)) return fehler(403, "Fragen sind in der Online-Demo noch gesperrt.");
    // Die Probierseite hat ihr eigenes Limit: Sie darf das Limit von /uc4 nicht verbrauchen, und umgekehrt.
    const gedrosselt = (station ? stationRatenlimit : ratenlimit)(anfrage, jetzt());
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
    if (station) return stationFrage(eingabe.frage, eingabe.modell, station, anfrage.signal);

    if (offen >= maxLaeufe) return fehler(429, "Gerade laufen schon genug Fragen. Bitte gleich noch einmal fragen.");
    offen += 1;
    if ((anfrage.headers.get("accept") ?? "").includes(STROM_TYP)) {
      let frei = false;
      const freigeben = () => {
        if (!frei) {
          frei = true;
          offen -= 1;
        }
      };
      try {
        return await fuehreStromAus(eingabe.frage, eingabe.modell, freigeben, anfrage.signal);
      } catch (grund) {
        freigeben();
        throw grund;
      }
    }
    try {
      return await fuehreAus(eingabe.frage, eingabe.modell, anfrage.signal);
    } finally {
      offen -= 1;
    }
  };
}

/** Prozessweiter Handler für die Route: ein Ratenlimit je IP, höchstens `MAX_LAEUFE` Router-Läufe gleichzeitig. */
export const frageAntwort = erstelleFrageAntwort();
