import { act, render, screen } from "@testing-library/react";
import { ModellBadge } from "../../src/shell/modell-badge";

// Fängt ab: zod verwirft `zuletzt` aus `plattform.llm status --json`, und der Badge zeigt vor der Jury den
// gewählten Provider, obwohl laut Protokoll zuletzt eine Ausweichstufe oder ein anderer Provider geantwortet hat.

const gewaehlt = { provider: "azure", modell: "gpt-5", version: "2026-08-01", quelle: "env" };
const zuletzt = (provider: string, fallback_stufe: number) => ({
  provider,
  modell: "m",
  version: null,
  fallback_stufe,
  zweck: "regel_entwurf",
  zeit: "2026-11-05T09:12:00+01:00",
});

function zeige(body: unknown) {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(body)));
  return render(<ModellBadge />);
}

afterEach(() => vi.unstubAllGlobals());

describe("ModellBadge mit zuletzt", () => {
  it("nennt einen abweichenden Provider mit Stufe, ruhig als Hinweis mit Symbol", async () => {
    zeige({ ...gewaehlt, zuletzt: zuletzt("mistral", 2) });
    const hinweis = await screen.findByTestId("modell-zuletzt");
    expect(hinweis.textContent).toBe("zuletzt mistral (Stufe 2)");
    expect(hinweis.querySelector("[data-status-symbol]")?.getAttribute("data-status-symbol")).toBe("info");
    screen.getByText("azure · gpt-5");
  });

  it("nennt auch denselben Provider ab Stufe 2", async () => {
    zeige({ ...gewaehlt, zuletzt: zuletzt("azure", 2) });
    expect((await screen.findByTestId("modell-zuletzt")).textContent).toBe("zuletzt azure (Stufe 2)");
  });

  it("schweigt bei gleichem Provider auf Stufe 1 und bei zuletzt null", async () => {
    for (const z of [zuletzt("azure", 1), null]) {
      const { unmount } = zeige({ ...gewaehlt, zuletzt: z });
      await screen.findByText("azure · gpt-5");
      expect(screen.queryByTestId("modell-zuletzt")).toBeNull();
      unmount();
    }
  });
});

describe("ModellBadge lädt periodisch neu", () => {
  afterEach(() => vi.useRealTimers());

  const antwort = (zu: unknown) => Response.json({ ...gewaehlt, zuletzt: zu });

  it("zeigt nach 30 s eine neu eingetretene Ausweichstufe und räumt beim Unmount auf", async () => {
    vi.useFakeTimers();
    const holen = vi
      .fn()
      .mockImplementationOnce(async () => antwort(null))
      .mockImplementation(async () => antwort(zuletzt("mistral", 2)));
    vi.stubGlobal("fetch", holen);
    const { unmount } = render(<ModellBadge />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(holen).toHaveBeenCalledTimes(1);
    expect(screen.queryByTestId("modell-zuletzt")).toBeNull();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(holen).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId("modell-zuletzt").textContent).toBe("zuletzt mistral (Stufe 2)");

    unmount();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(90_000);
    });
    expect(holen).toHaveBeenCalledTimes(2);
  });

  it("lädt sofort neu, wenn der Tab wieder sichtbar wird", async () => {
    vi.useFakeTimers();
    const holen = vi.fn(async () => antwort(null));
    vi.stubGlobal("fetch", holen);
    render(<ModellBadge />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(holen).toHaveBeenCalledTimes(1);

    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(holen).toHaveBeenCalledTimes(2);
  });
});

