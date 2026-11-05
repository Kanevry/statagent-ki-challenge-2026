/**
 * Layout der Szene: reine Funktionen ohne three.js, damit die Seite DOM-Beschriftungen an die
 * Geometrie heften kann und Tests ohne WebGL laufen.
 *
 * Koordinaten: CSS-Pixel relativ zum Canvas, Ursprung links oben, y wächst nach unten.
 *
 * `berechneLayout(breite, hoehe, variante, kartenMeta?, raender?)` liefert `SzeneLayout`. `raender`
 * (Standard: `standardRaender(…, true)`, passend zur Sticky-Bühne in hero.module.css) hält Texte,
 * Navigation und Leiste der Seite frei. Der Motor löst nach jedem Aufbau am Canvas das Event
 * `szenelayout` aus (bubbles, `detail` = das verwendete Layout); daran heftet die Seite exakt an.
 *
 *   breite, hoehe, variante
 *   partikel            Partikelzahl der Variante (PARTIKEL aus vertrag.ts, ohne Ringe)
 *   zeilenJePartikel    SUMME_ZEILEN / partikel (≈ 211,5 desktop, ≈ 725,2 mobil)
 *   grundlinie          { y, links, rechts }  haarfeine Nulllinie unter den Säulen
 *   saeulen[24]         je Lieferung { lieferung, index, x (Mitte), links, rechts, oben, unten,
 *                       partikel, zeilen }  Schritt 1/2, oben = Oberkante der Partikelsäule
 *   pruefLinie          { von, bis, oben, unten }  Weg der Prüflinie in Schritt 2 (x von → bis)
 *   befunde[5]          je Befund { id (wie BEFUNDE.id in fakten.ts), lieferung, art: "markiert" | "fehlt",
 *                       partikel (dargestellt, mit Minimum), partikelEcht (ohne Minimum, gerundet),
 *                       quelle: Rechteck (Ort in/auf der Säule während der Prüfung; bei „fehlt“ der
 *                       Hohlraum aus Ringen), gruppe: Rechteck (Endzustand Schritt 2), x, y (Mitte der
 *                       Gruppe), label { x, y, breite } (links oben der Beschriftung, Platz ≥ 200 px),
 *                       ringe (nur „fehlt“: Zahl der Ringe), ringPx (Durchmesser der Ringe),
 *                       quelleSpalten, gruppeSpalten (Raster der Ringe bzw. Punkte) }
 *                       Reihenfolge: geburtsmonat-13, bl-oenace-leer, volldubletten, fd-fehlen, teil-lieferung
 *   karte               Rechteck der Österreich-Karte (Schritt 3), dazu
 *                       unbekannt: Rechteck der gelben Gruppe „ohne Bundesland“ neben der Karte,
 *                       unbekanntLabel { x, y, breite }, legende { x, y, breite } (unter der Karte),
 *                       punkte (Partikel auf der Karte), unbekanntPunkte (Partikel der gelben Gruppe),
 *                       verhaeltnisseProPunkt (gerundet: Bestand 31.08.2024 / punkte; desktop 8, mobil 28)
 *   bundeslaender[9]    je Land { code, name, kurz, anzahl, x, y (Anker im Land), lx, ly (Ort der
 *                       Beschriftung), ausrichtung "mitte" | "links" | "rechts" (lx ist Mitte, linker
 *                       bzw. rechter Rand des Texts), fuehrung (feine Linie Anker → Beschriftung) }
 *   tabelle             { x0 (Beginn der Punkt-Balken), punktAbstand, punktReihen,
 *                       zeilen[9] (absteigend nach Anzahl) { code, name, kurz, anzahl, partikel,
 *                       y (Mitte), oben, unten, x0, x1 (Balkenende) },
 *                       unbekannt: Rechteck des gelben Balkens als zehnte Zeile }  Schritt 4.
 *                       Links von x0 ist Platz für Namen (desktop 156 px, mobil 40 px), rechts von
 *                       x1 für Zahlen (84 bzw. 64 px).
 *
 * Schritt 3 und 4 nutzen alle Partikel: jeder Kartenpunkt bekommt ein Partikel (Präfix der
 * Kartendatei), die gelbe Gruppe „ohne Bundesland“ hat dieselbe Auflösung.
 *
 * Rechteck = { x, y, breite, hoehe } (x/y = links oben).
 */
