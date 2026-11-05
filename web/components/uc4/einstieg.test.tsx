import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import fixture from "../../../shared/schema/fixtures/uc-antwort.json";
import { BUDGET_MELDUNG, type Ergebnis } from "../../lib/plattform/uc4-ergebnis";
import { AppShell } from "@kic/ui/shell";
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

/** Bodies der POSTs an /api/uc4/frage; der Sprechknopf holt daneben seine Konfiguration. */
function fragen(abruf: ReturnType<typeof antworte>): unknown[] {
  return abruf.mock.calls.filter(([adresse]) => adresse === "/api/uc4/frage").map(([, optionen]) => JSON.parse(String(optionen?.body)));
}

const karten = () => Array.from(document.querySelectorAll<HTMLElement>("[data-uc-karte]"));

it("Enter schickt ab; Karten stehen in Kettenreihenfolge, jede Zahl mit Herkunft, fehlender UC mit Grund", async () => {
  const user = userEvent.setup();
  const abruf = antworte(200, ergebnis);
  render(<Einstieg />);
  expect(karten().map((k) => k.dataset.zustand)).toEqual(["leer", "leer", "leer"]);

  await user.type(screen.getByLabelText("Frage an die Kette"), "Wie viele Beschäftigte?{Enter}");
  expect(await screen.findByText("Einfach erklärt.")).toBeTruthy();
  expect(fragen(abruf)).toEqual([{ frage: "Wie viele Beschäftigte?" }]);

  expect(karten().map((k) => [k.dataset.ucKarte, k.dataset.zustand])).toEqual([
    ["uc3", "antwort"],
    ["uc2", "fehlt"],
    ["uc1", "antwort"],
  ]);
  const zahlen = karten()[0]!.querySelectorAll("[data-zahl]");
  expect(zahlen).toHaveLength(1);
  for (const zahl of zahlen) expect(zahl.querySelector('[data-baustein="herkunft"]')).not.toBeNull();
  expect(within(karten()[1]!).getByText("Noch nicht angeschlossen")).toBeTruthy();
  expect(document.querySelector("[data-uc4-ansage]")?.textContent).toBe("2 Antworten da, es fehlt HealthPolicy Simulator.");
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
  antworte(429, { fehler: BUDGET_MELDUNG });
  render(<Einstieg />);
  await user.type(screen.getByLabelText("Frage an die Kette"), "x{Enter}");
  expect(await screen.findAllByText(BUDGET_MELDUNG)).toHaveLength(4);
});

// Fängt ab: Budget mitten in der Kette erschöpft (router meldet grund BudgetErschoepft), die Karte zeigt aber
// „Antwort fehlgeschlagen“ statt des Budget-Hinweises (Review !36, Pflicht 3).
it("fehlender UC mit grund BudgetErschoepft zeigt den Budget-Hinweis in seiner Karte", async () => {
  const user = userEvent.setup();
  antworte(200, { antworten: [uc3], fehlend: [{ uc: "uc2", grund: "BudgetErschoepft" }, { uc: "uc1", grund: "BudgetErschoepft" }] });
  render(<Einstieg />);
  await user.type(screen.getByLabelText("Frage an die Kette"), "x{Enter}");
  expect(await within(karten()[1]!).findByText(BUDGET_MELDUNG)).toBeTruthy();
  expect(within(karten()[2]!).getByText(BUDGET_MELDUNG)).toBeTruthy();
  expect(screen.queryByText("Antwort fehlgeschlagen")).toBeNull();
});

// Fängt ab: der Chip zeigt den ersten statt des referenzierten Belegs (ein Test mit nur belege[0] bliebe grün),
// und eine von StatAgent durchgereichte Zahl steht in der Panel-Karte ohne Herkunft (Review !34).
it("Zahl mit beleg = 1 zeigt den zweiten Beleg, durchgereichte Zahl trägt „von StatAgent“", async () => {
  const user = userEvent.setup();
  const erster = { ...uc3.belege[0]!, lieferung: "2025-01", monat: "2025-01" };
  const zweiter = { ...uc3.belege[0]!, lieferung: "2025-03", monat: "2025-02", regelstand: "v2", lauf: "abcdef0123456789" };
  const uc2 = {
    ...uc3,
    uc: "uc2" as const,
    modell: "mock",
    belege: [erster, zweiter],
    zahlen: [{ ...uc3.zahlen[0]!, beleg: 1 }],
  };
  antworte(200, { antworten: [uc3, uc2], fehlend: [{ uc: "uc1", grund: "ValueError" }] });
  render(<Einstieg />);
  await user.type(screen.getByLabelText("Frage an die Kette"), "x{Enter}");

  const panel = (await screen.findAllByText("von StatAgent")).map((el) => el.closest("[data-uc-karte]"));
  expect(panel.map((k) => k?.getAttribute("data-uc-karte"))).toEqual(["uc2"]);
  const chip = within(karten()[1]!).getByRole("button", { name: /ansehen$/ });
  expect(chip.textContent).toBe(
    "stat.beschaeftigte_monat Monat 2025-02 aus Lieferung 2025-03 · Regelstand v2 · Lauf abcdef01 · SQL ansehen",
  );
  expect(within(karten()[2]!).getByText("Antwort fehlgeschlagen")).toBeTruthy();
});

