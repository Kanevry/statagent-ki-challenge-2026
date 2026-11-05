// @vitest-environment node
import path from "node:path";
import { describe, expect, it, vi } from "vitest";
import { antragArgv, antragPdfPfad, erstelleAntragAntwort, erstelleAntragPdf, type PdfOptionen } from "./antrag-server";
import pflege from "./fixtures/pflege.json";
import type { Ausfuehren } from "./lotse";

const SITZUNG = "54612949-24fa-4a69-b846-9ad7054da93c";
const WURZEL = path.resolve("/repo");
const ORDNER = path.join(WURZEL, "uc1", "laufzeit", "antraege");
const KERN = { ...pflege.antrag, pdf: path.join(ORDNER, `pflegegeld-${SITZUNG}-entwurf.pdf`) };

const COOKIE = `uc1_sitzung=${SITZUNG}`;
const FREMD = "uc1_sitzung=0b7e2f10-1111-4222-8333-444455556666";

function post(body: unknown, cookie: string | null = COOKIE): Request {
  return new Request("http://localhost/api/uc1/antrag", {
    method: "POST",
    headers: { "content-type": "application/json", ...(cookie ? { cookie } : {}) },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
}

function handler(ausfuehren: Ausfuehren, umgebung: Record<string, string | undefined> = {}) {
  return erstelleAntragAntwort({ ausfuehren, umgebung, wurzel: () => WURZEL });
}

describe("POST /api/uc1/antrag", () => {
  // Fängt: Art oder Sitzung an falscher Stelle im argv (Kern liest sie dann als etwas anderes).
  it("ruft lotse antrag <art> --sitzung <id> --json auf", () => {
    expect(antragArgv({ art: "pflegegeld", sitzung: SITZUNG })).toEqual([
      "run", "--frozen", "--package", "uc1", "lotse", "antrag", "pflegegeld", "--sitzung", SITZUNG, "--json",
    ]);
  });

  // Fängt: Online-Demo startet doch einen Lauf, oder die Seite bekommt keinen Hinweis auf das Beispiel.
  it("403 mit replay bei KIC_ONLINE_LESEND=1, ohne Subprozess", async () => {
    const ausfuehren = vi.fn<Ausfuehren>();
    const antwort = await handler(ausfuehren, { KIC_ONLINE_LESEND: "1" })(post({ art: "pflegegeld", sitzung: SITZUNG }));
    expect(antwort.status).toBe(403);
    expect(await antwort.json()).toMatchObject({ replay: true });
    expect(ausfuehren).not.toHaveBeenCalled();
  });

  // Fängt: Schalter oder Pfade als Art („--help“, „../x“), kaputte Sitzung, zod-Texte im Client, großer Body.
  it("400 mit deutschem Satz bei falscher Art oder Sitzung, 413 bei großem Body", async () => {
    const ausfuehren = vi.fn<Ausfuehren>();
    const h = handler(ausfuehren);
    for (const body of [
      { art: "--help", sitzung: SITZUNG },
      { art: "../x", sitzung: SITZUNG },
      { art: "pflegegeld", sitzung: "abc" },
      { art: "pflegegeld", sitzung: SITZUNG.toUpperCase() },
      { art: "pflegegeld" },
      "kein json",
    ]) {
      const antwort = await h(post(body));
      expect(antwort.status).toBe(400);
      const { fehler } = (await antwort.json()) as { fehler: string };
      expect(fehler).toMatch(/^[A-ZÄÖÜ]/);
      expect(fehler).not.toMatch(/Invalid|expected/i);
    }
    expect((await h(post({ art: "pflegegeld", sitzung: SITZUNG, x: "y".repeat(2000) }))).status).toBe(413);
    expect(ausfuehren).not.toHaveBeenCalled();
  });

  // Fängt: Exit ≠ 0 oder Vertragsbruch als 200 oder 500 statt 503 mit Replay-Angebot.
  it("503 mit replay bei Exit 1 und fehlendem befuellt", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    for (const ausfuehren of [
      async () => ({ code: 1, stdout: "" }),
      async () => ({ code: 0, stdout: JSON.stringify({ ...KERN, befuellt: undefined }) }),
    ] satisfies Ausfuehren[]) {
      const antwort = await handler(ausfuehren)(post({ art: "pflegegeld", sitzung: SITZUNG }));
      expect(antwort.status).toBe(503);
      expect(await antwort.json()).toMatchObject({ replay: true });
    }
  });

  // Fängt: absoluter PDF-Pfad oder Formulardatei in der Antwort an den Browser.
  it("200 ohne Pfad, mit befüllten Feldern", async () => {
    const antwort = await handler(async () => ({ code: 0, stdout: JSON.stringify(KERN) }))(
      post({ art: "pflegegeld", sitzung: SITZUNG }),
    );
    expect(antwort.status).toBe(200);
    const text = await antwort.text();
    expect(text).not.toMatch(/\.pdf|laufzeit|sha256|Anträge und Formulare/);
    expect(JSON.parse(text).befuellt).toContainEqual({ feld: "Vorname", wert: "Maria" });
  });

  // Fängt: ein Antrag, der ohne Cookie oder mit dem Cookie einer anderen Sitzung vorbereitet wird (fremde UUID im Netz).
  it("403 mit deutschem Satz ohne oder mit fremdem Sitzungs-Cookie, ohne Subprozess", async () => {
    const ausfuehren = vi.fn<Ausfuehren>(async () => ({ code: 0, stdout: JSON.stringify(KERN) }));
    const h = handler(ausfuehren);
    for (const cookie of [null, FREMD, `andere=1; uc1_sitzung=`]) {
      const antwort = await h(post({ art: "pflegegeld", sitzung: SITZUNG }, cookie));
      expect(antwort.status, String(cookie)).toBe(403);
      expect(((await antwort.json()) as { fehler: string }).fehler).toMatch(/^Dieser Antrag gehört nicht zu Ihrem Gespräch/);
    }
    expect(ausfuehren).not.toHaveBeenCalled();
    expect((await h(post({ art: "pflegegeld", sitzung: SITZUNG }, `andere=1; ${COOKIE}`))).status).toBe(200);
  });
});

describe("GET /api/uc1/antrag/pdf", () => {
  const pdf = (abfrage: string, optionen: PdfOptionen = {}, cookie: string | null = COOKIE) =>
    erstelleAntragPdf({ umgebung: {}, wurzel: () => WURZEL, ...optionen })(
      new Request(`http://localhost/api/uc1/antrag/pdf?${abfrage}`, { headers: cookie ? { cookie } : {} }),
    );

  // Fängt: ein Pfad aus dem Ordner der Entwürfe heraus, wenn Art oder Sitzung „../“ enthalten.
  it("antragPdfPfad lehnt Ausbruch und falsche UUID ab, baut sonst den Pfad im Ordner", () => {
    expect(antragPdfPfad(WURZEL, "../../etc", SITZUNG)).toBeNull();
    expect(antragPdfPfad(WURZEL, "pflegegeld", `../${SITZUNG}`)).toBeNull();
    expect(antragPdfPfad(WURZEL, "pflegegeld", "54612949-24fa-4a69-b846-9ad7054da93")).toBeNull();
    expect(antragPdfPfad(WURZEL, "pflegegeld", SITZUNG)).toBe(path.join(ORDNER, `pflegegeld-${SITZUNG}-entwurf.pdf`));
  });

  // Fängt: eine Route, die trotz ungültiger Parameter liest, und die Online-Demo, die Dateien ausliefert.
  it("400 bei ../ und falscher UUID, 403 online, ohne zu lesen", async () => {
    const lesen = vi.fn<NonNullable<PdfOptionen["lesen"]>>();
    expect((await pdf(`art=..%2F..%2Fetc&sitzung=${SITZUNG}`, { lesen })).status).toBe(400);
    expect((await pdf("art=pflegegeld&sitzung=nicht-uuid", { lesen })).status).toBe(400);
    expect((await pdf("art=pflegegeld", { lesen })).status).toBe(400);
    expect((await pdf(`art=pflegegeld&sitzung=${SITZUNG}`, { lesen, umgebung: { KIC_ONLINE_LESEND: "1" } })).status).toBe(403);
    expect(lesen).not.toHaveBeenCalled();
  });

  // Fängt: ein Entwurf mit Personenangaben, den jemand ohne oder mit fremdem Cookie über die UUID abholt.
  it("403 ohne oder mit fremdem Sitzungs-Cookie, ohne zu lesen", async () => {
    const lesen = vi.fn<NonNullable<PdfOptionen["lesen"]>>(async () => new TextEncoder().encode("%PDF-1.7"));
    for (const cookie of [null, FREMD]) {
      const antwort = await pdf(`art=pflegegeld&sitzung=${SITZUNG}`, { lesen }, cookie);
      expect(antwort.status, String(cookie)).toBe(403);
      expect(((await antwort.json()) as { fehler: string }).fehler).toMatch(/^Dieser Antrag gehört nicht zu Ihrem Gespräch/);
    }
    expect(lesen).not.toHaveBeenCalled();
  });

  // Fängt: 500 statt eines deutschen Satzes, wenn der Entwurf fehlt (Neustart, anderer Checkout).
  it("404 mit deutschem Satz, wenn die Datei fehlt", async () => {
    const lesen = async () => {
      throw Object.assign(new Error("fehlt"), { code: "ENOENT" });
    };
    const antwort = await pdf(`art=pflegegeld&sitzung=${SITZUNG}`, { lesen });
    expect(antwort.status).toBe(404);
    expect(((await antwort.json()) as { fehler: string }).fehler).toMatch(/^Diesen Antrag/);
  });

  // Fängt: Inline-Anzeige statt Download, ein Dateiname mit Sitzung, und ein Cache, der Personenangaben behält.
  it("200 als Download mit festem Namen und no-store", async () => {
    let gelesen = "";
    const antwort = await pdf(`art=pflegegeld&sitzung=${SITZUNG}`, {
      lesen: async (datei) => {
        gelesen = datei;
        return new TextEncoder().encode("%PDF-1.7");
      },
    });
    expect(antwort.status).toBe(200);
    expect(gelesen).toBe(path.join(ORDNER, `pflegegeld-${SITZUNG}-entwurf.pdf`));
    expect(antwort.headers.get("content-type")).toBe("application/pdf");
    expect(antwort.headers.get("content-disposition")).toBe('attachment; filename="antrag-pflegegeld-entwurf.pdf"');
    expect(antwort.headers.get("cache-control")).toBe("no-store");
    expect(await antwort.text()).toBe("%PDF-1.7");
  });
});
