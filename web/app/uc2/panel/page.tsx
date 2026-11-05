import type { Metadata } from "next";
import { findeUc } from "@kic/ui/ucs";
import { PanelSeite } from "@/components/uc2/panel-seite";
import { modusFuer } from "../../api/uc2/_lib/proxy";
import { modellWahl } from "../../api/uc2/_lib/vorbereitung";

// U2-1 Das Panel verhandelt (Pen f1ct2) und U2-1a Modellfehler (Pen NjP7Q). Der Fall steht in der Adresse
// (?fall=...), damit ein Lauf teilbar bleibt und sich neu laden lässt. Ohne Fall: Leerzustand.
export const metadata: Metadata = { title: `Panel · ${findeUc("uc2").name} · OneShotAndy` };
export const dynamic = "force-dynamic";

export default async function Uc2Panel({ searchParams }: { searchParams: Promise<{ fall?: string | string[]; akteure?: string | string[] }> }) {
  const { fall, akteure } = await searchParams;
  const id = typeof fall === "string" && /^[A-Za-z0-9_-]{1,64}$/.test(fall) ? fall : null;
  return <PanelSeite fallId={id} modelle={modellWahl()} akteureIgnoriert={akteure === "ignoriert"} modus={modusFuer(id)} />;
}
