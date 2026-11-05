import type { Metadata } from "next";
import { findeUc } from "@kic/ui/ucs";
import { FallStellen } from "@/components/uc2/fall-stellen";
import { ladeVorbereitung } from "../api/uc2/_lib/vorbereitung";

// U2-0 Fall stellen (Pen bhI7X). Die Seite rechnet nichts und ruft kein Modell: Start und Strom laufen über /api/uc2.
export const metadata: Metadata = { title: `${findeUc("uc2").name} · OneShotAndy` };
export const dynamic = "force-dynamic";

export default async function Uc2Start() {
  const vorbereitung = await ladeVorbereitung();
  return <FallStellen vorbereitung={vorbereitung} />;
}
