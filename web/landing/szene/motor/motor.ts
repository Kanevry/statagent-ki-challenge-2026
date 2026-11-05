/**
 * three.js-Motor der Landing-Szene. Wird von SzeneCanvas erst nach dem ersten Bild dynamisch
 * geladen. Pro Bild schreibt die CPU nur Uniforms; alle Partikel-Bewegung rechnet der Vertex-Shader.
 */
import {
  BufferAttribute,
  BufferGeometry,
  Color,
  DoubleSide,
  GLSL3,
  LineBasicMaterial,
  LineSegments,
  Mesh,
  MeshBasicMaterial,
  NormalBlending,
  OrthographicCamera,
  PlaneGeometry,
  Points,
  RawShaderMaterial,
  Scene,
  Vector2,
  WebGLRenderer,
} from "three";
import { SCHRITTE, type FortschrittSpeicher, type KartenDaten, type SzeneVariante } from "../vertrag";
import { ersatzKarte } from "./karteErsatz";
import { berechneLayout, planePartikel, PUNKT_STIL, standardRaender, type SzeneLayout } from "./layout";
import { bauePartikelStart, bauePartikelZiele, type PartikelStart } from "./partikel";
import { FRAGMENT, VERTEX } from "./shader";
import { linienZustand, RUHE_P } from "./zeitplan";

export interface SzeneOptionen {
  canvas: HTMLCanvasElement;
  fortschritt: FortschrittSpeicher;
  variante: SzeneVariante;
  reduziert: boolean;
  /**
   * Lädt die echten Kartendaten (mindestens planePartikel(variante).kartenPartikel Punkte). Schritt 1
   * und 2 stehen sofort; Karte und Tabelle entstehen, wenn die Daten da sind (bei Fehler mit der
   * Ersatz-Karte), in kleinen Häppchen im Leerlauf.
   */
  ladeKarte?: () => Promise<KartenDaten>;
  /** Schon erzeugter WebGL2-Kontext des Canvas (spart einen zweiten Kontext für die Prüfung). */
  kontext?: WebGL2RenderingContext;
  /** Ohne Ladeanimation starten (mobil: vorher stand das statische Bild der Säulen). */
  ohneLaden?: boolean;
  /** Wird nach dem ersten gezeichneten Bild mit Partikeln einmal aufgerufen. */
  beiErstemBild?: () => void;
}

export interface SzeneHandle {
  zerstoeren(): void;
}

/**
 * Name des DOM-Events, das der Motor nach jedem Neuaufbau am Canvas auslöst (bubbles).
 * `event.detail` ist das verwendete SzeneLayout, damit die Seite Beschriftungen exakt anheftet.
 */
export const LAYOUT_EVENT = "szenelayout";

/** Reduzierte Bewegung: immer der ruhende Zustand des Schritts, in dem p liegt. */
export function ruhendesP(p: number): number {
  const s = SCHRITTE.find((x) => p < x.bis) ?? SCHRITTE[SCHRITTE.length - 1];
  return RUHE_P[s.id];
}

/** Dauer der Ladeanimation */
export const LADEN_MS = 1200;
/** Glättung des Fortschritts (kritisch gedämpft) */
export const GLAETTUNG_S = 0.12;
/** Amplitude des Leerlauf-Atmens in CSS-Pixeln */
export const ATMEN_PX = 0.5;
/**
 * Karte und Tabelle rechnet der Motor in Häppchen im Leerlauf. Spätestens ab diesem Fortschritt
 * rechnet er den Rest sofort, damit Schritt 3 (ab SCHRITTE[2].von) fertige Ziele hat.
 */
export const ZIELE_SPAETESTENS_P = 0.15;
/** Rechenzeit je Häppchen in ms (Long Tasks bleiben weit unter 50 ms) */
const HAEPPCHEN_MS = 8;

const FARBE = {
  papier: new Color("#F4F7F5"),
  violett: new Color("#5B3DF5"),
  gelb: new Color("#F5D54F"),
};

const STIL = PUNKT_STIL;