import { BUNDESLAENDER_2024_08, GOLDEN_SET, LIEFERUNGEN, SUMME_ZEILEN, SZENE_BEFUNDE } from "../../daten/fakten";
import { PARTIKEL, type KartenMeta, type SzeneVariante } from "../vertrag";

/**
 * Mindestzahl Partikel je Befund in Schritt 2. Echte Anteile wären 2 bis 10 Partikel und damit
 * unsichtbar; angehoben wird nur die Darstellung, die Seite zeigt die exakten Zahlen.
 */
export const MIN_BEFUND_PARTIKEL: Record<SzeneVariante, number> = { desktop: 30, mobil: 16 };

/** Durchmesser der hohlen Ringe in CSS-Pixeln (höchstens; in engen Rastern kleiner). */
export const RING_PX: Record<SzeneVariante, number> = { desktop: 4.2, mobil: 3.4 };

/** Stil der Säulen-Partikel je Variante (Motor und statisches Bild in SzeneCanvas). */
export const PUNKT_STIL: Record<SzeneVariante, { dprMax: number; groesse: number; alpha: number }> = {
  desktop: { dprMax: 2, groesse: 2.0, alpha: 0.62 },
  mobil: { dprMax: 1.5, groesse: 1.8, alpha: 0.74 },
};

/** Abstand der Ringe im Raster (Mitte zu Mitte). */
const RING_ABSTAND: Record<SzeneVariante, number> = { desktop: 5.4, mobil: 4.2 };

/** Seitenverhältnis der Karte, falls noch keine Meta geladen ist (Wert der echten Meta). */
export const KARTE_SEITENVERHAELTNIS_ERSATZ = 1.9446;

export type BefundId = "geburtsmonat-13" | "bl-oenace-leer" | "volldubletten" | "fd-fehlen" | "teil-lieferung";

export interface Rechteck {
  x: number;
  y: number;
  breite: number;
  hoehe: number;
}

export interface Ort {
  x: number;
  y: number;
  breite: number;
}

export interface SaeulenAnker {
  lieferung: string;
  index: number;
  x: number;
  links: number;
  rechts: number;
  oben: number;
  unten: number;
  partikel: number;
  zeilen: number;
}

export interface BefundAnker {
  id: BefundId;
  lieferung: string;
  art: "markiert" | "fehlt";
  /** Zeilen bzw. Verhältnisse laut fakten.ts */
  zeilen: number;
  partikel: number;
  partikelEcht: number;
  quelle: Rechteck;
  gruppe: Rechteck;
  x: number;
  y: number;
  label: Ort;
  ringe: number;
  ringPx: number;
  quelleSpalten: number;
  gruppeSpalten: number;
}

export interface LandAnker {
  code: number;
  name: string;
  kurz: string;
  anzahl: number;
  x: number;
  y: number;
  lx: number;
  ly: number;
  ausrichtung: "mitte" | "links" | "rechts";
  fuehrung: boolean;
}

export interface TabellenZeile {
  code: number;
  name: string;
  kurz: string;
  anzahl: number;
  partikel: number;
  y: number;
  oben: number;
  unten: number;
  x0: number;
  x1: number;
}

