import type { Metadata } from "next";
import { findeUc } from "@kic/ui/ucs";
import { Fall } from "@/components/uc2/fall";
import { stationOffen } from "@/lib/plattform/uc4";
import { ladeVorbereitung } from "../api/uc2/_lib/vorbereitung";

// /uc2 Fall: Frage, Tisch, eine Hauptaktion (UI-Regie 05.11.). Die Seite rechnet nichts und ruft kein Modell: Start und Strom laufen über /api/uc2.
export const metadata: Metadata = { title: `${findeUc("uc2").name} · OneShotAndy` };
export const dynamic = "force-dynamic";

export default async function Uc2Start() {
  const vorbereitung = await ladeVorbereitung();
  return <Fall vorbereitung={vorbereitung} eigeneFrage={stationOffen("uc2")} />;
}
