"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { fassungsText, useFassung } from "../../lib/plattform/fassungs-knopf";
import { NAVIGATION, SEITE } from "../texte/inhalt";
import n from "./navigation.module.css";

/**
 * Kopfleiste: über dem Hero in Navy, danach auf Papier. Mobil sind die Sprungmarken in einem
 * Disclosure-Menü (aria-expanded, Escape schließt und gibt den Fokus an den Knopf zurück).
 */
export default function Navigation() {
  const kopfRef = useRef<HTMLElement>(null);
  const knopfRef = useRef<HTMLButtonElement>(null);
  // Nur die Startseite beginnt auf Navy; sonst blitzte die Leiste auf Papier-Seiten dunkel auf.
  const [aufNavy, setAufNavy] = useState(usePathname() === "/");
  const [offen, setOffen] = useState(false);
  const fassung = useFassung();

  useEffect(() => {
    let rahmen = 0;
    const messen = () => {
      rahmen = 0;
      const hero = document.querySelector("[data-szene]");
      const hoehe = kopfRef.current?.offsetHeight ?? 64;
      setAufNavy(hero ? hero.getBoundingClientRect().bottom > hoehe : false);
    };
    const anfordern = () => {
      if (!rahmen) rahmen = requestAnimationFrame(messen);
    };
    messen();
    window.addEventListener("scroll", anfordern, { passive: true });
    window.addEventListener("resize", anfordern, { passive: true });
    return () => {
      window.removeEventListener("scroll", anfordern);
      window.removeEventListener("resize", anfordern);
      if (rahmen) cancelAnimationFrame(rahmen);
    };
  }, []);

  useEffect(() => {
    if (!offen) return;
    const taste = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setOffen(false);
      knopfRef.current?.focus();
    };
    const zeiger = (e: PointerEvent) => {
      if (kopfRef.current && !kopfRef.current.contains(e.target as Node)) setOffen(false);
    };
    document.addEventListener("keydown", taste);
    document.addEventListener("pointerdown", zeiger);
    return () => {
      document.removeEventListener("keydown", taste);
      document.removeEventListener("pointerdown", zeiger);
    };
  }, [offen]);

  const grund = aufNavy && !offen ? "navy" : "papier";

  return (
    <header ref={kopfRef} className={n.kopf} data-grund={grund}>
      <a href="#inhalt" className={n.sprung}>
        {SEITE.sprungZumInhalt}
      </a>
      <nav className={n.leiste} aria-label={NAVIGATION.bereich}>
        <Link href="/" className={n.wortmarke}>
          <span className={n.marke}>{NAVIGATION.wortmarke}</span>
          <span className={n.team}>{NAVIGATION.team}</span>
        </Link>

        <ul className={n.marken}>
          {NAVIGATION.marken.map((m) => (
            <li key={m.href}>
              <Link href={m.href} className={n.link}>
                {m.text}
              </Link>
            </li>
          ))}
          {fassung && (
            <li>
              <a href={fassung.adresse} className={n.link} data-fassung={fassung.art}>
                {fassungsText(fassung)}
              </a>
            </li>
          )}
        </ul>

        <div className={n.rechts}>
          <button
            ref={knopfRef}
            type="button"
            className={n.menueKnopf}
            aria-expanded={offen}
            aria-controls="navigation-menue"
            onClick={() => setOffen((o) => !o)}
          >
            {NAVIGATION.menue}
          </button>
          <Link href={NAVIGATION.app.href} className={n.app}>
            {NAVIGATION.app.text}
          </Link>
        </div>
      </nav>

      <div id="navigation-menue" className={n.menue} hidden={!offen}>
        <ul>
          {NAVIGATION.marken.map((m) => (
            <li key={m.href}>
              <Link href={m.href} className={n.menueLink} onClick={() => setOffen(false)}>
                {m.text}
              </Link>
            </li>
          ))}
          {fassung && (
            <li>
              <a href={fassung.adresse} className={n.menueLink} data-fassung={fassung.art}>
                {fassungsText(fassung)}
              </a>
            </li>
          )}
        </ul>
      </div>
    </header>
  );
}
