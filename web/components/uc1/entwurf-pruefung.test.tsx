import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { abbildenAntrag } from "./antrag";
import { EntwurfPruefung, PRUEF_SATZ } from "./entwurf-pruefung";
import { LotseAnbieter } from "./lotse-kontext";
import pflege from "./fixtures/pflege.json";

const antrag = abbildenAntrag(pflege.antrag);
if (!antrag) throw new Error("Fixture ohne Antrag");
const PDF = "/api/uc1/antrag/pdf?art=pflegegeld&sitzung=x";

function stand(): string {
  return screen.getByTestId("uc1-entwurf-stand").textContent ?? "";
}

/** Prüfung im Anbieter; „Seite wechseln“ hängt sie aus und wieder ein, wie „Weiter zur Stelle“ und zurück. */
function Seite({ live = true }: { live?: boolean }) {
  const [sichtbar, setSichtbar] = useState(true);
  return (
    <LotseAnbieter>
      <button type="button" onClick={() => setSichtbar((s) => !s)}>
        Seite wechseln
      </button>
      {sichtbar && antrag && <EntwurfPruefung antrag={antrag} live={live} pdf={PDF} ebene="h2" />}
    </LotseAnbieter>
  );
}

describe("EntwurfPruefung", () => {
  // Fängt: ein PDF, das vor der Prüfung speicherbar ist, „Team“ als Name, ein Entwurf, der danach nicht mit Namen als
  // geprüft dasteht, und Bedienelemente unter 44 px.
  it("gibt das PDF erst nach der Prüfung mit Vor- und Nachnamen frei", async () => {
    const nutzer = userEvent.setup();
    render(<Seite />);
    expect(stand()).toBe("Entwurf nicht geprüft");
    expect(screen.queryByRole("link", { name: "Antrag als PDF speichern" })).toBeNull();
    expect((screen.getByRole("button", { name: "Antrag als PDF speichern" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(PRUEF_SATZ)).toBeTruthy();

    const feld = screen.getByLabelText("Ihr Vor- und Nachname");
    const markieren = screen.getByRole("button", { name: "Entwurf als geprüft markieren" }) as HTMLButtonElement;
    expect(feld.className).toContain("h-11");
    expect(markieren.className).toContain("min-h-11");
    await nutzer.type(feld, "Team");
    expect(markieren.disabled).toBe(true);
    expect(screen.getByText("Bitte Vor- und Nachname eingeben.")).toBeTruthy();
    await nutzer.clear(feld);
    await nutzer.type(feld, "Maria Huber");
    await nutzer.click(markieren);

    expect(stand()).toMatch(/^Entwurf geprüft von Maria Huber, /);
    expect(screen.getByRole("link", { name: "Antrag als PDF speichern" }).getAttribute("href")).toBe(PDF);
    expect(document.querySelector("[data-uc1-pruefung]")?.getAttribute("data-uc1-pruefung")).toBe("geprueft");
  });

  // Fängt: eine Prüfung, die beim Seitenwechsel verloren geht und das PDF wieder sperrt (lokaler Zustand).
  it("bleibt nach einem Seitenwechsel in der Sitzung erhalten", async () => {
    const nutzer = userEvent.setup();
    render(<Seite />);
    await nutzer.type(screen.getByLabelText("Ihr Vor- und Nachname"), "Maria Huber");
    await nutzer.click(screen.getByRole("button", { name: "Entwurf als geprüft markieren" }));
    await nutzer.click(screen.getByRole("button", { name: "Seite wechseln" }));
    expect(screen.queryByTestId("uc1-entwurf-stand")).toBeNull();
    await nutzer.click(screen.getByRole("button", { name: "Seite wechseln" }));
    expect(stand()).toMatch(/^Entwurf geprüft von Maria Huber, /);
    expect(screen.getByRole("link", { name: "Antrag als PDF speichern" })).toBeTruthy();
  });

  // Fängt: eine Prüfung, die sich nicht zurücknehmen lässt, oder ein PDF, das danach freigegeben bleibt.
  it("lässt die Prüfung zurücknehmen und sperrt das PDF wieder", async () => {
    const nutzer = userEvent.setup();
    render(<Seite />);
    await nutzer.type(screen.getByLabelText("Ihr Vor- und Nachname"), "Maria Huber");
    await nutzer.click(screen.getByRole("button", { name: "Entwurf als geprüft markieren" }));
    const zurueck = screen.getByRole("button", { name: "Prüfung zurücknehmen" });
    expect(zurueck.className).toContain("min-h-11");
    await nutzer.click(zurueck);
    expect(stand()).toBe("Entwurf nicht geprüft");
    expect(screen.queryByRole("link", { name: "Antrag als PDF speichern" })).toBeNull();
    expect((screen.getByLabelText("Ihr Vor- und Nachname") as HTMLInputElement).value).toBe("");
  });

  // Fängt: eine Prüfung, die im aufgezeichneten Beispiel fehlt oder dort ein PDF anbietet.
  it("funktioniert im Beispiel ohne PDF", async () => {
    const nutzer = userEvent.setup();
    render(<Seite live={false} />);
    expect(screen.queryByRole("button", { name: "Antrag als PDF speichern" })).toBeNull();
    await nutzer.type(screen.getByLabelText("Ihr Vor- und Nachname"), "Maria Huber");
    await nutzer.click(screen.getByRole("button", { name: "Entwurf als geprüft markieren" }));
    expect(stand()).toMatch(/^Entwurf geprüft von Maria Huber/);
    expect(screen.queryByRole("link", { name: "Antrag als PDF speichern" })).toBeNull();
  });
});
