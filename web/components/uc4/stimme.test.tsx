import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { VoiceSdk } from "@kic/ui/voice";
import { MAX_ABSCHNITTE, Stimme } from "./stimme";

// Fängt ab (Review !66, Vertrag V): Gesprochene Frage und Antwort bleiben auf /uc4 unsichtbar, und die Liste wächst
// ohne Grenze.

type Handler = (...args: never[]) => void;
class FalschesSdk implements VoiceSdk {
  handler = new Map<string, Handler[]>();
  start = vi.fn(async (_assistantId: string): Promise<unknown> => ({ id: "anruf-1" }));
  stop = vi.fn(async () => undefined);
  removeAllListeners = vi.fn();
  on(ereignis: string, f: Handler) {
    this.handler.set(ereignis, [...(this.handler.get(ereignis) ?? []), f]);
    return this;
  }
  emit(ereignis: string, ...args: unknown[]) {
    act(() => {
      for (const f of this.handler.get(ereignis) ?? []) (f as (...a: unknown[]) => void)(...args);
    });
  }
}

const abschnitt = (role: string, transcript: string) => ({ type: "transcript", role, transcriptType: "final", transcript });

it("zeigt gesprochene Frage und Antwort als Text, höchstens die letzten Abschnitte", async () => {
  const sdk = new FalschesSdk();
  render(<Stimme ladeSdk={async () => sdk} konfiguration={{ publicKey: "pk", assistantId: "asst", aktiv: true }} />);
  await userEvent.setup().click(screen.getByRole("button", { name: /Mit Stimme fragen/ }));
  sdk.emit("call-start");
  sdk.emit("message", abschnitt("user", "Wie viele im März?"));
  sdk.emit("message", abschnitt("assistant", "Im März 2025 waren es 412300."));
  const liste = screen.getByRole("list", { name: "Gesprochen" });
  expect(liste.textContent).toBe("Sie: Wie viele im März?Antwort: Im März 2025 waren es 412300.");

  for (let i = 0; i < MAX_ABSCHNITTE; i++) sdk.emit("message", abschnitt("user", `Frage ${i}`));
  expect(screen.getAllByRole("listitem")).toHaveLength(MAX_ABSCHNITTE);
  expect(liste.textContent).not.toContain("Wie viele im März?");
});
