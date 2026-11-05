import { Akzent, Ueberschrift } from "@kic/ui/basis";
import { WarnChip } from "@kic/ui/bausteine";
import { BelegChip } from "./beleg-chip";
import { akteurName, haltungWort, haltungZahl, klartext, themaKurz } from "./namen";
import type { FallZustand, RundeZustand, Zug } from "./zustand";

// Gesprächsverlauf (Pen f1ct2, unten): die Beiträge in der Reihenfolge, in der sie gesprochen wurden, nach Runden
// getrennt. Je Beitrag der Teil, der zählt: was sich geändert hat, sonst das Thema mit der stärksten Haltung.

const PHASE: Record<string, string> = {
  position: "Positionen beziehen",
  debatte: "Debatte",
  verhandlung: "Verhandlung",
  kompromiss: "Kompromiss",
};

function wichtigeThemen(zug: Zug, davor: Zug | undefined): string[] {
  const geaendert = davor
    ? Object.values(zug.themen).filter((t) => davor.themen[t.thema] && davor.themen[t.thema]!.haltung !== t.haltung)
    : [];
  if (geaendert.length > 0) return geaendert.slice(0, 2).map((t) => t.thema);
  const stark = Object.values(zug.themen).sort((a, b) => Math.abs(b.haltung) - Math.abs(a.haltung))[0];
  return stark ? [stark.thema] : [];
}

function vorigerZug(z: FallZustand, runde: RundeZustand, akteur: string): Zug | undefined {
  return [...z.runden].reverse().find((r) => r.nr < runde.nr && r.zuege[akteur])?.zuege[akteur];
}

export function Verlauf({ zustand }: { zustand: FallZustand }) {
  const runden = zustand.runden.filter((r) => Object.keys(r.zuege).length > 0 || r.notiz);
  return (
    <section className="flex flex-col gap-4" aria-labelledby="uc2-verlauf" data-spur="verlauf">
      <Ueberschrift stufe={3} als="h2" id="uc2-verlauf">
        Gesprächsverlauf
      </Ueberschrift>
      {runden.length === 0 ? (
        <p className="font-sans text-14 text-slate">Noch hat niemand gesprochen.</p>
      ) : (
        <ol className="flex flex-col gap-6">
          {runden.map((r) => (
            <li key={r.nr} className="flex flex-col gap-3" data-runde={r.nr}>
              <h3 className="border-b border-line pb-1 font-sans text-14 font-semibold text-ink">
                {`Runde ${r.nr}`}
                {r.phase && PHASE[r.phase] && <span className="font-normal text-slate">{`, ${PHASE[r.phase]}`}</span>}
              </h3>
              <ul className="flex flex-col gap-3">
                {Object.entries(r.zuege).map(([akteur, zug]) => {
                  const davor = vorigerZug(zustand, r, akteur);
                  const themen = wichtigeThemen(zug, davor);
                  const bewegt = davor ? themen.some((t) => davor.themen[t] && davor.themen[t]!.haltung !== zug.themen[t]?.haltung) : false;
                  const ohneQuelle = zustand.hinweise.some((h) => h.akteur === akteur && h.runde === r.nr && h.schluessel.startsWith("zob:"));
                  return (
                    <li key={akteur} className="flex flex-col gap-1" data-beitrag={akteur}>
                      <p className="flex flex-wrap items-center gap-2 font-sans text-12 text-slate">
                        <span className="font-semibold text-ink">{akteurName(akteur)}</span>
                        {bewegt && <span className="rounded bg-navy px-2 py-0.5 font-semibold text-white">bewegt</span>}
                        {ohneQuelle && <WarnChip>Zahl ohne Quelle</WarnChip>}
                      </p>
                      {themen.map((t) => {
                        const thema = zug.themen[t];
                        // Belege dieses Beitrags: die Quellen, die in genau dieser Runde zum Thema genannt wurden.
                        const belege = (thema?.beleg_ids ?? []).flatMap((id) => (zustand.belegIndex[id] ? [zustand.belegIndex[id]] : []));
                        return (
                          <div key={t} className="flex flex-col items-start gap-1" data-thema={t}>
                            <p className="max-w-3xl font-sans text-14 text-ink text-pretty">
                              <span className="font-semibold">{`${themaKurz(t)}: `}</span>
                              {thema && (
                                <span className="font-mono tabular-nums" data-teil="haltung">
                                  {`${haltungZahl(thema.haltung)} ${haltungWort(thema.haltung)}. `}
                                </span>
                              )}
                              {klartext(thema?.begruendung ?? "")}
                            </p>
                            {belege.map((b) => (
                              <BelegChip key={b.beleg_id} beleg={b} themen={[t]} />
                            ))}
                          </div>
                        );
                      })}
                    </li>
                  );
                })}
                {r.notiz && (
                  <li data-beitrag="moderator">
                    <Akzent art="ki" className="flex flex-col gap-1">
                      <p className="font-sans text-12 font-semibold text-ink">Moderator</p>
                      <p className="max-w-3xl font-sans text-14 text-ink text-pretty">{r.notiz.text}</p>
                    </Akzent>
                  </li>
                )}
              </ul>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
