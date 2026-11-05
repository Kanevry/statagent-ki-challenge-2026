import Link from "next/link";
import { laufBeleg } from "@/components/uc3/beleg";
import { BelegLink } from "@/components/uc3/beleg-link";
import { oenaceWechsel, wechselSaetze, wechselTitel } from "@/components/uc3/oenace-wechsel";
import type { Lauf } from "@/components/uc3/typen";

/** Erklärt die Sprünge je Abschnitt im Monat des ÖNACE-Wechsels (#179). Jeder andere Monat zeigt nichts. */
export function OenaceWechselAbsatz({ lauf }: { lauf: Lauf }) {
  const w = oenaceWechsel(lauf.lieferung, lauf.regelsatz);
  if (!w) return null;
  const [folge, umfang] = wechselSaetze(w, lauf.lieferung);
  return (
    <section aria-labelledby="oenace-wechsel-titel" className="flex max-w-4xl flex-col gap-2 border-t border-line pt-6">
      <h2 id="oenace-wechsel-titel" className="font-sans text-20 font-semibold text-ink">
        {wechselTitel(w)}
      </h2>
      <p className="max-w-3xl font-sans text-16 text-ink">{folge}</p>
      <p className="max-w-3xl font-sans text-14 text-slate">{umfang}</p>
      <p className="font-sans text-14 text-slate">
        {"Die amtlichen Übergänge stehen unter "}
        <Link href="/uc3/klassifikationen" className="text-ink underline decoration-line underline-offset-4 hover:decoration-ink">
          Klassifikationen
        </Link>
        .
      </p>
      <BelegLink {...laufBeleg(lauf, { quelle: "bereinigt.abschnitt", sql: w.beleg_sql })} />
    </section>
  );
}
