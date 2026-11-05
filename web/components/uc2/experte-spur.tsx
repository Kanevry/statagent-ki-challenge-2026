import { Fliesstext, Status, Ueberschrift, formatiereZahl } from "@kic/ui/basis";
import { klartext } from "./namen";
import type { FallZustand } from "./zustand";

// Experte (Pen f1ct2, rechts Mitte): rechnet das Paket durch, nennt die Annahme, an der das Ergebnis hängt, und zeigt
// Prüfhinweise in Gelb. Hinweise kommen aus dem Strom (Zahl ohne Quelle, Widerspruch, Haltung ohne Beleg).

const prozent = (w: number) => `${formatiereZahl(w)} %`;
const vorzeichen = (w: number) => `${w > 0 ? "+" : ""}${formatiereZahl(w)} %`;

/** Der Satz "entscheidend: ..." des Experten, in Alltagssprache. Passt er nicht ins Muster, bleibt er sinngemäß stehen. */
export function annahmeSatz(roh: string | null | undefined): string | null {
  if (!roh) return null;
  const m =
    /^entscheidend:\s*\S+\s*\((.*?)(?:,\s*Typ\s*\w+)?\):\s*bei Min ([\d,.]+) Wartezeit (\S+) %, Kosten \S+ %, Ziel (\w+); bei Max ([\d,.]+) Wartezeit (\S+) %, Kosten \S+ %, Ziel (\w+)\s*$/.exec(
      roh,
    );
  if (!m) return klartext(roh.replace(/^entscheidend:\s*/, "Am meisten hängt das Ergebnis hieran: "));
  const [, was, niedrig, wNiedrig, zNiedrig, hoch, wHoch, zHoch] = m;
  const wort = (z: string | undefined) => (z === "erreicht" ? "das Ziel wird erreicht" : "das Ziel wird verfehlt");
  const kehr = (w: string | undefined) => (w ?? "").replace(/^[−-]/, "");
  return klartext(
    `Am meisten hängt das Ergebnis an einer Annahme: ${was}. Ist der Wert niedrig (${niedrig}), sinkt die Wartezeit um ${kehr(wNiedrig)} % und ${wort(zNiedrig)}. Ist er hoch (${hoch}), sinkt sie um ${kehr(wHoch)} % und ${wort(zHoch)}.`,
  );
}

export function ExperteSpur({ zustand }: { zustand: FallZustand }) {
  const e = zustand.experte;
  const annahme = annahmeSatz(e?.entscheidend);

  return (
    <section className="flex flex-col gap-3" aria-label="Experte" data-spur="experte">
      <Ueberschrift stufe={3} als="h2">
        {e ? "Experte: Zahlen geprüft" : "Experte"}
      </Ueberschrift>
      {!e ? (
        <Fliesstext ton="gedaempft" groesse={14}>
          Rechnet das Maßnahmenpaket durch. Das Ergebnis erscheint gleich.
        </Fliesstext>
      ) : (
        <>
          {e.beschreibung && (
            <Fliesstext groesse={14} ton="gedaempft">{`Geprüftes Paket: ${klartext(e.beschreibung)}`}</Fliesstext>
          )}
          <dl className="grid grid-cols-[auto_1fr] items-baseline gap-x-4 gap-y-2 font-sans text-14">
            {e.wartezeit_aenderung_prozent && (
              <>
                <dt className="text-slate">Wartezeit</dt>
                <dd data-teil="wartezeit">
                  <span className="font-mono font-semibold tabular-nums">{prozent(e.wartezeit_aenderung_prozent.modus)}</span>
                  <span className="text-slate">{` am wahrscheinlichsten, möglich ${prozent(e.wartezeit_aenderung_prozent.min)} bis ${prozent(e.wartezeit_aenderung_prozent.max)}`}</span>
                </dd>
              </>
            )}
            {e.kosten_aenderung_prozent && (
              <>
                <dt className="text-slate">Ausgaben</dt>
                <dd data-teil="kosten">
                  <span className="font-mono font-semibold tabular-nums">{vorzeichen(e.kosten_aenderung_prozent.modus)}</span>
                  <span className="text-slate">{` am wahrscheinlichsten, möglich ${vorzeichen(e.kosten_aenderung_prozent.min)} bis ${vorzeichen(e.kosten_aenderung_prozent.max)}`}</span>
                </dd>
              </>
            )}
            {e.mehrkosten_mio_eur && (
              <>
                <dt className="text-slate">Mehrkosten</dt>
                <dd data-teil="mehrkosten">
                  <span className="font-mono font-semibold tabular-nums">{`${formatiereZahl(e.mehrkosten_mio_eur.modus)} Mio. €`}</span>
                  <span className="text-slate">{` am wahrscheinlichsten, möglich ${formatiereZahl(e.mehrkosten_mio_eur.min)} bis ${formatiereZahl(e.mehrkosten_mio_eur.max)} Mio. €`}</span>
                </dd>
              </>
            )}
          </dl>
          <ul className="flex flex-col gap-2">
            {e.modus_erreicht !== undefined && (
              <li>
                <Status art={e.modus_erreicht ? "ok" : "warnung"}>
                  {e.modus_erreicht
                    ? "Im wahrscheinlichsten Fall wird das Ziel erreicht."
                    : "Im wahrscheinlichsten Fall wird das Ziel nicht erreicht."}
                </Status>
              </li>
            )}
            {e.zielpruefung === "offen" && e.wartezeit_aenderung_prozent && (
              <li className="rounded bg-warn-bg px-3 py-2" data-hinweis="gelb">
                <Status art="warnung">
                  {`Ob das Ziel sicher klappt, ist offen: Im ungünstigsten Fall sinkt die Wartezeit nur um ${formatiereZahl(Math.abs(e.wartezeit_aenderung_prozent.max))} %.`}
                </Status>
              </li>
            )}
            {zustand.hinweise.map((h) => (
              <li key={h.schluessel} className="rounded bg-warn-bg px-3 py-2" data-hinweis="gelb">
                <Status art="warnung">{h.text}</Status>
              </li>
            ))}
          </ul>
          {annahme && (
            <Fliesstext groesse={14} ton="gedaempft" data-teil="annahme">
              {annahme}
            </Fliesstext>
          )}
        </>
      )}
    </section>
  );
}
