import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FreigabeKarte, type FreigabeKarteProps } from "../../src/bausteine";

const eintrag = {
  anweisung: "Prüfregel P07 ab 2025-01 als Fehler statt Warnung führen",
  name: "Anna Beispiel",
  zeit: "2026-11-05T09:12:30+00:00",
};

function karte(props: Partial<FreigabeKarteProps> = {}) {
  const onFreigeben = vi.fn<FreigabeKarteProps["onFreigeben"]>();
  const onAblehnen = vi.fn<FreigabeKarteProps["onAblehnen"]>();
  render(
    <FreigabeKarte
      eintrag={eintrag}
      vorher={387390}
      nachher={387130}
      onFreigeben={onFreigeben}
      onAblehnen={onAblehnen}
      {...props}
    />,
  );
  const knopf = screen.getByRole("button", { name: "Ja, so rechnen wir ab jetzt" }) as HTMLButtonElement;
  const feld = screen.getByRole("textbox", { name: "Vor- und Nachname" });
  return { onFreigeben, onAblehnen, knopf, feld };
}

// Fängt ab: falsches Vorzeichen (Bindestrich statt U+2212), Tausendertrennung per Leerzeichen
// (ICU-Standard für de-AT) und eine Prozentzahl mit falscher Basis.
it("zeigt vorher, nachher, Δ −260 und −0,07 % im Format de-AT", () => {
  karte();
  const waage = screen.getByLabelText("Freigabe-Waage");
  expect(waage.textContent).toContain("387.390");
  expect(waage.textContent).toContain("387.130");
  expect(screen.getByText("−260")).toBeTruthy();
  expect(screen.getByText("−0,07 %")).toBeTruthy();
});

// Fängt ab: Zonen, die beim Umbau ihre Reihenfolge tauschen (Freigabe vor dem Zitat).
it("hält die drei Zonen in fester Reihenfolge", () => {
  karte();
  const titel = screen.getAllByRole("heading").map((h) => h.textContent);
  expect(titel).toEqual(["Das wurde gesagt", "Das ändert sich", "Freigabe mit Vor- und Nachname"]);
});

// Fängt ab: Freigabe durch eine Rolle oder einen Vornamen allein, entgegen Vertrag P.
it("aktiviert den Knopf erst bei gültigem Vor- und Nachnamen", async () => {
  const user = userEvent.setup();
  const { knopf, feld } = karte();
  expect(knopf.disabled).toBe(true);
  for (const name of ["Team", "Bernhard"]) {
    await user.clear(feld);
    await user.type(feld, name);
    expect(knopf.disabled, name).toBe(true);
  }
  await user.clear(feld);
  await user.type(feld, "Bernhard Götzendorfer");
  expect(knopf.disabled).toBe(false);
});

// Fängt ab: Enter im Namensfeld gibt frei, direkt oder über ein umgebendes Formular.
it("löst mit Enter im Namensfeld nichts aus", async () => {
  const user = userEvent.setup();
  const senden = vi.fn((e: { preventDefault: () => void }) => e.preventDefault());
  const onFreigeben = vi.fn();
  render(
    <form onSubmit={senden}>
      <FreigabeKarte eintrag={eintrag} vorher={387390} nachher={387130} onFreigeben={onFreigeben} onAblehnen={vi.fn()} />
    </form>,
  );
  await user.type(screen.getByRole("textbox", { name: "Vor- und Nachname" }), "Bernhard Götzendorfer{Enter}");
  expect(onFreigeben).not.toHaveBeenCalled();
  expect(senden).not.toHaveBeenCalled();
});

// Fängt ab: Leerzeichen am Rand landen im Freigabe-Namen (und damit im Commit-Trailer).
it("ruft onFreigeben beim Klick mit dem getrimmten Namen", async () => {
  const user = userEvent.setup();
  const { onFreigeben, knopf, feld } = karte();
  await user.type(feld, "  Bernhard Götzendorfer  ");
  await user.click(knopf);
  expect(onFreigeben).toHaveBeenCalledTimes(1);
  expect(onFreigeben).toHaveBeenCalledWith("Bernhard Götzendorfer");
  expect(await screen.findByRole("heading", { name: "Freigegeben" })).toBeTruthy();
});

// Fängt ab: eine im Server abgelehnte Freigabe erscheint trotzdem als freigegeben.
it("zeigt einen Fehler und bleibt offen, wenn der Server ablehnt", async () => {
  const user = userEvent.setup();
  const { knopf, feld } = karte({ onFreigeben: () => Promise.reject(new Error("Name abgelehnt.")) });
  await user.type(feld, "Bernhard Götzendorfer");
  await user.click(knopf);
  expect((await screen.findByRole("alert")).textContent).toContain("Name abgelehnt.");
  expect(screen.queryByRole("heading", { name: "Freigegeben" })).toBeNull();
  expect(knopf.disabled).toBe(false);
});
