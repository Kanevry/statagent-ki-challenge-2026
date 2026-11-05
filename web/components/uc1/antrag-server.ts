import { readFile, realpath } from "node:fs/promises";
import path from "node:path";
import { abbildenAntrag, antragEingabeSchema, ART_MUSTER, UUID_MUSTER, type AntragEingabe } from "./antrag";
import {
  cliWurzel,
  fehler,
  leseBody,
  MAX_BUFFER,
  MAX_LAEUFE,
  NICHT_ERREICHBAR,
  standardAusfuehren,
  TIMEOUT_MS,
  ZuGross,
  type Ausfuehren,
  type Lauf,
} from "./lotse";

// POST /api/uc1/antrag und GET /api/uc1/antrag/pdf (#35). Gleiches Muster wie /api/uc1/frage: Subprozess mit argv
// (keine Shell), feste deutsche Sätze, Online-Demo und Ausfall mit `replay: true`. Nur für den Server.

/** `art` und `sitzung` sind geprüft (Regex), bevor sie hier landen; `--` braucht es deshalb nicht. */
export function antragArgv({ art, sitzung }: AntragEingabe): string[] {
  return ["run", "--frozen", "--package", "uc1", "lotse", "antrag", art, "--sitzung", sitzung, "--json"];
}

/** Zwei Felder mit kurzen Werten passen weit unter 1 KiB. */
export const MAX_ANTRAG_BODY_BYTES = 1024;
const UNGUELTIG = "Die Anfrage braucht JSON mit den Feldern art und sitzung.";
const ONLINE = "In der Online-Demo bereitet der Lotse keinen Antrag live vor.";

type Umgebung = Readonly<Record<string, string | undefined>>;

export interface AntragOptionen {
  ausfuehren?: Ausfuehren;
  umgebung?: Umgebung;
  wurzel?: () => string;
  maxLaeufe?: number;
}

function leseEingabe(text: string): AntragEingabe | { meldung: string } {
  let roh: unknown;
  try {
    roh = JSON.parse(text);
  } catch {
    return { meldung: UNGUELTIG };
  }
  if (typeof roh !== "object" || roh === null) return { meldung: UNGUELTIG };
  const eingabe = antragEingabeSchema.safeParse(roh);
  return eingabe.success ? eingabe.data : { meldung: eingabe.error.issues[0]?.message ?? UNGUELTIG };
}

/**
 * Handler für POST /api/uc1/antrag. `KIC_ONLINE_LESEND=1` → 403, Body über 1 KiB → 413, ungültige Art oder Sitzung
 * → 400, schon `maxLaeufe` offen → 429; Exit ≠ 0, Timeout oder Vertragsbruch → 503. Die Antwort ist die Web-Form
 * aus antrag.ts: ohne PDF-Pfad, Formulardatei und Hash.
 */
