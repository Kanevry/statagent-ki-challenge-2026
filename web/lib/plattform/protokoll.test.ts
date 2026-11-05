import { eintraegeSchema } from "@kic/ui/shell";
import { protokollAntwort } from "./protokoll";

// Referenz-Handler GET /api/<uc>/protokoll: Antwort erfüllt den Vertrag, Filter greifen, Unbekanntes wird abgewiesen.
const frage = (pfad: string, uc: string) => protokollAntwort(new Request(`http://lokal${pfad}`), uc);

describe("GET /api/<uc>/protokoll (Fallback)", () => {
  it("liefert gültige Einträge des UC, ?status filtert", async () => {
    const alle = eintraegeSchema.parse(await (await frage("/api/uc3/protokoll", "uc3")).json());
    expect(alle.map((e) => e.id)).toEqual([42, 41]);
    const offen = eintraegeSchema.parse(await (await frage("/api/uc3/protokoll?status=offen", "uc3")).json());
    expect(offen.map((e) => [e.id, e.status])).toEqual([[41, "offen"]]);
    expect(await (await frage("/api/uc1/protokoll", "uc1")).json()).toEqual([]);
  });

  it("404 für unbekannte Bereiche, 400 für unbekannten Status", async () => {
    expect((await frage("/api/uc9/protokoll", "uc9")).status).toBe(404);
    expect((await frage("/api/uc3/protokoll?status=erledigt", "uc3")).status).toBe(400);
  });

  it("zeigt die Fixture nur in Entwicklung oder mit KIC_FIXTURE=1, in Produktion eine leere Liste", async () => {
    try {
      vi.stubEnv("NODE_ENV", "production");
      vi.stubEnv("KIC_FIXTURE", "");
      expect(await (await frage("/api/uc3/protokoll", "uc3")).json()).toEqual([]);
      vi.stubEnv("KIC_FIXTURE", "1");
      expect(eintraegeSchema.parse(await (await frage("/api/uc3/protokoll", "uc3")).json()).map((e) => e.id)).toEqual([42, 41]);
    } finally {
      vi.unstubAllEnvs();
    }
  });
});
