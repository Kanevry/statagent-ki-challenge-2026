import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Fall } from "./fall";
import type { Vorbereitung } from "../../app/api/uc2/_lib/vorbereitung";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

const basis: Vorbereitung = {
  modus: "vorfuehrung",
  herkunft: "aufzeichnung",
  fall: { id: "wartezeiten", frage: "Wie werden Wartezeiten kürzer?", stichtag: "2026-09-30", paket: "Kassenstellen +3 %", maxAkteure: 6 },
  akteure: [
    { akteur: "aerztekammer", belegzahl: 5, vorgeschlagen: true },
    { akteur: "sv", belegzahl: 6, vorgeschlagen: true },
    { akteur: "pharma", belegzahl: 0, vorgeschlagen: false },
  ],
  modelle: [],
};

it("Vorführung: genau eine Aktion, keine Auswahl ohne Wirkung, kein Start mit Modell", () => {
  render(<Fall vorbereitung={basis} />);
  expect(screen.getByRole("link", { name: "Verhandlung ansehen" }).getAttribute("href")).toBe("/uc2/panel?fall=mock-wartezeiten");
  expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
  expect(screen.queryByRole("button")).toBeNull();
  // Am Tisch sitzen nur die eingeladenen Gruppen.
  expect(screen.getByText("Ärztekammer")).toBeTruthy();
  expect(screen.queryByText("Pharma")).toBeNull();
});

it("live (Python-API erreichbar): zusätzlich ein leiser Weg, neu mit Modell verhandeln zu lassen", () => {
  render(<Fall vorbereitung={{ ...basis, modus: "live" }} />);
  expect(screen.getByRole("button", { name: "Neu verhandeln lassen, mit Modell" })).toBeTruthy();
});

it("eigene Frage: leiser Link, nur wenn die Route sie annimmt", () => {
  const { rerender } = render(<Fall vorbereitung={basis} />);
  expect(screen.queryByRole("link", { name: "Eigene Frage ausprobieren" })).toBeNull();
  rerender(<Fall vorbereitung={basis} eigeneFrage />);
  expect(screen.getByRole("link", { name: "Eigene Frage ausprobieren" }).getAttribute("href")).toBe("/uc2/frage");
});


it("Hinweis zur Dauer steht nur im Modus live", () => {
  const satz = "Eine neue Verhandlung mit Modell dauert rund fünf Minuten. Die Runden erscheinen, sobald sie fertig sind.";
  const { rerender } = render(<Fall vorbereitung={basis} />);
  expect(screen.queryByText(satz)).toBeNull();
  rerender(<Fall vorbereitung={{ ...basis, modus: "live" }} />);
  expect(screen.getByText(satz)).toBeTruthy();
});

it("ein gescheiterter Start zeigt den Satz der Route statt eines allgemeinen Satzes", async () => {
  // Fängt den Fall 504 und 503: Der feste Satz der Route sagt, was los ist und was zu tun ist.
  const satz = "Der Start dauert gerade zu lange. Bitte in einer Minute noch einmal versuchen.";
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({ fehler: satz }, { status: 504 })));
  render(<Fall vorbereitung={{ ...basis, modus: "live" }} />);
  await userEvent.click(screen.getByRole("button", { name: "Neu verhandeln lassen, mit Modell" }));
  expect((await screen.findByRole("status")).textContent).toBe(satz);
  vi.unstubAllGlobals();
});