export function erstelleAntragAntwort({
  ausfuehren = standardAusfuehren,
  umgebung = process.env,
  wurzel = () => cliWurzel(umgebung),
  maxLaeufe = MAX_LAEUFE,
}: AntragOptionen = {}): (anfrage: Request) => Promise<Response> {
  let offen = 0;

  async function fuehreAus(eingabe: AntragEingabe): Promise<Response> {
    let lauf: Lauf;
    try {
      lauf = await ausfuehren("uv", antragArgv(eingabe), { cwd: wurzel(), timeout: TIMEOUT_MS, maxBuffer: MAX_BUFFER });
    } catch (grund) {
      console.warn(`[uc1/antrag] Lotse nicht erreichbar (${(grund as Error).name ?? "Fehler"})`);
      return fehler(503, NICHT_ERREICHBAR, true);
    }
    if (lauf.code !== 0) {
      console.warn(`[uc1/antrag] Lotse beendet mit Exit ${lauf.code}`);
      return fehler(503, NICHT_ERREICHBAR, true);
    }
    let antrag;
    try {
      antrag = abbildenAntrag(JSON.parse(lauf.stdout));
    } catch {
      antrag = null;
    }
    if (!antrag) {
      console.warn("[uc1/antrag] Lotse-Ausgabe verletzt den Vertrag");
      return fehler(503, NICHT_ERREICHBAR, true);
    }
    return Response.json(antrag, { headers: { "cache-control": "no-store" } });
  }

  return async function antragAntwort(anfrage: Request): Promise<Response> {
    if (umgebung.KIC_ONLINE_LESEND === "1") return fehler(403, ONLINE, true);
    let body: string;
    try {
      body = await leseBody(anfrage, MAX_ANTRAG_BODY_BYTES);
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

/** Ordner, in den der Kern die Entwürfe schreibt. */
export function antragOrdner(wurzel: string): string {
  return path.resolve(wurzel, "uc1", "laufzeit", "antraege");
}

/**
 * Pfad des Entwurfs `<wurzel>/uc1/laufzeit/antraege/<art>-<sitzung>-entwurf.pdf` oder `null`. Doppelt gesichert:
 * erst die Muster für Art und Sitzung, dann die Prüfung, dass der gebaute Pfad im Ordner der Entwürfe liegt.
 */
export function antragPdfPfad(wurzel: string, art: string, sitzung: string): string | null {
  if (!ART_MUSTER.test(art) || !UUID_MUSTER.test(sitzung)) return null;
  const ordner = antragOrdner(wurzel);
  const datei = path.join(ordner, `${art}-${sitzung}-entwurf.pdf`);
  return path.dirname(datei) === ordner && datei.startsWith(ordner + path.sep) ? datei : null;
}

export interface PdfOptionen {
  umgebung?: Umgebung;
  wurzel?: () => string;
  /** Liest die Datei; wirft mit `code: "ENOENT"`, wenn sie fehlt. Prüft vorher den echten Pfad (Symlinks). */
  lesen?: (datei: string, ordner: string) => Promise<Uint8Array>;
}

const standardLesen = async (datei: string, ordner: string): Promise<Uint8Array> => {
  const [echt, echterOrdner] = await Promise.all([realpath(datei), realpath(ordner)]);
  if (!echt.startsWith(echterOrdner + path.sep)) throw Object.assign(new Error("ausserhalb"), { code: "ENOENT" });
  return readFile(echt);
};

/**
 * Handler für GET /api/uc1/antrag/pdf?art=<art>&sitzung=<uuid>: der vom Kern erzeugte Entwurf als Download.
 * `KIC_ONLINE_LESEND=1` → 403, ungültige Art oder Sitzung → 400, Datei fehlt → 404.
 */
export function erstelleAntragPdf({
  umgebung = process.env,
  wurzel = () => cliWurzel(umgebung),
  lesen = standardLesen,
}: PdfOptionen = {}): (anfrage: Request) => Promise<Response> {
  return async function antragPdf(anfrage: Request): Promise<Response> {
    if (umgebung.KIC_ONLINE_LESEND === "1") {
      return fehler(403, "In der Online-Demo entsteht kein PDF. Das gibt es nur im echten Gespräch.", true);
    }
    const parameter = new URL(anfrage.url).searchParams;
    const art = parameter.get("art") ?? "";
    const sitzung = parameter.get("sitzung") ?? "";
    const basis = wurzel();
    const datei = antragPdfPfad(basis, art, sitzung);
    if (!datei) return fehler(400, "Art oder Sitzung des Antrags ist ungültig.");
    let inhalt: Uint8Array;
    try {
      inhalt = await lesen(datei, antragOrdner(basis));
    } catch (grund) {
      if ((grund as { code?: string }).code !== "ENOENT") console.warn("[uc1/antrag/pdf] Entwurf nicht lesbar");
      return fehler(404, "Diesen Antrag gibt es nicht mehr. Bitte bereiten Sie ihn neu vor.");
    }
    return new Response(new Uint8Array(inhalt), {
      headers: {
        "content-type": "application/pdf",
        "content-disposition": `attachment; filename="antrag-${art}-entwurf.pdf"`,
        "cache-control": "no-store",
        "x-content-type-options": "nosniff",
      },
    });
  };
}

/** Prozessweite Handler für die Routen. */
export const antragAntwort = erstelleAntragAntwort();
export const antragPdf = erstelleAntragPdf();