export interface SzeneLayout {
  breite: number;
  hoehe: number;
  variante: SzeneVariante;
  partikel: number;
  zeilenJePartikel: number;
  grundlinie: { y: number; links: number; rechts: number };
  saeulen: SaeulenAnker[];
  pruefLinie: { von: number; bis: number; oben: number; unten: number };
  befunde: BefundAnker[];
  karte: Rechteck & {
    unbekannt: Rechteck;
    unbekanntLabel: Ort;
    legende: Ort;
    punkte: number;
    unbekanntPunkte: number;
    verhaeltnisseProPunkt: number;
  };
  bundeslaender: LandAnker[];
  tabelle: {
    x0: number;
    punktAbstand: number;
    punktReihen: number;
    zeilen: TabellenZeile[];
    unbekannt: Rechteck;
  };
}

/** Punktabstand in Befund-Gruppen (CSS-Pixel) und Spalten je Gruppe. */
export const GRUPPE = {
  desktop: { abstand: 4.5, spalten: 12 },
  mobil: { abstand: 3.6, spalten: 10 },
} as const;

/** Desktop: Spalte der Befund-Gruppen zwischen Text und Säulen (Breite = Platz der Beschriftung). */
const SPALTE = { breite: 240, abstandSaeulen: 36, labelHoehe: 36, luecke: 22 } as const;
/** Mobil (und schmale Desktops): je Befund eine Zeile unter den Säulen. */
const LISTE = { blockBreite: 40, zeile: 18, luecke: 5, oben: 24 } as const;

const klemme = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/** Größte-Reste-Verteilung: ganzzahlige Anteile, deren Summe exakt `gesamt` ist. */
export function verteileGanzzahlig(gewichte: readonly number[], gesamt: number): number[] {
  const summe = gewichte.reduce((a, b) => a + b, 0);
  const roh = gewichte.map((g) => (g / summe) * gesamt);
  const basis = roh.map(Math.floor);
  let rest = gesamt - basis.reduce((a, b) => a + b, 0);
  const reihenfolge = roh.map((r, i) => ({ i, rest: r - Math.floor(r) })).sort((a, b) => b.rest - a.rest || a.i - b.i);
  for (let k = 0; rest > 0; k++, rest--) basis[reihenfolge[k % reihenfolge.length].i]++;
  return basis;
}

export interface BefundZaehlung {
  id: BefundId;
  lieferung: string;
  lieferungIndex: number;
  art: "markiert" | "fehlt";
  /** Zeilen laut fakten.ts */
  zeilen: number;
  /** dargestellte Partikel (markiert) bzw. Flächen-Äquivalent in Partikeln (fehlt), mit Minimum */
  partikel: number;
  partikelEcht: number;
}

export interface PartikelPlan {
  variante: SzeneVariante;
  gesamt: number;
  zeilenJePartikel: number;
  /** Partikel je Lieferung (Summe = gesamt) */
  saeulen: number[];
  befunde: BefundZaehlung[];
  /** Partikel der gelben Gruppe „ohne Bundesland“ in Schritt 3/4 (gleiche Auflösung wie die Karte) */
  unbekanntPunkte: number;
  /** Partikel auf der Karte in Schritt 3 (= gesamt − unbekanntPunkte, alle Säulen) */
  kartenPartikel: number;
  /** gerundet: Bestand am Stichtag je Kartenpunkt */
  verhaeltnisseProPunkt: number;
  /** erwartete Kartenpartikel je Bundesland-Code 1..9 (geschichtete Stichprobe) */
  jeLand: Map<number, number>;
}

const indexVon = (lieferung: string) => LIEFERUNGEN.findIndex((l) => l.lieferung === lieferung);
const UNBEKANNT_ANZAHL = BUNDESLAENDER_2024_08.find((l) => l.code === 0)?.anzahl ?? 0;

