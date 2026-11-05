import { lies, type Lesung, type Sql } from "./db";

/**
 * Pensionsstatistik 2018 bis 2025 (#77) für den Abschnitt auf /uc3/klassifikationen. Nur lesend. Die Summen über die Träger
 * bildet die Abfrage aus `stat.stat_pensionen`; Tabelle 13 ist ein Teil der Alterspensionen und wird nicht zu Tabelle 12 addiert.
 * Vor dem Laden (`uv run uc3 pensionen laden`) fehlen die Zeilen, und der Abschnitt bleibt weg.
 */

export interface PensionsJahr {
  jahr: number;
  insgesamt: number;
  unselbstaendige: number;
  selbstaendige: number;
  vorzeitig: number;
}

export interface Pensionsdaten {
  jahre: PensionsJahr[];
  /** `true`, solange die Zahlen nicht mit Namen freigegeben sind. */
  vorlaeufig: boolean;
}

export const SQL_PENSIONEN = `SELECT extract(year FROM s.zeitraum_von)::int AS jahr,
  coalesce(sum(s.wert) FILTER (WHERE a.uebergeordnet = 'T12'), 0) AS insgesamt,
  coalesce(sum(s.wert) FILTER (WHERE a.uebergeordnet = 'T12' AND g.uebergeordnet = 'PV-UNS'), 0) AS unselbstaendige,
  coalesce(sum(s.wert) FILTER (WHERE a.uebergeordnet = 'T12' AND g.uebergeordnet = 'PV-SEL'), 0) AS selbstaendige,
  coalesce(sum(s.wert) FILTER (WHERE a.uebergeordnet = 'T13'), 0) AS vorzeitig,
  bool_or(s.status <> 'endgueltig') AS vorlaeufig
FROM stat.stat_pensionen s
JOIN stat.klass_pensionsart a ON a.code = s.pensionsart
JOIN stat.klass_versicherungstraeger k ON k.code = s.versicherungstraeger
JOIN stat.klass_versicherungstraeger g ON g.code = CASE WHEN k.ebene = 4 THEN k.uebergeordnet ELSE k.code END
GROUP BY 1
ORDER BY 1`;

type Zeile = {
  jahr: number;
  insgesamt: string | number;
  unselbstaendige: string | number;
  selbstaendige: string | number;
  vorzeitig: string | number;
  vorlaeufig: boolean;
};

/** Macht aus den Zeilen der Abfrage die Daten des Abschnitts; der Treiber liefert große Summen als Text. */
export function pensionsdaten(zeilen: readonly Zeile[]): Pensionsdaten {
  return {
    jahre: zeilen.map((z) => ({
      jahr: Number(z.jahr),
      insgesamt: Number(z.insgesamt),
      unselbstaendige: Number(z.unselbstaendige),
      selbstaendige: Number(z.selbstaendige),
      vorzeitig: Number(z.vorzeitig),
    })),
    vorlaeufig: zeilen.some((z) => z.vorlaeufig),
  };
}

export async function lesePensionen(optionen: { sql?: Sql | null } = {}): Promise<Lesung<Pensionsdaten>> {
  return lies(async (sql) => {
    const [da] = await sql<{ da: boolean }[]>`SELECT to_regclass('stat.stat_pensionen') IS NOT NULL AS da`;
    if (!da?.da) return pensionsdaten([]);
    return pensionsdaten(await sql.unsafe<Zeile[]>(SQL_PENSIONEN));
  }, optionen);
}
