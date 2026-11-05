import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { UcAntwort } from "@kic/ui/antwortform";
import { Kette } from "./kette";

const ANTWORT = {
  text: "Im März 2025 gab es 388.650 Beschäftigungsverhältnisse. Mehr steht im Bericht.",
  belege: [],
  zahlen: [],
  uc: "uc3",
  modell: null,
  protokoll_id: null,
};

function stromAntwort(zeilen: unknown[]): Response {
  const text = zeilen.map((z) => JSON.stringify(z)).join("\n") + "\n";
  return new Response(text, { status: 200, headers: { "content-type": "application/x-ndjson" } });
}

function fetchMit(antwort: () => Response) {
  const f = vi.fn(async (url: string) => (url.includes("voice-config") ? Response.json({ publicKey: null, assistantId: null, aktiv: false }) : antwort()));
  vi.stubGlobal("fetch", f);
  return f;
}

afterEach(() => vi.unstubAllGlobals());

it("liest den Strom: die Station zeigt ihre erste Zeile, am Ende steht die Dauer", async () => {
  fetchMit(() =>
    stromAntwort([
      { art: "start", kette: ["uc3"], modell: null },
      { art: "station", uc: "uc3", stufe: 1, zustand: "laeuft" },
      { art: "antwort", uc: "uc3", stufe: 1, dauer_ms: 1100, kern: "Im März 2025 gab es 388.650 Beschäftigungsverhältnisse.", antwort: ANTWORT },
      { art: "ende", fehlend: [], dauer_ms: 1200 },
    ]),
  );
  render(<Kette kette={["uc3"]} fragenOffen mitModell={false} />);
  await userEvent.type(screen.getByLabelText("Ihre Frage"), "Beschäftigte März 2025{Enter}");
  await screen.findByText(ANTWORT.text);
  expect(document.querySelector('[data-uc-karte="uc3"]')?.getAttribute("data-zustand")).toBe("antwort");
  await screen.findByText(/Fertig in 1,2 s/);
});

it("eine Station, die fehlt, sagt das ruhig, und die Kette läuft weiter", async () => {
  fetchMit(() =>
    stromAntwort([
      { art: "start", kette: ["uc3", "uc2"], modell: null },
      { art: "station", uc: "uc3", stufe: 1, zustand: "laeuft" },
      { art: "fehlt", uc: "uc3", stufe: 1, grund: "zeitueberschreitung" },
      { art: "station", uc: "uc2", stufe: 2, zustand: "laeuft" },
      { art: "antwort", uc: "uc2", stufe: 2, dauer_ms: 900, kern: "Das Panel wägt ab.", antwort: { ...ANTWORT, uc: "uc2", text: "Das Panel wägt ab." } },
      { art: "ende", fehlend: [], dauer_ms: 1000 },
    ]),
  );
  render(<Kette kette={["uc3", "uc2"]} fragenOffen mitModell={false} />);
  await userEvent.type(screen.getByLabelText("Ihre Frage"), "Frage{Enter}");
  await screen.findByText("Das Panel wägt ab.");
  expect(document.querySelector('[data-uc-karte="uc3"]')?.getAttribute("data-zustand")).toBe("fehlt");
  expect(screen.getByText(/Die Kette lief ohne diese Station weiter/)).toBeTruthy();
});

it("gesperrt (403/405): ein Satz, keine Meldung je Station", async () => {
  fetchMit(() => new Response("", { status: 405 }));
  render(<Kette kette={["uc3", "uc2", "uc1"]} fragenOffen mitModell />);
  await userEvent.type(screen.getByLabelText("Ihre Frage"), "Frage{Enter}");
  await waitFor(() => expect(screen.getAllByText("Fragen sind hier gerade nicht offen.")).toHaveLength(1));
  expect(document.querySelectorAll('[data-zustand="fehlt"]')).toHaveLength(0);
});

it("ohne Wirkung wird nichts angeboten: keine Modellwahl ohne Modell, kein Feld, wenn Fragen zu sind", () => {
  fetchMit(() => new Response("", { status: 500 }));
  const { unmount } = render(<Kette kette={["uc3"]} fragenOffen mitModell={false} />);
  expect(screen.queryByText("Modell wählen")).toBeNull();
  unmount();
  render(<Kette kette={["uc3"]} fragenOffen={false} mitModell={false} />);
  expect(screen.queryByLabelText("Ihre Frage")).toBeNull();
  expect(screen.queryAllByRole("button")).toHaveLength(0);
});

