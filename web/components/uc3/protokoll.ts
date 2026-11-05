import { eintragStatus, type Eintrag } from "@kic/ui/shell";
import { lies, type Sql } from "./db";

/** Zeile aus meta.protokoll der UC3-Datenbank (Vertrag P). */
export interface ProtokollZeile {
  id: number | string;
  zeit: Date | string;
  uc: string | null;
  akteur: string;
  name: string | null;
  anweisung: string | null;
  wirkung: string | null;
  status: string;
  modell: string | null;
  provider: string | null;
  ref: string | null;
}

/** Bildet eine Zeile auf den JSON-Vertrag `Eintrag` ab; unbekannte Werte fallen auf „offen“ bzw. „agent“. */
export function eintragAus(z: ProtokollZeile): Eintrag {
  const status = (eintragStatus as readonly string[]).includes(z.status) ? (z.status as Eintrag["status"]) : "offen";
  const modell = z.modell ? (z.provider ? `${z.modell} (${z.provider})` : z.modell) : null;
  return {
    id: Number(z.id),
    zeit: (z.zeit instanceof Date ? z.zeit : new Date(z.zeit)).toISOString(),
    uc: "uc3",
    akteur: z.akteur === "mensch" ? "mensch" : "agent",
    name: z.name ?? "",
    anweisung: z.anweisung ?? "",
    wirkung: z.wirkung,
    status,
    modell,
    ref: z.ref,
  };
}

export async function ladeProtokoll(sql: Sql, grenze = 200): Promise<Eintrag[]> {
  const zeilen = await sql<ProtokollZeile[]>`
    SELECT id, zeit, uc, akteur, name, anweisung, wirkung, status, modell, provider, ref
    FROM meta.protokoll
    WHERE uc IS NULL OR uc = 'uc3'
    ORDER BY id DESC
    LIMIT ${grenze}`;
  return zeilen.map(eintragAus);
}

/** Quelle für `protokollAntwort`: ohne Datenbank eine leere Liste (die Schublade zeigt dann ihren Leerzustand). */
export async function protokollQuelle(): Promise<Eintrag[]> {
  const lesung = await lies((sql) => ladeProtokoll(sql));
  return lesung.ok ? lesung.daten : [];
}
