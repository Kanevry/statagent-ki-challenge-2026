import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HerkunftChip } from "../../src/bausteine";

const sql = "select count(*) from roh.lieferung where lieferung = '2025-03'";

// Fängt ab: Beleg, der sich nicht öffnen lässt oder ein anderes SQL kopiert als das angezeigte.
it("zeigt nach Klick das SQL und kopiert genau dieses", async () => {
  const user = userEvent.setup();
  // Nach setup(), weil user-event eine eigene Zwischenablage einhängt.
  const schreiben = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue();
  render(<HerkunftChip sql={sql} lieferung="2025-03" lauf="L-0412" />);

  const chip = screen.getByRole("button", { name: "roh.lieferung 2025-03 · SQL ansehen" });
  expect(chip.getAttribute("aria-expanded")).toBe("false");
  expect(screen.queryByText(sql)).toBeNull();

  await user.click(chip);
  expect(chip.getAttribute("aria-expanded")).toBe("true");
  expect(screen.getByText(sql)).toBeTruthy();
  expect(screen.getByText(/Lauf L-0412/)).toBeTruthy();

  await user.click(screen.getByRole("button", { name: "Kopieren" }));
  expect(schreiben).toHaveBeenCalledWith(sql);
  expect(await screen.findByText("Kopiert")).toBeTruthy();
});

// Fängt ab: ein Beleg ohne SQL, der einen leeren „Kopieren“-Knopf anbietet, und ein vorläufiger Stand, der
// wie ein endgültiger aussieht (UC4-Antworten, #98).
it("ohne SQL: Beleg ansehen ohne Kopieren, vorläufiger Stand steht im Chip", async () => {
  const user = userEvent.setup();
  render(<HerkunftChip sql={null} lieferung="2025-03" stand="vorlaeufig" />);

  const chip = screen.getByRole("button", { name: "roh.lieferung 2025-03 · vorläufig · Beleg ansehen" });
  await user.click(chip);
  expect(screen.getByText(/keine Abfrage hinterlegt/)).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Kopieren" })).toBeNull();
});
