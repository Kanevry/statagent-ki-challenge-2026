import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Akzent, Fliesstext, knopfKlassen, Leerzustand, Ueberschrift } from "@kic/ui/basis";
import { formatDifferenz, formatZahl, HerkunftChip, type FreigabeEntscheidung } from "@kic/ui/bausteine";
import { nurLesend } from "@/components/uc3/cli";
import { leerSatz } from "@/components/uc3/db";
import { Begriffsliste, Fachbegriff } from "@/components/uc3/fachbegriff";
import type { Uc3Begriff } from "@/components/uc3/glossar";
import { laufBeleg } from "@/components/uc3/beleg";
import {
  auftraggeber,
  auftragsZitat,
  aenderungKurz,
  ergebnisPfad,
  gesamtZeile,
  gruppenBeleg,
  gruppenSatz,
  klartext,
  leseVorschlag,
  probeTitel,
  rollenName,
  sqlErgebnisLauf,
  sqlWirkung,
  sqlWirkungMonat,
  teilWort,
  umverteilung,
  vorschlagId,
  waage,
  waageBeleg,
  waageSatz,
  wirkungJeKategorie,
  type Bezeichnungen,
  type EchteWirkung,
  type Kategorien,
  type Umverteilung,
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
  const { vorschlag: v, bezeichnungen, kategorien, ergebnis, wirkung } = lesung.daten;
  if (!v) notFound();

  const w = waage(v.probe, bezeichnungen);
  // Bei einer Umverteilung steht groß, wie sich die Kategorien zusammensetzen; die gleichbleibende Summe nur klein.
  const u = w?.umverteilung ? umverteilung(v.probe, kategorien) : null;
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
          nurLesen={nurLesend()}
          vorschlagId={v.id}
          eintrag={{
            anweisung: auftragsZitat(v.anweisung),
            name: auftraggeber(v),
            zeit: v.gesagtAm ?? v.erstelltAm,
            wirkung: aenderungKurz(v),
            modell: v.modell,
            ref: `uc3/${v.id}`,
          }}
          zahlen={
            w && !u
              ? {
                  vorher: w.haupt.vorher,
                  nachher: w.haupt.nachher,
                  satz: `${probeTitel(w.lieferung)}. ${waageSatz(w)}`,
                  beleg: waageBeleg(v.id, w),
                }
              : null
          }
          diff={diff}
          entscheidung={entscheidung}
          ohneProbe={
            w && u ? (
              <>
                <UmverteilungZahlen vorschlag={v.id} waage={w} u={u} bezeichnungen={bezeichnungen} />
                {regelInWorten}
              </>
            ) : (
            <>
              {regelInWorten}
              <Fliesstext ton="gedaempft">Die Probe ist noch nicht gerechnet, deshalb fehlen die Zahlen.</Fliesstext>
              <div className="font-sans text-14 font-semibold text-ink">
                <Fachbegriff wort="Probe" />
              </div>
              {diff && <Regelzeilen text={diff} />}
            </>
            )
          }
        />

        {w && w.umverteilung && !u && (
          <section className="flex flex-col gap-2" aria-labelledby="verschiebung">
            <h2 id="verschiebung" className="font-sans text-16 font-semibold text-ink">
              {`${probeTitel(w.lieferung)}: Diese ${formatZahl(w.weitere.length)} Kategorien tauschen Beschäftigungsverhältnisse untereinander.`}
            </h2>
            <WaageZeilen vorschlag={v.id} waage={w} zeilen={w.weitere} />
          </section>
        )}

        {wirkung && <EchteWirkungTeil wirkung={wirkung} kategorien={kategorien} umverteilt={u !== null} />}

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

        <Begriffsliste worte={begriffe} label="Begriffe auf dieser Seite" className="grid gap-4 sm:grid-cols-2" />

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

/**
 * Die Probe einer Umverteilung in Worten: je neue Kategorie die Summe ihrer bisherigen Teile, dann was bleibt, und
 * klein die unveränderte Gesamtzahl. Jede Zahl mit Beleg auf meta.vorschlag.probe.
 */
function UmverteilungZahlen({
  vorschlag,
  waage: w,
  u,
  bezeichnungen,
}: {
  vorschlag: number;
  waage: Waage;
  u: Umverteilung;
  bezeichnungen: Bezeichnungen;
}) {
  const kategorienZahl = u.gruppen.length + u.bleibt.length;
  return (
    <div className="flex flex-col gap-3">
      <p className="font-sans text-16 font-semibold text-ink">{probeTitel(u.lieferung)}</p>
      <Fliesstext>{`Dieselben Beschäftigungsverhältnisse stehen in ${formatZahl(kategorienZahl)} Kategorien:`}</Fliesstext>
      <ul className="flex flex-col gap-3">
        {u.gruppen.map((g) => (
          <li key={g.ziel} className="flex flex-col items-start gap-1">
            <span className="break-words font-sans text-20 font-semibold tabular-nums text-ink">{gruppenSatz(g, bezeichnungen)}</span>
            <HerkunftChip {...gruppenBeleg(vorschlag, u, g)} />
          </li>
        ))}
        {u.bleibt.map((b) => (
          <li key={b.code} className="flex flex-col items-start gap-1">
            <span className="break-words font-sans text-20 font-semibold tabular-nums text-ink">
              {`${b.code} bleibt bei ${formatZahl(b.wert)}`}
            </span>
            <HerkunftChip
              {...waageBeleg(vorschlag, w, {
                merkmal: "qualifikation",
                code: b.code,
                bezeichnung: b.code,
                vorher: b.wert,
                nachher: b.wert,
                differenz: 0,
              })}
            />
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <Fliesstext groesse={14} ton="gedaempft">
          {`Zusammen ${formatZahl(u.gesamt)} wie bisher, Unterschied 0.`}
        </Fliesstext>
        <HerkunftChip {...waageBeleg(vorschlag, w, w.gesamt)} />
      </div>
    </div>
  );
}

/**
 * Echte Wirkung aus den Läufen: der jüngste Monat, den beide Regelsätze gerechnet haben. Bei einer Umverteilung je
 * Kategorie, sonst die Gesamtzahl. Enthält der Ziel-Regelsatz weitere Aufträge, sagt der Text das.
 */
function EchteWirkungTeil({
  wirkung: e,
  kategorien,
  umverteilt,
}: {
  wirkung: EchteWirkung;
  kategorien: Kategorien;
  umverteilt: boolean;
}) {
  const { basis, ziel } = e;
  const rb = basis.lauf.regelsatz;
  const rz = ziel.lauf.regelsatz;
  const zeilen = umverteilt ? wirkungJeKategorie(e, kategorien) : [];
  const differenz = ziel.gesamt - basis.gesamt;
  return (
    <section className="flex flex-col gap-3 border-t border-line pt-6" aria-labelledby="echte-wirkung">
      <h2 id="echte-wirkung" className="font-sans text-16 font-semibold text-ink">
        {`Gerechnet für ${monatName(e.monat)}: Regelsatz ${rb} und Regelsatz ${rz} im Vergleich`}
      </h2>
      <Fliesstext groesse={14} ton="gedaempft">
        {`Das ist der jüngste Monat, für den es mit beiden Regelsätzen einen fertigen Lauf gibt.`}
      </Fliesstext>
      {zeilen.length > 0 && (
        <ul className="flex flex-col gap-2">
          {zeilen.map((k) => (
            <li key={k.kategorie} className="break-words font-sans text-16 tabular-nums text-ink">
              {`${k.kategorie}: Regelsatz ${rb} ${formatZahl(k.basis)}${
                k.basisTeile.length > 1 ? ` (${k.basisTeile.map((t) => teilWort(t)).join(" + ")})` : ""
              }, Regelsatz ${rz} ${formatZahl(k.ziel)}`}
            </li>
          ))}
        </ul>
      )}
      <p className="font-sans text-16 tabular-nums text-ink">
        {`Gesamt: Regelsatz ${rb} ${formatZahl(basis.gesamt)}, Regelsatz ${rz} ${formatZahl(ziel.gesamt)} (${formatDifferenz(differenz)})`}
      </p>
      {e.auchImZiel.length > 0 && (
        <Fliesstext groesse={14}>
          {`Regelsatz ${rz} enthält auch ${e.auchImZiel.map((t) => `„${t}“`).join(" und ")}. Der Unterschied zwischen den Regelsätzen kommt deshalb nicht nur aus diesem Auftrag.`}
        </Fliesstext>
      )}
      <div className="flex flex-wrap gap-2">
        <HerkunftChip {...laufBeleg(basis.lauf, { sql: sqlWirkung(basis.lauf) })} />
        <HerkunftChip {...laufBeleg(ziel.lauf, { sql: sqlWirkung(ziel.lauf) })} />
        <HerkunftChip quelle="meta.lauf" lieferung={e.monat} sql={sqlWirkungMonat(rb, rz)} />
      </div>
    </section>
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
