import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ereignisseJson from "../../app/api/uc2/_fixtures/ereignisse-mock.json";
import { mockEreignisse, MOCK_ABBRUCH } from "../../app/api/uc2/_lib/mock";
import { modellWahl } from "../../app/api/uc2/_lib/vorbereitung";
import { MAX_ZITAT, klartext, ohneStriche, zitatText } from "./namen";
import { grundSatz } from "./fehler-karte";
import { PanelAnsicht, sprecherText, titelText } from "./panel-ansicht";
import { ableiten, type FallZustand } from "./zustand";
import { abbruchMitAnbieter, mitAnbieter } from "./testhilfen";

// Fängt ab: Persona ohne Haltung, Herkunft ohne Medium und Monat, Moderator-Spur fehlt oder vermischt sich mit den
// Personas, Zitate über 300 Zeichen, Gedankenstriche im sichtbaren Text, Abbruch, der die fertigen Runden verschluckt.

const alle = ereignisseJson as unknown[];
const fertig = ableiten(alle);

function zeige(zustand: FallZustand, fallId = "mock-wartezeiten", extra: Partial<Parameters<typeof PanelAnsicht>[0]> = {}) {
  return render(<PanelAnsicht zustand={zustand} verbindung="zu" fallId={fallId} modelle={modellWahl()} {...extra} />);
}

afterEach(() => vi.unstubAllGlobals());

it("zeigt Akteur, Haltung als Zahl und Wort, Herkunft-Chip mit Medium und Monat und die getrennte Moderator-Spur", () => {
  zeige(fertig);
  const kammer = document.querySelector<HTMLElement>('[data-akteur="aerztekammer"]')!;
  expect(within(kammer).getByRole("heading", { name: "Ärztekammer" })).toBeTruthy();
  const zeile = kammer.querySelector('[data-thema="kassenstellen"]')!;
  expect(zeile.querySelector('[data-teil="haltung-zahl"]')?.textContent).toBe("+1");
  expect(zeile.querySelector('[data-teil="haltung-wort"]')?.textContent).toBe("eher dafür");

  const chip = kammer.querySelector('[data-baustein="herkunft"] button')!;
  expect(chip.querySelector('[data-teil="medium"]')?.textContent).toBe("Fachdienst Gesundheit (Beispiel)");
  expect(chip.querySelector('[data-teil="monat"]')?.textContent).toMatch(/^\d{2}\/\d{4}$/);

  const moderator = document.querySelector('[data-spur="moderator"]')!;
  expect(moderator.textContent).toContain("denkt mit");
  expect(moderator.textContent).toContain("Runde 4");
  // Die Moderator-Spur steht außerhalb der Persona-Karten.
  expect(document.querySelector('[data-akteur] [data-spur="moderator"]')).toBeNull();
  expect(document.querySelector('[data-spur="experte"]')?.textContent).toContain("Zahlen geprüft");
});

it("genau ein Modellhinweis: live die Angabe des Laufs, in der Vorführung nur der Hinweis auf die Aufzeichnung", () => {
  const { unmount } = zeige(fertig, "mock-wartezeiten", { modus: "vorfuehrung" });
  expect(screen.getAllByTestId("uc2-vorfuehrung")).toHaveLength(1);
  expect(screen.queryByTestId("uc2-modell")).toBeNull();
  expect(document.body.textContent).not.toContain("mock-fixture");
  unmount();
  zeige(ableiten(mitAnbieter(mockEreignisse(MOCK_ABBRUCH)!, "azure", "gpt-5-4-mini")), "42", { modus: "live" });
  expect(screen.queryByTestId("uc2-vorfuehrung")).toBeNull();
  expect(screen.getByTestId("uc2-modell").textContent).toContain("azure · gpt-5-4-mini");
});

it("erfundene Medien tragen in der Anzeige den Zusatz (Beispiel)", () => {
  zeige(fertig);
  const medien = [...document.querySelectorAll('[data-baustein="herkunft"] [data-teil="medium"]')].map((m) => m.textContent ?? "");
  expect(medien.length).toBeGreaterThan(10);
  for (const m of medien) expect(m).toMatch(/ \(Beispiel\)$/);
});

