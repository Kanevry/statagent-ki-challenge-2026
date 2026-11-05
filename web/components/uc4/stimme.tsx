"use client";

import { VoiceKnopf } from "@kic/ui/voice";
import { ladeVapi } from "../../lib/plattform/voice-lader";

// Sprachzugang für /uc4 (#114): derselbe Weg wie das Frage-Feld, gesprochen über Vapi. Ohne Einrichtung
// (Schlüssel, Assistent, öffentliche Adresse) bleibt der Knopf aus und sagt, dass die Frage auch als Text geht.
// Eigene Client-Komponente, weil die Seite eine Server-Komponente ist und den Lader nicht übergeben kann.
export function Stimme() {
  return <VoiceKnopf ladeSdk={ladeVapi} />;
}