/** Kritisch gedämpfte Feder (SmoothDamp), stabil bei schwankender Bildrate. */
function daempfe(aktuell: number, ziel: number, v: { v: number }, zeit: number, dt: number): number {
  const omega = 2 / zeit;
  const x = omega * dt;
  const exp = 1 / (1 + x + 0.48 * x * x + 0.235 * x * x * x);
  const diff = aktuell - ziel;
  const temp = (v.v + omega * diff) * dt;
  v.v = (v.v - omega * temp) * exp;
  let neu = ziel + (diff + temp) * exp;
  if (ziel - aktuell > 0 === neu > ziel) {
    neu = ziel;
    v.v = 0;
  }
  return neu;
}

function linienMaterial(farbe = FARBE.papier): LineBasicMaterial {
  return new LineBasicMaterial({
    color: farbe,
    transparent: true,
    opacity: 0,
    depthTest: false,
    depthWrite: false,
  });
}

function setzeLinien(obj: LineSegments, punkte: number[]) {
  const alt = obj.geometry;
  const g = new BufferGeometry();
  g.setAttribute("position", new BufferAttribute(new Float32Array(punkte), 3));
  obj.geometry = g;
  alt.dispose();
}

function achsenPunkte(l: SzeneLayout): number[] {
  const y = Math.round(l.grundlinie.y) + 0.5;
  const p = [l.grundlinie.links, y, 0, l.grundlinie.rechts, y, 0];
  for (const s of l.saeulen) {
    const jahr = s.lieferung.endsWith("-01") || s.index === 0;
    const x = Math.round(s.x) + 0.5;
    p.push(x, y, 0, x, y + (jahr ? 9 : 4), 0);
  }
  return p;
}

function grenzenPunkte(l: SzeneLayout, karte: KartenDaten): number[] {
  const k = l.karte;
  const p: number[] = [];
  for (const linie of karte.meta.grenzen) {
    for (let i = 0; i + 3 < linie.length; i += 2) {
      p.push(
        k.x + linie[i] * k.breite,
        k.y + linie[i + 1] * k.hoehe,
        0,
        k.x + linie[i + 2] * k.breite,
        k.y + linie[i + 3] * k.hoehe,
        0,
      );
    }
  }
  return p;
}

/** Umriss eines Hohlraums (fehlende Zeilen) als Rechteck, 1 px außerhalb der Ringe. */
function umrissPunkte(l: SzeneLayout, id: "teil-lieferung" | "fd-fehlen"): number[] {
  const b = l.befunde.find((x) => x.id === id);
  if (!b) return [];
  const q = b.quelle;
  const x0 = Math.round(q.x - 1.5) + 0.5;
  const x1 = Math.round(q.x + q.breite + 1.5) - 0.5;
  const y0 = Math.round(q.y - 1.5) + 0.5;
  const y1 = Math.round(q.y + q.hoehe + 1);
  return [x0, y0, 0, x1, y0, 0, x1, y0, 0, x1, y1, 0, x0, y0, 0, x0, y1, 0];
}

function tabellenAchsePunkte(l: SzeneLayout): number[] {
  const z = l.tabelle.zeilen;
  if (z.length === 0) return [];
  const x = Math.round(l.tabelle.x0 - l.tabelle.punktAbstand * 0.6) + 0.5;
  return [x, z[0].oben - 6, 0, x, z[z.length - 1].unten + 6, 0];
}