/** Wie viele Partikel wohin gehören. Unabhängig von der Bildschirmgröße. */
export function planePartikel(variante: SzeneVariante): PartikelPlan {
  const gesamt = PARTIKEL[variante];
  const zjp = SUMME_ZEILEN / gesamt;
  const saeulen = verteileGanzzahlig(
    LIEFERUNGEN.map((l) => l.zeilen),
    gesamt,
  );
  const min = MIN_BEFUND_PARTIKEL[variante];
  const b = SZENE_BEFUNDE;
  const roh: [BefundId, string, "markiert" | "fehlt", number][] = [
    ["geburtsmonat-13", b.geburtsmonat13.lieferung, "markiert", b.geburtsmonat13.saetze],
    ["bl-oenace-leer", b.blOenaceLeer.lieferung, "markiert", b.blOenaceLeer.saetze],
    ["volldubletten", b.dubletten2025_03.lieferung, "markiert", b.dubletten2025_03.zeilen],
    ["fd-fehlen", b.fdFehlen2025_03.lieferung, "fehlt", b.fdFehlen2025_03.verhaeltnisse],
    ["teil-lieferung", b.teilLieferung2025_10.lieferung, "fehlt", b.teilLieferung2025_10.fehlen],
  ];
  const befunde: BefundZaehlung[] = roh.map(([id, lieferung, art, zeilen]) => {
    const echt = Math.round(zeilen / zjp);
    return { id, lieferung, lieferungIndex: indexVon(lieferung), art, zeilen, partikel: Math.max(min, echt), partikelEcht: echt };
  });
  // Schritt 3/4: alle Partikel bilden den Bestand am Stichtag ab, die gelbe Gruppe mit derselben Auflösung
  const blMarkiert = befunde.find((x) => x.id === "bl-oenace-leer")!.partikel;
  const unbekanntPunkte = Math.max(blMarkiert, Math.round((UNBEKANNT_ANZAHL * gesamt) / GOLDEN_SET.bestand));
  const kartenPartikel = gesamt - unbekanntPunkte;
  const laender = BUNDESLAENDER_2024_08.filter((l) => l.code !== 0);
  const verteilt = verteileGanzzahlig(
    laender.map((l) => l.anzahl),
    kartenPartikel,
  );
  const jeLand = new Map<number, number>();
  laender.forEach((l, i) => jeLand.set(l.code, verteilt[i]));
  return {
    variante,
    gesamt,
    zeilenJePartikel: zjp,
    saeulen,
    befunde,
    unbekanntPunkte,
    kartenPartikel,
    verhaeltnisseProPunkt: Math.round(GOLDEN_SET.bestand / kartenPartikel),
    jeLand,
  };
}

/** Bundesländer ohne „unbekannt“, absteigend nach Anzahl (Reihenfolge der Tabelle). */
export const LAENDER_ABSTEIGEND = BUNDESLAENDER_2024_08.filter((l) => l.code !== 0)
  .slice()
  .sort((a, b) => b.anzahl - a.anzahl);

/** Raster-Abmessungen für `n` Punkte in einem Rechteck b × h, möglichst quadratische Zellen. */
export function raster(n: number, b: number, h: number): { nx: number; ny: number } {
  const nx = Math.max(1, Math.round(Math.sqrt((n * Math.max(b, 1e-3)) / Math.max(h, 1e-3))));
  return { nx, ny: Math.max(1, Math.ceil(n / nx)) };
}

/** Freizuhaltende Ränder des Canvas in CSS-Pixeln (Texte, Navigation, Fortschrittsleiste der Seite). */
export interface Raender {
  links: number;
  rechts: number;
  oben: number;
  unten: number;
}

/** Breite der Textspalte der Seite (gemessen: breitester Schritt-Text 534 px ab --l-rand). */
export const TEXT_BREITE_DESKTOP = 540;

/** Anteil der Bühnenhöhe, den das Textfeld mobil unten belegt. */
export const MOBIL_TEXT_ANTEIL = 0.4;

/**
 * Ränder passend zu web/landing/sektionen/hero.module.css.
 * `vollflaechig`: Canvas liegt über der ganzen Bühne (Sticky-Modus) und teilt sie mit den Texten.
 * Desktop: Textspalte links (--l-rand + TEXT_BREITE_DESKTOP, Inhalt höchstens 1440 px breit),
 * Navigation 64 px oben, Fortschrittsleiste unten.
 * Mobil: Navigation und Leiste oben, Textfeld unten (~40 %).
 * Nicht vollflächig (reduzierte Bewegung, Canvas in eigener Spalte): schmaler Innenrand.
 */
