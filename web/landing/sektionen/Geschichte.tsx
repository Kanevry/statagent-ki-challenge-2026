"use client";

import Link from "next/link";
import { memo, useEffect, useRef, useState, type CSSProperties } from "react";
import { BESTAND_JE_MONAT, EINBRUCH, FREIGABE, GOLDEN_SET, LIEFERUNGEN, SUMME_ZEILEN, zahl } from "../daten/fakten";
import { BELEG, BUEHNE, GESCHICHTE, HERO, NAVIGATION } from "../texte/inhalt";
import g from "./geschichte.module.css";

/*
 * Die Bühne: 24 Säulen in Koordinaten 720 × 540, die ohne Modell und ohne Laufzeit-Rechnung aus fakten.ts entstehen.
 * Der aktive Schritt steht als data-schritt an der Bühne, alles Weitere (Bewegung, Farbe, Beschriftung) macht das CSS.
 * Ohne JavaScript und bei reduzierter Bewegung bleibt jeder Schritt als Text vollständig lesbar.
 */
const BREITE = 720;
const HOEHE = 540;
const BASIS = 480;
const SAEULEN_HOEHE = 340;
/** Oberer Rand der Achse; die Achse beginnt bei 0, damit die Fallhöhe ehrlich bleibt. */
const SKALA = 450_000;
const LINKS = 8;
const SCHRITT_X = (BREITE - 2 * LINKS) / LIEFERUNGEN.length;
const SAEULE = 20;

const x = (i: number) => LINKS + i * SCHRITT_X + (SCHRITT_X - SAEULE) / 2;
const mitte = (i: number) => x(i) + SAEULE / 2;
const hoehe = (wert: number) => (wert / SKALA) * SAEULEN_HOEHE;
const y = (wert: number) => BASIS - hoehe(wert);
const prozent = (wert: number, gesamt: number) => `${(wert / gesamt) * 100}%`;

const OKT = LIEFERUNGEN.findIndex((l) => l.lieferung === EINBRUCH.lieferung);
const SEP = OKT - 1;
const AUG = 0;
const MAERZ = LIEFERUNGEN.findIndex((l) => l.lieferung === FREIGABE.vorlaeufig[0]);

const KURVE = BESTAND_JE_MONAT.map((w, i) => `${i === 0 ? "M" : "L"}${mitte(i).toFixed(1)} ${y(w).toFixed(1)}`).join(" ");

/** 60 × 48 = 2.880: ein Kästchen je Zahl des Beispielberichts. */
const RASTER_SPALTEN = 60;
const RASTER_ZEILEN = GOLDEN_SET.zellenGesamt / RASTER_SPALTEN;
const KAESTCHEN = 6;

function art(i: number): string | undefined {
  if (i === OKT) return "okt";
  if (i === MAERZ) return "maerz";
  if (i === AUG) return "aug";
  return undefined;
}