it("markiert, wer sich bewegt hat und wer fest blieb, und zeigt am Ende, was gilt", () => {
  zeige(fertig);
  const marken = Object.fromEntries(
    [...document.querySelectorAll<HTMLElement>("[data-akteur]")].map((a) => [a.dataset.akteur, a.dataset.marke]),
  );
  expect(marken).toEqual({
    aerztekammer: "fest",
    finanzministerium: "bewegt",
    gesundheitsministerium: "fest",
    patienten: "bewegt",
    sv: "bewegt",
    vertragsaerzte: "bewegt",
  });
  const stand = document.querySelector('[data-spur="stand"]')!;
  expect(stand.getAttribute("data-fertig")).toBe("ja");
  expect(within(stand as HTMLElement).getByText("Am Ende gilt")).toBeTruthy();
  const arten = Object.fromEntries([...stand.querySelectorAll<HTMLElement>("[data-thema]")].map((t) => [t.dataset.thema, t.dataset.kategorie]));
  expect(arten).toEqual({
    triage: "offener_konflikt",
    finanzierung: "offener_konflikt",
    kassenstellen: "mehrheit",
    patientenlenkung: "konsens",
  });
  expect(stand.querySelector('[data-thema="kassenstellen"] [data-teil="zaehlung"]')?.textContent).toBe("4 von 6 dafür, 0 dagegen, 2 unentschieden");
  expect(stand.textContent).toContain("Einigung");
  expect(stand.textContent).toContain("Noch strittig");
  expect(screen.getByTestId("uc2-titel").textContent).toBe("Das Panel ist nach 4 Runden fertig");
});

it("zeigt während der Verhandlung, wer gerade spricht, und einen Zwischenstand", () => {
  // bis einschließlich der "belege" von Runde 2 der Finanzministerium-Spur
  const stand = ableiten(alle.slice(0, 24));
  expect(stand.status).toBe("laeuft");
  expect(stand.sprecher).toBe("finanzministerium");
  expect(sprecherText(stand)).toBe("Gerade spricht: Finanzministerium");
  expect(titelText(stand)).toBe("Das Panel verhandelt, Runde 2 von höchstens 5");
  zeige(stand);
  expect(document.querySelector('[data-akteur="finanzministerium"]')?.getAttribute("data-marke")).toBe("spricht");
  expect(document.querySelector('[data-spur="stand"]')?.getAttribute("data-fertig")).toBe("nein");
  expect(screen.getByText(/Zwischenstand nach Runde 1/)).toBeTruthy();
});

it("Belege sind zu, bis man sie aufklappt, und zeigen nie mehr als 300 Zeichen Zitat", async () => {
  const user = userEvent.setup();
  zeige(fertig);
  expect(document.querySelectorAll('[data-teil="zitat"]')).toHaveLength(0);
  const knoepfe = [...document.querySelectorAll<HTMLButtonElement>('[data-baustein="herkunft"] button')];
  expect(knoepfe.length).toBeGreaterThan(10);
  for (const k of knoepfe) await user.click(k);
  const zitate = [...document.querySelectorAll('[data-teil="zitat"]')].map((z) => z.textContent ?? "");
  expect(zitate).toHaveLength(knoepfe.length);
  for (const z of zitate) expect(z.replace(/[„“]/g, "").length).toBeLessThanOrEqual(MAX_ZITAT);
  const offen = document.querySelector('[data-teil="beleg-offen"]')!;
  expect(offen.textContent).toMatch(/Seite|\d{2}\.\d{2}\.\d{4}/);
});

it("kürzt ein zu langes Zitat an einer Wortgrenze auf höchstens 300 Zeichen", () => {
  const lang = "Wort ".repeat(200);
  const kurz = zitatText(lang);
  expect(kurz.length).toBeLessThanOrEqual(MAX_ZITAT);
  expect(kurz.endsWith("...")).toBe(true);
  expect(zitatText("Kurz.")).toBe("Kurz.");
});

it("der sichtbare Text enthält weder Geviertstrich noch Halbgeviertstrich", async () => {
  const user = userEvent.setup();
  // Auch wenn das Modell Striche schreibt: Anzeigetext bekommt keine.
  const verseucht = ableiten(
    alle.map((e) => {
      const ereignis = JSON.parse(JSON.stringify(e)) as { art: string; daten: { notiz?: string } };
      if (ereignis.art === "moderator_notiz") ereignis.daten.notiz = `${ereignis.daten.notiz} — Wartezeit 10–20 % – offen`;
      return ereignis;
    }),
  );
  zeige(verseucht);
  for (const k of document.querySelectorAll<HTMLButtonElement>('[data-baustein="herkunft"] button')) await user.click(k);
  expect(document.body.textContent).not.toMatch(/[—–]/);
  expect(ohneStriche("10–20 % — offen")).toBe("10 bis 20 %, offen");
  expect(klartext("Wir gehen auf die Position von sv ein.")).toBe("Wir gehen auf die Position von Sozialversicherung ein.");
});

