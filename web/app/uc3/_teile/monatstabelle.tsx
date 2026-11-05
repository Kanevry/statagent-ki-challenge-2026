import Link from "next/link";
import { Status } from "@kic/ui/basis";
import { formatDifferenz, formatZahl, HerkunftChip } from "@kic/ui/bausteine";
import { monatszeileBeleg, type Beleg } from "@/components/uc3/beleg";
import { abrechnung } from "@/components/uc3/laeufe";
import { monatName } from "@/components/uc3/monat";
import { monatsStand, vormonatIn } from "@/components/uc3/monatsstand";
import { laufPfad } from "@/components/uc3/navigation";
import type { Monatslauf } from "@/components/uc3/typen";

/** Stand eines Monats als Symbol und Wort. */
export function MonatsStatus({ monat }: { monat: Monatslauf }) {
  const stand = monatsStand({ ...monat, gehtAuf: abrechnung(monat).gehtAuf });
  return <Status art={stand.art}>{stand.wort}</Status>;
}

/** Haben alle Monate denselben Regelstand? Dann steht er einmal über der Tabelle statt in jeder Zeile. */
export function gemeinsamerRegelstand(monate: readonly Monatslauf[]): string | null {
  const erster = monate[0]?.regelstand;
  return erster && monate.every((m) => m.regelstand === erster) ? erster : null;
}

/**
 * Beleg einer Zeile; der Regelstand steht schon über der Tabelle. Den Stand behält der Chip, wenn der Monat
 * angehalten ist oder Fortgeschriebene enthält: dann bleibt er vorläufig, auch wenn die Spalte „angehalten“ zeigt.
 */
function zeilenBeleg(monat: Monatslauf, regelstandOben: boolean): Beleg {
  const standZeigen = monat.angehalten || monat.fortgeschrieben > 0;
  return { ...monatszeileBeleg(monat), ...(standZeigen ? {} : { stand: null }), ...(regelstandOben ? { regelstand: null } : {}) };
}

function Vormonat({ monat, monate }: { monat: Monatslauf; monate: readonly Monatslauf[] }) {
  const v = vormonatIn(monat, monate);
  const vormonat = typeof v === "string" ? undefined : monate.find((m) => m.lieferung === v.lieferung);
  return vormonat ? (
    <>{formatDifferenz(monat.gezaehlt - vormonat.gezaehlt)}</>
  ) : (
    <span className="font-sans text-12 text-slate">{typeof v === "string" ? v : "Vormonat fehlt"}</span>
  );
}

function Fortgeschrieben({ monat }: { monat: Monatslauf }) {
  if (monat.fortgeschrieben <= 0) return null;
  return (
    <span className="block font-sans text-12 text-slate">
      {`davon ${formatZahl(monat.fortgeschrieben)} aus dem Vormonat übernommen`}
    </span>
  );
}

const kopf = "border-b border-ink py-2 pr-4 text-left align-bottom font-sans text-12 font-semibold text-slate";
const zelle = "py-2 pr-4 align-top font-sans text-14 text-ink";
const zahlZelle = `${zelle} text-right font-mono tabular-nums`;
const monatsLink = "text-ink underline underline-offset-4 hover:text-gruen";

/**
 * Alle Monate mit ihrem maßgeblichen Lauf. Jede Zeile trägt einen Beleg, dessen Abfrage alle Zahlen der Zeile
 * liefert; die Veränderung zum Vormonat ist die Differenz zweier belegter Zeilen. Ab 768 px eine Tabelle,
 * darunter eine Liste mit denselben Angaben.
 */
export function Monatstabelle({ monate, regelsatz = "v1" }: { monate: readonly Monatslauf[]; regelsatz?: string }) {
  const regelstandOben = gemeinsamerRegelstand(monate) !== null;
  return (
    <>
      <table className="hidden w-full border-collapse md:table">
        <caption className="sr-only">
          Beschäftigungsverhältnisse am Stichtag je Monat, mit Abrechnung der gelesenen Sätze und Beleg
        </caption>
        <thead>
          <tr>
            <th scope="col" className={kopf}>
              Monat
            </th>
            <th scope="col" className={`${kopf} text-right`}>
              Beschäftigungs&shy;verhältnisse am Stichtag
            </th>
            <th scope="col" className={`${kopf} text-right`}>
              zum Vormonat
            </th>
            <th scope="col" className={`${kopf} text-right`}>
              gelesen
            </th>
            <th scope="col" className={`${kopf} text-right`}>
              nicht gezählt
            </th>
            <th scope="col" className={`${kopf} text-right`}>
              ausgeschlossen
            </th>
            <th scope="col" className={kopf}>
              Stand
            </th>
            <th scope="col" className={`${kopf} pr-0`}>
              Beleg
            </th>
          </tr>
        </thead>
        <tbody>
          {monate.map((monat) => (
            <tr key={monat.lieferung} className="border-b border-line" data-lieferung={monat.lieferung}>
              <th scope="row" className={`${zelle} text-left font-medium`}>
                <Link href={laufPfad(monat.lieferung, regelsatz)} className={monatsLink}>
                  {monatName(monat.lieferung)}
                </Link>
              </th>
              <td className={zahlZelle}>
                {formatZahl(monat.gezaehlt)}
                <Fortgeschrieben monat={monat} />
              </td>
              <td className={zahlZelle}>
                <Vormonat monat={monat} monate={monate} />
              </td>
              <td className={zahlZelle}>{formatZahl(monat.gelesen)}</td>
              <td className={zahlZelle}>{formatZahl(monat.nichtGezaehlt)}</td>
              <td className={zahlZelle}>{formatZahl(monat.ausgeschlossen)}</td>
              <td className={zelle}>
                <MonatsStatus monat={monat} />
              </td>
              <td className={`${zelle} pr-0`}>
                <HerkunftChip {...zeilenBeleg(monat, regelstandOben)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <ul className="flex flex-col md:hidden" aria-label="Monate">
        {monate.map((monat) => (
          <li key={monat.lieferung} className="flex flex-col gap-2 border-b border-line py-4" data-lieferung={monat.lieferung}>
            <div className="flex items-baseline justify-between gap-4">
              <Link href={laufPfad(monat.lieferung, regelsatz)} className={`font-sans text-16 font-semibold ${monatsLink}`}>
                {monatName(monat.lieferung)}
              </Link>
              <MonatsStatus monat={monat} />
            </div>
            <p className="font-sans text-14 text-ink">
              <span className="font-mono tabular-nums text-20">{formatZahl(monat.gezaehlt)}</span>
              {" Verhältnisse am Stichtag, zum Vormonat "}
              <span className="font-mono tabular-nums">
                <Vormonat monat={monat} monate={monate} />
              </span>
              <Fortgeschrieben monat={monat} />
            </p>
            <p className="font-sans text-12 text-slate">
              {`gelesen ${formatZahl(monat.gelesen)} · nicht gezählt ${formatZahl(monat.nichtGezaehlt)} · ausgeschlossen ${formatZahl(monat.ausgeschlossen)}`}
            </p>
            <HerkunftChip {...zeilenBeleg(monat, regelstandOben)} />
          </li>
        ))}
      </ul>
    </>
  );
}
