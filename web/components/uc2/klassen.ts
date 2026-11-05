// Nachbau von `klassen` und `fokus` aus @kic/ui (nicht exportiert): Klassen zusammensetzen und sichtbarer Fokus.
export function klassen(...teile: Array<string | false | null | undefined>): string {
  return teile.filter(Boolean).join(" ");
}

export const fokus = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen";
