import type { Metadata } from "next";
import { Fliesstext, Leerzustand, Ueberschrift } from "@kic/ui/basis";
import { annahmenKopf, geltungSatz, HERLEITUNG, leseAnnahmen, SQL_ANNAHMEN } from "@/components/uc3/annahmen";
import { BelegLink } from "@/components/uc3/beleg-link";
import { DatenFehler } from "@/components/uc3/daten-fehler";

// Annahmen (Raster Bereich 6): F1 bis F10 aus meta.annahme, wie sie in den Qualitätsberichten stehen; darunter
// aufklappbar die Herleitung A1 bis A13. Nur lesend; ohne die Tabelle ein Leerzustand mit HTTP 200.
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Annahmen · StatAgent" };

export default async function AnnahmenSeite() {
  const lesung = await leseAnnahmen();
  if (!lesung.ok) return <DatenFehler grund={lesung.grund} />;
  const zeilen = lesung.daten;

  return (
    <>
      <header className="flex max-w-4xl flex-col gap-3">
        <Ueberschrift stufe={2} als="h1">
          {zeilen.length > 0 ? annahmenKopf(zeilen.length, zeilen.filter((a) => a.wartet).length) : "Annahmen"}
        </Ueberschrift>
        {zeilen.length > 0 && (
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <Fliesstext ton="gedaempft">Jede ist als Regel umgesetzt und steht im Qualitätsbericht des Monats.</Fliesstext>
            <BelegLink quelle="meta.annahme, meta.rueckfrage" sql={SQL_ANNAHMEN} />
          </div>
        )}
      </header>

      {zeilen.length === 0 ? (
        <Leerzustand satz="Die Annahmen sind in dieser Datenbank noch nicht geladen." />
      ) : (
        <ul className="flex max-w-4xl flex-col border-t border-line">
          {zeilen.map((a) => (
            <li key={a.nr} className="flex gap-4 border-b border-line py-3">
              <span className="w-8 shrink-0 font-sans text-14 text-slate">{a.nr}</span>
              <div className="flex min-w-0 flex-col gap-1">
                <p className="max-w-3xl font-sans text-16 text-pretty text-ink">{a.satz}</p>
                <p className="font-sans text-14 text-slate">
                  {geltungSatz(a.lieferungen)}
                  {a.rueckfrage ? ` (Rückfrage ${a.rueckfrage}${a.wartet ? "" : ", beantwortet"})` : ""}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}

      <details className="max-w-4xl border-b border-line">
        <summary className="flex min-h-11 cursor-pointer items-center font-sans text-16 text-ink underline-offset-4 hover:underline">
          Herleitung der Zählung: Annahmen A1 bis A13
        </summary>
        <div className="flex flex-col gap-3 pb-3">
          <ul className="grid grid-cols-1 gap-x-8 gap-y-1 sm:grid-cols-2">
            {HERLEITUNG.map((a) => (
              <li key={a.nr} className="flex gap-3 font-sans text-14 text-ink">
                <span className="w-8 shrink-0 text-slate">{a.nr}</span>
                <span>{a.name}</span>
              </li>
            ))}
          </ul>
          <p className="font-sans text-14 text-slate">Ausführlich mit Zahlen und Belegen im Repo: docs/plan/uc3/annahmen.md</p>
        </div>
      </details>
    </>
  );
}