/** Zählt beim Eintritt in den ersten Schritt hoch; bei reduzierter Bewegung steht sofort die Zahl da. */
function Zaehler({ aktiv, wert }: { aktiv: boolean; wert: number }) {
  const [anzeige, setAnzeige] = useState(wert);
  useEffect(() => {
    if (!aktiv || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const dauer = 1800;
    const start = performance.now();
    let rahmen = requestAnimationFrame(function weiter(t) {
      const p = Math.min(1, (t - start) / dauer);
      setAnzeige(Math.round(wert * p));
      if (p < 1) rahmen = requestAnimationFrame(weiter);
    });
    return () => cancelAnimationFrame(rahmen);
  }, [aktiv, wert]);
  return <>{zahl(anzeige)}</>;
}

const Saeulen = memo(function Saeulen() {
  return (
    <svg className={g.bild} viewBox={`0 0 ${BREITE} ${HOEHE}`} role="presentation">
      <defs>
        <pattern id="kaestchen" width={KAESTCHEN} height={KAESTCHEN} patternUnits="userSpaceOnUse">
          <rect width={KAESTCHEN - 1.4} height={KAESTCHEN - 1.4} rx="0.6" />
        </pattern>
      </defs>

      <g className={g.flaeche}>
        {LIEFERUNGEN.map((l, i) => (
          <rect
            key={l.lieferung}
            className={g.saeule}
            data-art={art(i)}
            x={x(i)}
            y={BASIS - SAEULEN_HOEHE}
            width={SAEULE}
            height={SAEULEN_HOEHE}
            rx="1.5"
            style={
              {
                "--i": i,
                "--zeilen": l.zeilen / SKALA,
                "--bestand": BESTAND_JE_MONAT[i] / SKALA,
                "--vorlaeufig": (i === OKT ? EINBRUCH.vorlaeufig : BESTAND_JE_MONAT[i]) / SKALA,
              } as CSSProperties
            }
          />
        ))}
        {LIEFERUNGEN.map((l, i) => (
          <rect
            key={l.lieferung}
            className={g.paket}
            x={x(i)}
            y="0"
            width={SAEULE}
            height="12"
            rx="1.5"
            style={{ "--i": i, "--ziel": `${y(l.zeilen)}px` } as CSSProperties}
          />
        ))}
        <line className={g.achse} x1={LINKS} x2={BREITE - LINKS} y1={BASIS + 0.5} y2={BASIS + 0.5} />
        <path className={g.kurve} d={KURVE} pathLength={1} fill="none" />
        <line className={g.bruch} x1={mitte(SEP)} x2={mitte(OKT) + 26} y1={y(EINBRUCH.vormonat)} y2={y(EINBRUCH.vormonat)} />
        <circle className={g.punkt} cx={mitte(SEP)} cy={y(EINBRUCH.vormonat)} r="5" />
        <circle className={g.punktOkt} cx={mitte(OKT)} cy={y(EINBRUCH.geliefert)} r="6" />
      </g>

      <g className={g.pruefLinie}>
        <rect x={-46} y={BASIS - SAEULEN_HOEHE - 20} width={46} height={SAEULEN_HOEHE + 20} fill="url(#pruefSpur)" />
        <line x1="0" x2="0" y1={BASIS - SAEULEN_HOEHE - 20} y2={BASIS} />
        <linearGradient id="pruefSpur">
          <stop offset="0" stopColor="#3ddc97" stopOpacity="0" />
          <stop offset="1" stopColor="#3ddc97" stopOpacity="0.28" />
        </linearGradient>
      </g>

      {[AUG, MAERZ, OKT].map((i) => (
        <line
          key={i}
          className={g.faden}
          x1={mitte(i)}
          x2={mitte(i)}
          y1="104"
          y2={y(LIEFERUNGEN[i].zeilen) - 4}
          style={{ "--i": i } as CSSProperties}
        />
      ))}
      <line className={g.fadenOkt} x1={mitte(OKT)} x2={mitte(OKT)} y1="114" y2={y(EINBRUCH.geliefert) - 10} />

      <rect
        className={g.raster}
        x="0"
        y="40"
        width={RASTER_SPALTEN * KAESTCHEN}
        height={RASTER_ZEILEN * KAESTCHEN}
        fill="url(#kaestchen)"
      />
    </svg>
  );
});

function Buehne({ schritt }: { schritt: number }) {
  const t = BUEHNE;
  const f = t.freigabe;
  return (
    <div className={g.buehne} aria-hidden="true">
      <div className={g.feld} data-schritt={schritt}>
        <Saeulen />

        <p className={`${g.etikett} ${g.erklaerung}`}>{t.erklaerung}</p>

        <p className={`${g.etikett} ${g.ankunft}`}>
          <strong>
            <Zaehler aktiv={schritt === 1} wert={SUMME_ZEILEN} />
          </strong>
          <span>{t.ankunft.text}</span>
        </p>

        {t.marken.map((m, k) => {
          const i = [AUG, MAERZ, OKT][k];
          return (
            <p
              key={m.text}
              className={`${g.etikett} ${g.marke}`}
              style={{ "--i": i, left: prozent(mitte(i) - 4, BREITE) } as CSSProperties}
            >
              <strong>{m.wert}</strong>
              <span>{m.text}</span>
            </p>
          );
        })}

        <p className={`${g.etikett} ${g.vormonat}`} style={{ right: prozent(BREITE - mitte(SEP) - 6, BREITE) }}>
          <strong>{t.vormonat.wert}</strong>
          <span>{t.vormonat.text}</span>
        </p>
        <p className={`${g.etikett} ${g.einbruch}`} style={{ left: prozent(mitte(OKT) - 6, BREITE) }}>
          <strong>{t.einbruch.wert}</strong>
          <span>{t.einbruch.text}</span>
          <span className={g.folge}>{t.einbruch.folge}</span>
        </p>

        <div className={g.karte}>
          <p className={g.kartenTitel}>{f.feld}</p>
          <p className={g.zeileFalsch}>
            <span className={g.eingabeFalsch}>{f.falsch}</span>
            <span className={g.abgelehnt}>{f.abgelehnt}</span>
          </p>
          <p className={g.zeileRichtig}>
            <span className={g.eingabe}>
              <span className={g.tippen}>{f.name}</span>
            </span>
          </p>
          <p className={g.bestaetigt}>
            <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
              <path d="M2.5 8.5 6.2 12 13.5 4" fill="none" stroke="currentColor" strokeWidth="2" />
            </svg>
            {f.zeit}
          </p>
        </div>
        <p className={`${g.etikett} ${g.legende}`}>
          <span className={g.legendeGruen}>{f.gruen}</span>
          <span className={g.legendeGelb}>{f.gelb}</span>
        </p>

        <p className={`${g.etikett} ${g.rasterText}`}>{t.raster}</p>
        <ul className={g.ergebnis}>
          {t.ergebnis.map((e, k) => (
            <li key={e.text} style={{ "--k": k } as CSSProperties}>
              <strong>{e.wert}</strong>
              <span>{e.text}</span>
            </li>
          ))}
        </ul>

        <p className={`${g.monat} ${g.monatErste}`}>{t.erste}</p>
        <p className={g.monat} style={{ left: prozent(mitte(OKT), BREITE), transform: "translateX(-50%)" }}>
          {t.mitte}
        </p>
        <p className={`${g.monat} ${g.monatLetzte}`}>{t.letzte}</p>
      </div>

      <p className={g.stand} data-schritt={schritt}>
        <span className={g.standText}>{schritt > 0 ? t.stand(schritt) : " "}</span>
        <span className={g.standLeiste}>
          {GESCHICHTE.map((s, i) => (
            <span key={s.titel} data-an={i < schritt ? "" : undefined} />
          ))}
        </span>
      </p>
    </div>
  );
}

const Schritte = memo(function Schritte() {
  return (
    <ol className={g.schritte}>
      {GESCHICHTE.map((s, i) => (
        <li key={s.titel} id={`schritt-${i + 1}`} className={g.schritt} data-feld={i + 1}>
          <h2 className={g.schrittTitel}>{s.titel}</h2>
          <p className={g.schrittText}>{s.text}</p>
          {s.begriff ? (
            <p className={g.begriff}>
              <strong>{s.begriff.begriff}:</strong> {s.begriff.erklaerung}
            </p>
          ) : null}
          {i === GESCHICHTE.length - 1 ? (
            <>
              <figure className={g.beleg}>
                <pre tabIndex={0}>
                  <code>{BELEG.sql}</code>
                </pre>
                <figcaption>{BELEG.unterschrift}</figcaption>
              </figure>
              <Link href={NAVIGATION.app.href} className={g.knopf}>
                {HERO.knopf}
              </Link>
            </>
          ) : null}
        </li>
      ))}
    </ol>
  );
});

/**
 * Startseite als Geschichte: oben ein Satz und der Knopf, daneben die Bühne, die beim Scrollen stehen bleibt und sich
 * durch fünf Schritte verwandelt. Aktiv ist der Schritt, der gerade durch ein schmales Band im Bild läuft.
 */
export default function Geschichte() {
  const abschnitt = useRef<HTMLElement>(null);
  const [schritt, setSchritt] = useState(0);

  useEffect(() => {
    const felder = abschnitt.current?.querySelectorAll<HTMLElement>("[data-feld]");
    if (!felder || typeof IntersectionObserver === "undefined") return;
    // Breit steht der Text mittig im Feld, schmal direkt unter der klebenden Bühne: Das Band liegt so, dass die Bühne
    // wechselt, wenn der neue Text gerade gut lesbar ins Bild kommt und der alte geht.
    const schmal = window.matchMedia("(max-width: 899px)").matches;
    const b = new IntersectionObserver(
      (eintraege) => {
        for (const e of eintraege) {
          const feld = Number((e.target as HTMLElement).dataset.feld);
          if (e.isIntersecting) setSchritt(feld);
          // Schmal erreicht der kurze Kopf das Band nie: Läuft Schritt 1 nach unten hinaus, steht wieder das erste Bild.
          else if (feld === 1 && e.rootBounds && e.boundingClientRect.top > e.rootBounds.bottom) setSchritt(0);
        }
      },
      { rootMargin: schmal ? "-70% 0px -29% 0px" : "-18% 0px -81% 0px" },
    );
    felder.forEach((f) => b.observe(f));
    return () => b.disconnect();
  }, []);

  return (
    <section ref={abschnitt} id="start" className={g.geschichte} data-szene="" aria-labelledby="start-titel">
      <div className={g.raster2}>
        <header className={g.kopf} data-feld={0}>
          <h1 id="start-titel" className={g.titel}>
            {HERO.titel}
          </h1>
          <p className={g.satz}>{HERO.satz}</p>
          <Link href={NAVIGATION.app.href} className={g.knopf}>
            {HERO.knopf}
          </Link>
          <p className={g.autor}>{HERO.autor}</p>
          <p className={g.hinweis}>{HERO.hinweis}</p>
        </header>
        <Buehne schritt={schritt} />
        <Schritte />
      </div>
    </section>
  );
}
