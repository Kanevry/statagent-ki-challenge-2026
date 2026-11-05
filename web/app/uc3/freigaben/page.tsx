import type { Metadata } from "next";
import Link from "next/link";
import { Akzent, Fliesstext, Leerzustand, Status, Ueberschrift } from "@kic/ui/basis";
import { formatZahl, formatZeit, HerkunftChip } from "@kic/ui/bausteine";
import { leerSatz } from "@/lib/uc3/db";
import { Fachbegriff } from "@/lib/uc3/fachbegriff";
import {
  aenderungKurz,
  klartext,
  leseFreigaben,
  rollenName,
  waage,
  waageBeleg,
  waageSatz,
  type ErledigtZeile,
  type Freigaben,
} from "@/lib/uc3/freigabe";
import { istMonat, monatName } from "@/lib/uc3/monat";

// Freigaben (Frames qVTQj, PPe1S, uJbeL): Reiter „Wartet auf Sie“ (offene Vorschläge der Agenten) und „Erledigt“
// (Protokoll in Worten). Liest die UC3-Datenbank direkt; ohne Datenbank Leerzustand mit HTTP 200.
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Freigaben · StatAgent" };

type Reiter = "wartet" | "erledigt";

const reiterKlasse =
  "inline-flex min-h-11 items-center border-b-2 px-1 font-sans text-16 font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-navy";

function Reiterleiste({ aktiv, offen, erledigt }: { aktiv: Reiter; offen: number; erledigt: number }) {
  const eintraege: { reiter: Reiter; href: string; text: string }[] = [
    { reiter: "wartet", href: "/uc3/freigaben", text: `Wartet auf Sie (${offen})` },
    { reiter: "erledigt", href: "/uc3/freigaben?reiter=erledigt", text: `Erledigt (${erledigt})` },
  ];
  return (
    <nav aria-label="Freigaben" className="flex gap-6 border-b border-line">
      {eintraege.map((e) => (
        <Link
          key={e.reiter}
          href={e.href}
          aria-current={aktiv === e.reiter ? "page" : undefined}
          className={`${reiterKlasse} ${aktiv === e.reiter ? "border-gruen text-ink" : "border-transparent text-slate"}`}
        >
          {e.text}
        </Link>
      ))}
    </nav>
  );
}

