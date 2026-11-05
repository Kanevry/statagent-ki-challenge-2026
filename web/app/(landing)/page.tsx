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

export const metadata: Metadata = {
  title: SEITE.titel,
  description: SEITE.beschreibung,
  // Eigenes Zeichen: vier Lieferungs-Säulen, eine davon gelb markiert (sonst 404 auf /favicon.ico).
  icons: { icon: { url: "/landing/favicon.svg", type: "image/svg+xml" } },
};

// Befunde aus der UC3-Datenbank höchstens alle fünf Minuten neu lesen.
export const revalidate = 300;

export default async function Startseite() {
  const tabelle = await ladeBefunde();

  return (
    <div className={s.seite}>
      <Navigation />
      <main id="inhalt">
        <HeroSzene />
        <Ansatz />
        <Datenfehler tabelle={tabelle} />
        <UseCases />
        <Team />
      </main>
      <Fusszeile />
    </div>
  );
}
