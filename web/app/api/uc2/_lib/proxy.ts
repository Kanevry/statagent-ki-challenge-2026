// Durchreichen an die Python-Schnittstelle `uc2.api` (Port 8102). `web/` ruft nie ein Modell: die Handler leiten
// nur weiter oder liefern im Mock-Modus den aufgezeichneten Fall.

import { istMockId } from "./mock";

export const STANDARD_API = "http://localhost:8102";

export function apiUrl(): string {
  return (process.env.UC2_API_URL || STANDARD_API).replace(/\/+$/, "");
}

/** UC2_MOCK=1 erzwingt den aufgezeichneten Fall, auch wenn eine API läuft. */
export function mockErzwungen(): boolean {
  return process.env.UC2_MOCK === "1";
}

/**
 * Betriebsart eines Falls, vom Server bestimmt statt von der Seite geraten: "vorfuehrung" = aufgezeichnete Verhandlung
 * ohne Sprachmodell (Kennung mock-… oder UC2_MOCK=1), "live" = Lauf der Python-API.
 */
export type Modus = "vorfuehrung" | "live";

export function modusFuer(fallId: string | null): Modus {
  return mockErzwungen() || (fallId !== null && istMockId(fallId)) ? "vorfuehrung" : "live";
}

export const MODUS_KOPF = "x-uc2-modus";

/** Fall-Kennungen kommen aus der URL und gehen in einen Pfad: nur harmlose Zeichen. */
export function gueltigeId(id: string): boolean {
  return /^[A-Za-z0-9_-]{1,64}$/.test(id);
}

/**
 * Ruft die API auf. Liefert `null`, wenn sie nicht erreichbar ist (Verbindung abgelehnt, Zeitüberschreitung beim
 * Aufbau); eine Antwort mit Fehlerstatus kommt unverändert zurück. Bei Strömen gilt die Frist nur bis zu den Headern.
 */
export async function ruftApi(
  pfad: string,
  init: RequestInit & { frist?: number } = {},
): Promise<Response | null> {
  const { frist = 3000, signal, ...rest } = init;
  const steuerung = new AbortController();
  const timer = setTimeout(() => steuerung.abort(), frist);
  const weiter = () => steuerung.abort();
  signal?.addEventListener("abort", weiter, { once: true });
  try {
    return await fetch(`${apiUrl()}${pfad}`, { ...rest, signal: steuerung.signal, cache: "no-store" });
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
    // Der Strom läuft weiter; nur der Abbruch des Aufrufers (Tab zu) beendet ihn.
  }
}

export const SSE_KOPF = {
  "content-type": "text/event-stream; charset=utf-8",
  "cache-control": "no-store, no-transform",
  connection: "keep-alive",
  "x-accel-buffering": "no",
} as const;

export function fehler(status: number, meldung: string): Response {
  return Response.json({ fehler: meldung }, { status, headers: { "cache-control": "no-store" } });
}

/**
 * Fehler der API gehen nie als Körper nach außen (SEC-009: Details, Pfade, Stacktraces). Nach außen gehen nur feste,
 * einfache Sätze je Status.
 */
export function fehlerAusApiStatus(status: number): Response {
  if (status === 404) return fehler(404, "Diesen Fall gibt es nicht.");
  if (status === 409) return fehler(409, "Es läuft schon eine Verhandlung.");
  if (status === 422) return fehler(422, "Das Panel nimmt dieses Modell oder diese Auswahl gerade nicht an.");
  // 503: Tageslimit der Live-Verhandlungen verbraucht oder Dienst nicht bereit. 403 (echte Modelle gesperrt) bleibt beim
  // allgemeinen Satz für 4xx.
  if (status === 503) return fehler(503, "Heute sind keine neuen Live-Verhandlungen mehr möglich. Die aufgezeichnete Verhandlung bleibt.");
  if (status === 429) return fehler(429, "Das Panel hat gerade zu viele Anfragen. Bitte gleich noch einmal versuchen.");
  if (status >= 400 && status < 500) return fehler(400, "Das Panel hat die Anfrage abgelehnt.");
  return fehler(502, "Das Panel hat nicht geantwortet. Bitte später noch einmal versuchen.");
}