export default async function FreigabenSeite({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const reiter: Reiter = (await searchParams).reiter === "erledigt" ? "erledigt" : "wartet";
  const lesung = await leseFreigaben();

  if (!lesung.ok) {
    return (
      <>
        <Ueberschrift stufe={2} als="h1">
          Freigaben
        </Ueberschrift>
        <Leerzustand satz={leerSatz(lesung.grund)} />
      </>
    );
  }
  const daten = lesung.daten;
  const anzahl = daten.offen.length;
  const titel =
    anzahl === 0
      ? "Nichts wartet auf Ihre Freigabe."
      : anzahl === 1
        ? "1 Änderung wartet auf Ihre Freigabe."
        : `${formatZahl(anzahl)} Änderungen warten auf Ihre Freigabe.`;

  return (
    <>
      <header className="flex max-w-3xl flex-col gap-4">
        <Ueberschrift stufe={2} als="h1">
          {titel}
        </Ueberschrift>
        <Fliesstext>
          Die Agenten schlagen Änderungen nur vor. Gerechnet wird damit erst, wenn ein Mensch sie mit Vor- und
          Nachnamen freigibt.
        </Fliesstext>
        <div className="font-sans text-14 font-semibold text-ink">
          <Fachbegriff wort="Freigabe" />
        </div>
      </header>

      <div className="flex max-w-3xl flex-col gap-6">
        <Reiterleiste aktiv={reiter} offen={anzahl} erledigt={daten.erledigt.length} />
        {reiter === "wartet" ? <Wartet daten={daten} /> : <Erledigt zeilen={daten.erledigt} />}
      </div>
    </>
  );
}

function Wartet({ daten }: { daten: Freigaben }) {
  if (daten.offen.length === 0) {
    return <Leerzustand satz="Sobald ein Agent eine Änderung vorschlägt, erscheint sie hier." />;
  }
  return (
    <ul className="flex flex-col" aria-label="Offene Vorschläge">
      {daten.offen.map((v) => {
        const w = waage(v.probe, daten.bezeichnungen);
        const satz = w ? waageSatz(w) : (klartext(v).worte[0] ?? aenderungKurz(v));
        return (
          <li key={v.id} className="flex flex-col gap-3 border-t border-line py-6 first:border-t-0 first:pt-0">
            <blockquote className="border-l-2 border-line pl-4">
              <Fliesstext>{`„${v.anweisung}“`}</Fliesstext>
            </blockquote>
            <Fliesstext groesse={14} ton="gedaempft">
              {v.gesagtVon ? `Gesagt von ${v.gesagtVon} · ` : ""}
              <time dateTime={v.gesagtAm ?? v.erstelltAm}>{formatZeit(v.gesagtAm ?? v.erstelltAm)}</time>
            </Fliesstext>
            <Akzent art="ki" className="flex flex-col gap-1">
              <Fliesstext groesse={14} ton="gedaempft">
                {`Vorschlag von ${rollenName(v.rolle)}${v.modell ? ` mit ${v.modell}` : ""}`}
              </Fliesstext>
              <Fliesstext>{satz}</Fliesstext>
            </Akzent>
            {w && <HerkunftChip {...waageBeleg(v.id, w)} />}
            <div className="flex flex-wrap items-center gap-4">
              <Status art="warnung">Wartet auf Freigabe</Status>
              <Link
                href={`/uc3/freigaben/${v.id}`}
                className="inline-flex min-h-11 items-center font-sans text-16 font-semibold text-gruen underline underline-offset-4"
              >
                Ansehen und entscheiden
              </Link>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function Erledigt({ zeilen }: { zeilen: ErledigtZeile[] }) {
  if (zeilen.length === 0) {
    return <Leerzustand satz="Noch ist nichts entschieden. Jede Freigabe und jede Ablehnung steht dann hier mit Name und Uhrzeit." />;
  }
  return (
    <ol className="flex flex-col" aria-label="Protokoll der Entscheidungen">
      {zeilen.map((z) => {
        const teile = [
          formatZeit(z.zeit),
          `${z.art === "freigegeben" ? "Freigegeben" : "Abgelehnt"} von ${z.name}`,
          ...(z.anweisung ? [`Anweisung ‚${z.anweisung}‘`] : []),
          ...(z.geaendert ? [`Geändert: ${z.geaendert}`] : []),
        ];
        const w = z.waage;
        const monat = w && istMonat(w.lieferung) ? monatName(w.lieferung) : w?.lieferung;
        return (
          <li key={z.schluessel} className="flex flex-col gap-2 border-t border-line py-4 first:border-t-0 first:pt-0">
            <Status art={z.art === "freigegeben" ? "ok" : "info"}>
              {z.art === "freigegeben" ? "Freigegeben" : "Abgelehnt"}
            </Status>
            <Fliesstext className="break-words">
              {teile.join(" · ")}
              {w && (
                <>
                  {` · ${monat ? `${monat}: ` : ""}${w.haupt.bezeichnung} `}
                  <span className="font-mono tabular-nums">{`${formatZahl(w.haupt.vorher)} → ${formatZahl(w.haupt.nachher)}`}</span>
                </>
              )}
            </Fliesstext>
            {z.art === "abgelehnt" && z.begruendung && (
              <Fliesstext groesse={14}>{`Begründung: ${z.begruendung}`}</Fliesstext>
            )}
            {w && z.vorschlag && <HerkunftChip {...waageBeleg(z.vorschlag.id, w)} />}
            <div className="flex flex-wrap gap-4">
              {z.vorschlag && (
                <Link
                  href={`/uc3/freigaben/${z.vorschlag.id}`}
                  className="font-sans text-14 font-semibold text-gruen underline underline-offset-4"
                >
                  Einzelheiten ansehen
                </Link>
              )}
              {z.commit && (
                <details>
                  <summary className="cursor-pointer font-sans text-14 text-slate">Kennung im Repo</summary>
                  <code className="break-all font-mono text-12 text-ink">{z.commit}</code>
                </details>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
