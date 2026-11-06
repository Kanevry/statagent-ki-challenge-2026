import Link from "next/link";
import type { ReactNode } from "react";
import { knopfKlassen, Leerzustand, Ueberschrift } from "@kic/ui/basis";
import { formatZahl } from "@kic/ui/bausteine";
import { abrechnungBeleg, laufBeleg } from "@/components/uc3/beleg";
import { BelegLink, StandPunkt } from "@/components/uc3/beleg-link";
import {
  annahmeSatz,
  leseQualitaetsbericht,
  sqlAnnahmen,
  sqlAnnahmePruefung,
  sqlAnnahmeWirkung,
  sqlRueckfragen,
  type Annahme,
  type Qualitaetsbericht,
  type Rueckfrage,
} from "@/components/uc3/bericht";
import { DatenFehler } from "@/components/uc3/daten-fehler";
import {
  abrechnungSatz,
  ausLieferung,
  bestandSatz,
  determinismusSatz,
  einstufungStatus,
  fehlendeGruppen,
  haltSatz,
  haltTreffer,
  hatRevisionsbedarf,
  kannVeroeffentlichen,
  leseLaufDetail,
  massnahmeSatz,
  revisionSatz,
  sortiereTreffer,
  sqlBestandMitVormonat,
  sqlDeterminismus,
  sqlKeineRevision,
  sqlKennzahlen,
  sqlRegionen,
  sqlRevision,
  sqlTreffer,
  titelUndMesswerte,
  umschichtungSatz,
  ursachenSatz,
  type LaufDetail,
  type Treffer,
} from "@/components/uc3/lauf-detail";
import { istMonat, monatName, stichtag, verschieben } from "@/components/uc3/monat";
import { abrechnung } from "@/components/uc3/laeufe";
import { laufPfad, uebersichtPfad } from "@/components/uc3/navigation";
import { mitRegeln, regelsatzName } from "@/components/uc3/regelsatz-name";
import { OenaceWechselAbsatz } from "./oenace-wechsel-absatz";
import type { Lauf } from "@/components/uc3/typen";
import { alltag } from "@/components/uc3/sprache";
import { Bundeslaender } from "./bundeslaender";
import { imZeitraum } from "@/components/uc3/zeitraum";

// Monatsseite und Qualitätsbericht in einem (UI-Regie v1): /uc3/laeufe/[monat] und /uc3/berichte/[monat] rendern
// diese Seite. Oben eine Hauptaussage (warum angehalten oder wie viele), die Rechnung des Bestands in einer Zeile
// und der eine Weg weiter. Dann die Auffälligkeiten als Zeilen, die anhaltenden zuerst. Danach die fünf Abschnitte
// der Vorlage, jeder kurz, Einzelheiten eingeklappt. Ein Beleg je Aussage-Block.

const link = "text-ink underline decoration-line underline-offset-4 hover:decoration-ink";
const abschnittTitel = "font-sans text-20 font-semibold text-ink";

function Rechnung({ detail }: { detail: LaufDetail }) {
  const { lauf } = detail;
  const stand = lauf.ergebnisStand === "endgueltig" ? "veröffentlicht" : "vorläufig";
  const teil = "uc3-rechnung-teil inline-flex flex-col";
  const zahl = "font-sans text-32 font-semibold leading-none tabular-nums text-ink md:text-56";
  const wort = "font-sans text-14 text-slate";
  return (
    <div className="flex flex-col gap-2">
      <style>{`
        @keyframes uc3-auftauchen { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
        .uc3-rechnung-teil { animation: uc3-auftauchen 450ms ease-out both; }
        @media (prefers-reduced-motion: reduce) { .uc3-rechnung-teil { animation: none; } }
      `}</style>
      <div className="flex flex-wrap items-end gap-x-4 gap-y-2" aria-label="Rechnung des Bestands">
        {lauf.fortgeschrieben > 0 ? (
          <>
            <span className={teil}>
              <span className={zahl}>{formatZahl(ausLieferung(lauf))}</span>
              <span className={wort}>aus der Lieferung</span>
            </span>
            <span className={`${teil} ${zahl} text-slate`} style={{ animationDelay: "350ms" }} aria-hidden="true">
              +
            </span>
            <span className={teil} style={{ animationDelay: "450ms" }}>
              <span className={zahl}>{formatZahl(lauf.fortgeschrieben)}</span>
              <span className={wort}>{`aus ${monatName(verschieben(lauf.lieferung, -1)).split(" ")[0]} übernommen`}</span>
            </span>
            <span className={`${teil} ${zahl} text-slate`} style={{ animationDelay: "800ms" }} aria-hidden="true">
              =
            </span>
            <span className={teil} style={{ animationDelay: "900ms" }}>
              <span className={zahl}>{formatZahl(lauf.gezaehlt)}</span>
              <span className={wort}>{`${imZeitraum(lauf.zeitraumArt)}, ${stand}`}</span>
            </span>
          </>
        ) : (
          <span className={teil}>
            <span className={zahl}>{formatZahl(lauf.gezaehlt)}</span>
            <span className={wort}>{`Beschäftigungsverhältnisse ${imZeitraum(lauf.zeitraumArt)}, ${stand}`}</span>
          </span>
        )}
        <span className="pb-1">
          <BelegLink {...laufBeleg(lauf, { quelle: "meta.lauf", sql: sqlKennzahlen(lauf) })} />
        </span>
      </div>
      <Differenz detail={detail} />
    </div>
  );
}