describe("ModellBadge nach Frames CKCV4 und nas8Y", () => {
  // Fängt ab: ein Auf-/Ab-Symbol, das eine Auswahl verspricht, die es nicht gibt.
  it("ist eine ruhige Zeile ohne Fläche, Punkt oder Wechsel-Symbol (UI-Regie: keine Pillen, eine Akzentfarbe)", async () => {
    zeige({ ...gewaehlt, zuletzt: null });
    await screen.findByText("azure · gpt-5");
    const badge = screen.getByTestId("modell-badge");
    expect(badge.className).toContain("text-slate");
    expect(badge.className).not.toMatch(/bg-|rounded-full|violett/);
    expect(badge.className).not.toContain("border-l-2");
    expect(badge.querySelector("[data-piktogramm]")).toBeNull();
  });

  // Fängt ab: „Modell:“ nur für Screenreader; Sehende lesen dann eine Zeichenkette ohne Bezug.
  it("zeigt „Modell:“ sichtbar, kurz und lang; lang zusätzlich „austauschbar“", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ ...gewaehlt, zuletzt: null })));
    const kurz = render(<ModellBadge />);
    await screen.findByText("azure · gpt-5");
    expect(kurz.container.textContent).toBe("Modell:azure · gpt-5");
    expect(screen.getByText("Modell:").className).not.toContain("sr-only");
    kurz.unmount();

    const lang = render(<ModellBadge lang />);
    await screen.findByText("azure · gpt-5");
    expect(lang.container.textContent).toBe("Modell:azure · gpt-5· austauschbar");
    expect(screen.getByText("Modell:").className).not.toContain("sr-only");
  });

  // Fängt ab: der lange Hinweis „zuletzt mistral (Stufe 2)“ sprengt den Header bei 390 px.
  it("zeigt im Header nur „zuletzt mistral“, die Stufe für Screenreader und im Titel", async () => {
    zeige({ ...gewaehlt, zuletzt: zuletzt("mistral", 2) });
    const hinweis = await screen.findByTestId("modell-zuletzt");
    expect(screen.getByText("(Stufe 2)", { exact: false }).className).toContain("sr-only");
    expect(hinweis.getAttribute("title")).toBe("Zuletzt hat mistral geantwortet, Stufe 2.");
  });

  // Fängt ab: „mock · mock“ im Badge, das niemand ohne Fachwissen versteht.
  it("sagt im Mock-Betrieb in Alltagssprache, dass keine KI angeschlossen ist", async () => {
    zeige({ provider: "mock", modell: "mock", version: null, quelle: "env", zuletzt: null });
    await screen.findByText("Ohne Sprachmodell");
    expect(screen.getByTestId("modell-badge").textContent).toBe("Ohne Sprachmodell");
    expect(screen.queryByText(/mock/)).toBeNull();
  });

  it("zeigt den Fehlerzustand als ruhige Zeile mit Wort, ohne Alarmfläche", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 500 })));
    render(<ModellBadge />);
    const chip = await screen.findByText("Modell nicht erreichbar").then((t) => t.closest("[data-testid=modell-badge]")!);
    expect(chip.textContent).toBe("Modell nicht erreichbar");
    expect(chip.className).not.toContain("bg-warn-bg");
  });
});

// Fängt ab (Lead 58, UC2-Sichtprüfung): Die Seite läuft im Testbetrieb, der Header zeigt aber die globale
// Einstellung „azure · gpt-5“. Die Seite meldet ihr Modell über SeitenModell; beim Verlassen gilt wieder global.
describe("Modell der Seite", () => {
  it("SeitenModell mock schlägt die globale Angabe, nach dem Verlassen gilt sie wieder", async () => {
    const { AppShell } = await import("../../src/shell/app-shell");
    const { SeitenModell } = await import("../../src/shell/seiten-modell");
    const { TESTBETRIEB_TEXT } = await import("../../src/shell/modell-badge");
    vi.stubGlobal("fetch", vi.fn(async () => Response.json(gewaehlt)));
    const { rerender } = render(
      <AppShell pfad="/uc2">
        <SeitenModell provider="mock" />
      </AppShell>,
    );
    expect((await screen.findByTestId("modell-badge")).textContent).toBe(TESTBETRIEB_TEXT);
    rerender(<AppShell pfad="/uc2">ohne Angabe</AppShell>);
    expect(await screen.findByText("azure · gpt-5")).toBeTruthy();
  });

  // Fängt ab (Review !66): Die Seite meldet einen Anbieter, den der Server gar nicht nutzt, und der Badge zeigt
  // ihn trotzdem. Eine Vorgabe gilt nur für Testbetrieb oder wenn sie zum gemessenen Anbieter passt.
  it("eine fremde Vorgabe gilt nicht, eine passende schon", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json(gewaehlt)));
    const { rerender } = render(<ModellBadge vorgabe={{ provider: "mistral", modell: "mistral-large-latest" }} />);
    expect(await screen.findByText("azure · gpt-5")).toBeTruthy();
    rerender(<ModellBadge vorgabe={{ provider: "azure", modell: "gpt-5-4-mini" }} />);
    expect(screen.getByTestId("modell-badge").textContent).toBe("Modell:azure · gpt-5-4-mini");
  });
});


// Fängt ab (Modellwahl /uc4): Die Seite schickt den gewählten Anbieter mit jeder Anfrage, der Badge zeigt aber
// weiter die globale Einstellung.
it("eine gewählte Vorgabe gilt auch gegen den gemessenen Anbieter", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(gewaehlt)));
  render(<ModellBadge vorgabe={{ provider: "mistral", gewaehlt: true }} />);
  expect(screen.getByTestId("modell-badge").textContent).toBe("Modell:mistral");
  expect(screen.getByTestId("modell-badge").getAttribute("title")).toBe("Auf dieser Seite gewählt");
});
