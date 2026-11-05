import type { Metadata } from "next";
import { findeUc } from "@kic/ui/ucs";
import { PanelSeite } from "@/components/uc2/panel-seite";
import { modusFuer } from "../../api/uc2/_lib/proxy";

// /uc2/panel: Bühne der Verhandlung, ein Sprecher zur Zeit (UI-Regie 05.11.). Der Fall steht in der Adresse.
export const metadata: Metadata = { title: `Panel · ${findeUc("uc2").name} · OneShotAndy` };
export const dynamic = "force-dynamic";

export default async function Uc2Panel({ searchParams }: { searchParams: Promise<{ fall?: string | string[] }> }) {
  const { fall } = await searchParams;
  const id = typeof fall === "string" && /^[A-Za-z0-9_-]{1,64}$/.test(fall) ? fall : null;
  return <PanelSeite fallId={id} modus={modusFuer(id)} />;
}
