import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AppHeader } from "../../src/shell/header";
import { protokollUc, zeigtHeader } from "../../src/shell/navigation";

function zeige(pfad: string) {
  vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
  return render(<AppHeader pfad={pfad} protokollOffen={false} onProtokoll={() => {}} schubladeId="s" />);
}

afterEach(() => vi.unstubAllGlobals());

describe("AppHeader", () => {
  it("rendert fünf Tabs aus der Registry in fester Reihenfolge, UC3 trägt „bewertet“", () => {
    zeige("/uc3");
    const links = within(screen.getByRole("navigation", { name: "Bereiche" })).getAllByRole("link");
    expect(links.map((l) => l.getAttribute("href"))).toEqual(["/", "/uc3", "/uc1", "/uc2", "/praesentation"]);
    expect(links[1]?.textContent).toBe("UC3 StatAgentbewertet");
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
    expect(document.activeElement).toBe(links[4]);
    await nutzer.keyboard("{Home}");
    expect(document.activeElement).toBe(links[0]);
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
