"use client";

import { useCallback, useState } from "react";
import { Fliesstext } from "@kic/ui/basis";
import { VoiceKnopf, type VoiceKonfiguration, type VoiceSdkLader, type VoiceTranskript } from "@kic/ui/voice";
import { ladeVapi } from "../../lib/plattform/voice-lader";

/** So viele gesprochene Abschnitte bleiben sichtbar; ältere fallen weg. */
export const MAX_ABSCHNITTE = 6;

// Sprachzugang für /uc4 (#114): derselbe Weg wie das Frage-Feld, gesprochen über Vapi. Ohne Einrichtung bleibt der
// Knopf aus und sagt, dass die Frage auch als Text geht. Gesprochene Frage und Antwort stehen darunter als Text
// (Vertrag V, Review !66), damit man auch ohne Ton sieht, was verstanden und geantwortet wurde.
export function Stimme({
  ladeSdk = ladeVapi,
  konfiguration,
}: { ladeSdk?: VoiceSdkLader; konfiguration?: VoiceKonfiguration } = {}) {
  const [abschnitte, setAbschnitte] = useState<VoiceTranskript[]>([]);
  const neu = useCallback(
    (abschnitt: VoiceTranskript) => setAbschnitte((alt) => [...alt, abschnitt].slice(-MAX_ABSCHNITTE)),
    [],
  );
  return (
    <div className="flex max-w-3xl flex-col gap-3" data-uc4-stimme="">
      <VoiceKnopf ladeSdk={ladeSdk} konfiguration={konfiguration} onTranskript={neu} />
      {abschnitte.length > 0 && (
        <ol aria-label="Gesprochen" aria-live="polite" className="flex flex-col gap-1" data-uc4-gesprochen="">
          {abschnitte.map((abschnitt, i) => (
            <li key={i}>
              <Fliesstext groesse={14}>
                <span className="font-semibold">{abschnitt.rolle === "nutzer" ? "Sie: " : "Antwort: "}</span>
                {abschnitt.text}
              </Fliesstext>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