it("Prüfhinweise stehen gelb beim Experten, in Alltagssprache und ohne Doppelung", () => {
  zeige(fertig);
  const gelb = [...document.querySelectorAll('[data-hinweis="gelb"]')].map((h) => h.textContent);
  expect(gelb.filter((t) => t?.includes("300 Stellen"))).toHaveLength(1);
  expect(gelb.join(" ")).toContain("ohne Quelle");
  expect(gelb.join(" ")).toContain("Ob das Ziel sicher klappt, ist offen");
});

describe("Modellfehler (U2-1a)", () => {
  const abbruch = ableiten(mockEreignisse(MOCK_ABBRUCH)!);
  // Ein echter Lauf über azure, der nach Runde 2 mit einem Zeitfehler abbricht (Vertrag #44: Ereignis abbruch).
  const live = ableiten(abbruchMitAnbieter("azure", "gpt-5-4-mini"));

  it("Vorführung: sagt Testbetrieb, aufgezeichneter Abbruch, und erfindet keinen Ausfall eines Anbieters", () => {
    zeige(abbruch, MOCK_ABBRUCH, { onNeu: vi.fn(), modus: "vorfuehrung" });
    const text = screen.getByRole("alert").textContent ?? "";
    expect(text).toContain("Testbetrieb, aufgezeichneter Abbruch");
    expect(text).toContain("Hier ist kein Modell ausgefallen");
    expect(document.body.textContent).not.toMatch(/azure hat nicht|Modell azure|mock-fixture|mock · /);
    expect(text).toContain("Die Runden 1 und 2 sind fertig und bleiben stehen.");
    expect(document.querySelectorAll("[data-akteur]")).toHaveLength(6);
  });

  it("behält die fertigen Runden und zeigt Erneut und die Modellwahl, ollama nur mit sichtbarer Meldung", () => {
    const neu = vi.fn();
    zeige(live, "42", { onNeu: neu, modus: "live" });
    expect(live.status).toBe("abgebrochen");
    expect(screen.getByRole("alert").textContent).toContain("Runde 3 ist abgebrochen");
    expect(screen.getByRole("alert").textContent).toContain("Die Runden 1 und 2 sind fertig und bleiben stehen.");
    // Alltagssprache vorn, der Fehlertyp nur klein dahinter.
    expect(screen.getByRole("alert").querySelector('[data-teil="fehlertext"]')?.textContent).toContain(
      "Das Modell azure hat nicht rechtzeitig geantwortet. Zeitüberschreitung nach 30 Sekunden.",
    );
    expect(screen.getByRole("alert").querySelector('[data-teil="grund"]')?.textContent).toBe("Technischer Grund: TimeoutError");
    expect(screen.getByRole("alert").querySelector('[data-teil="fehlertext"]')?.textContent).not.toContain("TimeoutError");
    // Runde 1 und 2 bleiben: sechs Personas mit Haltung, Moderator-Notiz nach Runde 2.
    expect(document.querySelectorAll("[data-akteur]")).toHaveLength(6);
    expect(document.querySelector('[data-spur="moderator"]')?.textContent).toContain("Nach Runde 2");
    expect(document.querySelectorAll('[data-runde="1"], [data-runde="2"]')).toHaveLength(2);
    expect(screen.getByTestId("uc2-erneut")).toBeTruthy();
    expect((screen.getByTestId("uc2-modell-claude") as HTMLButtonElement).disabled).toBe(false);
    const ollama = screen.getByTestId("uc2-modell-ollama") as HTMLButtonElement;
    expect(ollama.disabled).toBe(true);
    expect(ollama.textContent).toContain("ollama · lokal · Fallback");
    expect(document.querySelector('[data-modell="ollama"]')?.textContent).toContain("nicht eingerichtet");
    expect(screen.queryByText("Am Ende gilt")).toBeNull();
  });

  it("Erneut und Modellwechsel rufen den Neustart mit dem gewählten Modell auf", async () => {
    const user = userEvent.setup();
    const neu = vi.fn();
    zeige(live, "42", { onNeu: neu, modus: "live" });
    await user.click(screen.getByTestId("uc2-erneut"));
    await user.click(screen.getByTestId("uc2-modell-claude"));
    expect(neu.mock.calls).toEqual([[null], ["claude"]]);
  });

  it("ein eingerichtetes ollama ist wählbar", () => {
    vi.stubEnv("OLLAMA_MODEL", "qwen3:8b");
    const neu = vi.fn();
    zeige(live, "42", { onNeu: neu, modelle: modellWahl(), modus: "live" });
    expect((screen.getByTestId("uc2-modell-ollama") as HTMLButtonElement).disabled).toBe(false);
    vi.unstubAllEnvs();
  });
});

