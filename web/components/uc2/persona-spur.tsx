import { akteurName, haltungWort, haltungZahl, themaKurz } from "./namen";
import { BelegChip } from "./beleg-chip";
import { belegeAllerZuege, hatSichBewegt, letzteAenderung, verlaufVon, zuegeVon, type FallZustand, belegeDesZugs } from "./zustand";
import { klassen } from "./klassen";

// Eine Spur je Persona (Pen f1ct2, Karte links): Name, Marke (spricht gerade, bewegt, fest), je Thema die Haltung als
// Zahl und Wort, darunter die Belege, auf die sich der jüngste Beitrag stützt. Belege stehen zu, bis jemand sie aufklappt.

export type Marke = "spricht" | "bewegt" | "fest" | "erste" | "wartet";

const MARKE_TEXT: Record<Marke, string> = {
  spricht: "spricht gerade",
  bewegt: "bewegt",
  fest: "fest",
  erste: "erste Position",
  wartet: "wartet",
};

const MARKE_KLASSE: Record<Marke, string> = {
  spricht: "bg-gruen text-white",
  bewegt: "bg-navy text-white",
  fest: "bg-line text-ink",
  erste: "border border-line text-slate",
  wartet: "border border-line text-slate",
};

export function markeVon(z: FallZustand, akteur: string): Marke {
  if (z.status === "laeuft" && z.sprecher === akteur) return "spricht";
  const zuege = zuegeVon(z, akteur).length;
  if (zuege === 0) return "wartet";
  if (zuege === 1) return "erste";
  return hatSichBewegt(z, akteur) ? "bewegt" : "fest";
}

/** Fünf Kästchen von −2 bis +2. Das gefüllte ist die Haltung jetzt, das umrandete die Haltung vor der letzten Änderung. Zahl und Wort stehen daneben. */
function Skala({ jetzt, frueher }: { jetzt: number; frueher?: number }) {
  return (
    <span aria-hidden="true" className="inline-flex gap-0.5" data-teil="skala">
      {[-2, -1, 0, 1, 2].map((stufe) => {
        const aktiv = stufe === jetzt;
        const farbe = jetzt > 0 ? "bg-gruen" : jetzt < 0 ? "bg-err-fg" : "bg-slate";
        return (
          <span
            key={stufe}
            className={klassen(
              "h-3 w-4 rounded-sm",
              aktiv ? farbe : stufe === frueher ? "border border-slate bg-white" : "bg-line",
            )}
          />
        );
      })}
    </span>
  );
}

export function PersonaSpur({ zustand, akteur }: { zustand: FallZustand; akteur: string }) {
  const marke = markeVon(zustand, akteur);
  const zug = zuegeVon(zustand, akteur).at(-1);
  const themen = zustand.themen.length > 0 ? zustand.themen.map((t) => t.id) : zug ? Object.keys(zug.themen) : [];
  const alleBelege = belegeAllerZuege(zustand, akteur);
  const letzteRunde = zug?.runde ?? 0;
  // Belege des jüngsten Beitrags stehen offen in der Liste, die der früheren Runden zugeklappt darunter, nicht verloren.
  // „Stützt“ zeigt beim aktuellen Beitrag nur die Themen des jüngsten Zugs; was ein Beleg früher stützte, steht in der
  // Historie darunter (Review 69).
  const belege = belegeDesZugs(zustand, akteur);
  const frueher = alleBelege.filter((b) => !b.runden.includes(letzteRunde));
  const eintrag = zustand.auswahl.find((a) => a.akteur === akteur);
  const spricht = marke === "spricht";

  return (
    <article
      aria-label={akteurName(akteur)}
      data-akteur={akteur}
      data-marke={marke}
      className={klassen(
        "flex flex-col gap-3 rounded border bg-white p-4",
        spricht ? "border-gruen outline outline-2 outline-gruen" : "border-line",
      )}
    >
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-display text-20 font-bold text-ink">{akteurName(akteur)}</h3>
        <span className={klassen("rounded px-2 py-1 font-sans text-12 font-semibold", MARKE_KLASSE[marke])} data-teil="marke">
          {MARKE_TEXT[marke]}
        </span>
      </header>

      {!zug ? (
        <p className="font-sans text-14 text-slate">
          {spricht
            ? "Liest die Belege und überlegt."
            : eintrag
              ? `Noch keine Position. ${eintrag.belegzahl === 1 ? "1 Beleg" : `${eintrag.belegzahl} Belege`} im Archiv.`
              : "Noch keine Position."}
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {themen.map((id) => {
            const t = zug.themen[id];
            if (!t) return null;
            const verlauf = verlaufVon(zustand, akteur, id);
            const aenderung = letzteAenderung(verlauf);
            const geaendert = aenderung !== null;
            return (
              <li
                key={id}
                data-thema={id}
                data-geaendert={geaendert ? "ja" : "nein"}
                className="grid grid-cols-[1fr_auto] items-baseline gap-x-3 gap-y-1 border-t border-line pt-2 first:border-t-0 first:pt-0"
              >
                <span className="font-sans text-14 font-medium text-ink">
                  {themaKurz(id, zustand.themen.find((x) => x.id === id)?.titel)}
                </span>
                <Skala jetzt={t.haltung} frueher={aenderung?.vorher} />
                <span className="col-span-2 flex flex-wrap items-baseline gap-x-2 font-sans text-14 text-ink">
                  <span className="font-mono font-semibold tabular-nums" data-teil="haltung-zahl">
                    {haltungZahl(t.haltung)}
                  </span>
                  <span data-teil="haltung-wort">{haltungWort(t.haltung)}</span>
                  {aenderung && (
                    <span className="text-slate" data-teil="aenderung">
                      {`vorher ${haltungZahl(aenderung.vorher)} ${haltungWort(aenderung.vorher)}, geändert in Runde ${aenderung.runde}`}
                    </span>
                  )}
                </span>
              </li>
            );
          })}
        </ul>
      )}

      {(belege.length > 0 || frueher.length > 0) && (
        <div className="flex flex-col gap-2 border-t border-line pt-3" data-teil="belege">
          <p className="font-sans text-12 text-slate">Stützt sich auf</p>
          <div className="flex flex-col items-start gap-2">
            {belege.map(({ beleg, themen: stuetzt }) => (
              <BelegChip key={beleg.beleg_id} beleg={beleg} themen={stuetzt} />
            ))}
          </div>
          {frueher.length > 0 && (
            <details className="font-sans text-12" data-teil="belege-frueher">
              <summary className="cursor-pointer text-slate">{`Belege früherer Runden (${frueher.length})`}</summary>
              <div className="mt-2 flex flex-col items-start gap-2">
                {frueher.map(({ beleg, themen: stuetzt, runden }) => (
                  <div key={beleg.beleg_id} className="flex flex-col items-start gap-1">
                    <span className="text-slate">{`Runde ${runden.join(", ")}`}</span>
                    <BelegChip beleg={beleg} themen={stuetzt} />
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </article>
  );
}
