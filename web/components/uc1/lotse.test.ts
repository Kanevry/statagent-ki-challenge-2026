// @vitest-environment node
import { describe, expect, it, vi } from "vitest";
import { erstelleLotseAntwort, lotseArgv, MAX_BODY_BYTES, type Ausfuehren } from "./lotse";

const KERN = {
  text: "Pflegegeld kommt in Frage.",
  verhalten: "antwort",
  sitzung_id: "3f1c2a9e-0000-4000-8000-000000000001",
  aussagen: [
    {
      text: "Pflegegeld gibt es ab sechs Monaten Bedarf.",
      zitat: "voraussichtlich mindestens sechs Monate",
      abschnitt_id: 14171,
      schluessel: "BPGG § 4",
      stand: "2015-01-01",
      betrag: false,
      hinweis_hoehe: false,
      treffer: { volltext: "GEHEIMER VOLLTEXT DES ABSCHNITTS" },
      deckung: 0.9,
      angebot: false,
    },
    {
      text: "Dort beantragt man Pflege zu Hause.",
      zitat: "Pflege und Betreuung zu Hause",
      abschnitt_id: 1,
      schluessel: "Anträge und Formulare/FSW_Antrag_2024.pdf, S. 5",
      stand: null,
      betrag: false,
      hinweis_hoehe: false,
      treffer: {},
      deckung: null,
      angebot: true,
    },
  ],
  belege: [
    { abschnitt_id: 14171, zitat: "…", quelle: "BPGG § 4", stand: "2015-01-01" },
    { abschnitt_id: 1, zitat: "…", quelle: "FSW-Antrag auf Förderung, S. 5", stand: null },
  ],
  rueckfrage: null,
  traeger: [{ leistung: "pflegegeld", name: "Pensionsversicherungsanstalt (PVA)" }],
  naechste_schritte: ["Antrag stellen."],
  modell: "gpt-5-4-mini",
  provider: "azure",
  dauer_ms: { gesamt: 1200 },
  grenze: false,
  grenze_art: null,
  uebergabe_an: null,
  lage: "Pflegebedarf",
  leistungen: ["pflegegeld"],
  angaben: { status: "pva" },
  antrag: {},
  antraege: ["pflegegeld"],
  begriffe: [],
  verworfen: [{ text: "verworfen" }],
  sprache: "de",
  stil: "einfach",
  satzlaenge: 9.5,
  hinweise: [],
  modus: "live",
  angebot_zitiert: true,
};