const BELEG = { uc: "uc3", lieferung: "2025-03", monat: "2025-03", sql: null, ref: null, regelstand: "v1", lauf: null, stand: "endgueltig" };

it("jede Zahl hat ihren eigenen Beleg (zwei Zahlen aus zwei Quellen)", async () => {
  const antwort = {
    ...ANTWORT,
    text: "Kernsatz.",
    belege: [
      { ...BELEG, quelle: "stat.beschaeftigte_monat" },
      { ...BELEG, quelle: "stat.klass_oenace" },
    ],
    zahlen: [
      { bezeichnung: "Beschäftigte", wert: 388650, einheit: null, beleg: 0 },
      { bezeichnung: "davon Wien", wert: 92480, einheit: null, beleg: 1 },
    ],
  };
  fetchMit(() =>
    stromAntwort([
      { art: "start", kette: ["uc3"], modell: null },
      { art: "station", uc: "uc3", stufe: 1, zustand: "laeuft" },
      { art: "antwort", uc: "uc3", stufe: 1, dauer_ms: 900, kern: "Kernsatz.", antwort },
      { art: "ende", fehlend: [], dauer_ms: 1000 },
    ]),
  );
  render(<Kette kette={["uc3"]} fragenOffen mitModell={false} />);
  await userEvent.type(screen.getByLabelText("Ihre Frage"), "Frage{Enter}");
  await screen.findByText("Kernsatz.");
  const zahlen = document.querySelectorAll("[data-zahl]");
  expect(zahlen).toHaveLength(2);
  expect(screen.getByRole("button", { name: /stat\.beschaeftigte_monat/ })).toBeTruthy();
  expect(screen.getByRole("button", { name: /stat\.klass_oenace/ })).toBeTruthy();
});

it("Strom ohne Abschluss oder mit kaputter Zeile wird ein Fehlersatz, die Seite läuft nicht ewig", async () => {
  fetchMit(() =>
    stromAntwort([
      { art: "start", kette: ["uc3"], modell: null },
      { art: "station", uc: "uc3", stufe: 1, zustand: "laeuft" },
    ]),
  );
  const { unmount } = render(<Kette kette={["uc3"]} fragenOffen mitModell={false} />);
  await userEvent.type(screen.getByLabelText("Ihre Frage"), "Frage{Enter}");
  expect((await screen.findByRole("alert")).textContent).toContain("brach ab");
  expect(screen.getByRole("button", { name: "Fragen" }).hasAttribute("disabled")).toBe(false);
  unmount();

  vi.unstubAllGlobals();
  fetchMit(() => new Response('{"art":"start","kette":["uc3"]}\nkein json\n', { status: 200 }));
  render(<Kette kette={["uc3"]} fragenOffen mitModell={false} />);
  await userEvent.type(screen.getByLabelText("Ihre Frage"), "Frage{Enter}");
  expect((await screen.findByRole("alert")).textContent).toContain("nicht im erwarteten Format");
});

it("der Screenreader hört die tatsächliche Zahl der Antworten, nicht pauschal alle", async () => {
  fetchMit(() =>
    stromAntwort([
      { art: "start", kette: ["uc3", "uc2"], modell: null },
      { art: "station", uc: "uc3", stufe: 1, zustand: "laeuft" },
      { art: "antwort", uc: "uc3", stufe: 1, dauer_ms: 900, kern: "Eins.", antwort: ANTWORT },
      { art: "station", uc: "uc2", stufe: 2, zustand: "laeuft" },
      { art: "fehlt", uc: "uc2", stufe: 2, grund: "zeitueberschreitung" },
      { art: "ende", fehlend: [], dauer_ms: 1000 },
    ]),
  );
  render(<Kette kette={["uc3", "uc2"]} fragenOffen mitModell={false} />);
  await userEvent.type(screen.getByLabelText("Ihre Frage"), "Frage{Enter}");
  await waitFor(() => expect(screen.getByRole("status").textContent).toBe("1 von 2 Stationen haben geantwortet."));
});

