// Schutz der POST-Routen von /api/uc3 gegen Anfragen fremder Seiten (CSRF). Ein Formular einer anderen Seite kann
// mit enctype=text/plain ohne CORS-Vorabprüfung gültiges JSON an localhost schicken (Review !51, w2-review-3).
// Deshalb: nur application/json (erzwingt bei fremder Herkunft die Vorabprüfung, die Next nicht beantwortet) und
// nur Aufrufe von derselben Seite. Werkzeuge ohne Browser (curl) senden keine Fetch-Metadaten und bleiben erlaubt;
// gegen Zugriffe aus dem Netz hilft nur, den Server an 127.0.0.1 zu binden.

function abweisen(status: 403 | 415, meldung: string): Response {
  return Response.json({ fehler: meldung }, { status, headers: { "cache-control": "no-store" } });
}

/** Host der Anfrage, hinter einem Proxy der weitergereichte. */
function eigenerHost(anfrage: Request): string | null {
  const weitergereicht = anfrage.headers.get("x-forwarded-host")?.split(",")[0]?.trim();
  if (weitergereicht) return weitergereicht;
  const host = anfrage.headers.get("host")?.trim();
  if (host) return host;
  try {
    return new URL(anfrage.url).host;
  } catch {
    return null;
  }
}

/**
 * `null`, wenn die Anfrage JSON ist und von dieser Seite kommt; sonst die fertige Antwort 415 bzw. 403.
 * Vor jeder weiteren Arbeit aufrufen (vor dem Lesen des Bodys und vor jedem Subprozess).
 */
export function pruefeHerkunft(anfrage: Request): Response | null {
  const art = (anfrage.headers.get("content-type") ?? "").trim().toLowerCase();
  if (!/^application\/json(\s*;|$)/.test(art)) return abweisen(415, "Die Anfrage muss JSON sein.");

  const seite = anfrage.headers.get("sec-fetch-site");
  if (seite !== null && seite !== "same-origin" && seite !== "none") {
    return abweisen(403, "Das geht nur direkt auf dieser Seite.");
  }

  const herkunft = anfrage.headers.get("origin");
  if (herkunft !== null && herkunft !== "null") {
    let herkunftHost: string;
    try {
      herkunftHost = new URL(herkunft).host;
    } catch {
      return abweisen(403, "Das geht nur direkt auf dieser Seite.");
    }
    if (herkunftHost !== eigenerHost(anfrage)) return abweisen(403, "Das geht nur direkt auf dieser Seite.");
  } else if (herkunft === "null") {
    // „null“ senden sandboxed iframes und data:-Seiten: nie die eigene Seite.
    return abweisen(403, "Das geht nur direkt auf dieser Seite.");
  }
  return null;
}
