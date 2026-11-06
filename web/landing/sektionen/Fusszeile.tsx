import { AUSRICHTER, FUSSZEILE } from "../texte/inhalt";
import a from "./abschnitte.module.css";
import s from "./seite.module.css";

const LOGO_HOEHE = 28;

export default function Fusszeile() {
  return (
    <footer className={a.fuss}>
      <div className={`${s.rahmen} ${a.fussRaster}`}>
        <div className={a.ausrichter}>
          <p className={a.ausrichterZeile}>{AUSRICHTER.zeile}</p>
          {AUSRICHTER.logos.length > 0 ? (
            <ul className={a.ausrichterLogos}>
              {AUSRICHTER.logos.map((logo) => (
                <li key={logo.src}>
                  <a href={logo.href} className={a.ausrichterLink} rel="noopener">
                    {/* eslint-disable-next-line @next/next/no-img-element -- kleines statisches Logo, feste Maße */}
                    <img
                      src={logo.src}
                      alt={logo.alt}
                      width={Math.round((logo.breite / logo.hoehe) * LOGO_HOEHE)}
                      height={LOGO_HOEHE}
                      loading="lazy"
                      decoding="async"
                    />
                  </a>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        <ul className={a.fussZeile}>
          <li>
            <a href={FUSSZEILE.repo.href} className={a.fussLink}>
              {FUSSZEILE.repo.text}
            </a>
          </li>
        </ul>
        <ul className={a.fussZeile}>
          {FUSSZEILE.hinweise.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
      </div>
    </footer>
  );
}