it("Fehlertypen des Abbruchs werden zu Sätzen für Bürger", () => {
  expect(grundSatz("TimeoutError", "azure")).toBe("Das Modell azure hat nicht rechtzeitig geantwortet.");
  expect(grundSatz("ConnectError", "claude")).toBe("Das Modell claude war nicht erreichbar.");
  expect(grundSatz("RateLimitError", "azure")).toContain("zu viele Anfragen");
  expect(grundSatz("AuthenticationError", "azure")).toBe("Die Anmeldung beim Modell azure hat nicht geklappt.");
  expect(grundSatz("Merkwuerdig", null)).toBe("Das Modell hat einen Fehler gemeldet.");
  expect(grundSatz(null, "azure")).toBe("Das Modell azure hat einen Fehler gemeldet.");
});

it("zeigt, wenn die API die Auswahl der Gruppen nicht übernommen hat", () => {
  zeige(fertig, "mock-wartezeiten", { akteureIgnoriert: true });
  expect(screen.getByTestId("uc2-akteure-hinweis").textContent).toContain("nicht übernommen");
});

it("ohne Ereignisse zeigt die Seite Wartezustand statt Leere", () => {
  zeige(ableiten([]));
  expect(screen.getByTestId("uc2-titel").textContent).toBe("Das Panel wird vorbereitet");
  expect(screen.getByTestId("uc2-leer").textContent).toContain("Der Moderator wählt");
});

it("eine unterbrochene Verbindung bietet Neu verbinden an und behält den Stand", async () => {
  const user = userEvent.setup();
  const verbinden = vi.fn();
  zeige(ableiten(alle.slice(0, 20)), "mock-wartezeiten", { verbindung: "unterbrochen", onNeuVerbinden: verbinden });
  expect(screen.getByText(/Die Verbindung zum Panel ist abgebrochen/)).toBeTruthy();
  expect(document.querySelectorAll("[data-akteur]")).toHaveLength(6);
  await user.click(screen.getByRole("button", { name: "Neu verbinden" }));
  expect(verbinden).toHaveBeenCalledOnce();
});

describe("Verlauf: je Beitrag Haltung und Herkunft, auch aus früheren Runden", () => {
  it("Beiträge aus Runde 1 und 2 zeigen nach Runde 4 Haltung und Herkunft-Chip", () => {
    zeige(fertig);
    for (const runde of [1, 2, 3, 4]) {
      const beitraege = document.querySelectorAll(`[data-spur="verlauf"] [data-runde="${runde}"] [data-beitrag]:not([data-beitrag="moderator"])`);
      expect(beitraege.length, `Runde ${runde}`).toBe(6);
      for (const b of beitraege) {
        expect(b.querySelector('[data-teil="haltung"]')?.textContent, `${b.getAttribute("data-beitrag")} R${runde} Haltung`).toMatch(/^[+−0]\d? .+\. $/);
        const chip = b.querySelector('[data-baustein="herkunft"] [data-teil="medium"]');
        expect(chip?.textContent, `${b.getAttribute("data-beitrag")} R${runde} Herkunft`).toMatch(/\(Beispiel\)$/);
      }
    }
  });

  it("die Persona-Karte behält Belege früherer Runden zugeklappt, auch wenn Runde 4 andere nennt", () => {
    // Die Ärztekammer zitiert in Runde 4 nichts mehr: ihre Belege aus Runde 1 bis 3 dürfen nicht verschwinden.
    const z = ableiten(
      alle.map((e) => {
        const x = JSON.parse(JSON.stringify(e)) as { art: string; runde: number; akteur: string; daten: { zug?: { themen: { beleg_ids: string[] }[] } } };
        if (x.art === "zug" && x.runde === 4 && x.akteur === "aerztekammer") for (const t of x.daten.zug!.themen) t.beleg_ids = [];
        return x;
      }),
    );
    zeige(z);
    const frueher = document.querySelector('[data-akteur="aerztekammer"] [data-teil="belege-frueher"]')!;
    expect(frueher.querySelector("summary")?.textContent).toMatch(/^Belege früherer Runden \(\d+\)$/);
    expect(frueher.textContent).toMatch(/Runde 1, 2, 3/);
    expect(frueher.querySelectorAll('[data-baustein="herkunft"]').length).toBeGreaterThan(1);
  });
});

