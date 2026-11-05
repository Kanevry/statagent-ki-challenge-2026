import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Akzent, Fliesstext, knopfKlassen, Leerzustand, Ueberschrift } from "@kic/ui/basis";
import { formatDifferenz, formatZahl, HerkunftChip, type FreigabeEntscheidung } from "@kic/ui/bausteine";
import { leerSatz } from "@/lib/uc3/db";
import { Fachbegriff } from "@/lib/uc3/fachbegriff";
import {
  aenderungKurz,
  klartext,
  leseVorschlag,
  rollenName,
  vorschlagId,
  waage,
  waageBeleg,
  waageSatz,
  type Vorschlag,
} from "@/lib/uc3/freigabe";
import { istMonat, monatName } from "@/lib/uc3/monat";
import { laufPfad } from "@/lib/uc3/navigation";
import { Entscheiden } from "./entscheiden";

// Ein Vorschlag in drei Zonen (Frames qVTQj, oBcQu): das wurde gesagt, das ändert sich, Freigabe mit Namen.
// Liest die UC3-Datenbank direkt; ohne Datenbank Leerzustand mit HTTP 200, unbekannte ID → 404.
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Freigaben · StatAgent" };

function entscheidungAus(v: Vorschlag): FreigabeEntscheidung | undefined {
  if (v.status === "freigegeben" && v.freigegebenVon && v.freigegebenAm)
    return { art: "freigegeben", name: v.freigegebenVon, zeit: v.freigegebenAm };
  if (v.status === "abgelehnt" && v.abgelehntVon && v.abgelehntAm)
    return { art: "abgelehnt", name: v.abgelehntVon, zeit: v.abgelehntAm, begruendung: v.ablehnungsgrund ?? "" };
  return undefined;
}

export default async function FreigabeSeite({ params }: { params: Promise<{ id: string }> }) {
  const id = vorschlagId((await params).id);
  if (id === null) notFound();
  const lesung = await leseVorschlag(id);

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
  const { vorschlag: v, bezeichnungen } = lesung.daten;
  if (!v) notFound();

  const w = waage(v.probe, bezeichnungen);
  const { worte, diff } = klartext(v);
  const entscheidung = entscheidungAus(v);
  const lieferung = w?.lieferung && istMonat(w.lieferung) ? w.lieferung : null;
  const titel =
    v.status === "offen"
      ? "Diese Änderung wartet auf Ihre Freigabe."
      : v.status === "freigegeben"
        ? "Diese Änderung ist freigegeben."
        : "Diese Änderung ist abgelehnt.";

  const regelInWorten = (
    <div className="flex flex-col gap-2">
      {worte.map((satz) => (
        <Fliesstext key={satz}>{satz}</Fliesstext>
      ))}
    </div>
  );

  return (
    <>
      <nav aria-label="Zurück">
        <Link href="/uc3/freigaben" className="font-sans text-14 font-semibold text-gruen underline underline-offset-4">
          Zurück zu allen Freigaben
        </Link>
      </nav>
      <header className="flex max-w-3xl flex-col gap-2">
        <Ueberschrift stufe={2} als="h1">
          {titel}
        </Ueberschrift>
        <Fliesstext groesse={14} ton="gedaempft">
          {`Vorschlag uc3/${v.id} · ${aenderungKurz(v)}`}
        </Fliesstext>
      </header>

      <div className="flex max-w-3xl flex-col gap-6">
        <Entscheiden
          vorschlagId={v.id}
          eintrag={{
            anweisung: v.anweisung,
            name: v.gesagtVon ? `Gesagt von ${v.gesagtVon}` : "Wer es gesagt hat, ist nicht erfasst",
            zeit: v.gesagtAm ?? v.erstelltAm,
            wirkung: aenderungKurz(v),
            modell: v.modell,
            ref: `uc3/${v.id}`,
          }}
          zahlen={
            w
              ? { vorher: w.haupt.vorher, nachher: w.haupt.nachher, satz: waageSatz(w), beleg: waageBeleg(v.id, w) }
              : null
          }
          diff={diff}
          entscheidung={entscheidung}
          ohneProbe={
            <>
              {regelInWorten}
              <Fliesstext ton="gedaempft">Die Probe ist noch nicht gerechnet, deshalb fehlen die Zahlen.</Fliesstext>
              {diff && <Regelzeilen text={diff} />}
            </>
          }
        />

        {w && w.weitere.length > 0 && (
          <details className="flex flex-col gap-2">
            <summary className="cursor-pointer font-sans text-14 font-semibold text-gruen">
              {`${w.weitere.length} weitere Kategorien ändern sich`}
            </summary>
            <ul className="flex flex-col gap-1 pt-2">
              {w.weitere.map((z) => (
                <li key={`${z.merkmal}-${z.code}`} className="font-sans text-14 text-ink">
                  {`${z.bezeichnung}: `}
                  <span className="font-mono tabular-nums">
                    {`${formatZahl(z.vorher)} → ${formatZahl(z.nachher)} (${formatDifferenz(z.differenz)})`}
                  </span>
                </li>
              ))}
            </ul>
            <HerkunftChip
              quelle="meta.vorschlag"
              lieferung={w.lieferung}
              stand="vorlaeufig"
              sql={`SELECT probe->'${w.lieferung.replaceAll("'", "''")}' AS probe\nFROM meta.vorschlag\nWHERE id = ${v.id};`}
            />
          </details>
        )}

        <Akzent art="ki" className="flex flex-col gap-2">
          <Fliesstext groesse={14} ton="gedaempft">
            {`Vorschlag von ${rollenName(v.rolle)}${v.modell ? ` mit ${v.modell}` : ""}`}
          </Fliesstext>
          {w && regelInWorten}
          <Fliesstext groesse={14}>{`Begründung des Agenten: ${v.begruendung}`}</Fliesstext>
        </Akzent>

        <ul className="grid gap-4 sm:grid-cols-2" aria-label="Begriffe auf dieser Seite">
          {(["Freigabe", "Regel"] as const).map((wort) => (
            <li key={wort} className="font-sans text-14 font-semibold text-ink">
              <Fachbegriff wort={wort} />
            </li>
          ))}
        </ul>

        {v.status !== "offen" && lieferung && (
          <div>
            <Link href={laufPfad(lieferung)} className={knopfKlassen("sekundaer")}>
              {`Ergebnis ansehen: ${monatName(lieferung)}`}
            </Link>
          </div>
        )}
      </div>
    </>
  );
}

function Regelzeilen({ text }: { text: string }) {
  return (
    <pre className="max-w-full overflow-x-auto whitespace-pre-wrap break-words rounded border border-line bg-paper p-2 font-mono text-12 text-ink">
      {text.split("\n").map((zeile, index) => (
        <span
          key={index}
          className={`block ${zeile.startsWith("+") ? "bg-gruen-bg" : zeile.startsWith("-") ? "bg-err-bg" : ""}`}
        >
          {zeile}
        </span>
      ))}
    </pre>
  );
}
