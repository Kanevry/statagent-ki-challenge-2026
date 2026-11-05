// Durchreichen an die Python-Schnittstelle `uc2.api` (Port 8102). `web/` ruft nie ein Modell: die Handler leiten
// nur weiter oder liefern im Mock-Modus den aufgezeichneten Fall.

export const STANDARD_API = "http://localhost:8102";

export function apiUrl(): string {
  return (process.env.UC2_API_URL || STANDARD_API).replace(/\/+$/, "");
}

/** UC2_MOCK=1 erzwingt den aufgezeichneten Fall, auch wenn eine API läuft. */
export function mockErzwungen(): boolean {
  return process.env.UC2_MOCK === "1";
}

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
