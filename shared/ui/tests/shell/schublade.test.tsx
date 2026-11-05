import { act, render, screen, waitFor } from "@testing-library/react";
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
    // Frame yK42X: die Art steht als Wort vor dem Namen, bei einer Freigabe in Grün.
    const freigabe = screen.getByText("Freigabe");
    expect(freigabe.closest("[data-status]")?.getAttribute("data-status")).toBe("freigegeben");
    expect(freigabe.className).toContain("text-gruen");
    expect(screen.getByText("Vorschlag").closest("[data-status]")?.getAttribute("data-akteur")).toBe("agent");
    expect(aufrufe).toContain("/api/uc3/protokoll");
    await screen.findByText("mock · mock");

    await nutzer.keyboard("{Escape}");
    expect(schublade.isConnected).toBe(false);
    expect(document.activeElement).toBe(knopf);
  });

  it("ist modal: aria-modal, übriger Inhalt inert, Fokus kommt auch ohne Klick-Fokus an den Knopf zurück", async () => {
    antworte({ "/api/uc3/protokoll": [] });
    const nutzer = userEvent.setup();
    const { container } = render(<AppShell pfad="/uc3">inhalt</AppShell>);
    const geruest = container.querySelector("[data-shell-geruest]")!;
    const knopf = screen.getByRole("button", { name: "Protokoll" });

    // Safari fokussiert Buttons beim Klick nicht: Öffnen per Ereignis, ohne dass der Knopf je Fokus hatte.
    document.body.focus();
    act(() => knopf.click());
    const schublade = screen.getByRole("dialog", { name: "Protokoll StatAgent" });
    expect(schublade.getAttribute("aria-modal")).toBe("true");
    expect(geruest.hasAttribute("inert")).toBe(true);
    expect(geruest.contains(schublade)).toBe(false);
    await screen.findByText("Für StatAgent gibt es noch keine Einträge.");

    await nutzer.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(geruest.hasAttribute("inert")).toBe(false);
    expect(document.activeElement).toBe(knopf);
  });

  it("zeigt die Uhrzeit allein, das Datum nur bei Einträgen von einem anderen Tag", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-05T12:00:00+01:00"));
    antworte({
      "/api/uc3/protokoll": [
        { ...fixture[1], id: 2, zeit: "2026-11-05T11:05:00+01:00" },
        { ...fixture[1], id: 1, zeit: "2026-11-03T10:30:00+01:00" },
      ],
    });
    try {
      const nutzer = userEvent.setup({ advanceTimers: () => {} });
      render(<AppShell pfad="/uc3">inhalt</AppShell>);
      await nutzer.click(screen.getByRole("button", { name: "Protokoll" }));
      const zeiten = await screen.findAllByText(/^\d\d:\d\d$/);
      expect(zeiten.map((z) => z.closest("time")?.textContent)).toEqual(["11:05", "10:3003.11."]);
    } finally {
      vi.useRealTimers();
    }
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