it("die Einheit „Anzahl“ steht nicht hinter der Zahl", async () => {
  const antwort = {
    ...ANTWORT,
    text: "Kern.",
    belege: [{ ...BELEG, quelle: "stat.beschaeftigte_monat" }],
    zahlen: [{ bezeichnung: "Beschäftigte", wert: 7498, einheit: "Anzahl", beleg: 0 }],
  };
  fetchMit(() =>
    stromAntwort([
      { art: "start", kette: ["uc3"], modell: null },
      { art: "antwort", uc: "uc3", stufe: 1, dauer_ms: 900, kern: "Kern.", antwort },
      { art: "ende", fehlend: [], dauer_ms: 1000 },
    ]),
  );
  render(<Kette kette={["uc3"]} fragenOffen mitModell={false} />);
  await userEvent.type(screen.getByLabelText("Ihre Frage"), "Frage{Enter}");
  await screen.findByText("Kern.");
  expect(document.querySelector("[data-zahl]")?.textContent).not.toContain("Anzahl");
  expect(document.querySelector("[data-zahl]")?.textContent).toContain("7.498");
});

it("ein mit „…“ gekürzter Kernsatz wird durch die ganze kurze erste Zeile ersetzt", async () => {
  const antwort = { ...ANTWORT, text: "Im März 2025 gab es 7.498 Beschäftigungsverhältnisse in Wien im Gesundheits- und Sozialwesen, laut Statistik." };
  fetchMit(() =>
    stromAntwort([
      { art: "start", kette: ["uc3"], modell: null },
      { art: "antwort", uc: "uc3", stufe: 1, dauer_ms: 900, kern: "Im März 2025 gab es 7.498 Beschäftigungsverhältnisse in Wien …", antwort },
      { art: "ende", fehlend: [], dauer_ms: 1000 },
    ]),
  );
  render(<Kette kette={["uc3"]} fragenOffen mitModell={false} />);
  await userEvent.type(screen.getByLabelText("Ihre Frage"), "Frage{Enter}");
  await screen.findByText(antwort.text);
  expect(screen.queryByText("Ganze Antwort")).toBeNull();
});

const BELEG_UC3 = { uc: "uc3", quelle: "stat.stat_beschaeftigte", lieferung: "2025-03", monat: "2025-03", regelstand: "v1", sql: "select 1", lauf: null, ref: null, stand: "endgueltig" };
const PRESSE = { ...BELEG_UC3, uc: "uc2", quelle: "presse: Kurier", sql: null, regelstand: null, lieferung: null, ref: "b1", stand: null };
const EXPERTE = { ...PRESSE, quelle: "uc2.experte", ref: "paket" };
const ZAHL = { bezeichnung: "Beschäftigungsverhältnisse", wert: 7498, einheit: "Anzahl", beleg: 0 };

function antwort(uc: string, text: string, belege: unknown[], zahlen: unknown[]): UcAntwort {
  return { uc, text, belege, zahlen, modell: uc === "uc3" ? null : "gpt-5-4-mini", protokoll_id: null } as unknown as UcAntwort;
}

const UC3 = antwort("uc3", "Am 31.03.2025 gab es 7.498 Beschäftigungsverhältnisse.", [BELEG_UC3], [ZAHL]);
const UC2 = antwort(
  "uc2",
  "Mehr Personal heißt meist kürzere Wartezeiten. Weniger Personal heißt meist längere Wartezeiten.\nDie Zahl aus der Statistik: 7.498.\nWer ist dafür, wer dagegen:",
  [BELEG_UC3, PRESSE, PRESSE],
  [ZAHL],
);
const UC1 = antwort("uc1", "Für Ihren nächsten Arzttermin heißt das: Sie warten oft kürzer. Die Zahl dahinter für März 2025: 7.498 Beschäftigungsverhältnisse.", [BELEG_UC3, PRESSE], [ZAHL]);

function strom(...antworten: UcAntwort[]): Response {
  const zeilen: unknown[] = [{ art: "start", kette: ["uc3", "uc2", "uc1"], modell: null }];
  antworten.forEach((a, i) => {
    zeilen.push({ art: "station", uc: a.uc, stufe: i + 1, zustand: "laeuft" });
    zeilen.push({ art: "antwort", uc: a.uc, stufe: i + 1, dauer_ms: 900, kern: a.text.split(". ")[0], antwort: a });
  });
  zeilen.push({ art: "ende", fehlend: [], dauer_ms: 1000 });
  return new Response(zeilen.map((z) => JSON.stringify(z)).join("\n") + "\n", { status: 200 });
}