function anfrage(body: unknown): Request {
  return new Request("http://localhost/api/uc1/frage", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
}

function handler(ausfuehren: Ausfuehren, umgebung: Record<string, string | undefined> = {}) {
  return erstelleLotseAntwort({ ausfuehren, umgebung, wurzel: () => "/repo" });
}

describe("lotseArgv", () => {
  // Fängt: Text ohne „--“ davor würde als Schalter gelesen („-h“ zeigt die Hilfe statt einer Antwort).
  it("setzt -- vor den Text und lässt „-h“ als Text", () => {
    expect(lotseArgv({ text: "-h", stil: "standard" })).toEqual([
      "run", "--frozen", "--package", "uc1", "lotse", "frage", "--json", "--stil", "standard", "--", "-h",
    ]);
  });

  // Fängt: Folgefrage ohne Sitzung (Rückfrage verliert den Zusammenhang) oder falsche Reihenfolge der Schalter.
  it("reicht Sitzung, Stil und Sprache vor dem Text durch", () => {
    const sitzung = "3f1c2a9e-0000-4000-8000-000000000001";
    expect(lotseArgv({ text: "Ja", sitzung, stil: "einfach", sprache: "en" }).slice(7)).toEqual([
      "--sitzung", sitzung, "--stil", "einfach", "--sprache", "en", "--", "Ja",
    ]);
  });
});

describe("POST /api/uc1/frage", () => {
  // Fängt: Online-Demo startet doch einen Modell-Lauf, oder die Seite bekommt keinen Hinweis auf das Beispiel.
  it("403 mit replay bei KIC_ONLINE_LESEND=1, ohne Subprozess", async () => {
    const ausfuehren = vi.fn<Ausfuehren>();
    const antwort = await handler(ausfuehren, { KIC_ONLINE_LESEND: "1" })(anfrage({ text: "Hallo" }));
    expect(antwort.status).toBe(403);
    expect(await antwort.json()).toMatchObject({ replay: true });
    expect(ausfuehren).not.toHaveBeenCalled();
  });

  // Fängt: fehlende Body-Grenze (beliebig große Bodies landen im Speicher).
  it("413 über 4 KiB", async () => {
    const ausfuehren = vi.fn<Ausfuehren>();
    const antwort = await handler(ausfuehren)(anfrage({ text: "x".repeat(MAX_BODY_BYTES) }));
    expect(antwort.status).toBe(413);
    expect(ausfuehren).not.toHaveBeenCalled();
  });

  // Fängt: zod-Fehlertexte (englisch, intern) im Client und Läufe mit leerem oder falschem Text.
  it("400 mit deutschem Satz bei leerem Text, fehlendem Feld und kaputter Sitzung", async () => {
    const ausfuehren = vi.fn<Ausfuehren>();
    const h = handler(ausfuehren);
    for (const body of [{ text: "  " }, { frage: "Hallo" }, "kein json", { text: "Ja", sitzung: "abc" }, { text: "x".repeat(1001) }]) {
      const antwort = await h(anfrage(body));
      expect(antwort.status).toBe(400);
      const { fehler } = (await antwort.json()) as { fehler: string };
      expect(fehler).toMatch(/^[A-ZÄÖÜ]/);
      expect(fehler).not.toMatch(/Invalid|expected/i);
    }
    expect(ausfuehren).not.toHaveBeenCalled();
  });

  // Fängt: unbegrenzt viele Python-Prozesse gleichzeitig; und einen Zähler, der nach dem Lauf nicht frei wird.
  it("429 beim dritten gleichzeitigen Lauf, danach wieder frei", async () => {
    const offen: Array<() => void> = [];
    const ausfuehren: Ausfuehren = () =>
      new Promise((fertig) => offen.push(() => fertig({ code: 0, stdout: JSON.stringify(KERN) })));
    const h = handler(ausfuehren);
    const erste = [h(anfrage({ text: "a" })), h(anfrage({ text: "b" }))];
    await vi.waitFor(() => expect(offen).toHaveLength(2));
    expect((await h(anfrage({ text: "c" }))).status).toBe(429);
    offen.forEach((f) => f());
    expect((await Promise.all(erste)).map((a) => a.status)).toEqual([200, 200]);
    const vierte = h(anfrage({ text: "d" }));
    await vi.waitFor(() => expect(offen).toHaveLength(3));
    offen[2]?.();
    expect((await vierte).status).toBe(200);
  });

  // Fängt: Exit 2 („Kern noch nicht gebaut“ auf main) als 200 oder 500 statt 503 mit Replay-Angebot.
  it("503 mit replay bei Exit 2, kaputtem JSON und Timeout", async () => {
    const faelle: Ausfuehren[] = [
      async () => ({ code: 2, stdout: "" }),
      async () => ({ code: 0, stdout: "{kaputt" }),
      async () => ({ code: 0, stdout: JSON.stringify({ ...KERN, sitzung_id: undefined }) }),
      async () => {
        throw Object.assign(new Error("timeout"), { name: "TimeoutError" });
      },
    ];
    vi.spyOn(console, "warn").mockImplementation(() => {});
    for (const ausfuehren of faelle) {
      const antwort = await handler(ausfuehren)(anfrage({ text: "Hallo" }));
      expect(antwort.status).toBe(503);
      expect(await antwort.json()).toEqual({ fehler: "Der Lotse ist gerade nicht erreichbar.", replay: true });
    }
  });

  // Fängt: Volltext der Treffer, Deckung und verworfene Aussagen im Browser; Dateipfad statt Kurzform als Quelle.
  it("200 bildet auf die Web-Form ab: ohne treffer, deckung, verworfen; Quelle aus belege", async () => {
    let argv: readonly string[] = [];
    const antwort = await handler(async (_b, a) => {
      argv = a;
      return { code: 0, stdout: JSON.stringify(KERN) };
    })(anfrage({ text: "Mutter 84", stil: "einfach" }));
    expect(antwort.status).toBe(200);
    const roh = await antwort.text();
    expect(roh).not.toMatch(/treffer|deckung|verworfen|GEHEIMER|\.pdf|angaben|dauer_ms/);
    const daten = JSON.parse(roh);
    expect(daten.aussagen.map((a: { quelle: string }) => a.quelle)).toEqual(["BPGG § 4", "FSW-Antrag auf Förderung, S. 5"]);
    expect(daten.aussagen[0]).toEqual({
      text: "Pflegegeld gibt es ab sechs Monaten Bedarf.",
      zitat: "voraussichtlich mindestens sechs Monate",
      quelle: "BPGG § 4",
      stand: "2015-01-01",
      betrag: false,
      hinweis_hoehe: false,
      angebot: false,
    });
    expect(daten).toMatchObject({ verhalten: "antwort", modell: "gpt-5-4-mini", antraege: ["pflegegeld"] });
    expect(argv).toContain("einfach");
  });
});
