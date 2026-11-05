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
  it("ist eine violette Pille mit Punkt und Wechsel-Symbol, der Wert steht in Mono", async () => {
    zeige({ ...gewaehlt, zuletzt: null });
    const wert = await screen.findByText("azure · gpt-5");
    expect(wert.className).toContain("font-mono");
    const badge = screen.getByTestId("modell-badge");
    expect(badge.className).toContain("rounded-full");
    expect(badge.className).toContain("bg-violett-bg");
    expect(badge.className).not.toContain("border-l-2");
    expect(badge.querySelector('[data-piktogramm="wechseln"]')?.getAttribute("width")).toBe("14");
  });

  it("kurz im Header, „Modell:“ nur für Screenreader; lang mit „Modell:“ und „austauschbar“ sichtbar", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ ...gewaehlt, zuletzt: null })));
    const kurz = render(<ModellBadge />);
    await screen.findByText("azure · gpt-5");
    expect(kurz.container.textContent).toBe("Modell:azure · gpt-5");
    expect(screen.getByText("Modell:").className).toContain("sr-only");
    kurz.unmount();

    const lang = render(<ModellBadge lang />);
    await screen.findByText("azure · gpt-5");
    expect(lang.container.textContent).toBe("Modell:azure · gpt-5· austauschbar");
    expect(screen.getByText("Modell:").className).not.toContain("sr-only");
  });

  it("zeigt den Fehlerzustand als Warn-Chip mit Symbol und Wort", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 500 })));
    render(<ModellBadge />);
    const chip = await screen.findByText("Modell nicht erreichbar").then((t) => t.closest("[data-testid=modell-badge]")!);
    expect(chip.textContent).toBe("Modell nicht erreichbar");
    expect(chip.className).toContain("bg-warn-bg");
    expect(chip.querySelector("[data-status-symbol=warnung]")).not.toBeNull();
  });
});
