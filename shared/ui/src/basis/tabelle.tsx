import type { ReactNode } from "react";
import { klassen } from "./klassen";

export type Spalte = {
  schluessel: string;
  titel: string;
  /** Zahlenspalte: rechtsbündig, Mono, Ziffern gleicher Breite. */
  zahl?: boolean;
};

export type TabelleProps = {
  /** Beschreibt die Tabelle für Screenreader; sichtbar nur mit `beschriftungZeigen`. */
  beschriftung: string;
  beschriftungZeigen?: boolean;
  spalten: readonly Spalte[];
  zeilen: ReadonlyArray<Readonly<Record<string, ReactNode>>>;
  /** Stabiler Schlüssel je Zeile; ohne Angabe der Index. */
  zeilenSchluessel?: (zeile: Readonly<Record<string, ReactNode>>, index: number) => string;
  className?: string;
};

/** Tabelle mit Trennlinien zwischen den Zeilen, ohne Zebra und ohne Karten. */
export function Tabelle({
  beschriftung,
  beschriftungZeigen = false,
  spalten,
  zeilen,
  zeilenSchluessel,
  className,
}: TabelleProps) {
  return (
    <table className={klassen("w-full border-collapse font-sans", className)}>
      <caption
        className={beschriftungZeigen ? "pb-2 text-left text-14 text-slate" : "sr-only"}
      >
        {beschriftung}
      </caption>
      <thead>
        <tr>
          {spalten.map((spalte) => (
            <th
              key={spalte.schluessel}
              scope="col"
              className={klassen(
                "border-b border-ink py-2 pr-4 text-12 font-semibold text-slate last:pr-0",
                spalte.zahl ? "text-right" : "text-left",
              )}
            >
              {spalte.titel}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {zeilen.map((zeile, index) => (
          <tr key={zeilenSchluessel ? zeilenSchluessel(zeile, index) : index} className="border-b border-line">
            {spalten.map((spalte) => (
              <td
                key={spalte.schluessel}
                className={klassen(
                  "py-2 pr-4 align-top text-14 text-ink last:pr-0",
                  spalte.zahl && "text-right font-mono tabular-nums",
                )}
              >
                {zeile[spalte.schluessel]}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
