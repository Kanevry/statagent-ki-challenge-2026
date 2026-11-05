import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { Leerzustand, Ueberschrift } from "@kic/ui/basis";
import { formatZahl } from "@kic/ui/bausteine";
import { StandPunkt } from "@/components/uc3/beleg-link";
import { DatenFehler } from "@/components/uc3/daten-fehler";
import {
  aenderungSatz,
  auftragKopf,
  freigabenKopf,
  kurzZeit,
  leseFreigaben,
  protokollZeilen,
  type ErledigtZeile,
  type Vorschlag,
} from "@/components/uc3/freigabe";

// Freigaben (UI-Regie v1): ein Kopfsatz aus den Daten, offene Vorschläge als eigener Block oben, darunter die
// entschiedenen. Keine Reiter, keine leere Startansicht. Je Zeile Auftrag, Änderung in Worten, Name mit Zeit und
// ein Link zur Detailseite. Weitere Freigaben aus dem Aufbau (Regelstände je Monat) stehen eingeklappt darunter.
// Liest die UC3-Datenbank direkt; ohne Datenbank Leerzustand mit HTTP 200.
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Freigaben · StatAgent" };

const pfeilLink =
  "inline-flex min-h-11 items-center font-sans text-16 font-medium text-gruen underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-navy";

export default async function FreigabenSeite() {
  const lesung = await leseFreigaben();

  if (!lesung.ok) return <DatenFehler grund={lesung.grund} />;
  const { offen, erledigt } = lesung.daten;
  const entschieden = erledigt.filter((z): z is ErledigtZeile & { vorschlag: Vorschlag } => z.vorschlag !== null);
  const protokoll = protokollZeilen(erledigt);
  const kopf = freigabenKopf(offen.length, entschieden);

  return (
    <>
      <header className="flex max-w-3xl flex-col gap-3">
        <Ueberschrift stufe={2} als="h1" className="hyphens-auto break-words">
          {kopf}
        </Ueberschrift>
        <p className="font-sans text-16 text-slate">
          Die Agenten schlagen Änderungen nur vor. Gerechnet wird damit erst, wenn ein Mensch sie mit Vor- und Nachnamen
          freigibt.
        </p>
      </header>

      {offen.length > 0 && (
        <section aria-labelledby="offen-titel" className="flex max-w-3xl flex-col gap-2">
          <h2 id="offen-titel" className="font-sans text-16 font-semibold text-ink">
            Wartet auf Ihre Freigabe
          </h2>
          <ul className="flex flex-col border-t border-line">
            {offen.map((v) => (
              <Zeile
                key={v.id}
                vorschlag={v}
                wer={<StandPunkt stand="offen" />}
                link={{ text: "Ansehen und entscheiden", label: `${auftragKopf(v.anweisung).titel} ansehen und entscheiden` }}
              />
            ))}
          </ul>
        </section>
      )}

      {entschieden.length > 0 && (
        <section aria-labelledby="erledigt-titel" className="flex max-w-3xl flex-col gap-2">
          <h2 id="erledigt-titel" className="font-sans text-16 font-semibold text-ink">
            {offen.length > 0 ? "Schon entschieden" : "Entschieden"}
          </h2>
          <ul className="flex flex-col border-t border-line">
            {entschieden.map((z) => (
              <Zeile
                key={z.schluessel}
                vorschlag={z.vorschlag}
                wer={
                  <span className="font-sans text-14 text-slate">
                    {z.art === "abgelehnt" ? `Abgelehnt von ${z.name}, ` : `${z.name}, `}
                    <time dateTime={z.zeit} className="tabular-nums">
                      {kurzZeit(z.zeit)}
                    </time>
                  </span>
                }
                link={{ text: "Ansehen", label: `${auftragKopf(z.vorschlag.anweisung).titel} ansehen` }}
              />
            ))}
          </ul>
        </section>
      )}

      {offen.length === 0 && entschieden.length === 0 && (
        <Leerzustand satz="Sobald ein Agent eine Änderung vorschlägt, steht sie hier. Sie gilt erst, wenn ein Mensch sie freigibt." />
      )}

      {protokoll.length > 0 && (
        <details className="max-w-3xl">
          <summary className="inline-flex min-h-11 cursor-pointer items-center font-sans text-14 text-slate underline decoration-line underline-offset-4 hover:text-ink">
            {`Weitere Freigaben (${formatZahl(protokoll.length)})`}
          </summary>
          <ul className="mt-2 flex flex-col">
            {protokoll.map((p) => (
              <li
                key={p.schluessel}
                className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 border-b border-line py-2 font-sans text-14"
              >
                <span className="min-w-0 text-ink">{p.satz}</span>
                <span className="text-slate">
                  {p.art === "abgelehnt" ? `Abgelehnt von ${p.name}, ` : `${p.name}, `}
                  <time dateTime={p.zeit} className="tabular-nums">
                    {kurzZeit(p.zeit)}
                  </time>
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </>
  );
}

function Zeile({
  vorschlag: v,
  wer,
  link,
}: {
  vorschlag: Vorschlag;
  wer: ReactNode;
  link: { text: string; label: string };
}) {
  const kopf = auftragKopf(v.anweisung);
  return (
    <li className="flex flex-col gap-x-6 gap-y-1 border-b border-line py-4 sm:flex-row sm:items-center">
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="font-sans text-16 font-semibold text-ink">{kopf.titel}</span>
        <span className="font-sans text-14 text-slate">
          {kopf.nummer ? `Auftrag ${kopf.nummer}. ` : ""}
          {`${aenderungSatz(v)}.`}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-x-6 gap-y-1">
        {wer}
        <Link href={`/uc3/freigaben/${v.id}`} className={pfeilLink} aria-label={link.label}>
          {link.text}
        </Link>
      </div>
    </li>
  );
}
