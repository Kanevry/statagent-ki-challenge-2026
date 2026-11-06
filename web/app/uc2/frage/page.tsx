import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { findeUc } from "@kic/ui/ucs";
import { EigeneFrage } from "@/components/uc2/eigene-frage";
import { stationOffen } from "@/lib/plattform/uc4";

// /uc2/frage: eine eigene gesundheitspolitische Frage eintippen und eine echte Antwort sehen. Die Seite ruft kein
// Modell: Sie fragt POST /api/uc4/frage mit station uc2, also mit Ratenlimit, Längengrenze und Tagesbudget dieser Route.
// Ist die Station gesperrt, gibt es die Seite nicht; kein Formular, das nur in einer Sperre endet.
export const metadata: Metadata = { title: `Eigene Frage · ${findeUc("uc2").name} · OneShotAndy` };
export const dynamic = "force-dynamic";

export default function Uc2EigeneFrage() {
  if (!stationOffen("uc2")) redirect("/uc2");
  return <EigeneFrage />;
}
