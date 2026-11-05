import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import fixture from "../../../shared/schema/fixtures/uc-antwort.json";
import type { Ergebnis } from "../../lib/plattform/uc4-ergebnis";
import { Einstieg } from "./einstieg";

// Fängt ab: Karten in Antwort- statt Kettenreihenfolge, eine Zahl ohne Herkunft, Enter ohne Wirkung, ein
// gesperrter POST (Online-Demo, #100) als Absturz, ein 429 ohne seinen Hinweis und ein fehlender UC ohne lesbaren
// Grund.

const uc3 = fixture as Ergebnis["antworten"][number];
const ergebnis: Ergebnis = {
  // absichtlich nicht in Kettenreihenfolge: die Seite ordnet selbst
  antworten: [
    { text: "Einfach erklärt.", belege: [], zahlen: [], uc: "uc1", modell: "mock", protokoll_id: null },
    uc3,
  ],
  fehlend: [{ uc: "uc2", grund: "kein_adapter" }],
};

function antworte(status: number, body: unknown) {
  const abruf = vi.fn(async (_adresse: string, _optionen?: RequestInit) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } }));
  vi.stubGlobal("fetch", abruf);
  return abruf;
}

afterEach(() => vi.unstubAllGlobals());

const karten = () => Array.from(document.querySelectorAll<HTMLElement>("[data-uc-karte]"));

it("Enter schickt ab; Karten stehen in Kettenreihenfolge, jede Zahl mit Herkunft, fehlender UC mit Grund", async () => {
  const user = userEvent.setup();
  const abruf = antworte(200, ergebnis);
  render(<Einstieg />);
  expect(karten().map((k) => k.dataset.zustand)).toEqual(["leer", "leer", "leer"]);

  await user.type(screen.getByLabelText("Frage an die Kette"), "Wie viele Beschäftigte?{Enter}");
  expect(await screen.findByText("Einfach erklärt.")).toBeTruthy();
  expect(JSON.parse(String(abruf.mock.calls[0]?.[1]?.body))).toEqual({ frage: "Wie viele Beschäftigte?" });

  expect(karten().map((k) => [k.dataset.ucKarte, k.dataset.zustand])).toEqual([
    ["uc3", "antwort"],
    ["uc2", "fehlt"],
    ["uc1", "antwort"],
  ]);
  const zahlen = karten()[0]!.querySelectorAll("[data-zahl]");
  expect(zahlen).toHaveLength(1);
  for (const zahl of zahlen) expect(zahl.querySelector('[data-baustein="herkunft"]')).not.toBeNull();
  expect(within(karten()[1]!).getByText("Noch nicht angeschlossen")).toBeTruthy();
  expect(screen.getByRole("status").textContent).toBe("2 Antworten da, es fehlt HealthPolicy Simulator.");
});

it("ein gesperrter POST zeigt in jeder Karte den Hinweis auf die Online-Demo", async () => {
  const user = userEvent.setup();
  antworte(405, null);
  render(<Einstieg />);
  await user.type(screen.getByLabelText("Frage an die Kette"), "x");
  await user.click(screen.getByRole("button", { name: "Frage stellen" }));
  expect(await screen.findAllByText("Fragen sind in der Online-Demo noch gesperrt.")).toHaveLength(4);
  expect(karten().map((k) => k.dataset.zustand)).toEqual(["fehler", "fehler", "fehler"]);
});

it("429 (Ratenlimit oder Tagesbudget, #100) zeigt den Hinweis aus der Antwort, nicht „Antwort fehlgeschlagen“", async () => {
  const user = userEvent.setup();
  antworte(429, { fehler: "Das Tageskontingent für Modellaufrufe ist aufgebraucht." });
  render(<Einstieg />);
  await user.type(screen.getByLabelText("Frage an die Kette"), "x{Enter}");
  expect(await screen.findAllByText("Das Tageskontingent für Modellaufrufe ist aufgebraucht.")).toHaveLength(4);
});
