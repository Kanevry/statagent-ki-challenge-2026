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
