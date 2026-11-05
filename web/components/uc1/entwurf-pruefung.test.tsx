import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { abbildenAntrag } from "./antrag";
import { entwurfAnweisung, EntwurfPruefung } from "./entwurf-pruefung";
import pflege from "./fixtures/pflege.json";

const antrag = abbildenAntrag(pflege.antrag);
if (!antrag) throw new Error("Fixture ohne Antrag");
const PDF = "/api/uc1/antrag/pdf?art=pflegegeld&sitzung=x";

function stand(): string {
  return screen.getByTestId("uc1-entwurf-stand").textContent ?? "";
}

describe("EntwurfPruefung", () => {
  // Fängt: eine Anweisung ohne Formularcode oder mit der ID statt des Leistungsnamens.
  it("nennt Leistung und Formular in der Anweisung", () => {
    expect(entwurfAnweisung(antrag)).toBe("Antrag auf Pflegegeld (PAL080) als Entwurf vorausfüllen");
  });

  // Fängt: ein PDF, das vor der Prüfung speicherbar ist, „Team“ als Name, und einen Entwurf, der nach der
  // Freigabe nicht als geprüft mit Namen dasteht.
  it("gibt das PDF erst nach der Freigabe mit Vor- und Nachnamen frei", async () => {
    const nutzer = userEvent.setup();
    render(<EntwurfPruefung antrag={antrag} live pdf={PDF} ebene="h2" />);
    expect(stand()).toBe("Entwurf nicht geprüft");
    expect(screen.queryByRole("link", { name: "Antrag als PDF speichern" })).toBeNull();
    expect((screen.getByRole("button", { name: "Antrag als PDF speichern" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("Erst prüfen, dann speichern.")).toBeTruthy();

    const feld = screen.getByLabelText("Vor- und Nachname");
    const freigeben = screen.getByRole("button", { name: "Freigeben" }) as HTMLButtonElement;
    await nutzer.type(feld, "Team");
    expect(freigeben.disabled).toBe(true);
    await nutzer.clear(feld);
    await nutzer.type(feld, "Maria Huber");
    await nutzer.click(freigeben);

    expect(stand()).toMatch(/^Entwurf geprüft von Maria Huber, /);
    expect(screen.getByRole("link", { name: "Antrag als PDF speichern" }).getAttribute("href")).toBe(PDF);
    expect(document.querySelector("[data-uc1-pruefung]")?.getAttribute("data-uc1-pruefung")).toBe("geprueft");
  });

  // Fängt: eine Ablehnung, die den Entwurf als geprüft stehen lässt oder das PDF freigibt, und eine Sackgasse danach.
  it("setzt den Entwurf nach einer Ablehnung zurück und lässt neu prüfen", async () => {
    const nutzer = userEvent.setup();
    render(<EntwurfPruefung antrag={antrag} live pdf={PDF} ebene="h2" />);
    await nutzer.type(screen.getByLabelText("Vor- und Nachname"), "Maria Huber");
    await nutzer.click(screen.getByRole("button", { name: "Ablehnen" }));
    await nutzer.type(screen.getByLabelText(/Begründung der Ablehnung/), "Geburtsdatum stimmt nicht.");
    await nutzer.click(screen.getByRole("button", { name: "Ablehnung speichern" }));

    expect(stand()).toBe("Entwurf nicht geprüft");
    expect(screen.queryByRole("link", { name: "Antrag als PDF speichern" })).toBeNull();
    await nutzer.click(screen.getByRole("button", { name: "Noch einmal prüfen" }));
    expect((screen.getByLabelText("Vor- und Nachname") as HTMLInputElement).value).toBe("");
  });

  // Fängt: eine Karte, die im aufgezeichneten Beispiel fehlt oder dort ein PDF anbietet.
  it("funktioniert im Beispiel ohne PDF", async () => {
    const nutzer = userEvent.setup();
    render(<EntwurfPruefung antrag={antrag} live={false} pdf={PDF} ebene="h2" />);
    expect(screen.queryByRole("button", { name: "Antrag als PDF speichern" })).toBeNull();
    await nutzer.type(screen.getByLabelText("Vor- und Nachname"), "Maria Huber");
    await nutzer.click(screen.getByRole("button", { name: "Freigeben" }));
    expect(stand()).toMatch(/^Entwurf geprüft von Maria Huber/);
    expect(screen.queryByRole("link", { name: "Antrag als PDF speichern" })).toBeNull();
  });
});
