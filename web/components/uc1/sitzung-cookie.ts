import { UUID_MUSTER } from "./antrag";

// Bindung von Antrag und PDF an die Sitzung des Browsers (#35, Review !69). POST /api/uc1/frage setzt das Cookie mit
// der `sitzung_id` des Kerns; POST /api/uc1/antrag und GET /api/uc1/antrag/pdf liefern nur, wenn es zur angefragten
// Sitzung passt. So holt niemand im lokalen Netz mit einer erratenen oder mitgelesenen UUID einen fremden Entwurf.

export const SITZUNG_COOKIE = "uc1_sitzung";
/** Ein Tag, wie die Gesprächsdauer im Kern. */
export const SITZUNG_MAX_ALTER_S = 86_400;
export const FREMDE_SITZUNG = "Dieser Antrag gehört nicht zu Ihrem Gespräch. Bitte erzählen Sie die Situation neu.";

/** Läuft die Anfrage über https (direkt oder hinter einem Proxy)? Dann trägt das Cookie `Secure`. */
export function istHttps(anfrage: Request): boolean {
  const weitergeleitet = anfrage.headers.get("x-forwarded-proto")?.split(",")[0]?.trim().toLowerCase();
  if (weitergeleitet) return weitergeleitet === "https";
  return new URL(anfrage.url).protocol === "https:";
}

/** `Set-Cookie` für die Sitzung, oder `null`, wenn die ID keine UUID ist. */
export function sitzungCookie(sitzung: string, https: boolean): string | null {
  if (!UUID_MUSTER.test(sitzung)) return null;
  return [
    `${SITZUNG_COOKIE}=${sitzung}`,
    "HttpOnly",
    "SameSite=Strict",
    "Path=/api/uc1",
    `Max-Age=${SITZUNG_MAX_ALTER_S}`,
    ...(https ? ["Secure"] : []),
  ].join("; ");
}

/** Wert des Sitzungs-Cookies aus dem `cookie`-Header, oder `null`. */
export function leseSitzungCookie(anfrage: Request): string | null {
  const kopf = anfrage.headers.get("cookie") ?? "";
  for (const teil of kopf.split(";")) {
    const gleich = teil.indexOf("=");
    if (gleich < 0) continue;
    if (teil.slice(0, gleich).trim() === SITZUNG_COOKIE) return teil.slice(gleich + 1).trim() || null;
  }
  return null;
}

/** Passt das Cookie genau zur angefragten Sitzung? */
export function sitzungPasst(anfrage: Request, sitzung: string): boolean {
  const cookie = leseSitzungCookie(anfrage);
  return cookie !== null && cookie === sitzung;
}
