import { mockEreignisse, MOCK_ABBRUCH } from "../../app/api/uc2/_lib/mock";

// Hilfen für Tests: dieselbe Aufzeichnung mit einem echten Anbieter im Ereignis start, damit der Live-Text eines
// Abbruchs geprüft werden kann (die Aufzeichnung selbst läuft über das Testmodell).

export function mitAnbieter(ereignisse: unknown[], provider: string, modell: string): unknown[] {
  return ereignisse.map((e) => {
    const x = JSON.parse(JSON.stringify(e)) as { art: string; daten: { provider?: string; modelle: Record<string, { provider: string; modell: string }> } };
    if (x.art === "start") {
      x.daten.provider = provider;
      for (const rolle of Object.values(x.daten.modelle)) Object.assign(rolle, { provider, modell });
    }
    return x;
  });
}


/** Ein echter Lauf über `provider`, der nach Runde 2 mit einem Zeitfehler abbricht (Vertrag #44: Ereignis abbruch). */
export function abbruchMitAnbieter(provider: string, modell: string): unknown[] {
  return mitAnbieter(
    [
      ...mockEreignisse(MOCK_ABBRUCH)!.slice(0, -1),
      { seq: 37, runde: 3, art: "abbruch", akteur: null, daten: { grund: "TimeoutError", meldung: "Zeitüberschreitung nach 30 s" } },
    ],
    provider,
    modell,
  );
}
