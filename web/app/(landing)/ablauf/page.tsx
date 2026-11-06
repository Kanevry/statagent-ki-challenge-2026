import type { Metadata } from "next";
import { ABLAUF } from "@/landing/daten/ablauf";
import Ablauf from "@/landing/sektionen/Ablauf";
import Fusszeile from "@/landing/sektionen/Fusszeile";
import Navigation from "@/landing/sektionen/Navigation";
import s from "@/landing/sektionen/seite.module.css";

export const metadata: Metadata = {
  title: `${ABLAUF.titel} · StatAgent · KI Challenge 2026`,
  description: ABLAUF.satz,
  icons: { icon: { url: "/landing/favicon.svg", type: "image/svg+xml" } },
};

export default function AblaufSeite() {
  return (
    <div className={s.seite}>
      <Navigation />
      <main id="inhalt">
        <Ablauf />
      </main>
      <Fusszeile />
    </div>
  );
}
