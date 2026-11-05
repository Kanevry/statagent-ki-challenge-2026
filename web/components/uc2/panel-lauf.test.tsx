import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockEreignisse, MOCK_ABBRUCH } from "../../app/api/uc2/_lib/mock";
import { modellWahl } from "../../app/api/uc2/_lib/vorbereitung";
import { PanelSeite } from "./panel-lauf";

// Neuer Versuch nach dem Abbruch: Modellwechsel startet einen neuen Fall; lehnt die API das Modell mit 422 ab, steht
// eine klare Meldung da, und die Runden bleiben stehen.

const schieben = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: schieben, replace: vi.fn() }) }));

class Quelle {
  static letzte: Quelle | null = null;
  static readonly CLOSED = 2;
  readyState = 1;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  private hoerer = new Map<string, ((e: Event) => void)[]>();
  constructor(readonly url: string) {
    Quelle.letzte = this;
  }
  addEventListener(art: string, f: (e: Event) => void) {
    this.hoerer.set(art, [...(this.hoerer.get(art) ?? []), f]);
  }
  close() {
    this.readyState = 2;
  }
  sende(art: string, daten: unknown) {
    for (const f of this.hoerer.get(art) ?? []) f(new MessageEvent(art, { data: JSON.stringify(daten) }));
  }
}

beforeEach(() => {
  vi.stubGlobal("EventSource", Quelle);
  vi.stubEnv("OLLAMA_MODEL", "qwen3:8b");
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  schieben.mockClear();
});

function abgebrochenerLauf() {
  render(<PanelSeite fallId={MOCK_ABBRUCH} modelle={modellWahl()} />);
  act(() => {
    for (const e of mockEreignisse(MOCK_ABBRUCH)!) Quelle.letzte!.sende(e.art, e);
    Quelle.letzte!.sende("ende", { status: "abgebrochen", letzte_seq: 37 });
  });
}

it("Modellwechsel startet einen neuen Fall mit dem gewählten Modell und öffnet ihn", async () => {
  const user = userEvent.setup();
  const abruf = vi.fn(async (_u: string, _o?: RequestInit) => Response.json({ fall_id: "mock-wartezeiten" }, { status: 202 }));
  vi.stubGlobal("fetch", abruf);
  abgebrochenerLauf();
  expect(screen.getByTestId("uc2-titel").textContent).toBe("Die Verhandlung ist in Runde 3 abgebrochen");
  await user.click(screen.getByTestId("uc2-modell-claude"));
  await vi.waitFor(() => expect(schieben).toHaveBeenCalledWith("/uc2/panel?fall=mock-wartezeiten"));
  expect(JSON.parse(String(abruf.mock.calls[0]?.[1]?.body))).toEqual({ fall: "wartezeiten", provider: "claude" });
});

it("Erneut nimmt das Modell des abgebrochenen Laufs aus dem Ereignis start", async () => {
  const user = userEvent.setup();
  const abruf = vi.fn(async (_u: string, _o?: RequestInit) => Response.json({ fall_id: "8" }, { status: 202 }));
  vi.stubGlobal("fetch", abruf);
  abgebrochenerLauf();
  await user.click(screen.getByTestId("uc2-erneut"));
  await vi.waitFor(() => expect(schieben).toHaveBeenCalled());
  expect(JSON.parse(String(abruf.mock.calls[0]?.[1]?.body))).toEqual({ fall: "wartezeiten", provider: "azure" });
});

it("ollama, das die API noch nicht annimmt (422), zeigt eine klare Meldung und lässt die Runden stehen", async () => {
  const user = userEvent.setup();
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({ detail: [{ msg: "provider" }] }, { status: 422 })));
  abgebrochenerLauf();
  const ollama = screen.getByTestId("uc2-modell-ollama") as HTMLButtonElement;
  expect(ollama.disabled).toBe(false);
  await user.click(ollama);
  const alarm = await screen.findByText(/Das Panel nimmt ollama gerade nicht an/);
  expect(alarm.textContent).toContain("Wähle ein anderes Modell.");
  expect(schieben).not.toHaveBeenCalled();
  expect(document.querySelectorAll("[data-akteur]")).toHaveLength(6);
  expect((screen.getByTestId("uc2-erneut") as HTMLButtonElement).disabled).toBe(false);
});

it("zeigt den Hinweis zur nicht übernommenen Auswahl aus der Adresse", () => {
  render(<PanelSeite fallId="mock-wartezeiten" modelle={modellWahl()} akteureIgnoriert />);
  expect(screen.getByTestId("uc2-akteure-hinweis")).toBeTruthy();
});
