import berichtJson from "../_fixtures/bericht-mock.json";
import ereignisseJson from "../_fixtures/ereignisse-mock.json";

// Aufgezeichneter Fall für den Mock-Modus (UC2_MOCK=1 oder keine Python-API erreichbar). Die Fixtures stammen aus
// einem echten mock-Lauf mit erfundenen Belegen, schon durch den Online-Belegfilter gelaufen. Nichts hier ruft ein Modell.

export interface RohEreignis {
  seq: number;
  runde: number | null;
  art: string;
  akteur: string | null;
  daten: Record<string, unknown>;
  zeit?: string | null;
}

export const MOCK_FALL = "mock-wartezeiten";
export const MOCK_ABBRUCH = "mock-abbruch";
const MOCK_IDS = [MOCK_FALL, MOCK_ABBRUCH] as const;

const ALLE = ereignisseJson as unknown as RohEreignis[];
const BERICHT = berichtJson as unknown as Record<string, unknown> & { fall: Record<string, unknown>; runden: unknown[] };

/** Der Abbruch-Fall: Runde 1 und 2 komplett, Runde 3 beginnt, dann scheitert das Modell des ersten Sprechers. */
const ABBRUCH_NACH_SEQ = 36;

export function istMockId(id: string): boolean {
  return id.startsWith("mock-");
}

/** Der Abbruch-Fall läuft laut `start` über azure; die Aufzeichnung stammt vom Mock-Modell. */
function azureStart(e: RohEreignis): RohEreignis {
  const modelle = Object.fromEntries(
    Object.entries((e.daten.modelle ?? {}) as Record<string, Record<string, unknown>>).map(([rolle, m]) => [
      rolle,
      { ...m, provider: "azure", modell: "gpt-5-4-mini" },
    ]),
  );
  return { ...e, daten: { ...e.daten, provider: "azure", modelle } };
}

export function mockEreignisse(id: string): RohEreignis[] | null {
  if (id === MOCK_FALL) return ALLE;
  if (id === MOCK_ABBRUCH) {
    const bis = ALLE.filter((e) => e.seq <= ABBRUCH_NACH_SEQ).map((e) => (e.art === "start" ? azureStart(e) : e));
    const letzte = bis.at(-1);
    return [
      ...bis,
      {
        seq: ABBRUCH_NACH_SEQ + 1,
        runde: 3,
        art: "abbruch",
        akteur: null,
        daten: { grund: "TimeoutError", meldung: "Zeitüberschreitung nach 30 s" },
        zeit: letzte?.zeit ?? null,
      },
    ];
  }
  return null;
}

export function mockBericht(id: string): Record<string, unknown> | null {
  const ereignisse = mockEreignisse(id);
  if (!ereignisse) return null;
  if (id === MOCK_FALL) {
    return { ...BERICHT, fall: { ...BERICHT.fall, fall_id: id }, ereignisse: ereignisse.length };
  }
  return {
    ...BERICHT,
    fall: { ...BERICHT.fall, fall_id: id, status: "abgebrochen", status_gespeichert: "abgebrochen" },
    runden: BERICHT.runden.slice(0, 2),
    ergebnis: null,
    ereignisse: ereignisse.length,
  };
}

export function mockListe(): { fall_id: string; fall_name: string; status: string }[] {
  return MOCK_IDS.map((id) => ({
    fall_id: id,
    fall_name: "wartezeiten",
    status: id === MOCK_FALL ? "fertig" : "abgebrochen",
  }));
}

export const mockFall = BERICHT.fall;
export const mockBerichtRoh = BERICHT;

export function sse(e: RohEreignis): string {
  return `id: ${e.seq}\nevent: ${e.art}\ndata: ${JSON.stringify(e)}\n\n`;
}

export function mockTakt(): number {
  const wert = Number(process.env.UC2_MOCK_TAKT_MS ?? "150");
  return Number.isFinite(wert) ? Math.min(Math.max(wert, 0), 2000) : 150;
}

/**
 * SSE-Strom eines aufgezeichneten Falls. Wie die echte Schnittstelle: `id: seq`, `event: art`, `data: json`,
 * Wiederaufnahme ab `ab` (Last-Event-ID oder ?seq=), Ende mit `event: ende`. Zwischen den Ereignissen liegt `takt`
 * Millisekunden, damit die Verhandlung live wirkt.
 */
export function mockStrom(ereignisse: readonly RohEreignis[], ab: number, takt: number, signal?: AbortSignal): ReadableStream<Uint8Array> {
  const kodierer = new TextEncoder();
  let abgebrochen = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const warte = (ms: number) =>
    new Promise<void>((fertig) => {
      timer = setTimeout(fertig, ms);
    });
  const status = ereignisse.some((e) => e.art === "abbruch") ? "abgebrochen" : "fertig";
  const letzteSeq = ereignisse.at(-1)?.seq ?? 0;

  return new ReadableStream<Uint8Array>({
    async start(steuerung) {
      const stopp = () => {
        abgebrochen = true;
        clearTimeout(timer);
      };
      signal?.addEventListener("abort", stopp, { once: true });
      try {
        steuerung.enqueue(kodierer.encode("retry: 3000\n\n"));
        for (const e of ereignisse) {
          if (e.seq <= ab) continue;
          if (takt > 0) await warte(takt);
          if (abgebrochen) return;
          steuerung.enqueue(kodierer.encode(sse(e)));
        }
        steuerung.enqueue(kodierer.encode(`event: ende\ndata: ${JSON.stringify({ status, letzte_seq: letzteSeq })}\n\n`));
        steuerung.close();
      } catch {
        // Die Leser sind weg (Tab geschlossen); es gibt nichts mehr zu liefern.
      } finally {
        signal?.removeEventListener("abort", stopp);
      }
    },
    cancel() {
      abgebrochen = true;
      clearTimeout(timer);
    },
  });
}
