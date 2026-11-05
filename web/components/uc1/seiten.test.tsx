import { render, screen } from "@testing-library/react";
import { LotseAnbieter } from "./lotse-kontext";
import { StartSeite } from "./seiten";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/uc1" }));

afterEach(() => vi.unstubAllGlobals());

// Fängt ab (Live-Befund 05.11. 19:30): Online antwortet der Lotse nicht live; das Formular endete nach „Senden“ in
// einer roten Meldung. Dann gibt es kein Formular, sondern das aufgezeichnete Gespräch als Hauptaktion.
it("online ohne Sprachmodell: kein Formular, eine Hauptaktion „Aufgezeichnetes Gespräch ansehen“", () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({})));
  render(
    <LotseAnbieter>
      <StartSeite beispiel={false} nurAufzeichnung />
    </LotseAnbieter>,
  );
  expect(screen.queryByRole("textbox")).toBeNull();
  expect(screen.queryByRole("button", { name: "Senden" })).toBeNull();
  expect(screen.getByRole("button", { name: "Aufgezeichnetes Gespräch ansehen" })).toBeTruthy();
});

it("lokal mit Sprachmodell bleibt das Formular", () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({})));
  render(
    <LotseAnbieter>
      <StartSeite beispiel={false} />
    </LotseAnbieter>,
  );
  expect(screen.getByRole("button", { name: "Senden" })).toBeTruthy();
});
