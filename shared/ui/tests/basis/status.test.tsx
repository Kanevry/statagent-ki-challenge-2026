import { render } from "@testing-library/react";
import { Status, type StatusArt } from "../../src/basis";

// Fängt ab: ein Status, der nur noch Farbe oder nur noch das Symbol zeigt (etwa bei leerem Wort),
// und damit für Farbfehlsichtige und Screenreader nichts mehr sagt.
const arten: StatusArt[] = ["ok", "warnung", "fehler", "info"];

describe("Status", () => {
  it.each(arten)("zeigt bei %s immer Symbol und Wort", (art) => {
    for (const wort of [undefined, "", "Lieferung geprüft"]) {
      const { container, unmount } = render(<Status art={art}>{wort}</Status>);
      const svg = container.querySelector("svg");
      expect(svg, "Symbol fehlt").not.toBeNull();
      expect(svg?.getAttribute("aria-hidden")).toBe("true");
      expect(container.textContent?.trim().length ?? 0).toBeGreaterThan(0);
      if (wort) expect(container.textContent).toContain(wort);
      unmount();
    }
  });
});
