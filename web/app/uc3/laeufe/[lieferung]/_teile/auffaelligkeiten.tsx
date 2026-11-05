import { Status } from "@kic/ui/basis";
import { HerkunftChip, WarnChip } from "@kic/ui/bausteine";
import { laufBeleg } from "@/lib/uc3/beleg";
import {
  beispielText,
  einstufungStatus,
  massnahmeSatz,
  sqlTreffer,
  trefferTitel,
  umfangImTitel,
  type Treffer,
} from "@/lib/uc3/lauf-detail";
import type { Lauf } from "@/lib/uc3/typen";

/** Eine Auffälligkeit: Titel als Satz, Einstufung als Symbol und Wort, Maßnahme, Beispiele, Beleg. */
function Eintrag({ lauf, treffer }: { lauf: Lauf; treffer: Treffer }) {
  const status = einstufungStatus(treffer.einstufung, treffer.offeneRueckfragen);
  const massnahme = massnahmeSatz(treffer);
  const beispiele = beispielText(treffer.beispiele);
  return (
    <li className="flex flex-col gap-2 border-b border-line py-4" data-regel={treffer.name}>
      <div className="flex flex-wrap items-center gap-2">
        {treffer.anhalten && <WarnChip>hält den Monat an</WarnChip>}
        <Status art={status.art}>{status.wort}</Status>
      </div>
      <h3 className="hyphens-auto break-words font-sans text-16 font-semibold text-ink">{trefferTitel(treffer, lauf.lieferung)}</h3>
      <p className="break-all font-mono text-12 text-slate">{treffer.name}</p>
      {treffer.umfang && !umfangImTitel(treffer) && (
        <p className="break-words font-sans text-14 text-ink">{`Umfang: ${treffer.umfang}.`}</p>
      )}
      {massnahme && (
        <p className="break-words font-sans text-14 text-ink" title={treffer.massnahme ?? undefined}>
          {`Was wir tun: ${massnahme}`}
        </p>
      )}
      {beispiele && <p className="break-words font-sans text-12 text-slate">{`Beispiele (Verhältnis-Nummer): ${beispiele}`}</p>}
      <HerkunftChip {...laufBeleg(lauf, { quelle: "meta.pruefung_treffer", sql: sqlTreffer(lauf, treffer) })} />
    </li>
  );
}

export function Auffaelligkeiten({ lauf, treffer }: { lauf: Lauf; treffer: readonly Treffer[] }) {
  return (
    <ul className="flex flex-col" aria-label="Auffälligkeiten">
      {treffer.map((t) => (
        <Eintrag key={`${t.regelId}-${t.ebene}`} lauf={lauf} treffer={t} />
      ))}
    </ul>
  );
}