describe("richtige Anzeigen", () => {
  it("vorher ist die Haltung direkt vor der letzten Änderung: aus −2, −1, 0 wird vorher −1 in Runde 3", () => {
    zeige(fertig);
    const zeile = document.querySelector('[data-akteur="sv"] [data-thema="finanzierung"]')!;
    expect(zeile.querySelector('[data-teil="haltung-zahl"]')?.textContent).toBe("0");
    expect(zeile.querySelector('[data-teil="aenderung"]')?.textContent).toBe("vorher −1 eher dagegen, geändert in Runde 3");
  });

  it("n von N zählt je Thema aus den Teilnehmern dieses Themas", () => {
    const z = ableiten([
      { seq: 1, art: "start", daten: {} },
      {
        seq: 2,
        art: "ergebnis",
        daten: {
          runden: 1,
          klassifikation: {
            a: { kategorie: "mehrheit", zustimmend: ["sv", "patienten", "aerztekammer"], ablehnend: [], enthalten: [] },
            b: { kategorie: "offener_konflikt", zustimmend: ["sv"], ablehnend: ["patienten"], enthalten: [] },
          },
        },
      },
    ]);
    zeige(z);
    const zaehlung = Object.fromEntries([...document.querySelectorAll<HTMLElement>('[data-spur="stand"] [data-thema]')].map((t) => [t.dataset.thema, t.querySelector('[data-teil="zaehlung"]')?.textContent]));
    expect(zaehlung).toEqual({ a: "3 von 3 dafür, 0 dagegen, 0 unentschieden", b: "1 von 2 dafür, 1 dagegen, 0 unentschieden" });
  });

  it("ein unbekannter Fall zeigt Fall nicht gefunden, nicht Vorbereitung und nicht Verbindung abgebrochen", () => {
    zeige(ableiten([]), "gibt-es-nicht", { verbindung: "nicht-gefunden" });
    expect(screen.getByTestId("uc2-titel").textContent).toBe("Fall nicht gefunden");
    expect(screen.getByRole("link", { name: "Fall stellen" })).toBeTruthy();
    expect(document.body.textContent).not.toContain("wird vorbereitet");
    expect(document.body.textContent).not.toContain("Verbindung zum Panel ist abgebrochen");
  });
});

describe("Sprache und Farbe", () => {
  it("sagt unentschieden statt enthalten und nennt kein Modell roh", () => {
    zeige(fertig);
    const text = document.body.textContent ?? "";
    expect(text).toContain("unentschieden");
    expect(text).not.toMatch(/\benthalten\b/i);
    expect(text).not.toMatch(/mock-fixture|mock · /);
  });

  it("die Marke bewegt ist nicht violett (Violett ist nur das KI-Label)", () => {
    zeige(fertig);
    const marke = document.querySelector('[data-marke="bewegt"] [data-teil="marke"]')!;
    expect(marke.className).not.toMatch(/violett/);
    for (const el of document.querySelectorAll('[data-spur="verlauf"] .rounded')) expect(el.className).not.toMatch(/violett/);
  });

  it("Gedankenstriche in Belegtitel und Medium werden nicht angezeigt", async () => {
    const user = userEvent.setup();
    const verseucht = ableiten(
      alle.map((e) => {
        const x = JSON.parse(JSON.stringify(e)) as { art: string; daten: { belege?: { medium: string; titel: string }[] } };
        if (x.art === "belege") for (const b of x.daten.belege ?? []) Object.assign(b, { medium: `${b.medium} – Süd`, titel: `${b.titel} — Teil 2` });
        return x;
      }),
    );
    zeige(verseucht);
    for (const k of document.querySelectorAll<HTMLButtonElement>('[data-baustein="herkunft"] button')) await user.click(k);
    expect(document.body.textContent).not.toMatch(/[—–]/);
    expect(document.querySelector('[data-teil="titel"]')?.textContent).toMatch(/, Teil 2$/);
    expect(document.querySelector('[data-teil="medium"]')?.textContent).toContain(", Süd");
  });
});
