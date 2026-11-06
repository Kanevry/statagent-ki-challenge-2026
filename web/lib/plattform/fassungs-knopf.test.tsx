import { render, screen } from "@testing-library/react";
import { afterEach } from "vitest";
import type { Fassung } from "./fassung";
import { FassungsKnopf, fassungsLink } from "./fassungs-knopf";

// Fängt ab (UI-Regie): Wer die Passwortabfrage der Live-Vorführung abbricht, war von der Seite weg. Nur dieser Weg
// öffnet einen neuen Tab; der Rückweg zur öffentlichen Fassung bleibt im selben Tab.

const live: Fassung = { adresse: "https://live.example.org", art: "live" };
const oeffentlich: Fassung = { adresse: "https://www.example.org", art: "oeffentlich" };

function zeige(fassung: Fassung) {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({ fassung })));
  return render(<FassungsKnopf />);
}

afterEach(() => vi.unstubAllGlobals());

describe("FassungsKnopf", () => {
  it("öffnet die Live-Vorführung in einem neuen Tab und sagt es Screenreadern", async () => {
    zeige(live);
    const link = await screen.findByRole("link", { name: /^Live-Vorführung \(mit Passwort\)\s*\(öffnet in einem neuen Tab\)$/ });
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toContain("noopener");
    expect(link.querySelector(".sr-only")?.textContent).toBe(" (öffnet in einem neuen Tab)");
  });

  it("lässt die öffentliche Fassung im selben Tab", async () => {
    zeige(oeffentlich);
    const link = await screen.findByRole("link", { name: "Öffentliche Fassung" });
    expect(link.hasAttribute("target")).toBe(false);
    expect(link.hasAttribute("rel")).toBe(false);
    expect(link.querySelector(".sr-only")).toBeNull();
  });

  it("liefert die Link-Eigenschaften je Fassung für Kopf und Startseite", () => {
    expect(fassungsLink(live)).toEqual({ href: live.adresse, target: "_blank", rel: "noopener", "data-fassung": "live" });
    expect(fassungsLink(oeffentlich)).toEqual({ href: oeffentlich.adresse, "data-fassung": "oeffentlich" });
  });
});
