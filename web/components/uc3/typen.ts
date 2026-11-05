// Gemeinsame Typen der UC3-Seiten. Spaltennamen der Datenbank (snake_case) werden in den Lesern
// (`laeufe.ts` usw.) auf diese Formen abgebildet; Seiten kennen nur diese Typen.

/** Stand eines Ergebnisses: vorläufig, bis ein Mensch den Monat mit Namen veröffentlicht. */
export type Ergebnisstand = "vorlaeufig" | "endgueltig";

/** Ein Lauf aus `meta.lauf`. Große Zahlen (bigint) sind hier schon `number`. */
export interface Lauf {
  id: number;
  /**
   * Lauf, aus dem Prüftreffer und Regelwirkung stammen: bei einem veröffentlichten Monat der Lauf, der veröffentlicht
   * hat (wie `_veroeffentlichender_lauf` in qualitaetsbericht.py), sonst `id`. Revisionen kommen dagegen immer aus
   * `id`, dem jüngsten Lauf, wie § 5 des Generators (`_revision(conn, stand.lauf_id, …)`): rechnet ein späterer Lauf
   * einen veröffentlichten Monat nach, gehört sein Revisionsbedarf zu ihm.
   */
  quelleId: number;
  /** Berichtsmonat = Lieferung, „JJJJ-MM“. Ein Lauf rechnet genau eine Lieferung. */
  lieferung: string;
  /** „v1“ (Fachbeschreibung) oder „v2“ (nach Änderungsaufträgen). */
  regelsatz: string;
  /** Hash der aktiven Regeln, mit denen gerechnet wurde. */
  regelstand: string;
  /** fertig, unveraendert, abgebrochen, laeuft. */
  status: string;
  ergebnisStand: Ergebnisstand;
  gelesen: number;
  gezaehlt: number;
  nichtGezaehlt: number;
  ausgeschlossen: number;
  /** Verhältnisse, die aus dem Vormonat übernommen wurden (Teil-Lieferung, E07); zählen mit, stehen nicht in der Lieferung. */
  fortgeschrieben: number;
  ergebnisHash: string;
  gestartetAm: string;
  beendetAm: string | null;
  meldung: string | null;
  freigegebenVon: string | null;
  freigegebenAm: string | null;
}

/** Der maßgebliche Lauf eines Monats mit dem, was die Übersicht dazu braucht. */
export interface Monatslauf extends Lauf {
  /** Wie oft dieser Monat mit diesem Regelsatz schon gerechnet wurde. */
  laeufeGesamt: number;
  /** Mindestens eine Prüfregel hat den Monat angehalten. */
  angehalten: boolean;
  /** Namen der anhaltenden Prüfregeln, z. B. „P15_bestand_vs_vormonat“. */
  anhaltendeRegeln: string[];
  /** Prüfregeln mit mindestens einem Treffer. */
  auffaelligkeiten: number;
  /** Davon ohne Erklärung (Einstufung „nicht erklärbar“). */
  nichtErklaerbar: number;
}
