import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Begriff, GLOSSAR } from "../../src/bausteine";

// Fängt ab: eine Erklärung, die nur per Maus (Hover) erreichbar ist.
it("öffnet die Erklärung per Tastatur und schließt sie mit Escape", async () => {
  const user = userEvent.setup();
  render(<Begriff wort="Revisionsbedarf" />);
  await user.tab();
  const begriff = screen.getByRole("button", { name: "Revisionsbedarf" });
  expect(document.activeElement).toBe(begriff);

  await user.keyboard("{Enter}");
  expect(begriff.getAttribute("aria-expanded")).toBe("true");
  expect(screen.getByRole("note").textContent).toContain(GLOSSAR.Revisionsbedarf);

  await user.keyboard("{Escape}");
  expect(screen.queryByRole("note")).toBeNull();
});
