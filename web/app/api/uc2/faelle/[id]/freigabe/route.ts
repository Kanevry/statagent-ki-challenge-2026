import { pruefeName } from "@kic/ui/bausteine";
import { z } from "zod";
import { erstelleRatenlimit, grenzeAus } from "../../../../../../lib/plattform/ratenlimit";
import { leseBodyText, ZuGross } from "../../../_lib/body";
import { istMockId } from "../../../_lib/mock";
import { fehler, gueltigeId, MODUS_KOPF, mockErzwungen, ruftApi } from "../../../_lib/proxy";

// POST /api/uc2/faelle/{id}/freigabe  {name, entscheidung: "freigegeben" | "abgelehnt", begruendung?}
// Ein Mensch gibt den Bericht einer fertigen Verhandlung mit Vor- und Nachnamen frei oder lehnt ihn ab. Die Route
// reicht an `uc2.api` durch (POST /faelle/{id}/freigabe), die den Fall prüft und in PG speichert. Antwort 200 {zeitpunkt}.
//
// Vorführmodus (Kennung mock-… oder UC2_MOCK=1): es wird NICHTS gespeichert. Die Antwort sagt das ehrlich mit
// `gespeichert: false`; die Seite ruft die Route in der Vorführung gar nicht erst auf.
//
// Sperren, alle vor dem Body und vor jedem API-Aufruf (Muster: POST /api/uc2/faelle): KIC_ONLINE_LESEND=1 → 403,
// Ratenlimit je Client-IP → 429, Body über 4 KiB (auch gestreamt ohne Content-Length) → 413. Fehlerkörper der API gehen
// nie nach außen, nur feste Sätze (SEC-009).
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export const MAX_BODY = 4 * 1024;

export const ZU_OFT = "Zu viele Freigaben in kurzer Zeit. Bitte in einer Minute noch einmal.";
export const ANFRAGE_UNGUELTIG =
  "Die Eingabe passt nicht. Bitte Vor- und Nachnamen eintragen, eine Entscheidung wählen und die Begründung auf höchstens 500 Zeichen kürzen.";

export const NAME_UNGUELTIG = "Bitte Vor- und Nachnamen eines Menschen eintragen. „Team“ gilt nicht.";

const schema = z.object({
  name: z.string().max(200),
  entscheidung: z.enum(["freigegeben", "abgelehnt"]),
  begruendung: z.string().trim().max(500).optional(),
});

const antwortSchema = z.object({ zeitpunkt: z.string().min(1) });

const KEIN_CACHE = { "cache-control": "no-store" } as const;

const ratenlimit = erstelleRatenlimit({ proMinute: grenzeAus(process.env) });

/** Feste Sätze je Status der Python-API; ihr Körper geht nie nach außen. */
function fehlerAusApi(status: number): Response {
  if (status === 403) return fehler(403, "Freigeben ist in der Online-Demo gesperrt.");
  if (status === 404) return fehler(404, "Diesen Fall gibt es nicht.");
  if (status === 409) return fehler(409, "Dieser Bericht ist noch nicht fertig oder schon entschieden.");
  if (status === 413) return fehler(413, "Die Anfrage ist zu groß.");
  if (status === 422) return fehler(422, "Name oder Begründung passen nicht. Bitte Vor- und Nachnamen eintragen.");
  if (status === 429) {
    const response = fehler(429, ZU_OFT);
    response.headers.set("retry-after", "60");
    return response;
  }
  return fehler(502, "Das Panel hat nicht geantwortet. Bitte später noch einmal versuchen.");
}

export async function POST(anfrage: Request, { params }: { params: Promise<{ id: string }> }): Promise<Response> {
  if (process.env.KIC_ONLINE_LESEND === "1") return fehler(403, "Freigeben ist in der Online-Demo gesperrt.");
  const gedrosselt = ratenlimit(anfrage);
  if (gedrosselt) {
    // Das gemeinsame Limit spricht von „Fragen“; hier geht es um Freigaben. Die Wartezeit bleibt.
    const warten = gedrosselt.headers.get("retry-after") ?? "60";
    const response = fehler(429, ZU_OFT);
    response.headers.set("retry-after", warten);
    return response;
  }

  const { id } = await params;
  if (!gueltigeId(id)) return fehler(400, "Ungültige Fall-Kennung.");

  let roh: unknown;
  try {
    const text = await leseBodyText(anfrage, MAX_BODY);
    roh = JSON.parse(text);
  } catch (f) {
    return f instanceof ZuGross ? fehler(413, "Die Anfrage ist zu groß.") : fehler(400, "Die Anfrage braucht JSON.");
  }
  const eingabe = schema.safeParse(roh);
  if (!eingabe.success) return fehler(400, ANFRAGE_UNGUELTIG);
  const { entscheidung, begruendung } = eingabe.data;

  const name = pruefeName(eingabe.data.name);
  if (!name.gueltig) return fehler(422, NAME_UNGUELTIG);
  if (entscheidung === "abgelehnt" && !begruendung) return fehler(422, "Eine Ablehnung braucht eine Begründung.");

  if (istMockId(id) || mockErzwungen()) {
    return Response.json(
      { zeitpunkt: new Date().toISOString(), gespeichert: false },
      { headers: { ...KEIN_CACHE, [MODUS_KOPF]: "vorfuehrung" } },
    );
  }
  // Echte Fälle haben in PG eine Nummer.
  if (!/^\d{1,18}$/.test(id)) return fehler(404, "Diesen Fall gibt es nicht.");

  const antwort = await ruftApi(`/faelle/${encodeURIComponent(id)}/freigabe`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name: name.name, entscheidung, ...(begruendung ? { begruendung } : {}) }),
    frist: 5000,
  });
  if (!antwort) return fehler(502, "Die Schnittstelle des Panels ist nicht erreichbar.");
  if (!antwort.ok) return fehlerAusApi(antwort.status);
  const geprueft = antwortSchema.safeParse(await antwort.json().catch(() => null));
  if (!geprueft.success) return fehler(502, "Das Panel hat in einem unerwarteten Format geantwortet.");
  return Response.json(
    { zeitpunkt: geprueft.data.zeitpunkt, gespeichert: true },
    { headers: { ...KEIN_CACHE, [MODUS_KOPF]: "live" } },
  );
}
