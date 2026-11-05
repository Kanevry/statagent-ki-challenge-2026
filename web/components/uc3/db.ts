import postgres from "postgres";

/**
 * Lesender Zugang zur UC3-Datenbank (`UC3_DATABASE_URL`, Port 5433). Nur serverseitig importieren.
 *
 * Jede Seite fragt über `lies()`. Fehlt die Adresse (CI, Online-Demo ohne DB) oder antwortet die Datenbank nicht,
 * kommt ein Grund statt einer Ausnahme zurück; die Seite zeigt dann ihren Leerzustand mit HTTP 200.
 * Geschrieben wird hier nie: Änderungen laufen über die CLI (`uc3 freigabe`), siehe `cli.ts`.
 */

export type Sql = postgres.Sql;

export type Lesung<T> =
  | { ok: true; daten: T }
  | { ok: false; grund: "keine-datenbank" | "nicht-erreichbar" | "fehler"; meldung: string };

/** Obergrenze je Seitenaufruf; die größte Abfrage (24 Läufe mit Prüftreffern) braucht unter 200 ms. */
export const ZEITLIMIT_MS = 4_000;

type Ablage = { url: string; sql: Sql };
const SCHLUESSEL = Symbol.for("kic.uc3.datenbank");

function ablage(): { [SCHLUESSEL]?: Ablage } {
  return globalThis as { [SCHLUESSEL]?: Ablage };
}

/** Eine Verbindung je Prozess (auch über Hot Reload im Dev-Server), `null` ohne `UC3_DATABASE_URL`. */
export function verbindung(umgebung: Readonly<Record<string, string | undefined>> = process.env): Sql | null {
  const url = umgebung.UC3_DATABASE_URL?.trim();
  if (!url) return null;
  const vorhanden = ablage()[SCHLUESSEL];
  if (vorhanden?.url === url) return vorhanden.sql;
  const sql = postgres(url, {
    max: 3,
    connect_timeout: 3,
    idle_timeout: 20,
    prepare: false,
    onnotice: () => {},
    unref_sockets: true,
    // Lesend auch dann, wenn die Rolle schreiben dürfte; eine hängende Abfrage bricht der Server selbst ab.
    connection: {
      application_name: "kic-web-uc3",
      default_transaction_read_only: true,
      statement_timeout: ZEITLIMIT_MS,
    },
  });
  ablage()[SCHLUESSEL] = { url, sql };
  return sql;
}

const NICHT_ERREICHBAR = new Set(["ECONNREFUSED", "ENOTFOUND", "ETIMEDOUT", "CONNECT_TIMEOUT", "EHOSTUNREACH"]);

function grundAus(fehler: unknown): "nicht-erreichbar" | "fehler" {
  const code = (fehler as { code?: unknown } | null)?.code;
  return typeof code === "string" && NICHT_ERREICHBAR.has(code) ? "nicht-erreichbar" : "fehler";
}

/**
 * Führt eine Lese-Abfrage aus und liefert Daten oder einen Grund. Die Meldung geht nur ins Server-Log und in
 * `meldung`; Seiten zeigen dem Menschen einen eigenen Satz, nie den Text des Treibers.
 */
export async function lies<T>(
  abfrage: (sql: Sql) => Promise<T>,
  optionen: { sql?: Sql | null; zeitlimitMs?: number } = {},
): Promise<Lesung<T>> {
  const sql = optionen.sql === undefined ? verbindung() : optionen.sql;
  if (!sql) return { ok: false, grund: "keine-datenbank", meldung: "UC3_DATABASE_URL ist nicht gesetzt" };
  let zeitgeber: ReturnType<typeof setTimeout> | undefined;
  const zeitlimit = new Promise<never>((_, ablehnen) => {
    zeitgeber = setTimeout(
      () => ablehnen(Object.assign(new Error("Zeitlimit"), { code: "ETIMEDOUT" })),
      optionen.zeitlimitMs ?? ZEITLIMIT_MS,
    );
  });
  try {
    return { ok: true, daten: await Promise.race([abfrage(sql), zeitlimit]) };
  } catch (fehler) {
    const grund = grundAus(fehler);
    const meldung = fehler instanceof Error ? fehler.message : String(fehler);
    console.error(`[uc3] Datenbank ${grund}: ${meldung}`);
    return { ok: false, grund, meldung };
  } finally {
    clearTimeout(zeitgeber);
  }
}

/** Satz für den Leerzustand, wenn eine Lesung ohne Daten zurückkommt. */
export function leerSatz(grund: Exclude<Lesung<unknown>, { ok: true }>["grund"]): string {
  switch (grund) {
    case "keine-datenbank":
      return "Hier ist keine Datenbank angeschlossen. Die Zahlen erscheinen, sobald die UC3-Datenbank läuft.";
    case "nicht-erreichbar":
      return "Die Datenbank antwortet gerade nicht. Es wurde nichts geändert; bitte die Seite gleich neu laden.";
    default:
      return "Die Zahlen ließen sich gerade nicht lesen. Es wurde nichts geändert; bitte die Seite neu laden.";
  }
}