/**
 * Warum weniger übernommen als vermisst wird (Jury 05.11.: „78.949 fehlen, aber 77.746 übernommen?“): Übernommen
 * werden nur Verhältnisse, die laut Vormonats-Lieferung am Stichtag noch bestehen (Regel E07, docs/plan/uc3/2025-10-abgleich.md).
 * In v2 gilt dieselbe Regel: Gemessen endeten die nicht übernommenen Verhältnisse schon am Vormonatsletzten (2025-10: 1.203,
 * 2025-03: 234), sie bestanden also auch im ganzen Monat nicht.
 */
function Differenz({ detail }: { detail: LaufDetail }) {
  const { lauf, treffer } = detail;
  const fehlen = treffer.find((t) => t.art === "verhaeltnisse_verschwunden")?.anzahl ?? 0;
  const uebernommen = lauf.fortgeschrieben;
  if (!uebernommen || fehlen <= uebernommen) return null;
  const vm = monatName(verschieben(lauf.lieferung, -1));
  return (
    <p className="max-w-3xl font-sans text-14 text-slate">
      {`Übernommen sind nur die ${formatZahl(uebernommen)}, die laut Lieferung ${vm} ${lauf.zeitraumArt === "Monat" ? `im ${monatName(lauf.lieferung)}` : "am Stichtag"} noch bestanden. Die übrigen ${formatZahl(fehlen - uebernommen)} endeten schon vorher und zählen nicht.`}
    </p>
  );
}

function WegWeiter({ detail, angehalten }: { detail: LaufDetail; angehalten: boolean }) {
  const { lauf, veroeffentlichen } = detail;
  if (lauf.ergebnisStand === "endgueltig") {
    return <p className="font-sans text-16 text-slate">{lauf.freigegebenVon ? `Veröffentlicht von ${lauf.freigegebenVon}.` : "Veröffentlicht."}</p>;
  }
  if (veroeffentlichen.wartetAuf.length > 0) {
    const nrn = veroeffentlichen.wartetAuf;
    return (
      <p className="font-sans text-16 text-ink">
        {`Wartet auf Antwort der Fachabteilung (${nrn.length === 1 ? "Rückfrage" : "Rückfragen"} ${nrn.join(", ")}).`}
      </p>
    );
  }
  if (kannVeroeffentlichen(lauf, angehalten, veroeffentlichen)) {
    const befehl = `uv run uc3 veroeffentlichen --lieferung ${lauf.lieferung}${lauf.regelsatz === "v1" ? "" : ` --regelsatz ${lauf.regelsatz}`} --name "Vorname Nachname"`;
    return (
      <div className="flex flex-col gap-1">
        <p className="font-sans text-16 text-ink">Bereit zum Veröffentlichen. Ein Mensch gibt den Monat mit Vor- und Nachnamen frei.</p>
        <details>
          <summary className="inline-flex min-h-11 cursor-pointer items-center font-sans text-14 text-slate underline decoration-line underline-offset-4">
            Befehl zum Veröffentlichen
          </summary>
          <pre className="whitespace-pre-wrap break-all bg-paper p-2 font-mono text-12 text-ink">{befehl}</pre>
        </details>
      </div>
    );
  }
  return (
    <p className="font-sans text-16 text-ink">
      {veroeffentlichen.regelnOhneFreigabe > 0
        ? `Bleibt vorläufig, bis ${veroeffentlichen.regelnOhneFreigabe === 1 ? "die letzte Regel" : `${formatZahl(veroeffentlichen.regelnOhneFreigabe)} Regeln`} mit Namen freigegeben ${veroeffentlichen.regelnOhneFreigabe === 1 ? "ist" : "sind"}.`
        : "Bleibt vorläufig, bis die Regeln für diesen Monat mit Namen freigegeben sind."}
    </p>
  );
}

