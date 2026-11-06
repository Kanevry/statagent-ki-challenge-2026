import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { Leerzustand, Ueberschrift } from "@kic/ui/basis";
import { formatZahl } from "@kic/ui/bausteine";
import { StandPunkt } from "@/components/uc3/beleg-link";
import { nurLesend } from "@/components/uc3/cli";
import { DatenFehler } from "@/components/uc3/daten-fehler";
import {
  auftragKopf,
  auftragsZitat,
  auftragZahlen,
  auftragZuerst,
  freigabenKopf,
  kurzZeit,
  leseFreigaben,
  protokollZeilen,
  zitatTeile,
  type AuftragZahlen,
  type ErledigtZeile,
  type Vorschlag,
} from "@/components/uc3/freigabe";
import { uebersichtPfad } from "@/components/uc3/navigation";
import { AuftragBild } from "./_teile/auftrag-bild";

// Freigaben: ein Kopfsatz aus den Daten, offene Vorschläge als eigener Block oben, darunter die entschiedenen, die
// drei Aufträge der Aufgabe in ihrer Reihenfolge. Je Auftrag: was er will, Zahl vorher und nachher, Name mit Zeit und
// ein Link zur Detailseite. Weitere Freigaben aus dem Aufbau (Regeln, Veröffentlichungen) stehen eingeklappt darunter.
// Liest die UC3-Datenbank direkt; ohne Datenbank Leerzustand mit HTTP 200.
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Freigaben · StatAgent" };

const pfeilLink =
  "inline-flex min-h-11 items-center font-sans text-16 font-medium text-gruen underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-navy";

export default async function FreigabenSeite() {
  const lesung = await leseFreigaben();

  if (!lesung.ok) return <DatenFehler grund={lesung.grund} />;
  const { offen, erledigt, kategorien, wirkungen, bezeichnungen } = lesung.daten;
  const entschieden = auftragZuerst(
    erledigt.filter((z): z is ErledigtZeile & { vorschlag: Vorschlag } => z.vorschlag !== null),
    (z) => z.vorschlag.anweisung,
  );
  const protokoll = protokollZeilen(erledigt);
  const nurAuftraege = entschieden.every((z) => auftragKopf(z.vorschlag.anweisung).nummer !== null);
  const kopf = freigabenKopf(offen.length, entschieden, nurAuftraege);
  const zahlen = (v: Vorschlag) => auftragZahlen(v, kategorien, wirkungen[v.id], bezeichnungen);

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
        {nurLesend() && <p className="font-sans text-16 text-slate">Hier sehen Sie die Ergebnisse. Gerechnet und freigegeben wird im Programm.</p>}
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
                zahlen={zahlen(v)}
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
            {offen.length > 0 ? "Schon entschieden" : nurAuftraege ? "Was jeder Auftrag geändert hat" : "Entschieden"}
          </h2>
          <ul className="flex flex-col border-t border-line">
            {entschieden.map((z) => (
              <Zeile
                key={z.schluessel}
                vorschlag={z.vorschlag}
                zahlen={zahlen(z.vorschlag)}
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
          <Link href={uebersichtPfad("v2")} className={`${pfeilLink} w-fit`}>
            Alle Monate nach den Änderungsaufträgen ansehen
          </Link>
        </section>
      )}

      {offen.length === 0 && entschieden.length === 0 && (
        <Leerzustand satz="Sobald ein Agent eine Änderung vorschlägt, steht sie hier. Sie gilt erst, wenn ein Mensch sie freigibt." />
      )}

      {protokoll.length > 0 && (
        <details className="max-w-3xl">
          <summary className="inline-flex min-h-11 cursor-pointer items-center font-sans text-14 text-slate underline decoration-line underline-offset-4 hover:text-ink">
            {`Was sonst noch mit Namen freigegeben wurde (${formatZahl(protokoll.length)})`}
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

/** Zahl vorher und nachher; nachher ist das, was jetzt gilt, deshalb groß. */
function Zahlen({ zahlen }: { zahlen: AuftragZahlen }) {
  return (
    <div className="flex flex-col gap-2">
      {zahlen.zeilen.length > 0 && (
        <dl className="flex flex-col gap-2">
          {zahlen.zeilen.map((z) => (
            <div key={z.wort} className="flex flex-col gap-x-4 sm:flex-row sm:items-baseline">
              <dt className="font-sans text-14 text-slate sm:w-24 sm:shrink-0">{z.wort}</dt>
              <dd className="flex flex-wrap items-baseline gap-x-2 font-sans text-16 tabular-nums text-ink">
                <span>{z.vorher}</span>
                <span aria-hidden="true" className="text-slate">
                  →
                </span>
                <span className="sr-only">wird zu</span>
                <span className="text-20 font-semibold">{z.nachher}</span>
                {z.differenz && <span className="font-medium text-gruen">{z.differenz}</span>}
              </dd>
            </div>
          ))}
        </dl>
      )}
      {zahlen.satz && <p className="font-sans text-14 text-slate">{zahlen.satz}</p>}
    </div>
  );
}

function Zeile({
  vorschlag: v,
  zahlen,
  wer,
  link,
}: {
  vorschlag: Vorschlag;
  zahlen: AuftragZahlen;
  wer: ReactNode;
  link: { text: string; label: string };
}) {
  const kopf = auftragKopf(v.anweisung);
  // Kein Zitat, sondern der Inhalt in einem Satz: Codes wie „ArbeiterDV“ stehen im vollen Wortlaut auf der Detailseite.
  const inhalt = zitatTeile(auftragsZitat(v.anweisung)).anfang.replace(/\s*\(Arbeiter[^)]*\)/, "");
  const zweiZeilen = inhalt.trim().toLowerCase() !== kopf.titel.trim().toLowerCase();
  return (
    <li className="flex gap-x-5 border-b border-line py-6">
      <span className="hidden sm:block">
        <AuftragBild nummer={kopf.nummer} />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <div className="flex flex-col gap-1">
          {kopf.nummer && <span className="font-sans text-14 text-slate">{`Auftrag ${kopf.nummer}`}</span>}
          <h3 className="font-sans text-20 font-semibold text-pretty text-ink">{kopf.titel}</h3>
          {zweiZeilen && <p className="font-sans text-16 text-pretty text-ink">{inhalt}</p>}
        </div>
        <Zahlen zahlen={zahlen} />
        <div className="flex flex-wrap items-center gap-x-6 gap-y-1">
          {wer}
          <Link href={`/uc3/freigaben/${v.id}`} className={pfeilLink} aria-label={link.label}>
            {link.text}
          </Link>
        </div>
      </div>
    </li>
  );
}
