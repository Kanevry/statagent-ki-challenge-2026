import { fireEvent, render, screen } from "@testing-library/react";
import { Knopf } from "../../src/basis";

// Fängt ab: ein Knopf im Formular, der ohne ausdrückliches type="submit" sendet (Enter oder Klick
// löst dann z. B. eine Freigabe aus), und ein Knopf, der sich per autoFocus selbst den Fokus nimmt.
describe("Knopf", () => {
  it("ist standardmäßig type=button und sendet kein Formular", () => {
    const senden = vi.fn((e: SubmitEvent) => e.preventDefault());
    render(
      <form onSubmit={(e) => senden(e.nativeEvent as SubmitEvent)}>
        <Knopf>Freigeben</Knopf>
      </form>,
    );
    const knopf = screen.getByRole("button", { name: "Freigeben" });
    expect(knopf).toHaveProperty("type", "button");
    fireEvent.click(knopf);
    expect(senden).not.toHaveBeenCalled();
  });

  it("übernimmt kein autoFocus, auch nicht ungetypt hineingereicht", () => {
    const ungetypt = { autoFocus: true } as Record<string, unknown>;
    render(<Knopf {...ungetypt}>Freigeben</Knopf>);
    const knopf = screen.getByRole("button", { name: "Freigeben" });
    expect(document.activeElement).not.toBe(knopf);
  });
});