export function starteSzene(o: SzeneOptionen): SzeneHandle | null {
  const { canvas, fortschritt, variante, reduziert } = o;
  const ohneLaden = reduziert || Boolean(o.ohneLaden);
  let renderer: WebGLRenderer;
  try {
    renderer = new WebGLRenderer({
      canvas,
      context: o.kontext,
      alpha: true,
      antialias: true,
      premultipliedAlpha: true,
      powerPreference: "high-performance",
    });
  } catch {
    return null;
  }
  renderer.setClearColor(0x000000, 0);
  // Reihenfolge = Szenengraph (Linien, Punkte, Prüflinie); keine Tiefensortierung nötig, und die
  // 2-komponentige Position würde computeBoundingSphere mit NaN füttern.
  renderer.sortObjects = false;
  const stil = STIL[variante];

  const szene = new Scene();
  const kamera = new OrthographicCamera(0, 1, 0, 1, -10, 10);

  const uniforms = {
    uAufloesung: { value: new Vector2(1, 1) },
    uPR: { value: 1 },
    uFortschritt: { value: reduziert ? ruhendesP(fortschritt.wert()) : fortschritt.wert() },
    uLaden: { value: ohneLaden ? 1 : 0 },
    uZeit: { value: 0 },
    uAtmen: { value: reduziert ? 0 : ATMEN_PX },
    uScan: { value: -1e4 },
    uGroesse: { value: stil.groesse },
    uAlpha: { value: stil.alpha },
    uSaeulen: { value: new Vector2(0, 1) },
    uTabPunkt: { value: 1.5 },
  };
  const material = new RawShaderMaterial({
    glslVersion: GLSL3,
    vertexShader: VERTEX,
    fragmentShader: FRAGMENT,
    uniforms,
    transparent: true,
    depthTest: false,
    depthWrite: false,
    blending: NormalBlending,
    premultipliedAlpha: true,
  });
  const punkte = new Points(new BufferGeometry(), material);
  punkte.frustumCulled = false;
  punkte.renderOrder = 2;

  const achsenMat = linienMaterial();
  const grenzenMat = linienMaterial();
  const tabAchseMat = linienMaterial();
  const achsen = new LineSegments(new BufferGeometry(), achsenMat);
  const grenzen = new LineSegments(new BufferGeometry(), grenzenMat);
  const tabAchse = new LineSegments(new BufferGeometry(), tabAchseMat);
  // Umrisse der Hohlräume 2025-10 (Teil-Lieferung) und 2025-03 (freie Dienstverträge), gelb
  const hohlMat = [linienMaterial(FARBE.gelb), linienMaterial(FARBE.gelb)];
  const hohl = hohlMat.map((m) => new LineSegments(new BufferGeometry(), m));
  const hohlIds = ["teil-lieferung", "fd-fehlen"] as const;
  const linien = [achsen, grenzen, tabAchse, ...hohl];
  for (const l of linien) {
    l.frustumCulled = false;
    l.renderOrder = 1;
  }
  // DoubleSide: die Kamera spiegelt y (CSS-Pixel), dadurch kehrt sich die Dreiecks-Orientierung um
  const scanMat = new MeshBasicMaterial({
    color: FARBE.violett,
    side: DoubleSide,
    transparent: true,
    opacity: 0,
    depthTest: false,
    depthWrite: false,
  });
  const scanGeo = new PlaneGeometry(1, 1);
  const scan = new Mesh(scanGeo, scanMat);
  scan.frustumCulled = false;
  scan.renderOrder = 3;
  szene.add(...linien, punkte, scan);

  // Schritt 1 und 2 entstehen sofort; Karte und Tabelle (Ziele) erst mit den Kartendaten, in
  // Häppchen im Leerlauf. Ohne Lader die Ersatz-Karte.
  const kartenPunkte = planePartikel(variante).kartenPartikel;
  let karte: KartenDaten | null = o.ladeKarte ? null : ersatzKarte(kartenPunkte);
  let erstesBild = false;
  let layout: SzeneLayout | null = null;
  let breite = 0;
  let hoehe = 0;
  let zerstoert = false;
  let neuZeichnen = true;
  /** Shader fertig übersetzt (compileAsync); vorher kein Bild, damit nichts blockiert */
  let bereit = false;
  let start: PartikelStart | null = null;
  let zielAttribute: BufferAttribute[] = [];
  let ziele: Generator<void, void, void> | null = null;
  let zieleFertig = false;
  const mitIdle = typeof window.requestIdleCallback === "function";
  let auftrag = 0;

  function auftragAbbrechen() {
    if (!auftrag) return;
    if (mitIdle) window.cancelIdleCallback(auftrag);
    else window.clearTimeout(auftrag);
    auftrag = 0;
  }

  function zieleStarten() {
    auftragAbbrechen();
    zieleFertig = false;
    ziele = start && layout && karte ? bauePartikelZiele(start, layout, karte) : null;
    if (ziele) zielePlanen();
  }

  function zielePlanen() {
    if (auftrag || !ziele || zerstoert) return;
    auftrag = mitIdle
      ? window.requestIdleCallback(haeppchen, { timeout: 120 })
      : window.setTimeout(() => haeppchen(), 0);
  }

  function haeppchen(frist?: IdleDeadline) {
    auftrag = 0;
    if (zerstoert || !ziele) return;
    const budget = frist && !frist.didTimeout ? Math.max(4, Math.min(HAEPPCHEN_MS, frist.timeRemaining())) : HAEPPCHEN_MS;
    if (!zieleRechnen(budget)) zielePlanen();
  }

  /** Rechnet Ziele bis das Budget (ms) verbraucht ist; true, wenn alle Ziele stehen. */
  function zieleRechnen(budget: number): boolean {
    if (!ziele) return zieleFertig;
    const bis = performance.now() + budget;
    do {
      if (ziele.next().done) {
        ziele = null;
        zieleFertig = true;
        auftragAbbrechen();
        for (const a of zielAttribute) a.needsUpdate = true;
        neuZeichnen = true;
        anfordern();
        canvas.dispatchEvent(new CustomEvent(LAYOUT_EVENT, { detail: layout, bubbles: true }));
        return true;
      }
    } while (performance.now() < bis);
    return false;
  }

  function aufbauen() {
    if (breite < 2 || hoehe < 2) return;
    // Vollflächig (Sticky-Bühne mit Texten links bzw. unten) oder eigene Spalte (reduziert)
    const rect = canvas.getBoundingClientRect();
    const vollflaechig = rect.width >= window.innerWidth * 0.9 && rect.height >= window.innerHeight * 0.85;
    // Säulen, Befunde und Tabelle hängen nicht von der Kartenmeta ab; die Karte schon.
    layout = berechneLayout(breite, hoehe, variante, karte?.meta ?? null, standardRaender(breite, hoehe, variante, vollflaechig));
    start = bauePartikelStart(layout);
    const puffer = start.puffer;
    const g = new BufferGeometry();
    g.setAttribute("position", new BufferAttribute(puffer.position, 2));
    g.setAttribute("aPruef", new BufferAttribute(puffer.pruef, 2));
    const aKarte = new BufferAttribute(puffer.karte, 2);
    const aTabelle = new BufferAttribute(puffer.tabelle, 2);
    const aStil = new BufferAttribute(puffer.stil, 2);
    zielAttribute = [aKarte, aTabelle, aStil];
    g.setAttribute("aKarte", aKarte);
    g.setAttribute("aTabelle", aTabelle);
    g.setAttribute("aZufall", new BufferAttribute(puffer.zufall, 4));
    g.setAttribute("aInfo", new BufferAttribute(puffer.info, 4));
    g.setAttribute("aDichte", new BufferAttribute(puffer.dichte, 1));
    g.setAttribute("aStil", aStil);
    const alt = punkte.geometry;
    punkte.geometry = g;
    alt.dispose();

    setzeLinien(achsen, achsenPunkte(layout));
    setzeLinien(grenzen, karte ? grenzenPunkte(layout, karte) : []);
    setzeLinien(tabAchse, tabellenAchsePunkte(layout));
    hohlIds.forEach((id, k) => setzeLinien(hohl[k], umrissPunkte(layout!, id)));
    const sl = layout.saeulen;
    uniforms.uSaeulen.value.set(sl[0].x, sl[sl.length - 1].x);
    uniforms.uTabPunkt.value = layout.tabelle.punktAbstand;
    const pl = layout.pruefLinie;
    scan.scale.set(2, pl.unten - pl.oben, 1);
    scan.position.set(pl.von, (pl.oben + pl.unten) / 2, 0);
    neuZeichnen = true;
    // Ziele neu; das Layout-Event folgt, sobald sie stehen (dann mit Kartenmeta)
    zieleStarten();
    if (zielP() > ZIELE_SPAETESTENS_P) zieleRechnen(Infinity);
  }

  function groesseAnwenden(w: number, h: number) {
    const dpr = Math.min(window.devicePixelRatio || 1, stil.dprMax);
    if (Math.abs(w - breite) < 0.5 && Math.abs(h - hoehe) < 0.5 && uniforms.uPR.value === dpr) return;
    breite = w;
    hoehe = h;
    renderer.setPixelRatio(dpr);
    renderer.setSize(w, h, false);
    kamera.left = 0;
    kamera.right = w;
    kamera.top = 0;
    kamera.bottom = h;
    kamera.updateProjectionMatrix();
    uniforms.uAufloesung.value.set(w, h);
    uniforms.uPR.value = dpr;
    aufbauen();
    anfordern();
  }

  function zeichnen(pRoh: number) {
    if (!layout || !bereit) return;
    // Ohne fertige Ziele steht die Szene höchstens am Ende von Schritt 2 (danach wären die
    // Kartenziele noch 0); sobald sie stehen, gleitet sie weiter.
    const p = zieleFertig ? pRoh : Math.min(pRoh, SCHRITTE[2].von);
    const lz = linienZustand(p, layout.pruefLinie.von, layout.pruefLinie.bis);
    uniforms.uFortschritt.value = p;
    uniforms.uScan.value = lz.scanX;
    const laden = Math.min(1, uniforms.uLaden.value * 1.4);
    achsenMat.opacity = 0.4 * lz.achsenAlpha * laden;
    grenzenMat.opacity = 0.26 * lz.grenzenAlpha;
    tabAchseMat.opacity = 0.34 * lz.tabellenAchseAlpha;
    hohlIds.forEach((id, k) => {
      const b = layout!.befunde.find((x) => x.id === id);
      const sx = b ? (layout!.saeulen.find((s) => s.lieferung === b.lieferung)?.x ?? 0) : 0;
      const markiert = Math.min(1, Math.max(0, (lz.scanX - sx + 3) / 12));
      hohlMat[k].opacity = 0.85 * markiert * lz.hohlAlpha * (p > SCHRITTE[1].von ? 1 : 0);
      hohl[k].visible = hohlMat[k].opacity > 0.002;
    });
    scanMat.opacity = lz.scanAlpha;
    scan.position.x = lz.scanX;
    achsen.visible = achsenMat.opacity > 0.002;
    grenzen.visible = grenzenMat.opacity > 0.002;
    tabAchse.visible = tabAchseMat.opacity > 0.002;
    scan.visible = scanMat.opacity > 0.002;
    renderer.render(szene, kamera);
    if (!erstesBild) {
      erstesBild = true;
      o.beiErstemBild?.();
    }
  }

  // Schleife: läuft nur bei Bewegung (Laden, Glättung, Fortschritt) und, ohne reduzierte
  // Bewegung, für das Atmen mit ~30 Bildern/s. Pausiert, wenn Canvas oder Tab nicht sichtbar.
  let raf = 0;
  let letzt = 0;
  let letzterRender = -1e9;
  let ladeZeit = ohneLaden ? LADEN_MS : 0;
  const zielP = () => (reduziert ? ruhendesP(fortschritt.wert()) : fortschritt.wert());
  let pGlatt = zielP();
  const v = { v: 0 };
  let sichtbar = true;
  let tabSichtbar = document.visibilityState !== "hidden";

  function anfordern() {
    if (raf || zerstoert || !sichtbar || !tabSichtbar) return;
    raf = requestAnimationFrame(bild);
  }

  function bild(t: number) {
    raf = 0;
    if (zerstoert) return;
    const dt = letzt ? Math.min(0.05, (t - letzt) / 1000) : 1 / 60;
    letzt = t;
    const ziel = zielP();
    // Spätestens jetzt fertig rechnen (Karte geladen, Nutzer nähert sich Schritt 3)
    if (ziele && ziel > ZIELE_SPAETESTENS_P) zieleRechnen(Infinity);
    // Reduziert ohne Gleiten: lieber kurz warten als vom Standbild Schritt 2 zur Karte springen
    const warten = !bereit || (reduziert && !zieleFertig && ziel >= SCHRITTE[2].von);
    if (warten) {
      letzt = 0;
      return;
    }
    pGlatt = reduziert ? ziel : daempfe(pGlatt, ziel, v, GLAETTUNG_S, dt);
    if (Math.abs(pGlatt - ziel) < 1e-5) pGlatt = ziel;
    // Ohne Ziele wartet die Glättung am Ende von Schritt 2 und gleitet danach weiter (kein Sprung)
    if (!zieleFertig && pGlatt > SCHRITTE[2].von) {
      pGlatt = SCHRITTE[2].von;
      v.v = 0;
    }
    // Laden nur zählen, solange etwas gezeigt wird
    if (layout) ladeZeit = Math.min(LADEN_MS, ladeZeit + dt * 1000);
    uniforms.uLaden.value = ladeZeit / LADEN_MS;
    uniforms.uZeit.value = t / 1000;
    const bewegt = pGlatt !== ziel || ladeZeit < LADEN_MS || neuZeichnen;
    if (bewegt || (!reduziert && t - letzterRender >= 32)) {
      zeichnen(pGlatt);
      letzterRender = t;
      neuZeichnen = false;
    }
    if (bewegt || !reduziert) anfordern();
    else letzt = 0;
  }

  const abmelden = fortschritt.abonnieren(() => anfordern());

  const ro = new ResizeObserver((eintraege) => {
    const r = eintraege[eintraege.length - 1]?.contentRect;
    if (r && r.width > 0 && r.height > 0) groesseAnwenden(r.width, r.height);
  });
  ro.observe(canvas);

  const io = new IntersectionObserver((eintraege) => {
    sichtbar = eintraege[eintraege.length - 1]?.isIntersecting ?? true;
    if (sichtbar) anfordern();
    else letzt = 0;
  });
  io.observe(canvas);

  const sichtbarkeit = () => {
    tabSichtbar = document.visibilityState !== "hidden";
    if (tabSichtbar) anfordern();
    else letzt = 0;
  };
  document.addEventListener("visibilitychange", sichtbarkeit);

  const kontextVerloren = (e: Event) => {
    e.preventDefault();
    cancelAnimationFrame(raf);
    raf = 0;
  };
  const kontextZurueck = () => {
    neuZeichnen = true;
    anfordern();
  };
  canvas.addEventListener("webglcontextlost", kontextVerloren);
  canvas.addEventListener("webglcontextrestored", kontextZurueck);

  // Shader ohne Blockieren übersetzen (KHR_parallel_shader_compile, sonst kurze Wartezeit)
  renderer
    .compileAsync(szene, kamera)
    .catch(() => undefined)
    .then(() => {
      if (zerstoert) return;
      bereit = true;
      neuZeichnen = true;
      anfordern();
    });

  const startRect = canvas.getBoundingClientRect();
  if (startRect.width > 0 && startRect.height > 0) groesseAnwenden(startRect.width, startRect.height);

  // Kartendaten laden; erst dann entstehen die Partikel. Bei Fehler die Ersatz-Karte.
  if (o.ladeKarte) {
    o.ladeKarte()
      .then((k) => (k.n >= 1 ? k : ersatzKarte(kartenPunkte)))
      .catch(() => ersatzKarte(kartenPunkte))
      .then((k) => {
        if (zerstoert) return;
        karte = k;
        // Neu mit Kartenmeta (Säulen bleiben gleich), dann Ziele in Häppchen
        aufbauen();
        anfordern();
      });
  }

  return {
    zerstoeren() {
      zerstoert = true;
      auftragAbbrechen();
      ziele = null;
      cancelAnimationFrame(raf);
      abmelden();
      ro.disconnect();
      io.disconnect();
      document.removeEventListener("visibilitychange", sichtbarkeit);
      canvas.removeEventListener("webglcontextlost", kontextVerloren);
      canvas.removeEventListener("webglcontextrestored", kontextZurueck);
      punkte.geometry.dispose();
      material.dispose();
      for (const l of linien) {
        l.geometry.dispose();
        (l.material as LineBasicMaterial).dispose();
      }
      scanGeo.dispose();
      scanMat.dispose();
      renderer.dispose();
    },
  };
}
