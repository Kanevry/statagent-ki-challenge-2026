import { render } from "@testing-library/react";
import { FehlerChip, HerkunftChip, WarnChip } from "../../src/bausteine";

// Fängt ab: Chips, die vom Frame abweichen (Pen NeqAs, QVMco): Pille mit Padding 4/10, Symbol 12 px, Text 12 px.
describe("Chips nach Pen-Frames", () => {
  it("Warn-Chip: gelbe Pille, Symbol 12 px und Wort", () => {
    const { container } = render(<WarnChip>Auffälligkeit · erklärt-Datenproblem</WarnChip>);
    const chip = container.firstElementChild!;
    expect(chip.className).toContain("rounded-full");
    expect(chip.className).toContain("bg-warn-bg");
    expect(chip.className).toContain("px-2.5");
    expect(chip.querySelector("svg")?.getAttribute("class")).toContain("size-3");
    expect(chip.textContent).toBe("Auffälligkeit · erklärt-Datenproblem");
  });

  it("Fehler-Chip behält Symbol und Wort in derselben Form", () => {
    const { container } = render(<FehlerChip />);
    expect(container.querySelector("svg")?.getAttribute("class")).toContain("size-3");
    expect(container.textContent).toBe("Fehler");
  });

  it("Herkunft-Chip: ruhiger Textlink „Beleg“ mit Datenbank-Symbol 12 px, ohne Fläche und ohne Mono", () => {
    const { container } = render(<HerkunftChip sql="select 1" lieferung="2025-03" />);
    const knopf = container.querySelector("button")!;
    expect(knopf.className).not.toMatch(/bg-|rounded-full/);
    expect(knopf.className).toContain("underline");
    const symbol = knopf.querySelector('[data-piktogramm="datenbank"]');
    expect(symbol?.getAttribute("width")).toBe("12");
    expect(symbol?.getAttribute("aria-hidden")).toBe("true");
    expect(knopf.querySelector(".font-mono")).toBeNull();
  });
});
