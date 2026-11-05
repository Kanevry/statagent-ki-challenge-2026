import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.resetModules();
  vi.doUnmock("@kic/ui/ucs");
});

async function rendereMitRegistry(zusatz: Record<string, unknown>) {
  vi.doMock("@kic/ui/ucs", async (original) => ({ ...(await original<Record<string, unknown>>()), ...zusatz }));
  const { default: UseCases } = await import("./UseCases");
  return render(<UseCases />);
}

describe("UseCases, verdeckter UC4", () => {
  it("zeigt den Link auf /uc4, sobald die Registry uc4 in `bereiche` führt", async () => {
    const { ucs } = await import("@kic/ui/ucs");
    const einstieg = { id: "uc4", name: "Gemeinsamer Einstieg", kurz: "", route: "/uc4", bewertet: false };
    const { container } = await rendereMitRegistry({ bereiche: [...ucs, einstieg], einstieg });
    expect(container.querySelector('a[href="/uc4"]')).not.toBeNull();
    expect(container.textContent).not.toContain("Entsteht gerade");
  });

  it("bleibt bei „Entsteht gerade“, solange die Registry keinen uc4-Eintrag hat", async () => {
    const { container } = await rendereMitRegistry({ bereiche: undefined });
    expect(container.querySelector('a[href="/uc4"]')).toBeNull();
    expect(container.textContent).toContain("Entsteht gerade");
  });
});