async function fragen(antwort: Response) {
  vi.stubGlobal("fetch", vi.fn(async (ziel: string) => (String(ziel).includes("uc4/frage") ? antwort : new Response("{}", { status: 200 }))));
  const { container } = render(<Kette kette={["uc3", "uc2", "uc1"]} fragenOffen mitModell={false} />);
  const nutzer = userEvent.setup();
  await nutzer.type(screen.getByLabelText("Ihre Frage"), "Wie viele?{Enter}");
  await waitFor(() => expect(container.querySelector('[data-zustand="laeuft"]')).toBeNull());
  return container;
}

it("die Zahl steht mit ihren Angaben nur bei Station 1, nicht dreimal (#164)", async () => {
  const seite = await fragen(strom(UC3, UC2, UC1));
  await screen.findByText(/Fertig in/);
  expect(seite.querySelectorAll("[data-zahl]")).toHaveLength(1);
  expect(seite.querySelector('[data-uc-karte="uc3"] [data-zahl]')).not.toBeNull();
});

it("der Simulator zeigt oben seine Aussage und seine eigenen Quellen, nicht die Zahl von StatAgent", async () => {
  const seite = await fragen(strom(UC3, UC2, UC1));
  await screen.findByText(/Fertig in/);
  const karte = seite.querySelector('[data-uc-karte="uc2"]')!;
  const aussage = karte.querySelector("[data-uc4-antwort] p")!.textContent;
  expect(aussage).toBe("Mehr Personal heißt meist kürzere Wartezeiten. Weniger Personal heißt meist längere Wartezeiten.");
  // Zwei gleiche Quellen zählen einmal, die weitergereichte Zahl fehlt hier.
  expect(karte.querySelectorAll('[data-baustein="herkunft"]')).toHaveLength(1);
  expect(karte.querySelector('[data-baustein="herkunft"]')!.textContent).toContain("presse: Kurier");
});

it("der Lotse zeigt den Beleg seiner Zahl", async () => {
  const seite = await fragen(strom(UC3, UC2, UC1));
  await screen.findByText(/Fertig in/);
  const karte = seite.querySelector('[data-uc-karte="uc1"]')!;
  expect(karte.querySelector("[data-uc4-antwort] p")!.textContent).toContain("Arzttermin");
  expect(karte.querySelector('[data-baustein="herkunft"]')!.textContent).toContain("stat.stat_beschaeftigte");
});

it("ohne Zahl von Station 1 steht nur deren Rückfrage da, ohne leere Stationen", async () => {
  const seite = await fragen(strom(antwort("uc3", "Bitte nennen Sie einen Monat, zum Beispiel März 2025.", [], [])));
  await waitFor(() => expect(seite.querySelectorAll("[data-uc-karte]")).toHaveLength(1));
  expect(seite.querySelector("[data-uc-karte]")!.getAttribute("data-uc-karte")).toBe("uc3");
  expect(seite.textContent).toContain("Bitte nennen Sie einen Monat");
  expect(seite.textContent).not.toContain("Fertig in");
});

it("Station 1 mit Zahl zeigt den ersten Satz, der Rest steht unter „Ganze Antwort“", async () => {
  // Fängt den Lauf mit !192: Bis 320 Zeichen stand „Verstanden: …, übernommen, gezählt …“ groß in der Karte, darüber
  // hinaus nur der erste Satz, je nach Frage verschieden lang.
  const lang = "Am 31.10.2025 gab es 390.900 Beschäftigungsverhältnisse. Verstanden: Oktober 2025. Die Zahlen sind vorläufig.";
  const seite = await fragen(strom(antwort("uc3", lang, [BELEG_UC3], [ZAHL])));
  await waitFor(() => expect(seite.querySelector("[data-uc4-antwort] p")?.textContent).toBe("Am 31.10.2025 gab es 390.900 Beschäftigungsverhältnisse"));
  expect(screen.getByText("Ganze Antwort")).toBeTruthy();
});