function TrefferZeile({ detail, t }: { detail: LaufDetail; t: Treffer }) {
  const { lauf } = detail;
  const massnahme = massnahmeSatz(t, { fehlendeGruppen: fehlendeGruppen(detail.treffer, detail.fdCodes) });
  const status = einstufungStatus(t.einstufung, t.offeneRueckfragen);
  const { titel, messwerte } = titelUndMesswerte(t, lauf.lieferung);
  return (
    <li className="border-b border-line" data-regel={t.name}>
      <details className="group">
        <summary className="flex min-h-11 cursor-pointer list-none items-center gap-3 py-3 [&::-webkit-details-marker]:hidden">
          <span aria-hidden="true" className={`size-2 shrink-0 rounded-full ${t.anhalten ? "bg-gelb" : "bg-slate"}`} />
          <span className="flex-1 font-sans text-16 text-ink">{alltag(titel)}</span>
          <span className="font-sans text-16 tabular-nums text-ink">{formatZahl(t.anzahl)}</span>
          <span aria-hidden="true" className="font-sans text-14 text-slate transition-transform group-open:rotate-90">
            ›
          </span>
        </summary>
        <div className="flex flex-col items-start gap-2 pb-4 pl-5">
          {messwerte && <p className="font-sans text-14 tabular-nums text-ink">{alltag(messwerte)}</p>}
          <p className="font-sans text-14 text-slate">{status.wort}{t.anhalten ? ", hält den Monat an" : ""}</p>
          {massnahme && <p className="font-sans text-16 text-ink">{`Was wir tun: ${alltag(massnahme)}`}</p>}
          <BelegLink {...laufBeleg(lauf, { quelle: "meta.pruefung_treffer", sql: sqlTreffer(lauf, t) })} />
        </div>
      </details>
    </li>
  );
}

