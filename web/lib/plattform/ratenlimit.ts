// Ratenlimit (#100) für Routen, die ein Modell auslösen: gleitendes Fenster von einer Minute je Client-IP, im
// Speicher. Das reicht, weil je Container genau ein Next-Prozess läuft; das Tagesbudget über alle Prozesse
// zählt `plattform.llm` selbst (LLM_TAGESBUDGET_AUFRUFE).

export const FENSTER_MS = 60_000;
export const STANDARD_PRO_MINUTE = 10;
/** Obergrenze der gemerkten IPs; darüber fliegen die ältesten Einträge, damit der Speicher nicht wächst. */
export const MAX_SCHLUESSEL = 10_000;
export const UNBEKANNT = "unbekannt";

/** Client-IP: erster Eintrag von `x-forwarded-for` (setzt Caddy), sonst `x-real-ip`, sonst ein fester Schlüssel. */
export function clientSchluessel(anfrage: Request): string {
  const weitergeleitet = anfrage.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  if (weitergeleitet) return weitergeleitet;
  return anfrage.headers.get("x-real-ip")?.trim() || UNBEKANNT;
}

/** `RATENLIMIT_PRO_MINUTE` als ganze Zahl ab 1; fehlt oder ungültig: Standard 10 (nie „unbegrenzt“). */
export function grenzeAus(umgebung: Readonly<Record<string, string | undefined>>): number {
  const wert = Number(umgebung.RATENLIMIT_PRO_MINUTE);
  return Number.isInteger(wert) && wert >= 1 ? wert : STANDARD_PRO_MINUTE;
}

export function erstelleRatenlimit({ proMinute, maxSchluessel = MAX_SCHLUESSEL }: { proMinute: number; maxSchluessel?: number }) {
  // Map behält die Einfügereihenfolge: vorne stehen die am längsten nicht mehr gesehenen IPs.
  const zeiten = new Map<string, number[]>();

  function raeumen(jetzt: number) {
    for (const [schluessel, liste] of zeiten) {
      if (liste.length === 0 || liste[liste.length - 1]! <= jetzt - FENSTER_MS) zeiten.delete(schluessel);
    }
    while (zeiten.size >= maxSchluessel) {
      const aeltester = zeiten.keys().next().value;
      if (aeltester === undefined) break;
      zeiten.delete(aeltester);
    }
  }

  /** `null`, wenn die Anfrage durch darf (und zählt), sonst eine fertige 429-Antwort mit `Retry-After`. */
  return function pruefeRatenlimit(anfrage: Request, jetzt: number = Date.now()): Response | null {
    const schluessel = clientSchluessel(anfrage);
    const liste = (zeiten.get(schluessel) ?? []).filter((zeit) => zeit > jetzt - FENSTER_MS);
    if (liste.length >= proMinute) {
      zeiten.set(schluessel, liste);
      const sekunden = Math.max(1, Math.ceil((liste[0]! + FENSTER_MS - jetzt) / 1000));
      return Response.json(
        { fehler: `Zu viele Fragen in kurzer Zeit. Bitte in ${sekunden} Sekunden noch einmal versuchen.` },
        { status: 429, headers: { "retry-after": String(sekunden), "cache-control": "no-store" } },
      );
    }
    if (!zeiten.has(schluessel)) raeumen(jetzt);
    zeiten.delete(schluessel);
    zeiten.set(schluessel, [...liste, jetzt]);
    return null;
  };
}

export type PruefeRatenlimit = ReturnType<typeof erstelleRatenlimit>;

/** Prozessweites Limit für die Route-Handler. */
export const pruefeRatenlimit = erstelleRatenlimit({ proMinute: grenzeAus(process.env) });