it("eine Rückfrage von Station 1 steht ganz da, nicht nur ihr erster Satz", async () => {
  // Fängt: „… zwölf Werte.“ steht da, die eigentliche Frage „Meinen Sie …?“ ist unter „Ganze Antwort“ versteckt.
  const rueckfrage = "Für 2025 gibt es zwölf Werte. Meinen Sie einen Monat oder den Durchschnitt?";
  const seite = await fragen(strom(antwort("uc3", rueckfrage, [], [])));
  await waitFor(() => expect(seite.querySelector("[data-uc4-antwort] p")?.textContent).toBe(rueckfrage));
  expect(screen.queryByText("Ganze Antwort")).toBeNull();
});

it("fester Text der Stationen danach heißt so, nicht „Mit KI geschrieben“", async () => {
  // Fängt die UI-Regie 05.11.: Der feste Satz des Lotsen stünde sonst über einer KI-Kennzeichnung oder hieße „nur Code“.
  const fest = { ...UC1, modell: null };
  const seite = await fragen(strom(UC3, UC2, fest as UcAntwort));
  await screen.findByText(/Fertig in/);
  const zeile = seite.querySelector('[data-uc-karte="uc1"] [data-testid="uc4-modell"]')!.textContent;
  // Keine Zeit beim festen Text: „Fester Text, 0,0 s“ sagte nichts (UI-Regie).
  expect(zeile).toBe("Fester Text");
  expect(seite.querySelector('[data-uc-karte="uc2"] [data-testid="uc4-modell"]')!.textContent).toContain("Mit KI geschrieben");
  expect(seite.querySelector('[data-uc-karte="uc3"] [data-testid="uc4-modell"]')!.textContent).toContain("Ohne KI, nur Code");
  // Die Schlusszeile darf dann nicht behaupten, das Modell schreibe die Sätze.
  expect(screen.getByText(/Fertig in/).textContent).not.toContain("Die Sätze schreibt");
});

function zahlenAntwort(anzahl: number): UcAntwort {
  const zahlen = Array.from({ length: anzahl }, (_, i) => ({ ...ZAHL, bezeichnung: `Branche ${i + 1}`, wert: i + 1 }));
  return antwort("uc3", "Im Oktober 2024 gab es Zugänge.", [BELEG_UC3], zahlen);
}

it("89 Zahlen: höchstens 5 auf der Karte, der Rest als Verweis auf Fragen an die Daten", async () => {
  // Fängt die UI-Regie 05.11.: „Zugänge im Oktober 2024“ zeigte 89 Zeilen auf der Karte von Station 1.
  const seite = await fragen(strom(zahlenAntwort(89)));
  await waitFor(() => expect(seite.querySelectorAll("[data-zahl]")).toHaveLength(5));
  expect(seite.textContent).toContain("und 84 weitere unter Fragen an die Daten");
  expect(screen.getByRole("link", { name: "Fragen an die Daten" }).getAttribute("href")).toBe("/uc3/fragen");
});

it("6 Zahlen: Einzahl im Verweis", async () => {
  const seite = await fragen(strom(zahlenAntwort(6)));
  await waitFor(() => expect(seite.querySelectorAll("[data-zahl]")).toHaveLength(5));
  expect(seite.textContent).toContain("und eine weitere unter Fragen an die Daten");
});

it("bis 5 Zahlen ändert sich nichts", async () => {
  const seite = await fragen(strom(zahlenAntwort(5)));
  await waitFor(() => expect(seite.querySelectorAll("[data-zahl]")).toHaveLength(5));
  expect(screen.queryByRole("link", { name: "Fragen an die Daten" })).toBeNull();
});

it("nennt die erste Zeile Zahlen des Rechenmodells, steht dessen Beleg sichtbar da", async () => {
  // Fängt das Review von !210: „Wartezeit −22,2 %, Mehrkosten 128,2 Mio. Euro pro Jahr“ ohne jede Herkunft.
  const fall = antwort("uc2", "Das durchgerechnete Maßnahmenpaket bringt laut Rechenmodell: Wartezeit −22,2 %.\nRest.", [BELEG_UC3, EXPERTE, PRESSE], [ZAHL]);
  const seite = await fragen(strom(UC3, fall, UC1));
  await screen.findByText(/Fertig in/);
  const chips = seite.querySelectorAll('[data-uc-karte="uc2"] [data-baustein="herkunft"]');
  expect(chips).toHaveLength(1);
  expect(chips[0]!.textContent).toContain("uc2.experte");
});
