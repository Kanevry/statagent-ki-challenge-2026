import { type Ausfuehren, standardAusfuehren, uc3 } from "./cli";
import { istMonat } from "./monat";

// Auftrags-Weg der Vorführ-Instanz (nur mit KIC_VORFUEHRUNG=1, nie in der öffentlichen Demo): Ein Agentenlauf dauert
// Minuten, über einen Handy-Hotspot reißt so eine offene Anfrage ab. Deshalb startet POST den Lauf im Server-Prozess und
// antwortet sofort; der Browser fragt den Stand per GET ab und findet ihn auch nach einem Neuladen wieder.
// Gerechnet wird nur über die CLI (`uc3 agent`, `uc3 lauf`), web/ ruft nie ein Modell.

export const MAX_BODY_BYTES = 4 * 1024;
export const MAX_ANWEISUNG = 1000;
/** `uc3 agent` rechnet die Probe mit: Ziel unter 4 Minuten (!150), Grenze mit Luft. */
export const AGENT_TIMEOUT_MS = 8 * 60_000;
export const LAUF_TIMEOUT_MS = 20 * 60_000;
const REGELSATZ = /^v[1-9][0-9]{0,2}$/;
const MAX_MELDUNG = 400;

export type AuftragEingabe = { art: "agent"; anweisung: string; probe?: string } | { art: "lauf"; lieferung: string; regelsatz: string };

export type AuftragStand = {
  id: number;
  art: AuftragEingabe["art"];
  /** Der getippte Satz bzw. der Monat. */
  text: string;
  gestartetAm: string;
  endeAm: string | null;
  zustand: "laeuft" | "vorschlag" | "rueckfrage" | "abgelehnt" | "gerechnet" | "fehler";
  /** Wirkung, Rückfrage, Ablehnungsgrund oder Fehler in einem Satz. */
  satz: string | null;
  vorschlagId: number | null;
  regelsatz: string | null;
  gezaehlt: number | null;
  ergebnisHash: string | null;
};

/** Offen nur in der Vorführ-Instanz; die lesende Online-Demo gewinnt immer. */
export function vorfuehrungOffen(umgebung: Readonly<Record<string, string | undefined>> = process.env): boolean {
  return umgebung.KIC_VORFUEHRUNG === "1" && umgebung.KIC_ONLINE_LESEND !== "1";
}

/**
 * Monate, die `uc3 lauf` mit diesem Regelsatz annimmt: Er rechnet in zeitlicher Reihenfolge, also alle schon gerechneten
 * und der erste fehlende. Ein neuer Regelsatz beginnt deshalb beim ersten Monat. Neueste zuerst.
 */
export function rechenbareMonate(alle: readonly string[], gerechnet: ReadonlySet<string>): string[] {
  const aufsteigend = [...alle].sort();
  const luecke = aufsteigend.findIndex((m) => !gerechnet.has(m));
  return (luecke < 0 ? aufsteigend : aufsteigend.slice(0, luecke + 1)).reverse();
}

function json(status: number, daten: unknown): Response {
  return Response.json(daten, { status, headers: { "cache-control": "no-store" } });
}

function fehler(status: number, meldung: string): Response {
  return json(status, { fehler: meldung });
}

/** Argumente nach `uc3`; `--` hält einen Satz, der mit einem Strich beginnt, von den Optionen fern. */
export function auftragArgv(eingabe: AuftragEingabe): string[] {
  return eingabe.art === "agent"
    ? ["agent", "--json", ...(eingabe.probe ? ["--probe", eingabe.probe] : []), "--", eingabe.anweisung]
    : ["lauf", "--lieferung", eingabe.lieferung, "--regelsatz", eingabe.regelsatz, "--json"];
}

/** Liest die Eingabe oder nennt in einem Satz, was fehlt. */
export function leseEingabe(text: string): AuftragEingabe | { meldung: string } {
  let daten: unknown;
  try {
    daten = JSON.parse(text);
  } catch {
    return { meldung: "Die Anfrage braucht JSON." };
  }
  if (typeof daten !== "object" || daten === null) return { meldung: "Die Anfrage braucht JSON." };
  const { art, anweisung, lieferung, regelsatz, probe } = daten as Record<string, unknown>;
  if (art === "agent") {
    const satz = typeof anweisung === "string" ? anweisung.trim() : "";
    if (!satz) return { meldung: "Bitte schreiben Sie den Auftrag in einem Satz." };
    if (satz.length > MAX_ANWEISUNG) return { meldung: `Der Auftrag ist länger als ${MAX_ANWEISUNG} Zeichen.` };
    // Ohne Probemonat nimmt `uc3 agent` den jüngsten gerechneten Monat
    if (probe === undefined || probe === "") return { art, anweisung: satz };
    if (typeof probe !== "string" || !istMonat(probe)) return { meldung: "Bitte wählen Sie einen Monat für die Probe." };
    return { art, anweisung: satz, probe };
  }
  if (art === "lauf") {
    if (typeof lieferung !== "string" || !istMonat(lieferung)) return { meldung: "Bitte wählen Sie einen Monat." };
    if (typeof regelsatz !== "string" || !REGELSATZ.test(regelsatz)) return { meldung: "Unbekannter Regelsatz." };
    return { art, lieferung, regelsatz };
  }
  return { meldung: "Unbekannte Art des Auftrags." };
}

