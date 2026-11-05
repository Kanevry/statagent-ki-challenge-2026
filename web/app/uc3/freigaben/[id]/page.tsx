import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Akzent, Fliesstext, knopfKlassen, Leerzustand, Ueberschrift } from "@kic/ui/basis";
import { formatDifferenz, formatZahl, HerkunftChip, type FreigabeEntscheidung } from "@kic/ui/bausteine";
import { leerSatz } from "@/components/uc3/db";
import { Fachbegriff } from "@/components/uc3/fachbegriff";
import type { Uc3Begriff } from "@/components/uc3/glossar";
import {
  aenderungKurz,
  ergebnisPfad,
  gesamtZeile,
  klartext,
  leseVorschlag,
  rollenName,
  sqlErgebnisLauf,
  vorschlagId,
  waage,
  waageBeleg,
  waageSatz,
  type Vorschlag,
  type Waage,
  type WaageZeile,
} from "@/components/uc3/freigabe";
import { monatName } from "@/components/uc3/monat";
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
  const { vorschlag: v, bezeichnungen, ergebnis } = lesung.daten;
  if (!v) notFound();

  const w = waage(v.probe, bezeichnungen);
  const { worte, diff } = klartext(v);
  const entscheidung = entscheidungAus(v);
  const gesamt = w ? gesamtZeile(w) : null;
  // Probe steht ohne gerechnete Probe schon in Zone 2 neben dem Hinweis.
  const begriffe: Uc3Begriff[] = w ? ["Freigabe", "Regel", "Regelsatz", "Probe"] : ["Freigabe", "Regel", "Regelsatz"];
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
              <div className="font-sans text-14 font-semibold text-ink">
                <Fachbegriff wort="Probe" />
              </div>
              {diff && <Regelzeilen text={diff} />}
            </>
          }
        />

        {w && w.umverteilung && (
          <section className="flex flex-col gap-2" aria-labelledby="verschiebung">
            <h2 id="verschiebung" className="font-sans text-16 font-semibold text-ink">
              {`Diese ${formatZahl(w.weitere.length)} Kategorien tauschen Verhältnisse untereinander.`}
            </h2>
            <WaageZeilen vorschlag={v.id} waage={w} zeilen={w.weitere} />
          </section>
        )}

        {w && !w.umverteilung && gesamt && <WaageZeilen vorschlag={v.id} waage={w} zeilen={[gesamt]} />}

        {w && !w.umverteilung && w.weitere.length > 0 && (
          <details className="flex flex-col gap-2">
            <summary className="cursor-pointer font-sans text-14 font-semibold text-gruen">
              {`${w.weitere.length} weitere Kategorien ändern sich`}
            </summary>
            <div className="pt-2">
              <WaageZeilen vorschlag={v.id} waage={w} zeilen={w.weitere} />
            </div>
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
          {begriffe.map((wort) => (
            <li key={wort} className="font-sans text-14 font-semibold text-ink">
              <Fachbegriff wort={wort} />
            </li>
          ))}
        </ul>

        {ergebnis && (
          <div className="flex flex-col gap-2">
            <div>
              <Link href={ergebnisPfad(ergebnis)} className={knopfKlassen("sekundaer")}>
                {`Ergebnis ansehen: ${monatName(ergebnis.monat)}, Regelsatz ${ergebnis.regelsatz}`}
              </Link>
            </div>
            {v.status === "freigegeben" && !ergebnis.laufDa && (
              <div className="flex flex-wrap items-center gap-2">
                <Fliesstext groesse={14}>
                  {`Die neuen Zahlen entstehen, sobald der Monat mit Regelsatz ${ergebnis.regelsatz} gerechnet ist.`}
                </Fliesstext>
                <HerkunftChip
                  quelle="meta.lauf"
                  lieferung={ergebnis.monat}
                  stand="vorlaeufig"
                  sql={sqlErgebnisLauf(ergebnis.monat, ergebnis.regelsatz)}
                />
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}

/** Zeilen „Arbeiter (Qualifikation): 0 → 210.000 (+210.000)“, jede mit Beleg auf genau ihre Zahlen. */
function WaageZeilen({ vorschlag, waage: w, zeilen }: { vorschlag: number; waage: Waage; zeilen: WaageZeile[] }) {
  return (
    <ul className="flex flex-col gap-2">
      {zeilen.map((z) => (
        <li key={`${z.merkmal}-${z.code}`} className="flex flex-wrap items-center gap-x-3 gap-y-1 font-sans text-14 text-ink">
          <span className="break-words">
            {`${z.merkmal === "gesamt" ? "Gesamt" : z.bezeichnung}: `}
            <span className="font-mono tabular-nums">
              {`${formatZahl(z.vorher)} → ${formatZahl(z.nachher)} (${formatDifferenz(z.differenz)})`}
            </span>
          </span>
          <HerkunftChip {...waageBeleg(vorschlag, w, z)} />
        </li>
      ))}
    </ul>
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
