import type { Metadata } from "next";
import { ladeBefunde } from "@/landing/daten/befunde";
import Ansatz from "@/landing/sektionen/Ansatz";
import Datenfehler from "@/landing/sektionen/Datenfehler";
import Fusszeile from "@/landing/sektionen/Fusszeile";
import HeroSzene from "@/landing/sektionen/HeroSzene";
import Navigation from "@/landing/sektionen/Navigation";
import s from "@/landing/sektionen/seite.module.css";
import Team from "@/landing/sektionen/Team";
import UseCases from "@/landing/sektionen/UseCases";
import { SEITE } from "@/landing/texte/inhalt";
import l from "./landing.module.css";

export const metadata: Metadata = {
  title: SEITE.titel,
  description: SEITE.beschreibung,
  // Eigenes Zeichen: vier Lieferungs-Säulen, eine davon gelb markiert (sonst 404 auf /favicon.ico).
  icons: { icon: { url: "/landing/favicon.svg", type: "image/svg+xml" } },
};

// Nie beim Build vorrendern: `next build` läuft ohne UC3_DATABASE_URL, sonst stünden nach jedem Deploy einige Minuten
// lang die Beispieldaten auf der Seite (gemessen von infra-52 am 05.11.). Die Befunde hält ladeBefunde 60 s vor.
export const dynamic = "force-dynamic";

export default async function Startseite() {
  const tabelle = await ladeBefunde();

  return (
    <div className={s.seite}>
      <Navigation />
      <main id="inhalt">
        <HeroSzene />
        {/* Erst rendern, wenn sie in die Nähe kommen (eine Hülle, damit `.abschnitt + .abschnitt` greift) */}
        <div className={l.spaeter}>
          {/* Nach dem Einstieg zuerst der Weg in die App (UI-Regie 05.11.), dann Ansatz und Befunde. */}
          <UseCases />
          <Ansatz />
          <Datenfehler tabelle={tabelle} />
          <Team />
        </div>
      </main>
      <Fusszeile />
    </div>
  );
}
