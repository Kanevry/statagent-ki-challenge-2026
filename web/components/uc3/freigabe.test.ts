import { describe, expect, it, vi } from "vitest";
import { UC3_ARGV, type Ausfuehren, type CliLauf } from "./cli";
import {
  auftraggeber,
  auftragsZitat,
  entscheidungArgv,
  ergebnisPfad,
  erstelleFreigabeAntwort,
  gesamtZeile,
  GRUND_UNBEKANNT,
  gruppenSatz,
  isoZeit,
  klartext,
  kurzerGrund,
  probeTitel,
  umverteilung,
  vorschlagId,
  waage,
  waageBeleg,
  waageSatz,
  wirkungJeKategorie,
  aenderungSatz,
  auftragKopf,
  freigabenKopf,
  kurzZeit,
  ohneProbeSatz,
  probeJeKategorie,
  protokollZeilen,
  vorgeschlagenVon,
  type ErledigtZeile,
} from "./freigabe";

// Nie die echte CLI: jeder Handler bekommt ein gefälschtes `ausfuehren` (die Prozessgrenze); der Aufbau des
// Aufrufs aus cli.ts (uv, UC3_ARGV, argv) bleibt echt.

function anfrage(body: unknown): Request {
  return new Request("http://localhost/api/uc3/freigabe", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
}

function fake(lauf: Partial<CliLauf> = {}) {
  return vi.fn<Ausfuehren>(async () => ({ code: 0, stdout: "", stderr: "", ...lauf }));
}

const freigabeJson = JSON.stringify({
  vorschlag_id: 1,
  name: "Anna Beispiel",
  commit_hash: "a81f3c2",
  angewendet: true,
  fehler: null,
  meldung: null,
  freigegeben_am: "2026-11-05 14:06:41.123456+01:00",
  ref: "v2/R6_beschaeftigungskategorie",
  protokoll_id: 1,
});

function handler(ausfuehren: Ausfuehren, umgebung: Record<string, string | undefined> = {}) {
  return erstelleFreigabeAntwort({ ausfuehren, umgebung, wurzel: () => "/repo" });
}

describe("POST /api/uc3/freigabe", () => {
  it("Fehler: Online-Demo könnte freigeben. KIC_ONLINE_LESEND=1 sperrt vor dem Subprozess", async () => {
    const aus = fake({ stdout: freigabeJson });
    const antwort = await handler(aus, { KIC_ONLINE_LESEND: "1" })(
      anfrage({ id: 1, name: "Anna Beispiel", entscheidung: "ja" }),
    );
    expect(antwort.status).toBe(403);
    expect((await antwort.json()).fehler).toBe("In der Online-Demo kann nichts freigegeben werden.");
    expect(aus).not.toHaveBeenCalled();
  });

  it("Fehler: eine Rolle gibt frei. „Team“ wird vor dem Subprozess abgewiesen", async () => {
    const aus = fake({ stdout: freigabeJson });
    for (const name of ["Team", "Team Statistik"]) {
      const antwort = await handler(aus)(anfrage({ id: 1, name, entscheidung: "ja" }));
      expect(antwort.status).toBe(400);
    }
    expect(aus).not.toHaveBeenCalled();
  });

  it("Fehler: Shell-Injektion über die Begründung. Sie ist ein eigenes argv-Element", async () => {
    const aus = fake({ stdout: JSON.stringify({ id: 1, status: "abgelehnt", protokoll_id: 1 }) });
    const begruendung = "Passt nicht; rm -rf / && echo $(whoami)";
    const antwort = await handler(aus)(anfrage({ id: 1, name: "Anna Beispiel", entscheidung: "nein", begruendung }));
    expect(antwort.status).toBe(200);
    const [befehl, argv] = aus.mock.calls[0]!;
    expect(befehl).toBe("uv");
    expect(argv).toEqual([
      ...UC3_ARGV,
      "ablehnen", "1", "--name", "Anna Beispiel", "--begruendung", begruendung, "--json",
    ]);
  });

  it("Fehler: Ablehnung ohne Begründung erreicht die CLI", async () => {
    const aus = fake();
    const antwort = await handler(aus)(anfrage({ id: 1, name: "Anna Beispiel", entscheidung: "nein", begruendung: "  " }));
    expect(antwort.status).toBe(400);
    expect(aus).not.toHaveBeenCalled();
  });

  it("Fehler: stderr landet beim Client. Bekannter Fehler → 409 mit festem Satz, nichts aus stderr", async () => {
    const stderr =
      "nicht freigegeben: Vorschlag uc3/1 ist bereits freigegeben, angewendet in /Users/x/Projects/repo/uc3\nTraceback (most recent call last):\n  File \"/opt/geheim.py\"";
    const aus = fake({ code: 1, stderr });
    const antwort = await handler(aus)(anfrage({ id: 1, name: "Anna Beispiel", entscheidung: "ja" }));
    expect(antwort.status).toBe(409);
    const daten = await antwort.json();
    expect(daten.grund).toBe("Über diese Änderung ist schon entschieden.");
    const text = JSON.stringify(daten);
    for (const teil of ["/Users", "Traceback", "geheim", "uc3/1", "angewendet in"]) expect(text).not.toContain(teil);
  });

  it("Fehler: Git-Fehler mit Pfad erreicht den Client. GitFehler → fester Satz, kein Pfad, kein git-Text", async () => {
    const stderr =
      "nicht freigegeben: git commit: fatal: Unable to create '/Users/anna/Projects/ki-challenge/.git/index.lock': File exists.";
    const antwort = await handler(fake({ code: 1, stderr }))(anfrage({ id: 1, name: "Anna Beispiel", entscheidung: "ja" }));
    expect(antwort.status).toBe(409);
    const daten = await antwort.json();
    expect(daten).toEqual({
      fehler: GRUND_UNBEKANNT,
      grund: GRUND_UNBEKANNT,
    });
    const text = JSON.stringify(daten);
    for (const teil of ["/Users", "index.lock", "git", "fatal"]) expect(text).not.toContain(teil);
  });

  it("Fehler: gespeicherte Freigabe, deren Anwenden scheiterte, gilt als abgewiesen. Exit 1 mit JSON → 200", async () => {
    const stdout = JSON.stringify({ ...JSON.parse(freigabeJson), angewendet: false, fehler: "RegelKonflikt" });
    const antwort = await handler(fake({ code: 1, stdout }))(anfrage({ id: 1, name: "Anna Beispiel", entscheidung: "ja" }));
    expect(antwort.status).toBe(200);
    expect(await antwort.json()).toMatchObject({ angewendet: false, commit: "a81f3c2" });
  });

  it("Fehler: Zeit der Freigabe ist die Browser-Uhr. Exit 0 liefert freigegeben_am als ISO", async () => {
    const aus = fake({ stdout: freigabeJson });
    const antwort = await handler(aus)(anfrage({ id: 1, name: "  Anna   Beispiel ", entscheidung: "ja" }));
    expect(antwort.status).toBe(200);
    expect(await antwort.json()).toEqual({
      zeitpunkt: "2026-11-05T14:06:41.123+01:00",
      commit: "a81f3c2",
      protokoll_id: 1,
      angewendet: true,
    });
    expect(aus.mock.calls[0]![1]).toEqual([...UC3_ARGV, "freigabe", "1", "--name", "Anna Beispiel", "--json"]);
  });

  it("Fehler: Timeout bringt den Server zum Absturz. Startfehler → 502", async () => {
    const aus = vi.fn<Ausfuehren>(async () => {
      throw Object.assign(new Error("spawn uv ENOENT /Users/x"), { name: "Error" });
    });
    const antwort = await handler(aus)(anfrage({ id: 1, name: "Anna Beispiel", entscheidung: "ja" }));
    expect(antwort.status).toBe(502);
    expect(JSON.stringify(await antwort.json())).not.toContain("/Users");
  });

  it("Fehler: Body ohne Grenze. Über 4 KiB → 413, ungültige ID → 400", async () => {
    const aus = fake();
    const gross = await handler(aus)(anfrage({ id: 1, name: "Anna Beispiel", entscheidung: "ja", x: "a".repeat(5000) }));
    expect(gross.status).toBe(413);
    for (const id of [0, -1, 1.5, "1"]) {
      expect((await handler(aus)(anfrage({ id, name: "Anna Beispiel", entscheidung: "ja" }))).status).toBe(400);
    }
    expect(aus).not.toHaveBeenCalled();
  });

  it("Fehler: zwei Freigaben gleichzeitig schreiben denselben Commit. Die zweite → 429", async () => {
    let loesen: (l: CliLauf) => void = () => {};
    const aus = vi.fn<Ausfuehren>(() => new Promise((r) => (loesen = r)));
    const h = handler(aus);
    const erste = h(anfrage({ id: 1, name: "Anna Beispiel", entscheidung: "ja" }));
    await vi.waitFor(() => expect(aus).toHaveBeenCalledTimes(1));
    const zweite = await h(anfrage({ id: 2, name: "Anna Beispiel", entscheidung: "ja" }));
    expect(zweite.status).toBe(429);
    loesen({ code: 0, stdout: freigabeJson, stderr: "" });
    expect((await erste).status).toBe(200);
  });
});

describe("Freigabe-Waage", () => {
  const probe = {
    "2025-10": {
      lieferung: "2025-10",
      vorher: {
        regelsatz: "v1",
        gesamt: 410587,
        zellen: 100,
        je_merkmal: {
          qualifikation: { ArbeiterDV: 200000, ArbeiterFD: 10000, AngestellteDV: 190000, AngestellteFD: 10587 },
          geschlecht: { M: 210000, W: 200587 },
        },
      },
      nachher: {
        regelsatz: "v2",
        gesamt: 410587,
        zellen: 80,
        je_merkmal: { qualifikation: { Arbeiter: 210000, Angestellte: 200587 }, geschlecht: { M: 210000, W: 200587 } },
      },
      differenz_gesamt: 0,
    },
  };

  it("Fehler: Umschlüsselung darf nicht als Zuwachs erscheinen. Gesamt gleich → Hauptzeile ist die Gesamtzahl", () => {
    const w = waage(probe, { qualifikation: { Arbeiter: "Arbeiter", ArbeiterDV: "Arbeiter DV" } });
    expect(w).not.toBeNull();
    expect(w!.umverteilung).toBe(true);
    // Nicht „Arbeiter 0 → 210.000“ groß: das läse sich wie 210.000 zusätzliche Verhältnisse.
    expect(w!.haupt).toMatchObject({ merkmal: "gesamt", vorher: 410587, nachher: 410587, differenz: 0 });
    expect(waageSatz(w!)).toBe("Im Oktober 2025 verteilen sich die 410.587 Beschäftigungsverhältnisse neu, gesamt bleibt 410.587.");
    // Alle verschobenen Kategorien stehen darunter, unveränderte (Geschlecht) nicht.
    expect(w!.weitere).toHaveLength(6);
    expect(w!.weitere.map((z) => z.merkmal)).not.toContain("geschlecht");
    expect(w!.weitere.find((z) => z.code === "Arbeiter")).toMatchObject({ vorher: 0, nachher: 210000 });
    expect(w!.weitere.find((z) => z.code === "ArbeiterDV")).toMatchObject({ vorher: 200000, nachher: 0 });
    expect(gesamtZeile(w!)).toBeNull();
    // Beleg der Hauptzeile zielt auf die Gesamtzahl.
    expect(waageBeleg(1, w!).sql).toContain("probe->'2025-10'->'vorher'->>'gesamt'");
  });

  // Fehler, den das fängt: „25-34 (altersgruppe)“ und „C (oenace)“ auf der Seite, ein ÖNACE-Abschnitt als Hauptzeile
  // oder rund 30 Zeilen mehr bei jeder Stichtags-Änderung (!150, #168).
  it("zeigt Altersgruppe und Branche lesbar und nur, wenn sich die Grundgliederung nicht ändert", () => {
    const probeMit = (vorher: Record<string, Record<string, number>>, nachher: Record<string, Record<string, number>>, gesamtNachher = 100) => ({
      "2025-10": {
        lieferung: "2025-10",
        vorher: { gesamt: 100, je_merkmal: vorher },
        nachher: { gesamt: gesamtNachher, je_merkmal: nachher },
      },
    });
    const nurAlter = waage(probeMit({ altersgruppe: { "25-34": 40, "35-44": 60 } }, { altersgruppe: { "25-34": 45, "35-44": 55 } }))!;
    expect(nurAlter.weitere.map((z) => z.bezeichnung)).toEqual(["25-34 (Altersgruppe)", "35-44 (Altersgruppe)"]);
    const nurBranche = waage(probeMit({ oenace: { C: 10 } }, { oenace: { C: 20 } }, 110))!;
    expect(nurBranche.haupt.bezeichnung).toBe("Abschnitt C (Branche)");
    const mitKategorie = waage(
      probeMit(
        { qualifikation: { Arbeiter: 50 }, oenace: { C: 10 }, altersgruppe: { "25-34": 40 } },
        { qualifikation: { Arbeiter: 55 }, oenace: { C: 500 }, altersgruppe: { "25-34": 400 } },
        105,
      ),
    )!;
    expect(mitKategorie.haupt.merkmal).toBe("qualifikation");
    expect(mitKategorie.weitere).toHaveLength(0);
  });

  it("Fehler: Gesamtzahl ändert sich unbemerkt. Hauptzeile ist die Kategorie, dazu eine Zeile zur Gesamtzahl", () => {
    const monat = probe["2025-10"];
    const mitZuwachs = {
      "2025-10": {
        ...monat,
        nachher: {
          ...monat.nachher,
          gesamt: 412000,
          je_merkmal: { ...monat.vorher.je_merkmal, qualifikation: { ...monat.vorher.je_merkmal.qualifikation, ArbeiterDV: 201413 } },
        },
      },
    };
    const w = waage(mitZuwachs)!;
    expect(w.umverteilung).toBe(false);
    expect(w.haupt).toMatchObject({ code: "ArbeiterDV", vorher: 200000, nachher: 201413 });
    expect(gesamtZeile(w)).toMatchObject({ merkmal: "gesamt", vorher: 410587, nachher: 412000, differenz: 1413 });
    expect(waageBeleg(1, w, gesamtZeile(w)!).sql).toContain("->'nachher'->>'gesamt'");
  });

  it("Fehler: leere Probe erfindet Zahlen. Ohne Probe → null", () => {
    expect(waage({})).toBeNull();
    expect(waage({ "2025-10": { lieferung: "2025-10", hinweis: "Code-Datei ändert keine Zahl" } })).toBeNull();
  });

  it("Fehler: Beleg zeigt eine andere Zahl als die Waage. SQL zielt auf genau Merkmal und Code", () => {
    const w = waage(probe)!;
    const sql = waageBeleg(1, w, w.weitere.find((z) => z.code === "Arbeiter")).sql ?? "";
    expect(sql).toContain("probe->'2025-10'->'nachher'->'je_merkmal'->'qualifikation'->>'Arbeiter'");
    expect(sql).toContain("->'vorher'->");
    expect(sql).toContain("WHERE id = 1;");
  });
});

describe("Hilfen", () => {
  it("Fehler: Regeländerung ohne Wortlaut. Klartext mit - und + nur für geänderte Werte", () => {
    const { worte, diff } = klartext({
      typ: "regel_aendern",
      aenderungen: [
        {
          regel_name: "R6",
          parameter_alt: { qualifikation: "code", gleich: 1 },
          parameter_neu: { qualifikation: "beschaeftigungskategorie", gleich: 1 },
        },
      ],
    });
    expect(worte).toEqual(["In der Regel R6 wird „qualifikation“ von „code“ auf „beschaeftigungskategorie“ geändert."]);
    expect(diff).toBe("- R6: qualifikation = „code“\n+ R6: qualifikation = „beschaeftigungskategorie“");
  });

  it("Fehler: Ergebnis-Link zeigt nach der Freigabe die alten Zahlen. Er trägt den Regelsatz", () => {
    expect(ergebnisPfad({ monat: "2025-10", regelsatz: "v2" })).toBe("/uc3/laeufe/2025-10?regelsatz=v2");
  });

  it("Fehler: Routen-ID „1abc“ oder „0“ öffnet einen Vorschlag", () => {
    expect(vorschlagId("1")).toBe(1);
    for (const t of ["0", "1abc", "-1", "01", "99999999999"]) expect(vorschlagId(t)).toBeNull();
  });

  it("Fehler: Python-Zeit ohne T zeigt im Browser „Invalid Date“", () => {
    expect(isoZeit("2026-11-05 14:41:07.655871+01:00")).toBe("2026-11-05T14:41:07.655+01:00");
    expect(isoZeit("2026-11-05 14:41:07+01")).toBe("2026-11-05T14:41:07+01:00");
    expect(isoZeit("None")).toBeNull();
  });

  it("Fehler: CLI-Text wird durchgereicht. Bekannte Fehler → fester Satz, alles andere → Standardsatz", () => {
    expect(kurzerGrund("Traceback /opt/x.py")).toBe(GRUND_UNBEKANNT);
    expect(kurzerGrund("nicht freigegeben: Rollenbezeichnung statt Name: 'team'")).toBe("Bitte Vor- und Nachname eingeben.");
    expect(kurzerGrund("nicht freigegeben: Vorschlag 7 ist abgelehnt, nicht offen")).toBe(
      "Über diese Änderung ist schon entschieden.",
    );
    expect(kurzerGrund("nicht abgelehnt: Vorschlag uc3/9 gibt es nicht")).toBe("Diesen Vorschlag gibt es nicht.");
    expect(kurzerGrund("nicht abgelehnt: Eine Ablehnung braucht eine Begründung")).toBe(
      "Eine Ablehnung braucht eine Begründung.",
    );
    expect(kurzerGrund("nicht freigegeben: objekt_ref '/Users/x' liegt nicht innerhalb des Repos")).toBe(GRUND_UNBEKANNT);
    expect(entscheidungArgv({ id: 3, name: "Anna Beispiel", entscheidung: "ja" })).toEqual([
      "freigabe", "3", "--name", "Anna Beispiel", "--json",
    ]);
  });
});

describe("Probe für Auftrag 1 (Umverteilung)", () => {
  // Probe wie in meta.vorschlag id 24: Monat nur als Schlüssel des jsonb, ohne Feld „lieferung“.
  const probe = {
    "2024-08": {
      vorher: {
        gesamt: 392236,
        je_merkmal: {
          qualifikation: { Beamte: 13562, ArbeiterDV: 141331, ArbeiterFD: 382, AngestellteDV: 235819, AngestellteFD: 1142 },
        },
      },
      nachher: {
        gesamt: 392236,
        je_merkmal: { qualifikation: { Beamte: 13562, Arbeiter: 141713, Angestellte: 236961 } },
      },
    },
  };
  const kategorien = {
    ArbeiterDV: { kategorie: "Arbeiter", frei: false },
    ArbeiterFD: { kategorie: "Arbeiter", frei: true },
    AngestellteDV: { kategorie: "Angestellte", frei: false },
    AngestellteFD: { kategorie: "Angestellte", frei: true },
    Beamte: { kategorie: "Beamte", frei: false },
  };

  // Fehler, den das fängt: Monat aus dem Feld „lieferung“ statt aus dem Schlüssel; dann fehlt „Probe für August 2024“.
  it("nimmt den Probemonat aus dem Schlüssel", () => {
    const w = waage(probe);
    expect(w?.lieferung).toBe("2024-08");
    expect(probeTitel(w?.lieferung ?? "")).toBe("Probe für August 2024");
  });

  // Fehler, den das fängt: groß stand „Δ 0“, die eigentliche Änderung (Zusammenlegung) fehlte.
  it("sagt je Kategorie, woraus sie besteht", () => {
    const u = umverteilung(probe, kategorien);
    expect(u?.gruppen.map((g) => gruppenSatz(g))).toEqual([
      "Angestellte 236.961 = 235.819 mit Dienstvertrag + 1.142 freie Dienstverträge",
      "Arbeiter 141.713 = 141.331 mit Dienstvertrag + 382 freie Dienstverträge",
    ]);
    expect(u?.bleibt).toEqual([{ code: "Beamte", wert: 13562 }]);
    expect(u?.gesamt).toBe(392236);
  });

  // Fehler, den das fängt (auch: vorher zeigte dieselbe Summe wie nachher, die Umverteilung war unsichtbar): Tabelle „vorher | nachher“ zeigt Codes (ArbeiterDV) statt Kategorien oder verliert Beamte.
  it("fasst die Probe je Beschäftigungskategorie zur Tabelle zusammen", () => {
    expect(probeJeKategorie(probe, kategorien)).toEqual({
      lieferung: "2024-08",
      zeilen: [
        { kategorie: "Angestellte", vorher: 236961, nachher: 236961, vorherTeile: [{ wort: "Angestellte mit Dienstvertrag", wert: 235819 }, { wort: "Angestellte freier Dienstvertrag", wert: 1142 }] },
        { kategorie: "Arbeiter", vorher: 141713, nachher: 141713, vorherTeile: [{ wort: "Arbeiter mit Dienstvertrag", wert: 141331 }, { wort: "Arbeiter freier Dienstvertrag", wert: 382 }] },
        { kategorie: "Beamte", vorher: 13562, nachher: 13562, vorherTeile: [{ wort: "Beamte", wert: 13562 }] },
      ],
      gesamt: { vorher: 392236, nachher: 392236 },
    });
    expect(probeJeKategorie(null, kategorien)).toBeNull();
  });

  it("erfindet keine Zusammensetzung, wenn die Summe nicht stimmt", () => {
    const falsch = structuredClone(probe);
    falsch["2024-08"].nachher.je_merkmal.qualifikation.Arbeiter = 141700;
    expect(umverteilung(falsch, kategorien)).toBeNull();
  });
});

describe("wirkungJeKategorie", () => {
  // Orakel Juli 2026, Regelsatz v1: Arbeiter 143.076, Angestellte 243.817, Beamte 12.134 (zusammen 399.027).
  it("fasst die Codes des v1-Laufs je Kategorie zusammen", () => {
    const lauf = { regelsatz: "v1" } as never;
    const zeilen = wirkungJeKategorie(
      {
        monat: "2026-07",
        basis: {
          lauf,
          je: { AngestellteDV: 242665, AngestellteFD: 1152, ArbeiterDV: 142684, ArbeiterFD: 392, Beamte: 12134 },
          gesamt: 399027,
        },
        ziel: { lauf, je: {}, gesamt: 0 },
        auchImZiel: [],
      },
      {
        ArbeiterDV: { kategorie: "Arbeiter", frei: false },
        ArbeiterFD: { kategorie: "Arbeiter", frei: true },
        AngestellteDV: { kategorie: "Angestellte", frei: false },
        AngestellteFD: { kategorie: "Angestellte", frei: true },
        Beamte: { kategorie: "Beamte", frei: false },
      },
    );
    expect(zeilen.map((z) => [z.kategorie, z.basis])).toEqual([
      ["Angestellte", 243817],
      ["Arbeiter", 143076],
      ["Beamte", 12134],
    ]);
  });
});

describe("Auftragszitat (Sichtprüfung bb, #18)", () => {
  // Fehler: das Zitat zeigte die Arbeitsanweisung an den Agenten samt Dateinamen und Spaltennamen.
  it("zeigt nur den fachlichen Auftrag", () => {
    const anweisung =
      "Auftrag 1, Dienstvertrag und freier Dienstvertrag zusammen: In der Statistik wird nicht mehr unterschieden. Die Beschäftigungskategorie hat nur noch drei Ausprägungen (siehe Spalte BESCHAEFTIGUNGSKATEGORIE in qualifikation.csv). Die Änderung gilt rückwirkend. Ändere dafür nur die Zählregel. Ziel ist der neue Regelsatz v2.";
    expect(auftragsZitat(anweisung)).toBe(
      "In der Statistik wird nicht mehr unterschieden. Die Beschäftigungskategorie hat nur noch drei Ausprägungen. Die Änderung gilt rückwirkend.",
    );
    expect(auftraggeber({ gesagtVon: null, anweisung })).toBe("Änderungsauftrag aus der Aufgabenstellung");
  });

  // Fehler (Review !77 Runde 2): jeder Doppelpunkt in den ersten 120 Zeichen schnitt den Anfang ab.
  it("schneidet nur einen erkannten Titel „Auftrag N …:“ ab", () => {
    expect(auftragsZitat("Fasse Gruppen zusammen: Die Gesamtzahl bleibt gleich.")).toBe(
      "Fasse Gruppen zusammen: Die Gesamtzahl bleibt gleich.",
    );
    expect(auftragsZitat("Auftrag 2, ganzes Monat: Gezählt wird das ganze Monat.")).toBe("Gezählt wird das ganze Monat.");
  });
});

describe("Sätze der Freigabe-Seiten (UI-Regie v1)", () => {
  // Fehler, den das fängt: Zeit in UTC oder mit Jahr und Komma statt „05.11. 16:53“ in Wiener Zeit.
  it("schreibt die Zeit kurz in Wiener Zeit", () => {
    expect(kurzZeit("2026-11-05T15:53:10Z")).toBe("05.11. 16:53");
    expect(kurzZeit("kein Datum")).toBe("kein Datum");
  });

  // Fehler, den das fängt: der Zeilentitel ist der ganze 15-zeilige Auftrag statt des Teils vor dem Doppelpunkt.
  it("nimmt den Titel aus dem Teil vor dem Doppelpunkt", () => {
    expect(auftragKopf("Auftrag 2, ganzes Monat statt Stichtag: Gezählt wird nicht mehr der Monatsletzte.")).toEqual({
      nummer: "2",
      titel: "Ganzes Monat statt Stichtag",
    });
    expect(auftragKopf("Regelsatz v2 freigeben")).toEqual({ nummer: null, titel: "Regelsatz v2 freigeben" });
  });

  // Fehler, den das fängt: Regelcodes wie R6_… im Fließtext der Zeile.
  it("sagt ohne Regelcode, was sich ändert", () => {
    const satz = aenderungSatz({ typ: "regel_aendern", aenderungen: [{ regel_name: "R6_beschaeftigungskategorie" }], regelsatzZiel: "v2" });
    expect(satz).toBe("Ändert eine Regel im Regelsatz v2");
    expect(aenderungSatz({ typ: "regel_neu", aenderungen: [{}], regelsatzZiel: "ministerium" })).toBe(
      "Neue Regel für die Ministeriums-Lieferung",
    );
  });

  // Fehler, den das fängt: Kopf sagt „Nichts wartet“, obwohl drei Änderungen entschieden sind.
  it("bildet den Kopfsatz aus den Daten", () => {
    const frei = { art: "freigegeben" as const };
    expect(freigabenKopf(0, [frei, frei, frei])).toBe("3 Änderungen, alle mit Namen freigegeben.");
    expect(freigabenKopf(1, [frei])).toBe("1 Änderung wartet auf Ihre Freigabe.");
    expect(freigabenKopf(0, [frei, { art: "abgelehnt" }])).toBe("2 Änderungen mit Namen entschieden: 1 freigegeben, 1 abgelehnt.");
    expect(freigabenKopf(0, [])).toBe("Noch hat kein Agent eine Änderung vorgeschlagen.");
  });

  it("nennt Agent, Anbieter und Modell", () => {
    expect(vorgeschlagenVon({ rolle: "klassifikation", provider: "azure", modell: "gpt-5-4-mini" })).toBe(
      "Vorgeschlagen vom Klassifikations-Agenten (Azure gpt-5-4-mini)",
    );
    expect(vorgeschlagenVon({ rolle: "qs", provider: null, modell: null })).toBe("Vorgeschlagen vom Prüf-Agenten");
  });

  // Fehler, den das fängt: Auftrag 3 sagt „Probe noch nicht gerechnet“, obwohl es nie ein vorher und nachher gibt.
  it("begründet eine fehlende Probe", () => {
    expect(ohneProbeSatz({ typ: "regel_neu", regelsatzZiel: "ministerium" })).toMatch(/Ministeriums-Lieferung/);
    expect(ohneProbeSatz({ typ: "regel_aendern", regelsatzZiel: "v2" })).toMatch(/noch nicht gerechnet/);
  });

  // Fehler, den das fängt: 72 Zeilen „Regelstand … für Monat“ derselben Person in derselben Minute.
  it("fasst die Regelstände eines Regelsatzes zu einer Zeile zusammen", () => {
    const basis = { art: "freigegeben" as const, name: "Erika Muster", anweisung: null, geaendert: null, begruendung: null, commit: null, vorschlag: null, waage: null };
    const zeilen: ErledigtZeile[] = [
      { ...basis, schluessel: "r1", zeit: "2026-11-05T15:54:00Z", regelstand: { regelsatz: "v2", lieferung: "2024-09" } },
      { ...basis, schluessel: "r2", zeit: "2026-11-05T15:54:01Z", regelstand: { regelsatz: "v2", lieferung: "2024-08" } },
      { ...basis, schluessel: "f1", zeit: "2026-11-05T15:53:00Z", anweisung: "Regelsatz v2 freigeben" },
    ];
    expect(protokollZeilen(zeilen).map((z) => z.satz)).toEqual([
      "Regeln von Regelsatz v2 für 2 Monate festgehalten, August 2024 bis September 2024",
      "Regelsatz v2 freigeben",
    ]);
  });
});
