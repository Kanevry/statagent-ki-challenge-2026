import { render, screen } from "@testing-library/react";
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
