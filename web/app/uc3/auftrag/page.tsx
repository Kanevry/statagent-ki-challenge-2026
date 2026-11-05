import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { vorfuehrungOffen } from "@/components/uc3/auftrag";
import { lies } from "@/components/uc3/db";
import { AuftragFormular } from "./_teile/auftrag-formular";

// Auftrag an die Agenten (nur Vorführ-Instanz, KIC_VORFUEHRUNG=1; sonst 404): ein Satz in Alltagssprache, die Agenten
// schreiben einen Vorschlag, wirksam wird er erst mit einem Namen auf /uc3/freigaben/<id>. Darunter ein Monat zum
// Neurechnen. Ohne Datenbank bleibt die Monatsliste leer; der Auftrag selbst läuft über die CLI.
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Auftrag · StatAgent" };

// Monate und aktueller Regelsatz (wie `produktions_regelsatz` in uc3/statagent/agenten/koordinator.py: der jüngste
// v<Zahl> mit freigegebener Regel oder angewendetem Vorschlag). Nach einer Freigabe rechnet ein Lauf also den neuen Stand.
async function leseStand(): Promise<{ monate: string[]; regelsatz: string }> {
  const lesung = await lies(async (sql) => {
    const monate = await sql`SELECT DISTINCT lieferung FROM meta.lauf ORDER BY lieferung DESC`;
    const [aktuell] = await sql`
      SELECT regelsatz FROM (
        SELECT regelsatz FROM meta.regel WHERE aktiv AND freigegeben_von IS NOT NULL
        UNION SELECT regelsatz_ziel FROM meta.vorschlag WHERE status = 'freigegeben' AND angewendet_am IS NOT NULL
      ) s WHERE regelsatz ~ '^v[0-9]+$' ORDER BY substr(regelsatz, 2)::int DESC LIMIT 1`;
    return { monate: monate.map((z) => String(z.lieferung)), regelsatz: String(aktuell?.regelsatz ?? "v1") };
  });
  return lesung.ok ? lesung.daten : { monate: [], regelsatz: "v1" };
}

export default async function AuftragSeite() {
  if (!vorfuehrungOffen()) notFound();
  return <AuftragFormular {...await leseStand()} />;
}