export function standardRaender(breite: number, hoehe: number, variante: SzeneVariante, vollflaechig = true): Raender {
  if (!vollflaechig) return { links: 16, rechts: 16, oben: 16, unten: 16 };
  if (variante === "mobil") return { links: 16, rechts: 16, oben: 124, unten: Math.round(hoehe * MOBIL_TEXT_ANTEIL) };
  const rand = klemme(breite * 0.08333, 20, 120);
  const inhalt = Math.max(0, (breite - 1440) / 2);
  return {
    links: Math.round(inhalt + rand + TEXT_BREITE_DESKTOP + 32),
    rechts: Math.round(inhalt + Math.min(rand, 72)),
    oben: 64 + 40,
    unten: 112,
  };
}

/** Ringe in einem Rechteck: Raster mit Abstand ≈ `abstand`, Durchmesser passend zur engsten Zelle. */
function ringRaster(r: Rechteck, abstand: number, maxPx: number) {
  const nx = Math.max(1, Math.round(r.breite / abstand));
  const ny = Math.max(1, Math.round(r.hoehe / abstand));
  const zelle = Math.min(r.breite / nx, r.hoehe / ny);
  return { nx, ny, n: nx * ny, px: Math.min(maxPx, Math.max(2.4, zelle - 1)) };
}

/**
 * Lage der Länder-Beschriftungen (normiert auf das Kartenrechteck). Ohne Eintrag: am Label-Punkt
 * der Kartendaten, zentriert. Wien, Burgenland und Vorarlberg liegen außerhalb der Fläche bzw. in
 * leeren Ecken des Rechtecks, mit feiner Führungslinie.
 */
const LAND_LAGE: Record<SzeneVariante, Record<number, [number, number, LandAnker["ausrichtung"]]>> = {
  desktop: {
    9: [1.025, 0.307, "links"],
    1: [1.025, 0.558, "links"],
    3: [0.79, 0.13, "mitte"],
    8: [0.0, 0.97, "links"],
  },
  mobil: {
    9: [1.0, -0.1, "rechts"],
    1: [1.0, 0.98, "rechts"],
    3: [0.75, 0.13, "mitte"],
    8: [0.0, 0.93, "links"],
  },
};

