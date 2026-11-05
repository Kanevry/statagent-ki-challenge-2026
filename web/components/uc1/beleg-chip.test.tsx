import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { BelegChip } from "./beleg-chip";

const ZITAT = "Pflegegeld gebührt bei ständigem Betreuungsbedarf von mehr als 65 Stunden im Monat.";

describe("BelegChip", () => {
  // Fängt: ein Zitat, das schon zu sichtbar ist oder beim Aufklappen fehlt, ein aria-expanded, das nicht mitwechselt,
  // ein aria-controls ins Leere und eine fehlende Zeile „Stand“.
  it("klappt das Zitat wörtlich mit Quelle und Stand auf und wieder zu", async () => {
    const nutzer = userEvent.setup();
    render(<BelegChip quelle="BPGG § 4" zitat={ZITAT} fassung="1. Jänner 2015" />);
    const knopf = screen.getByRole("button", { name: /BPGG § 4.*Zitat ansehen/ });
    expect(knopf.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText(ZITAT)).toBeNull();

    await nutzer.click(knopf);
    expect(knopf.getAttribute("aria-expanded")).toBe("true");
    const bereich = document.getElementById(knopf.getAttribute("aria-controls") ?? "");
    expect(bereich?.querySelector("blockquote")?.textContent).toBe(ZITAT);
    expect(bereich?.querySelector("p")?.textContent).toBe("Stand: 1. Jänner 2015");

    await nutzer.click(knopf);
    expect(knopf.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText(ZITAT)).toBeNull();
  });

  // Fängt: den Zahlen-Text „keine Abfrage hinterlegt“ an einem Zitat und einen erfundenen Stand.
  it("zeigt ohne Fassung keinen Stand und nichts über Abfragen", async () => {
    render(<BelegChip quelle="Antrag PAL080, S. 2" zitat="Gründe Ihrer Pflegebedürftigkeit:" />);
    await userEvent.setup().click(screen.getByRole("button"));
    expect(document.querySelector("blockquote")?.textContent).toBe("Gründe Ihrer Pflegebedürftigkeit:");
    expect(document.body.textContent).not.toMatch(/Abfrage|Stand:/);
  });
});