function alsObjekt(text: string): Record<string, unknown> | null {
  try {
    const wert: unknown = JSON.parse(text);
    return typeof wert === "object" && wert !== null ? (wert as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function text(wert: unknown): string | null {
  return typeof wert === "string" && wert.trim() ? wert.trim() : null;
}

function letzteZeile(stderr: string): string {
  const zeile = stderr.trim().split("\n").at(-1)?.trim() ?? "";
  return zeile.slice(0, MAX_MELDUNG);
}

type Ergebnis = Pick<AuftragStand, "zustand" | "satz" | "vorschlagId" | "gezaehlt" | "ergebnisHash">;
const LEER: Ergebnis = { zustand: "fehler", satz: null, vorschlagId: null, gezaehlt: null, ergebnisHash: null };

/** Was aus dem CLI-Aufruf wurde. Exit 1 mit JSON ist eine begründete Ablehnung, ohne JSON ein Fehler. */
export function ergebnisAus(art: AuftragEingabe["art"], code: number, stdout: string, stderr: string): Ergebnis {
  const daten = alsObjekt(stdout);
  if (art === "lauf") {
    if (code === 0 && daten) {
      return {
        ...LEER,
        zustand: "gerechnet",
        gezaehlt: typeof daten.gezaehlt === "number" ? daten.gezaehlt : null,
        ergebnisHash: text(daten.ergebnis_hash),
        satz: text(daten.meldung),
      };
    }
    return { ...LEER, satz: letzteZeile(stderr) || "Der Lauf ist abgebrochen." };
  }
  if (daten) {
    if (typeof daten.vorschlag_id === "number") {
      return { ...LEER, zustand: "vorschlag", vorschlagId: daten.vorschlag_id, satz: text(daten.wirkung) };
    }
    const rueckfrage = text(daten.rueckfrage);
    if (rueckfrage) return { ...LEER, zustand: "rueckfrage", satz: rueckfrage };
    const abgelehnt = text(daten.abgelehnt);
    if (abgelehnt) return { ...LEER, zustand: "abgelehnt", satz: abgelehnt };
  }
  return { ...LEER, satz: letzteZeile(stderr) || "Der Agent hat keinen Vorschlag geliefert." };
}

class ZuGross extends Error {}

async function leseBody(anfrage: Request, grenze: number): Promise<string> {
  const leser = anfrage.body?.getReader();
  if (!leser) return "";
  const teile: Uint8Array[] = [];
  let laenge = 0;
  for (;;) {
    const { done, value } = await leser.read();
    if (done) break;
    laenge += value.byteLength;
    if (laenge > grenze) {
      await leser.cancel();
      throw new ZuGross();
    }
    teile.push(value);
  }
  return Buffer.concat(teile).toString("utf8");
}

export type AuftragOptionen = {
  umgebung?: Readonly<Record<string, string | undefined>>;
  ausfuehren?: Ausfuehren;
  jetzt?: () => Date;
};

/** POST und GET der Route. Der Stand liegt im Prozess: ein Vortragender, ein Lauf zur Zeit, Neustart heißt Ausgangsstand. */
export function erstelleAuftragWeg({
  umgebung = process.env,
  ausfuehren = standardAusfuehren,
  jetzt = () => new Date(),
}: AuftragOptionen = {}) {
  let aktuell: AuftragStand | null = null;
  let naechsteId = 1;
  const gesperrt = () => fehler(403, "Das geht nur in der Vorführung.");

  async function rechne(stand: AuftragStand, eingabe: AuftragEingabe): Promise<void> {
    const timeout = eingabe.art === "agent" ? AGENT_TIMEOUT_MS : LAUF_TIMEOUT_MS;
    let ergebnis: Ergebnis;
    try {
      const lauf = await uc3(auftragArgv(eingabe), { ausfuehren, timeout });
      ergebnis = ergebnisAus(eingabe.art, lauf.code, lauf.stdout, lauf.stderr);
    } catch {
      ergebnis = { ...LEER, satz: "Das Programm hat nicht rechtzeitig geantwortet." };
    }
    if (aktuell?.id === stand.id) aktuell = { ...stand, ...ergebnis, endeAm: jetzt().toISOString() };
  }

  return {
    async starte(anfrage: Request): Promise<Response> {
      if (!vorfuehrungOffen(umgebung)) return gesperrt();
      let roh: string;
      try {
        roh = await leseBody(anfrage, MAX_BODY_BYTES);
      } catch (grund) {
        if (grund instanceof ZuGross) return fehler(413, "Der Auftrag ist zu lang.");
        return fehler(400, "Die Anfrage braucht JSON.");
      }
      const eingabe = leseEingabe(roh);
      if ("meldung" in eingabe) return fehler(400, eingabe.meldung);
      if (aktuell?.zustand === "laeuft") return json(409, { fehler: "Es läuft schon ein Auftrag.", stand: aktuell });
      const stand: AuftragStand = {
        id: naechsteId++,
        art: eingabe.art,
        text: eingabe.art === "agent" ? eingabe.anweisung : eingabe.lieferung,
        gestartetAm: jetzt().toISOString(),
        endeAm: null,
        zustand: "laeuft",
        satz: null,
        vorschlagId: null,
        regelsatz: eingabe.art === "lauf" ? eingabe.regelsatz : null,
        gezaehlt: null,
        ergebnisHash: null,
      };
      aktuell = stand;
      // bewusst ohne await: der Lauf gehört dem Server, nicht dieser Anfrage
      void rechne(stand, eingabe);
      return json(202, { stand });
    },
    stand(): Response {
      if (!vorfuehrungOffen(umgebung)) return gesperrt();
      return json(200, { stand: aktuell });
    },
  };
}

/** Prozessweiter Weg für die Route. */
export const auftragWeg = erstelleAuftragWeg();