function Auffaelligkeiten({ detail }: { detail: LaufDetail }) {
  const liste = sortiereTreffer(detail.treffer);
  const anhaltend = liste.filter((t) => t.anhalten);
  const weitere = liste.filter((t) => !t.anhalten);
  const titel =
    liste.length === 0
      ? "In diesem Monat ist keine Prüfung auffällig."
      : `${formatZahl(liste.length)} ${liste.length === 1 ? "Prüfung" : "Prüfungen"} auffällig${
          anhaltend.length === 0 ? "" : `, ${anhaltend.length === 1 ? "eine hält" : `${formatZahl(anhaltend.length)} halten`} den Monat an`
        }.`;
  const oben = anhaltend.length > 0 ? anhaltend : weitere.slice(0, 3);
  const rest = anhaltend.length > 0 ? weitere : weitere.slice(3);
  return (
    <section id="auffaelligkeiten" aria-labelledby="auffaelligkeiten-titel" className="flex max-w-4xl scroll-mt-24 flex-col gap-2">
      <h2 id="auffaelligkeiten-titel" className={abschnittTitel}>
        {titel}
      </h2>
      {oben.length > 0 && (
        <ul className="flex flex-col border-t border-line">
          {oben.map((t) => (
            <TrefferZeile key={`${t.regelId}-${t.ebene}`} detail={detail} t={t} />
          ))}
        </ul>
      )}
      {rest.length > 0 && (
        <details>
          <summary className="inline-flex min-h-11 cursor-pointer items-center font-sans text-14 text-slate underline decoration-line underline-offset-4">
            {`${formatZahl(rest.length)} weitere`}
          </summary>
          <ul className="flex flex-col border-t border-line">
            {rest.map((t) => (
              <TrefferZeile key={`${t.regelId}-${t.ebene}`} detail={detail} t={t} />
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

function Abschnitt({ id, titel, children }: { id: string; titel: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-titel`} className="flex max-w-4xl scroll-mt-24 flex-col gap-2 border-t border-line pt-6">
      <h2 id={`${id}-titel`} className={abschnittTitel}>
        {titel}
      </h2>
      {children}
    </section>
  );
}

function Mehr({ text, children }: { text: string; children: ReactNode }) {
  return (
    <details>
      <summary className="inline-flex min-h-11 cursor-pointer items-center font-sans text-14 text-slate underline decoration-line underline-offset-4">
        {text}
      </summary>
      <div className="flex flex-col items-start gap-2 pt-2">{children}</div>
    </details>
  );
}

function RueckfrageZeile({ r }: { r: Rueckfrage }) {
  return (
    <li className="border-b border-line">
      <details>
        <summary className="flex min-h-11 cursor-pointer list-none items-center gap-3 py-3 [&::-webkit-details-marker]:hidden">
          <span className="w-10 shrink-0 font-sans text-16 font-medium text-ink">{r.nr}</span>
          <span className="flex-1 font-sans text-16 text-ink">{r.titel}</span>
          <StandPunkt stand={r.offen ? "offen" : "veroeffentlicht"} wort={r.offen ? "offen" : "beantwortet"} />
        </summary>
        <div className="flex flex-col gap-2 pb-4 pl-13">
          <p className="font-sans text-16 text-ink">{r.frage}</p>
          {r.vorschlag && <p className="font-sans text-14 text-slate">{`Unser Vorschlag: ${r.vorschlag}`}</p>}
          {r.antwort && <p className="font-sans text-14 text-ink">{`Antwort${r.antwortAm ? ` vom ${r.antwortAm}` : ""}: ${r.antwort}`}</p>}
        </div>
      </details>
    </li>
  );
}

function AnnahmeZeile({ a, lauf }: { a: Annahme; lauf: Lauf }) {
  const wirkung = a.wirkungSaetze === null ? null : formatZahl(a.wirkungSaetze);
  const eins = a.wirkungSaetze === 1;
  // Umfasst die Zahl alle geprüften Zeilen (eine Regel, die jede Zeile anfasst), sagt der Satz das dazu.
  const alleZeilen = a.wirkungSaetze !== null && (a.wirkungSaetze === lauf.gelesen || a.wirkungSaetze === lauf.gelesen + lauf.fortgeschrieben);
  const belegSql =
    a.wirkungQuelle === "pruefung" && a.wirkungRegel
      ? sqlAnnahmePruefung(lauf, a.wirkungRegel)
      : a.wirkungQuelle === "regel" && a.wirkungRegel
        ? sqlAnnahmeWirkung(lauf, a.wirkungRegel)
        : null;
  return (
    <li className="border-b border-line">
      <details>
        <summary className="flex min-h-11 cursor-pointer list-none items-center gap-3 py-3 [&::-webkit-details-marker]:hidden">
          <span className="flex-1 font-sans text-16 text-ink">{annahmeSatz(a.satz).replace(/^Annahme:\s*/, "")}</span>
          <span className="font-sans text-16 tabular-nums text-ink">{a.wirkungSaetze ? wirkung : ""}</span>
        </summary>
        <div className="flex flex-col gap-2 pb-4">
          <p className="font-sans text-14 text-slate">
            {wirkung === null
              ? "Für diese Annahme gibt es in diesem Monat keine eindeutige Zahl."
              : a.wirkungQuelle === "pruefung"
                ? `Betrifft in diesem Monat ${wirkung} ${eins ? "Beschäftigungsverhältnis" : "Beschäftigungsverhältnisse"}, so viele findet die Prüfung.`
                : `Betrifft in diesem Monat ${wirkung} ${eins ? "Zeile" : "Zeilen"}.${alleZeilen ? " Diese Zahl umfasst alle geprüften Zeilen, nicht nur die geänderten." : ""}`}
          </p>
          {a.begruendung && <p className="font-sans text-14 text-ink">{`Begründung: ${a.begruendung}`}</p>}
          {a.rueckfrage && <p className="font-sans text-14 text-slate">{`Gehört zu Rückfrage ${a.rueckfrage}.`}</p>}
          {belegSql && <BelegLink {...laufBeleg(lauf, { quelle: a.wirkungQuelle === "pruefung" ? "meta.pruefung_treffer" : "meta.regel_wirkung", sql: belegSql })} />}
        </div>
      </details>
    </li>
  );
}

type Marke = { id: string; text: string; anzahl: number | null };

function marken(detail: LaufDetail, bericht: Qualitaetsbericht | null): Marke[] {
  return [
    { id: "ueberblick", text: "Überblick", anzahl: null },
    { id: "auffaelligkeiten", text: "Auffälligkeiten", anzahl: sortiereTreffer(detail.treffer).length },
    { id: "rueckfragen", text: "Rückfragen", anzahl: bericht ? bericht.rueckfragen.length : null },
    { id: "annahmen", text: "Annahmen", anzahl: bericht ? bericht.annahmen.length : null },
    { id: "revisionsbedarf", text: "Revisionsbedarf", anzahl: detail.revisionen.filter(hatRevisionsbedarf).length },
  ];
}

/** Die fünf Abschnitte der Vorlage als Sprungmarken: ab lg schmal und mitlaufend rechts, darunter im Fluss. */
function Sprungmarken({ liste, seitlich }: { liste: readonly Marke[]; seitlich: boolean }) {
  return (
    <nav
      aria-label="Abschnitte des Qualitätsberichts"
      className={
        seitlich
          ? "sticky top-24 flex flex-col gap-1 border-l border-line pl-4 font-sans text-14"
          : "flex max-w-4xl flex-wrap gap-x-6 gap-y-1 border-t border-line pt-4 font-sans text-14 lg:hidden"
      }
    >
      {seitlich && <p className="pb-1 font-sans text-12 font-semibold text-slate">Qualitätsbericht</p>}
      {liste.map((m) => (
        <a key={m.id} href={`#${m.id}`} className={`inline-flex min-h-11 items-center justify-between gap-3 ${link}`}>
          <span>{m.text}</span>
          {m.anzahl !== null && <span className="tabular-nums text-slate">{formatZahl(m.anzahl)}</span>}
        </a>
      ))}
    </nav>
  );
}

const BERICHT_FEHLER = "Dieser Teil des Qualitätsberichts ließ sich gerade nicht lesen. Es wurde nichts geändert. Laden Sie die Seite in einer Minute neu.";

function Abschnitte({ detail, bericht }: { detail: LaufDetail; bericht: Qualitaetsbericht | null }) {
  const { lauf, revisionen, regionen, determinismus } = detail;
  const tag = stichtag(lauf.lieferung);
  const mitRevision = revisionen.filter(hatRevisionsbedarf);
  const rueckfragen = bericht?.rueckfragen ?? [];
  const offen = rueckfragen.filter((r) => r.offen).length;
  const annahmen = bericht?.annahmen ?? [];
  return (
    <>
      <Sprungmarken liste={marken(detail, bericht)} seitlich={false} />

      <Abschnitt id="ueberblick" titel="Überblick">
        <div className="flex flex-wrap items-baseline gap-x-3">
          <p className="font-sans text-16 text-ink">{abrechnungSatz(lauf, abrechnung(lauf).gehtAuf)}</p>
          <BelegLink {...abrechnungBeleg(lauf)} />
        </div>
        <Mehr text="Bundesländer">
          {regionen.length === 0 ? (
            <p className="font-sans text-14 text-slate">Für diesen Monat liegen keine Zahlen je Bundesland vor.</p>
          ) : (
            <Bundeslaender regionen={regionen} wann={lauf.zeitraumArt === "Monat" ? `im ${monatName(lauf.lieferung)}` : `am ${tag}`} />
          )}
          <BelegLink {...laufBeleg(lauf, { sql: sqlRegionen(lauf) })} />
        </Mehr>
        <Mehr text="Gleiche Daten, gleiche Zahlen">
          <p className="font-sans text-14 text-ink">{`Dieselben Daten und Regeln ergeben dieselben Zahlen: ${determinismusSatz(determinismus)}`}</p>
          <BelegLink {...laufBeleg(lauf, { quelle: "meta.lauf", sql: sqlDeterminismus(lauf) })} />
        </Mehr>
      </Abschnitt>

      <Abschnitt
        id="rueckfragen"
        titel={
          !bericht
            ? "Rückfragen"
            : rueckfragen.length === 0
            ? "Keine Rückfrage betrifft diesen Monat."
            : `${formatZahl(rueckfragen.length)} ${rueckfragen.length === 1 ? "Rückfrage betrifft" : "Rückfragen betreffen"} diesen Monat, ${offen === 0 ? "alle beantwortet" : `${formatZahl(offen)} offen`}.`
        }
      >
        {!bericht && <p className="font-sans text-16 text-ink">{BERICHT_FEHLER}</p>}
        {rueckfragen.length > 0 && (
          <ul className="flex flex-col border-t border-line">
            {rueckfragen.map((r) => (
              <RueckfrageZeile key={r.nr} r={r} />
            ))}
          </ul>
        )}
        <BelegLink {...laufBeleg(lauf, { quelle: "meta.rueckfrage", sql: sqlRueckfragen(lauf) })} />
      </Abschnitt>

      <Abschnitt
        id="annahmen"
        titel={!bericht ? "Annahmen" : annahmen.length === 0 ? "In diesem Monat gilt keine Annahme." : `${formatZahl(annahmen.length)} ${annahmen.length === 1 ? "Annahme gilt" : "Annahmen gelten"} in diesem Monat, jede als Regel umgesetzt.`}
      >
        {!bericht && <p className="font-sans text-16 text-ink">{BERICHT_FEHLER}</p>}
        {annahmen.length > 0 && (
          <ul className="flex flex-col border-t border-line">
            <li aria-hidden="true" className="flex justify-end border-b border-line py-1 font-sans text-12 font-semibold text-slate">
              betrifft
            </li>
            {annahmen.map((a) => (
              <AnnahmeZeile key={a.nr} a={a} lauf={lauf} />
            ))}
          </ul>
        )}
        {bericht && <BelegLink {...laufBeleg(lauf, { quelle: bericht.annahmenQuelle, sql: sqlAnnahmen(lauf, bericht.annahmenQuelle) })} />}
      </Abschnitt>

      <Abschnitt
        id="revisionsbedarf"
        titel={
          mitRevision.length === 0
            ? "Diese Lieferung ändert keinen früheren Monat."
            : `Diese Lieferung zeigt Revisionsbedarf für ${mitRevision.length === 1 ? "einen früheren Monat" : `${formatZahl(mitRevision.length)} frühere Monate`}.`
        }
      >
        {mitRevision.length === 0 ? (
          <BelegLink {...laufBeleg(lauf, { quelle: "meta.revision", sql: sqlKeineRevision(lauf) })} />
        ) : (
          <ul className="flex flex-col">
            {mitRevision.map((r) => {
              const gruende = ursachenSatz(r.ursachen);
              return (
                <li key={r.berichtsmonat} className="flex flex-col items-start gap-1 border-b border-line py-3">
                  <p className="font-sans text-16 text-ink">{r.differenz === 0 ? umschichtungSatz(r) : revisionSatz(r)}</p>
                  {gruende && <p className="font-sans text-14 text-slate">{gruende}</p>}
                  <BelegLink {...laufBeleg(lauf, { quelle: "meta.revision", monat: r.berichtsmonat, sql: sqlRevision(lauf, r.berichtsmonat) })} />
                </li>
              );
            })}
          </ul>
        )}
      </Abschnitt>
    </>
  );
}

function Weiter({ detail }: { detail: LaufDetail }) {
  const { lauf } = detail;
  const vor = verschieben(lauf.lieferung, -1);
  const nach = verschieben(lauf.lieferung, 1);
  return (
    <nav aria-label="Weitere Monate" className="flex max-w-4xl flex-wrap items-center justify-between gap-4 border-t border-line pt-6 font-sans text-16">
      {detail.davor ? (
        <Link href={laufPfad(vor, lauf.regelsatz)} className={`inline-flex min-h-11 items-center ${link}`}>
          {`Zurück zu ${monatName(vor)}`}
        </Link>
      ) : (
        <span />
      )}
      <Link href={uebersichtPfad(lauf.regelsatz)} className={`inline-flex min-h-11 items-center ${link}`}>
        Alle Läufe
      </Link>
      {detail.danach ? (
        <Link href={laufPfad(nach, lauf.regelsatz)} className={`inline-flex min-h-11 items-center ${link}`}>
          {`Weiter zu ${monatName(nach)}`}
        </Link>
      ) : (
        <span />
      )}
    </nav>
  );
}

/** Die ganze Monatsseite; ohne Lauf ein gestalteter Leerzustand (HTTP 200). */
export async function Monatsseite({ lieferung, regelsatz }: { lieferung: string; regelsatz: string }) {
  const [lesung, berichtLesung] = await Promise.all([leseLaufDetail(lieferung, regelsatz), leseQualitaetsbericht(lieferung, regelsatz)]);
  const name = istMonat(lieferung) ? monatName(lieferung) : lieferung;

  if (!lesung.ok) return <DatenFehler grund={lesung.grund} />;
  if (lesung.daten === null) {
    const satz =
      regelsatz !== "v1"
        ? `Für ${name} gibt es ${mitRegeln(regelsatz)} noch keinen Lauf. Er entsteht, sobald die freigegebene Änderung gerechnet ist.`
        : `Für ${name} gibt es noch keinen Lauf.`;
    return (
      <>
        <Ueberschrift stufe={2} als="h1">
          {name}
        </Ueberschrift>
        <Leerzustand
          satz={satz}
          aktion={
            <Link href={regelsatz !== "v1" ? laufPfad(lieferung) : "/uc3"} className={knopfKlassen("sekundaer")}>
              {regelsatz !== "v1" ? `${name} ${mitRegeln("v1")} ansehen` : "Alle Monate ansehen"}
            </Link>
          }
        />
      </>
    );
  }

  const detail = lesung.daten;
  const bericht = berichtLesung.ok ? berichtLesung.daten : null;
  const { lauf, vormonat } = detail;
  const halt = haltTreffer(detail.treffer);
  const stand = halt ? "angehalten" : lauf.ergebnisStand === "endgueltig" ? "veroeffentlicht" : "vorlaeufig";

  return (
    <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_13rem] lg:gap-12">
      <div className="flex min-w-0 flex-col gap-10">
      <header className="flex max-w-4xl flex-col gap-4">
        <p className="flex flex-wrap items-center gap-x-3 font-sans text-14 text-slate">
          <span>{name}</span>
          {lauf.zeitraumArt !== "Monat" && (
            <>
              <span aria-hidden="true">·</span>
              <span>{`Stichtag ${stichtag(lauf.lieferung)}`}</span>
            </>
          )}
          {lauf.regelsatz !== "v1" && (
            <>
              <span aria-hidden="true">·</span>
              <span>{regelsatzName(lauf.regelsatz)}</span>
            </>
          )}
          <span aria-hidden="true">·</span>
          <StandPunkt stand={stand} />
        </p>
        <Ueberschrift stufe={2} als="h1" className="hyphens-auto break-words">
          {halt ? haltSatz(halt, lauf.lieferung, detail.fdCodes) : bestandSatz(lauf, vormonat)}
        </Ueberschrift>
        {/* Ohne Halt und ohne Übernahme wiederholte die Rechnung nur die Zahl der Überschrift, samt zweitem Beleg. */}
        <div>
          {halt ? (
            <BelegLink {...laufBeleg(lauf, { quelle: "meta.pruefung_treffer", sql: sqlTreffer(lauf, halt) })} />
          ) : (
            <BelegLink {...laufBeleg(lauf, { sql: sqlBestandMitVormonat(lauf, vormonat) })} />
          )}
        </div>
        {(halt || lauf.fortgeschrieben > 0) && <Rechnung detail={detail} />}
        <WegWeiter detail={detail} angehalten={halt !== null} />
      </header>

      <Auffaelligkeiten detail={detail} />
      <OenaceWechselAbsatz lauf={lauf} />
      <Abschnitte detail={detail} bericht={bericht} />
      <Weiter detail={detail} />
      </div>
      <aside className="hidden lg:block">
        <Sprungmarken liste={marken(detail, bericht)} seitlich />
      </aside>
    </div>
  );
}
