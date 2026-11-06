import type { ReactNode } from "react";
import { formatDifferenz, formatZahl } from "@kic/ui/bausteine";
import { bestandBeleg } from "@/components/uc3/beleg";
import { BelegLink } from "@/components/uc3/beleg-link";
import { sqlAuffaelligkeiten } from "@/components/uc3/bericht";
import { sqlEinstufungen, sqlVorlaeufig, vorlaeufigSatz, type EinstufungsZahl } from "@/components/uc3/dashboard";
import { trefferTitel, sortiereTreffer, type Treffer } from "@/components/uc3/lauf-detail";
import { monatName } from "@/components/uc3/monat";
import { alltag } from "@/components/uc3/sprache";
import type { Monatslauf } from "@/components/uc3/typen";
import { imZeitraum, zeitraumArtAus } from "@/components/uc3/zeitraum";

// Vier ruhige Kennzahlen unter der Kurve: je eine Frage, eine Zahl, ein Satz, ein Beleg. Keine Karten, die Linie
// oben bindet Zahl und Satz zusammen. Die Einstufungen tragen Zahl und Wort, die Farbe ist nur Zusatz.

const FARBE: Record<EinstufungsZahl["code"], string> = {
  "nicht-erklaerbar": "bg-gelb",
  "erklaert-datenproblem": "bg-navy",
  "erklaert-plausibel": "bg-slate",
};

function Kennzahl({ frage, zahl, children, beleg }: { frage: string; zahl: string; children: ReactNode; beleg: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 border-t border-ink pt-3">
      <h3 className="font-sans text-14 font-medium text-slate">{frage}</h3>
      <p className="font-display text-32 font-bold tabular-nums text-ink">{zahl}</p>
      <div className="flex flex-col gap-2 font-sans text-14 text-pretty text-ink">{children}</div>
      <div className="pt-1">{beleg}</div>
    </div>
  );
}

function Einstufungen({ reihe }: { reihe: readonly EinstufungsZahl[] }) {
  const summe = reihe.reduce((s, e) => s + e.anzahl, 0);
  return (
    <>
      {summe > 0 && (
        <div aria-hidden="true" className="flex h-2 gap-0.5">
          {reihe
            .filter((e) => e.anzahl > 0)
            .map((e) => (
              <span key={e.code} className={FARBE[e.code]} style={{ width: `${(e.anzahl / summe) * 100}%` }} />
            ))}
        </div>
      )}
      <ul className="flex flex-col">
        {reihe.map((e) => (
          <li key={e.code} className="flex items-center gap-2">
            <span aria-hidden="true" className={`size-2 shrink-0 ${FARBE[e.code]} ${e.code === "nicht-erklaerbar" ? "outline outline-1 outline-ink" : ""}`} />
            <span className="tabular-nums">{formatZahl(e.anzahl)}</span>
            <span>{e.wort}</span>
          </li>
        ))}
      </ul>
    </>
  );
}

export function Kennzahlen({
  monate,
  vormonat,
  treffer,
  einstufungen,
}: {
  monate: readonly Monatslauf[];
  vormonat: number | null;
  treffer: readonly Treffer[];
  einstufungen: readonly EinstufungsZahl[];
}) {
  const letzter = monate.at(-1)!;
  const name = monatName(letzter.lieferung);
  // „im Monat im Juli 2026“ wäre doppelt, deshalb trägt nur der Stichtag ein Zeitwort.
  const wann = zeitraumArtAus(letzter.zeitraumArt) === "Monat" ? "" : ` ${imZeitraum("Stichtag")}`;
  const ersterTreffer = sortiereTreffer(treffer).find((t) => t.anhalten || t.einstufung === "nicht-erklaerbar");
  const vorlaeufig = monate.filter((m) => m.ergebnisStand !== "endgueltig").length;
  const summe = einstufungen.reduce((s, e) => s + e.anzahl, 0);
  const anzahlWort = letzter.nichtErklaerbar === 1 ? "Auffälligkeit" : "Auffälligkeiten";

  return (
    <section aria-labelledby="kennzahlen-titel" className="grid gap-x-8 gap-y-6 sm:grid-cols-2 lg:grid-cols-4">
      <h2 id="kennzahlen-titel" className="sr-only">
        Kennzahlen
      </h2>
      <Kennzahl frage="Letzter Monat" zahl={formatZahl(letzter.gezaehlt)} beleg={<BelegLink {...bestandBeleg(letzter)} />}>
        <p>
          {`Beschäftigungsverhältnisse${wann} im ${name}`}
          {vormonat !== null && <span className="tabular-nums">{`, ${formatDifferenz(letzter.gezaehlt - vormonat)} zum Vormonat`}</span>}
          .
        </p>
      </Kennzahl>
      <Kennzahl
        frage="Gerade auffällig"
        zahl={formatZahl(letzter.nichtErklaerbar)}
        beleg={<BelegLink quelle="meta.pruefung_treffer" lieferung={letzter.lieferung} sql={sqlAuffaelligkeiten(letzter)} />}
      >
        <p>{`noch nicht erklärte ${anzahlWort} im ${name}, ${letzter.nichtErklaerbar === 1 ? "sie geht" : "sie gehen"} als Rückfrage an die Fachabteilung.`}</p>
        {ersterTreffer && <p className="text-slate">{alltag(trefferTitel(ersterTreffer, letzter.lieferung))}</p>}
      </Kennzahl>
      <Kennzahl
        frage="Noch nicht veröffentlicht"
        zahl={`${formatZahl(vorlaeufig)} von ${formatZahl(monate.length)}`}
        beleg={<BelegLink quelle="meta.lauf" sql={sqlVorlaeufig(letzter.regelsatz)} />}
      >
        <p>{vorlaeufigSatz(monate)}</p>
      </Kennzahl>
      <Kennzahl
        frage="Auffälligkeiten"
        zahl={formatZahl(summe)}
        beleg={<BelegLink quelle="meta.pruefung_treffer" sql={sqlEinstufungen(letzter.regelsatz)} />}
      >
        <p>{`in ${formatZahl(monate.length)} Monaten`}</p>
        <Einstufungen reihe={einstufungen} />
      </Kennzahl>
    </section>
  );
}
