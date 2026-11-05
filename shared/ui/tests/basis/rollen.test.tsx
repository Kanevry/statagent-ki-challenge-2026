import { render, screen } from "@testing-library/react";
import { Feld, Status, Tabelle, Zahl } from "../../src/basis";

// Fängt ab: Zahlen mit Leerzeichen statt Punkt oder Bindestrich statt Minus, Status nur als Symbol,
// verlorene aria-describedby-IDs und eine Tabelle ohne Spaltenköpfe für Screenreader.
describe("Basis-Elemente: Rollen und Format", () => {
  it("Zahl formatiert 612.340 und −260 und hängt die Einheit geschützt an", () => {
    render(
      <>
        <Zahl wert={612340} data-testid="a" />
        <Zahl wert={-260} einheit="Personen" data-testid="b" />
      </>,
    );
    expect(screen.getByTestId("a").textContent).toBe("612.340");
    expect(screen.getByTestId("b").textContent).toBe("\u2212260\u00a0Personen");
  });

  it.each([false, "   "])("Status zeigt bei %j das Standardwort", (inhalt) => {
    render(<Status art="warnung">{inhalt}</Status>);
    expect(screen.getByText("Warnung")).toBeTruthy();
  });

  it("Feld führt eigene und hereingereichte Beschreibungen zusammen und markiert Fehler", () => {
    render(<Feld label="Name" hinweis="Vor- und Nachname" fehler="Bitte ausfüllen" aria-describedby="extra" />);
    const eingabe = screen.getByRole("textbox", { name: "Name" });
    const ids = (eingabe.getAttribute("aria-describedby") ?? "").split(" ");
    expect(ids).toContain("extra");
    expect(ids).toHaveLength(3);
    expect(eingabe.getAttribute("aria-invalid")).toBe("true");
  });

  it("Tabelle hat Beschriftung und Spaltenköpfe", () => {
    render(
      <Tabelle
        beschriftung="Beschäftigte je Monat"
        spalten={[
          { schluessel: "monat", titel: "Monat" },
          { schluessel: "anzahl", titel: "Anzahl", zahl: true },
        ]}
        zeilen={[{ monat: "2025-03", anzahl: "387.180" }]}
      />,
    );
    expect(screen.getByRole("table", { name: "Beschäftigte je Monat" })).toBeTruthy();
    expect(screen.getAllByRole("columnheader").map((th) => th.textContent)).toEqual(["Monat", "Anzahl"]);
  });
});
