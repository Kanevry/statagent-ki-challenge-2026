import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AppHeader } from "../../src/shell/header";
import { marke, protokollUc, zeigtHeader } from "../../src/shell/navigation";

function zeige(pfad: string) {
  vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
  return render(<AppHeader pfad={pfad} protokollOffen={false} onProtokoll={() => {}} schubladeId="s" />);
}

afterEach(() => vi.unstubAllGlobals());

describe("AppHeader", () => {
  it("rendert sechs Tabs aus der Registry in fester Reihenfolge, UC3 trägt „bewertet“", () => {
    zeige("/uc3");
    const links = within(screen.getByRole("navigation", { name: "Bereiche" })).getAllByRole("link");
    expect(links.map((l) => l.getAttribute("href"))).toEqual(["/", "/uc3", "/uc1", "/uc2", "/uc4", "/praesentation"]);
    expect(links[1]?.textContent).toBe("UC3 · StatAgentbewertet");
    expect(links[4]?.textContent).toBe("UC4 · Einstieg");
    expect(links.filter((l) => l.textContent?.includes("bewertet"))).toHaveLength(1);
  });

  it("markiert genau den Tab der Route mit aria-current, auch auf Unterseiten", () => {
    zeige("/uc1/chat");
    const aktuell = screen.getAllByRole("link").filter((l) => l.getAttribute("aria-current") === "page");
    expect(aktuell.map((l) => l.getAttribute("href"))).toEqual(["/uc1"]);
  });

  it("Pfeiltasten wandern zwischen den Tabs, Ende und Pos1 springen an den Rand", async () => {
    const nutzer = userEvent.setup();
    zeige("/uc3");
    const links = screen.getAllByRole("link");
    links[0]!.focus();
    await nutzer.keyboard("{ArrowRight}");
    expect(document.activeElement).toBe(links[1]);
    await nutzer.keyboard("{ArrowLeft}{ArrowLeft}");
    expect(document.activeElement).toBe(links[5]);
    await nutzer.keyboard("{Home}");
    expect(document.activeElement).toBe(links[0]);
  });
});

describe("AppHeader nach Frame nas8Y", () => {
  it("füllt den aktiven Tab mit Grün und weißer Fettschrift, die anderen bleiben ohne Fläche", () => {
    zeige("/uc3");
    const [uebersicht, uc3] = screen.getAllByRole("link");
    expect(uc3?.className).toContain("bg-gruen");
    expect(uc3?.className).toContain("text-white");
    expect(uc3?.className).toContain("font-bold");
    expect(uebersicht?.className).not.toContain("bg-gruen");
    expect(uebersicht?.className).toContain("rounded-lg");
  });

  it("setzt den Chip „bewertet“ in Mint auf UC3", () => {
    zeige("/uc1");
    const chip = screen.getByText("bewertet");
    expect(chip.className).toContain("bg-mint");
    expect(chip.closest("a")?.getAttribute("data-tab")).toBe("uc3");
  });

  it("zeigt links die Marke mit zweiter Zeile und rechts den Protokoll-Knopf mit Symbol", () => {
    zeige("/uc3");
    const kopf = screen.getByRole("banner");
    expect(kopf.querySelector("[data-marke]")?.textContent).toBe("StatAgentby Bernhard Götzendorfer · Team OneShotAndy");
    const knopf = screen.getByRole("button", { name: "Protokoll" });
    expect(knopf.querySelector('[data-piktogramm="protokoll"]')).not.toBeNull();
    expect(knopf.className).toContain("border-line");
  });

  it("nennt die Marke nur auf UC3 StatAgent, sonst OneShotAndy", () => {
    expect(marke("/uc3").name).toBe("StatAgent");
    expect(marke("/uc3/lauf/2025-10").name).toBe("StatAgent");
    for (const pfad of ["/uc1", "/uc2", "/uc4", "/praesentation", "/_bausteine"]) {
      expect(marke(pfad).name, pfad).toBe("OneShotAndy");
    }
    expect(marke("/uc1").zeile).not.toContain("—");
  });
});

describe("Shell-Regeln", () => {
  it("Header nur außerhalb der Landing", () => {
    expect(zeigtHeader("/")).toBe(false);
    expect(zeigtHeader("/praesentation")).toBe(true);
  });

  it("Schublade zeigt den UC der Route, auf / und /praesentation UC3", () => {
    expect(protokollUc("/uc2/szenario").id).toBe("uc2");
    expect(protokollUc("/praesentation").id).toBe("uc3");
    expect(protokollUc("/").id).toBe("uc3");
    expect(protokollUc("/uc10").id).toBe("uc3");
  });
});
