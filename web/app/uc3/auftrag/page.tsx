import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { rechenbareMonate, vorfuehrungOffen } from "@/components/uc3/auftrag";
import { lies } from "@/components/uc3/db";
import { AuftragFormular } from "./_teile/auftrag-formular";

// Auftrag an die Agenten (nur Vorführ-Instanz, KIC_VORFUEHRUNG=1; sonst 404): ein Satz in Alltagssprache, die Agenten
// schreiben einen Vorschlag, wirksam wird er erst mit einem Namen auf /uc3/freigaben/<id>. Darunter ein Monat zum
// Neurechnen. Ohne Datenbank bleibt die Monatsliste leer; der Auftrag selbst läuft über die CLI.
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Auftrag · StatAgent" };

// Monate und aktueller Regelsatz (wie `produktions_regelsatz` in uc3/statagent/agenten/koordinator.py: der jüngste
// v<Zahl> mit freigegebener Regel oder angewendetem Vorschlag). Nach einer Freigabe rechnet ein Lauf also den neuen Stand.
async function leseStand(): Promise<{ monate: string[]; probeMonate: string[]; rechenbar: string[]; regelsatz: string }> {
  const lesung = await lies(async (sql) => {
    const monate = await sql`SELECT DISTINCT lieferung FROM meta.lauf ORDER BY lieferung DESC`;
    const [aktuell] = await sql`
      SELECT regelsatz FROM (
        SELECT regelsatz FROM meta.regel WHERE aktiv AND freigegeben_von IS NOT NULL
        UNION SELECT regelsatz_ziel FROM meta.vorschlag WHERE status = 'freigegeben' AND angewendet_am IS NOT NULL
      ) s WHERE regelsatz ~ '^v[0-9]+$' ORDER BY substr(regelsatz, 2)::int DESC LIMIT 1`;
    const regelsatz = String(aktuell?.regelsatz ?? "v1");
    const gerechnet = await sql`SELECT DISTINCT lieferung FROM meta.lauf WHERE regelsatz = ${regelsatz} AND status IN ('fertig', 'unveraendert')`;
    const alle = monate.map((z) => String(z.lieferung));
    // Monate mit Fortschreibung zeigen in der Probe bisher eine falsche Gesamtzahl: Im neuen Regelsatz fehlt der Vormonat,
    // also auch die Fortschreibung (gemessen in !150). Die Probe bietet sie erst an, wenn das dort behoben ist.
    const fortgeschrieben = await sql`SELECT DISTINCT lieferung FROM meta.lauf WHERE fortgeschrieben > 0`;
    const ohne = new Set(fortgeschrieben.map((z) => String(z.lieferung)));
    return { monate: alle, probeMonate: alle.filter((m) => !ohne.has(m)), rechenbar: rechenbareMonate(alle, new Set(gerechnet.map((z) => String(z.lieferung)))), regelsatz };
  });
  return lesung.ok ? lesung.daten : { monate: [], probeMonate: [], rechenbar: [], regelsatz: "v1" };
}

export default async function AuftragSeite() {
  if (!vorfuehrungOffen()) notFound();
  return <AuftragFormular {...await leseStand()} />;
}
