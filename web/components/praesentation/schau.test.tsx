import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Schau, type SchauFolie } from "./schau";

// Fängt ab: Pfeiltaste, die die Folie wechselt, aber die Adresse nicht mitführt (Neuladen springt zurück); Notizen,
// die ohne N sichtbar sind; Tasten, die beim Tippen in einem Feld die Folie wechseln; Wechsel über das Ende hinaus.

class Beobachter {
  observe() {}
  disconnect() {}
}

const folien: SchauFolie[] = ["Eins", "Zwei", "Drei"].map((titel, i) => ({
  id: `0${i + 1}`,
  titel,
  inhalt: <p>{`Inhalt ${titel}`}</p>,
  notizen: <p>{`Sprechtext ${titel}`}</p>,
}));

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", Beobachter);
  window.history.replaceState(null, "", "/praesentation");
});
afterEach(() => vi.unstubAllGlobals());

const aktuell = () => screen.getByRole("region", { name: /^Folie \d/ }).getAttribute("data-folie");

it("Pfeil rechts und links wechseln die Folie und schreiben ?folie=N in die Adresse, am Ende ist Schluss", async () => {
  const user = userEvent.setup();
  render(<Schau folien={folien} start={1} />);
  expect(aktuell()).toBe("1");
  await user.keyboard("{ArrowRight}");
  expect(aktuell()).toBe("2");
  expect(window.location.search).toBe("?folie=2");
  await user.keyboard("{ArrowRight}{ArrowRight}");
  expect(aktuell()).toBe("3");
  expect(window.location.search).toBe("?folie=3");
  await user.keyboard("{ArrowLeft}");
  expect(window.location.search).toBe("?folie=2");
});

it("startet auf der übergebenen Folie und die Knöpfe sind am Rand gesperrt", () => {
  render(<Schau folien={folien} start={3} />);
  expect(aktuell()).toBe("3");
  expect((screen.getByRole("button", { name: "Nächste Folie" }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole("button", { name: "Vorherige Folie" }) as HTMLButtonElement).disabled).toBe(false);
});

it("Notizen sind erst nach N sichtbar und nach erneutem N wieder weg", async () => {
  const user = userEvent.setup();
  render(<Schau folien={folien} start={1} />);
  expect(screen.queryByText("Sprechtext Eins")).toBeNull();
  await user.keyboard("n");
  expect(screen.getByText("Sprechtext Eins")).toBeTruthy();
  await user.keyboard("N");
  expect(screen.queryByText("Sprechtext Eins")).toBeNull();
});

it("Tasten in einem Eingabefeld wechseln die Folie nicht", async () => {
  const user = userEvent.setup();
  render(
    <>
      <input aria-label="Feld" />
      <Schau folien={folien} start={1} />
    </>,
  );
  await user.click(screen.getByLabelText("Feld"));
  await user.keyboard("n{ArrowRight}");
  expect(aktuell()).toBe("1");
  expect(screen.queryByText("Sprechtext Eins")).toBeNull();
});