export function berechneLayout(
  breite: number,
  hoehe: number,
  variante: SzeneVariante,
  kartenMeta?: KartenMeta | null,
  raender?: Raender,
): SzeneLayout {
  const w = Math.max(breite, 120);
  const h = Math.max(hoehe, 120);
  const plan = planePartikel(variante);
  const mobil = variante === "mobil";
  const g = GRUPPE[variante];
  const r = raender ?? standardRaender(w, h, variante);
  const ringAbstand = RING_ABSTAND[variante];
  const ringMax = RING_PX[variante];

  const L = Math.min(r.links, w * 0.6);
  const R = Math.max(w - r.rechts, L + 120);
  const mt = Math.min(r.oben, h * 0.4);
  const unten = Math.max(h - r.unten, mt + 120);
  // Befund-Gruppen: als Spalte zwischen Text und Säulen, wenn rechts genug Platz bleibt, sonst als
  // Liste unter den Säulen (mobil immer).
  const spalte = !mobil && R - L >= SPALTE.breite + SPALTE.abstandSaeulen + 360;
  const n = plan.befunde.length;
  const listeHoehe = spalte ? 0 : LISTE.oben + n * LISTE.zeile + (n - 1) * LISTE.luecke;
  const grundY = Math.round(spalte ? unten - 22 : unten - listeHoehe - 8);
  const sx0 = spalte ? L + SPALTE.breite + SPALTE.abstandSaeulen : L;
  const sx1 = R;

  // Säulen (Höhe ab Null, proportional zu den Zeilen)
  const maxZeilen = Math.max(...LIEFERUNGEN.map((l) => l.zeilen));
  const maxH = grundY - mt;
  const jeZeile = maxH / maxZeilen;
  const slot = (sx1 - sx0) / LIEFERUNGEN.length;
  const sb = slot * (mobil ? 0.72 : 0.68);
  const saeulen: SaeulenAnker[] = LIEFERUNGEN.map((l, i) => {
    const x = sx0 + slot * (i + 0.5);
    return {
      lieferung: l.lieferung,
      index: i,
      x,
      links: x - sb / 2,
      rechts: x + sb / 2,
      oben: grundY - l.zeilen * jeZeile,
      unten: grundY,
      partikel: plan.saeulen[i],
      zeilen: l.zeilen,
    };
  });

  // Befunde: Ort in bzw. auf der Säule
  const quelleVon = (z: BefundZaehlung): Rechteck => {
    const s = saeulen[z.lieferungIndex];
    const hz = s.unten - s.oben;
    if (z.id === "teil-lieferung") {
      // Hohlraum in voller Höhe des Fehlenden (maßstabsgetreu), genau über der kurzen Säule
      const fh = z.zeilen * jeZeile;
      return { x: s.links, y: s.oben - fh, breite: sb, hoehe: fh };
    }
    if (z.id === "fd-fehlen") {
      // schmales Ring-Band oben auf der Säule (echt wären ~2 px)
      return { x: s.links, y: s.oben - ringAbstand - 1, breite: sb, hoehe: ringAbstand };
    }
    if (z.id === "volldubletten") {
      // gefülltes Band: die obersten Partikel der Säule
      const anteil = z.partikel / s.partikel;
      return { x: s.links, y: s.oben, breite: sb, hoehe: hz * anteil };
    }
    // verstreut in der ganzen Säule
    return { x: s.links, y: s.oben, breite: sb, hoehe: hz };
  };

  const befunde: BefundAnker[] = [];
  const blockBreite = spalte ? g.spalten * g.abstand : LISTE.blockBreite;
  const spaltenMarkiert = Math.max(4, Math.floor(blockBreite / g.abstand));
  const gruppenMasse = plan.befunde.map((z) => {
    const quelle = quelleVon(z);
    if (z.art === "fehlt") {
      const rr = ringRaster(quelle, ringAbstand, ringMax);
      // Gruppe: dieselben Ringe, kompakt (desktop bis Spaltenbreite, mobil in der Blockbreite)
      const maxSpalten = Math.max(1, Math.floor((spalte ? SPALTE.breite : 9999) / ringAbstand));
      const gSpalten = spalte ? Math.min(rr.n, maxSpalten) : Math.min(rr.n, Math.max(1, Math.floor(blockBreite / ringAbstand)));
      const gBreite = gSpalten * ringAbstand;
      const gHoehe = Math.ceil(rr.n / gSpalten) * ringAbstand;
      return { z, quelle, ringe: rr.n, ringPx: rr.px, quelleSpalten: rr.nx, gruppeSpalten: gSpalten, gBreite, gHoehe };
    }
    const gHoehe = Math.ceil(z.partikel / spaltenMarkiert) * g.abstand;
    return {
      z,
      quelle,
      ringe: 0,
      ringPx: 0,
      quelleSpalten: 0,
      gruppeSpalten: spaltenMarkiert,
      gBreite: spaltenMarkiert * g.abstand,
      gHoehe,
    };
  });

  if (spalte) {
    const summe = gruppenMasse.reduce((a, m) => a + m.gHoehe + 6 + SPALTE.labelHoehe, 0) + SPALTE.luecke * (n - 1);
    let y = mt + Math.max(0, (grundY - mt - summe) / 2);
    for (const m of gruppenMasse) {
      const gruppe = { x: L, y, breite: m.gBreite, hoehe: m.gHoehe };
      const label = { x: L, y: y + m.gHoehe + 6, breite: SPALTE.breite };
      befunde.push(anker(m, gruppe, label));
      y += m.gHoehe + 6 + SPALTE.labelHoehe + SPALTE.luecke;
    }
  } else {
    let y = grundY + LISTE.oben;
    for (const m of gruppenMasse) {
      const hoeheZ = Math.min(m.gHoehe, LISTE.zeile);
      const gruppe = { x: L, y: y + (LISTE.zeile - hoeheZ) / 2, breite: m.gBreite, hoehe: m.gHoehe };
      const label = { x: L + LISTE.blockBreite + 8, y, breite: R - L - LISTE.blockBreite - 8 };
      befunde.push(anker(m, gruppe, label));
      y += LISTE.zeile + LISTE.luecke;
    }
  }

  // Karte: ganze Fläche über der Grundlinie, desktop mit Platz rechts für Wien und Burgenland
  const legendeH = mobil ? 22 : 30;
  const bereich: Rechteck = {
    x: L,
    y: mt + (mobil ? 14 : 0),
    breite: R - L - (mobil ? 0 : 112),
    hoehe: grundY - mt - legendeH - (mobil ? 14 : 0),
  };
  const sv = kartenMeta?.seitenverhaeltnis ?? KARTE_SEITENVERHAELTNIS_ERSATZ;
  const kb = Math.min(bereich.breite, bereich.hoehe * sv);
  const kh = kb / sv;
  const kx = bereich.x + (bereich.breite - kb) / 2;
  const ky = bereich.y + (bereich.hoehe - kh) / 2;
  // Die linke obere Ecke des Kartenrechtecks liegt außerhalb Österreichs (Bayern): dort sitzt
  // die gelbe Gruppe „ohne Bundesland“, mit Beschriftung darunter.
  const ugSpalten = mobil ? 14 : 22;
  const unbekanntKarte: Rechteck = {
    x: kx + 2,
    y: ky + 2,
    breite: ugSpalten * g.abstand,
    hoehe: Math.ceil(plan.unbekanntPunkte / ugSpalten) * g.abstand,
  };
  const unbekanntLabel: Ort = { x: kx + 2, y: unbekanntKarte.y + unbekanntKarte.hoehe + 6, breite: kb * 0.42 };
  const legende: Ort = { x: kx, y: ky + kh + (mobil ? 8 : 14), breite: kb };

  const lage = LAND_LAGE[variante];
  const bundeslaender: LandAnker[] = BUNDESLAENDER_2024_08.filter((l) => l.code !== 0).map((l) => {
    const m = kartenMeta?.laender.find((x) => x.code === l.code);
    const [ax, ay] = m?.label ?? ERSATZ_LABEL[l.code] ?? [0.5, 0.5];
    const eigen = lage[l.code];
    const [nx, ny, ausrichtung] = eigen ?? [ax, ay, "mitte" as const];
    return {
      code: l.code,
      name: l.name,
      kurz: l.kurz,
      anzahl: l.anzahl,
      x: kx + ax * kb,
      y: ky + ay * kh,
      lx: kx + nx * kb,
      ly: ky + ny * kh,
      ausrichtung,
      fuehrung: Boolean(eigen) && l.code !== 3,
    };
  });

  // Tabelle: 9 Zeilen (absteigend) + gelber Balken „unbekannt“ als zehnte Zeile, alle Partikel.
  const tabBereich: Rechteck = { x: L, y: mt, breite: R - L, hoehe: grundY - mt };
  const zeilenH = Math.min(tabBereich.hoehe / 10.4, mobil ? 30 : 50);
  const labelBreite = mobil ? 40 : 156;
  const zahlBreite = mobil ? 64 : 84;
  const tx0 = tabBereich.x + labelBreite;
  const tabRechts = tabBereich.x + tabBereich.breite;
  const tabOben = tabBereich.y + (tabBereich.hoehe - 10 * zeilenH) / 2;
  const zeileMitte = (i: number) => tabOben + zeilenH * (i + 0.5);
  const maxPartikel = Math.max(...plan.jeLand.values());
  const balkenMax = Math.max(40, tabRechts - tx0 - zahlBreite);
  const dicke = zeilenH * 0.76;
  // Raster: gleicher Punktabstand in x und y, so dicht, dass der längste Balken in balkenMax passt
  const a0 = Math.sqrt((balkenMax * dicke) / maxPartikel);
  const punktReihen = Math.max(1, Math.floor(dicke / a0));
  const punktAbstand = Math.min(balkenMax / Math.ceil(maxPartikel / punktReihen), dicke / punktReihen);
  const halb = (punktReihen * punktAbstand) / 2;
  const zeilen: TabellenZeile[] = LAENDER_ABSTEIGEND.map((l, i) => {
    const partikel = plan.jeLand.get(l.code) ?? 0;
    const yM = zeileMitte(i);
    return {
      code: l.code,
      name: l.name,
      kurz: l.kurz,
      anzahl: l.anzahl,
      partikel,
      y: yM,
      oben: yM - halb,
      unten: yM + halb,
      x0: tx0,
      x1: tx0 + Math.ceil(partikel / punktReihen) * punktAbstand,
    };
  });
  const unbekanntTabelle: Rechteck = {
    x: tx0,
    y: zeileMitte(9) - halb,
    breite: Math.ceil(plan.unbekanntPunkte / punktReihen) * punktAbstand,
    hoehe: 2 * halb,
  };

  const hoechste = Math.min(...saeulen.map((s) => s.oben), ...befunde.map((b) => b.quelle.y));
  return {
    breite: w,
    hoehe: h,
    variante,
    partikel: plan.gesamt,
    zeilenJePartikel: plan.zeilenJePartikel,
    grundlinie: { y: grundY, links: sx0 - 6, rechts: sx1 + 6 },
    saeulen,
    pruefLinie: { von: sx0 - 10, bis: sx1 + 10, oben: hoechste - 14, unten: grundY + 8 },
    befunde,
    karte: {
      x: kx,
      y: ky,
      breite: kb,
      hoehe: kh,
      unbekannt: unbekanntKarte,
      unbekanntLabel,
      legende,
      punkte: plan.kartenPartikel,
      unbekanntPunkte: plan.unbekanntPunkte,
      verhaeltnisseProPunkt: plan.verhaeltnisseProPunkt,
    },
    bundeslaender,
    tabelle: { x0: tx0, punktAbstand, punktReihen, zeilen, unbekannt: unbekanntTabelle },
  };
}