// Fängt ab (#113): Die Modellangabe je Karte war eine eigene Randlinie statt der Modell-Pille (Frame CKCV4), und
// eine Karte ohne Modell (UC3 rechnet mit Code) stand in KI-Violett.
it("Modell je Karte als Modell-Pille, ohne Modell ein ruhiger Satz ohne Pille", async () => {
  const user = userEvent.setup();
  const mitModell = { text: "Einfach erklärt.", belege: [], zahlen: [], uc: "uc1" as const, modell: "gpt-5-4-mini", protokoll_id: null };
  antworte(200, { antworten: [{ ...uc3, modell: null }, mitModell], fehlend: [{ uc: "uc2", grund: "kein_adapter" }] });
  render(<Einstieg />);
  await user.type(screen.getByLabelText("Frage an die Kette"), "x{Enter}");
  await screen.findByText("Einfach erklärt.");
  const [uc3Karte, , uc1Karte] = karten();
  const pille = within(uc1Karte!).getByTestId("uc4-modell");
  expect(pille.getAttribute("data-baustein")).toBe("modell");
  expect(pille.textContent).toBe("Modell:gpt-5-4-mini");
  const ohne = within(uc3Karte!).getByTestId("uc4-modell");
  expect(ohne.getAttribute("data-baustein")).toBeNull();
  expect(ohne.textContent).toBe("Ohne KI gerechnet, nur mit Code.");
});

// Fängt ab (Modellwahl, Lead c0): die Wahl kommt nicht im POST an, „Voreinstellung der App“ schickt trotzdem ein
// Modell, und eine vom Zweck nicht erlaubte Wahl (ZweckFehler, hier UC2) steht als „Antwort fehlgeschlagen“ da.
it("schickt die Modellwahl mit, ohne Wahl kein Feld modell, gesperrte Wahl mit lesbarem Grund", async () => {
  const user = userEvent.setup();
  const abruf = antworte(200, { antworten: [uc3], fehlend: [{ uc: "uc2", grund: "ZweckFehler" }, { uc: "uc1", grund: "kein_adapter" }] });
  render(<Einstieg />);
  await user.type(screen.getByLabelText("Frage an die Kette"), "x{Enter}");
  await screen.findByText("Mit diesem Modell gesperrt");
  expect(fragen(abruf)).toEqual([{ frage: "x" }]);

  await user.click(screen.getByRole("radio", { name: "Claude" }));
  await user.click(screen.getByRole("button", { name: "Frage stellen" }));
  await screen.findByText("Mit diesem Modell gesperrt");
  expect(fragen(abruf)).toEqual([{ frage: "x" }, { frage: "x", modell: "claude" }]);
  expect(screen.queryByText("Antwort fehlgeschlagen")).toBeNull();
});

// Fängt ab (Review !72): Der Badge im Header zeigte die Wahl im Radio („claude“), auch wenn ein anderes Modell
// geantwortet hat oder die Frage scheiterte. Er zeigt das Modell aus der Antwort, vorher die Einstellung der App.
it("Badge zeigt das Modell, das geantwortet hat, nicht die Wahl", async () => {
  const user = userEvent.setup();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (adresse: string) => {
      if (adresse === "/api/uc4/frage") return Response.json({ antworten: [{ ...uc3, modell: "mistral-large-latest" }], fehlend: [] });
      if (adresse === "/api/plattform/modell") return Response.json({ provider: "azure", modell: "gpt-5-4-mini", version: null, quelle: "env" });
      return Response.json({});
    }),
  );
  render(
    <AppShell pfad="/uc4">
      <Einstieg />
    </AppShell>,
  );
  await user.click(screen.getByRole("radio", { name: "Claude" }));
  expect((await screen.findByTestId("modell-badge")).textContent).toContain("azure");
  await user.type(screen.getByLabelText("Frage an die Kette"), "x{Enter}");
  await screen.findByText(uc3.text);
  expect(screen.getByTestId("modell-badge").textContent).toBe("Modell:mistral-large-latest");
});
