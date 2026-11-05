import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

it("liest den Strom: die Station zeigt ihren Kernsatz, am Ende steht die Dauer", async () => {
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
  await screen.findByText("Im März 2025 gab es 388.650 Beschäftigungsverhältnisse.");
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
      { art: "antwort", uc: "uc2", stufe: 2, dauer_ms: 900, kern: "Das Panel wägt ab.", antwort: { ...ANTWORT, uc: "uc2" } },
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

it("ein mit „…“ gekürzter Kernsatz wird durch die ganze kurze Antwort ersetzt", async () => {
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