function anker(
  m: {
    z: BefundZaehlung;
    quelle: Rechteck;
    ringe: number;
    ringPx: number;
    quelleSpalten: number;
    gruppeSpalten: number;
  },
  gruppe: Rechteck,
  label: Ort,
): BefundAnker {
  return {
    id: m.z.id,
    lieferung: m.z.lieferung,
    art: m.z.art,
    zeilen: m.z.zeilen,
    partikel: m.z.partikel,
    partikelEcht: m.z.partikelEcht,
    quelle: m.quelle,
    gruppe,
    x: gruppe.x + gruppe.breite / 2,
    y: gruppe.y + gruppe.hoehe / 2,
    label,
    ringe: m.ringe,
    ringPx: m.ringPx,
    quelleSpalten: m.quelleSpalten,
    gruppeSpalten: m.gruppeSpalten,
  };
}

/** Grobe Label-Lagen (normiert) für den Ersatz ohne Kartendaten; echte kommen aus meta.laender. */
export const ERSATZ_LABEL: Record<number, [number, number]> = {
  1: [0.9164, 0.5583],
  2: [0.575, 0.8491],
  3: [0.8171, 0.2834],
  4: [0.5812, 0.3339],
  5: [0.4657, 0.6169],
  6: [0.7183, 0.662],
  7: [0.2332, 0.6696],
  8: [0.0479, 0.673],
  9: [0.8973, 0.3069],
};
