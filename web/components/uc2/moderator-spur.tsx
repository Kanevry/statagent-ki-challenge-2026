import { Akzent, Fliesstext, Ueberschrift } from "@kic/ui/basis";
import { akteurName, klartext } from "./namen";
import type { FallZustand } from "./zustand";

// Moderator-Spur (Pen f1ct2, rechts oben): getrennt von den Personas, in Violett als KI-Linie. Zeigt die jüngste
// Zusammenfassung groß, frühere Runden zugeklappt, und auf Nachfrage, wer am Tisch sitzt und warum.

/** Technische Begründung der Auswahl in einen Satz für Bürger. */
export function auswahlSatz(eingeladen: boolean, begruendung: string): string {
  const m = /(\d+) Belege? zum Fall, (\d+) Themenbez/.exec(begruendung);
  if (!m) return klartext(begruendung);
  const artikel = `${m[1]} Artikel im Archiv, ${m[2]} Themen berührt`;
  return eingeladen ? `Dabei: ${artikel}.` : `Nicht dabei: ${artikel}. Die Plätze gingen an Gruppen mit mehr Belegen.`;
}

export function ModeratorSpur({ zustand }: { zustand: FallZustand }) {
  const notizen = zustand.runden.flatMap((r) => (r.notiz ? [r.notiz] : [])).reverse();
  const [neueste, ...fruehere] = notizen;
  const denkt = zustand.status === "laeuft" && zustand.sprecher === "moderator";

  return (
    <Akzent art="ki" className="flex flex-col gap-3" data-spur="moderator" aria-label="Moderator">
      <div className="flex flex-col">
        <Ueberschrift stufe={3} als="h2">
          Moderator
        </Ueberschrift>
        <p className="font-sans text-12 text-slate">{denkt ? "denkt gerade mit" : "denkt mit"}</p>
      </div>

      {neueste ? (
        <div className="flex flex-col gap-1" data-teil="notiz-neueste">
          <p className="font-sans text-12 text-slate">{`Nach Runde ${neueste.runde}`}</p>
          <Fliesstext>{neueste.text}</Fliesstext>
        </div>
      ) : (
        <Fliesstext ton="gedaempft" groesse={14}>
          {zustand.teilnehmer.length > 0
            ? "Hört zu. Die erste Zusammenfassung kommt nach Runde 1."
            : "Wählt gerade, wer am Tisch sitzt."}
        </Fliesstext>
      )}

      {fruehere.length > 0 && (
        <details className="font-sans text-14">
          <summary className="cursor-pointer text-slate">{`Frühere Runden (${fruehere.length})`}</summary>
          <ul className="mt-2 flex flex-col gap-2">
            {fruehere.map((n) => (
              <li key={n.runde} className="text-ink">
                <span className="text-slate">{`Nach Runde ${n.runde}: `}</span>
                {n.text}
              </li>
            ))}
          </ul>
        </details>
      )}

      {zustand.auswahl.length > 0 && (
        <details className="font-sans text-14">
          <summary className="cursor-pointer text-slate">Wer am Tisch sitzt und warum</summary>
          <ul className="mt-2 flex flex-col gap-2">
            {zustand.auswahl.map((a) => (
              <li key={a.akteur} data-eingeladen={a.eingeladen ? "ja" : "nein"}>
                <span className="font-semibold text-ink">{akteurName(a.akteur)}</span>
                <span className="text-slate">{`: ${auswahlSatz(a.eingeladen, a.begruendung)}`}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </Akzent>
  );
}
