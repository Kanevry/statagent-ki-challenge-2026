import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import fixture from "../../../schema/fixtures/protokoll-eintraege.json";
import { AppShell } from "../../src/shell/app-shell";
import { UcBereich } from "../../src/shell/uc-bereich";

function antworte(daten: Record<string, unknown>) {
  const aufrufe: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (adresse: string) => {
      aufrufe.push(adresse);
      const body = daten[adresse];
      return body === undefined ? new Response("{}", { status: 404 }) : Response.json(body);
    }),
  );
  return aufrufe;
}

afterEach(() => vi.unstubAllGlobals());

describe("Protokoll-Schublade", () => {
  it("lädt das Protokoll des aktiven UC, Esc schließt und gibt den Fokus an den Knopf zurück", async () => {
    const aufrufe = antworte({ "/api/plattform/modell": { provider: "mock", modell: "mock", version: null, quelle: "env" }, "/api/uc3/protokoll": fixture });
    const nutzer = userEvent.setup();
    render(<AppShell pfad="/uc3">inhalt</AppShell>);

    const knopf = screen.getByRole("button", { name: "Protokoll" });
    await nutzer.click(knopf);
    const schublade = screen.getByRole("dialog", { name: "Protokoll StatAgent" });
    await screen.findByText("Lieferung 2025-03 freigeben");
    expect(screen.getByText("Freigegeben").closest("[data-status]")?.getAttribute("data-status")).toBe("freigegeben");
    expect(aufrufe).toContain("/api/uc3/protokoll");
    await screen.findByText("mock · mock");

    await nutzer.keyboard("{Escape}");
    expect(schublade.isConnected).toBe(false);
    expect(document.activeElement).toBe(knopf);
  });

  it("zeigt den Fehlerzustand, wenn die Antwort den Vertrag verletzt", async () => {
    antworte({ "/api/uc1/protokoll": [{ id: 1, uc: "uc1" }] });
    const nutzer = userEvent.setup();
    render(<AppShell pfad="/uc1">inhalt</AppShell>);
    await nutzer.click(screen.getByRole("button", { name: "Protokoll" }));
    await screen.findByText("Protokoll nicht erreichbar");
    await waitFor(() => expect(screen.queryByText("Modell nicht erreichbar")).not.toBeNull());
  });

  it("auf der Landing gibt es weder Header noch Schublade", () => {
    antworte({});
    render(<AppShell pfad="/">landing</AppShell>);
    expect(screen.queryByRole("banner")).toBeNull();
    expect(screen.queryByRole("button", { name: "Protokoll" })).toBeNull();
    screen.getByText("landing");
  });
});

describe("UcBereich", () => {
  it("rendert die Unter-Navigation, aktiv ist der längste passende Punkt", () => {
    antworte({});
    render(
      <AppShell pfad="/uc3/lauf/2025-10">
        <UcBereich uc="uc3" nav={[{ href: "/uc3", label: "Start" }, { href: "/uc3/lauf", label: "Läufe" }]}>
          <p>seite</p>
        </UcBereich>
      </AppShell>,
    );
    const nav = screen.getByRole("navigation", { name: "StatAgent, Unterseiten" });
    expect(nav.querySelector('[aria-current="page"]')?.textContent).toBe("Läufe");
    expect(screen.getByRole("main").textContent).toBe("seite");
  });
});
