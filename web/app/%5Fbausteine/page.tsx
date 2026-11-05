import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import {
  Akzent,
  Feld,
  Fliesstext,
  Knopf,
  knopfKlassen,
  Leerzustand,
  Status,
  Tabelle,
  Ueberschrift,
  Zahl,
} from "@kic/ui/basis";
import { bausteineSichtbar } from "./sichtbar";

// Musterseite aller Basis-Elemente (#56) mit erfundenen Inhalten. Zur Laufzeit geprüft, damit
// KIC_BAUSTEINE auch in einem fertigen Build wirkt.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Bausteine · Klarton+",
  robots: { index: false, follow: false },
};

function Abschnitt({ id, titel, children }: { id: string; titel: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-titel`} className="flex flex-col gap-6 border-t border-line pt-8">
      <Ueberschrift stufe={2} id={`${id}-titel`}>
        {titel}
      </Ueberschrift>
      {children}
    </section>
  );
}

const spalten = [
  { schluessel: "abschnitt", titel: "Wirtschaftsabschnitt" },
  { schluessel: "beschaeftigte", titel: "Beschäftigte", zahl: true },
  { schluessel: "veraenderung", titel: "Veränderung zum Vormonat", zahl: true },
] as const;

const zeilen = [
  { abschnitt: "C Herstellung von Waren", beschaeftigte: 612340, veraenderung: 0.3 },
  { abschnitt: "F Bau", beschaeftigte: 284115, veraenderung: -1.2 },
  { abschnitt: "G Handel", beschaeftigte: 598702, veraenderung: 0.1 },
  { abschnitt: "Q Gesundheits- und Sozialwesen", beschaeftigte: 341876, veraenderung: 0.6 },
].map((z) => ({
  abschnitt: z.abschnitt,
  beschaeftigte: <Zahl wert={z.beschaeftigte} />,
  veraenderung: <Zahl wert={z.veraenderung} einheit="%" />,
}));

export default function BausteineSeite() {
  if (!bausteineSichtbar({ NODE_ENV: process.env.NODE_ENV, KIC_BAUSTEINE: process.env.KIC_BAUSTEINE })) {
    notFound();
  }

  return (
    <main className="min-h-screen bg-paper text-ink">
      <div className="mx-auto flex max-w-5xl flex-col gap-12 px-8 py-16">
        <header className="flex flex-col gap-4">
          <Ueberschrift stufe={1}>Bausteine Klarton+</Ueberschrift>
          <Fliesstext ton="gedaempft">
            Alle Basis-Elemente mit erfundenen Beispielinhalten. Die Seite ist nur in der Entwicklung sichtbar.
          </Fliesstext>
        </header>

        <Abschnitt id="text" titel="Text">
          <div className="flex flex-col gap-4">
            <Ueberschrift stufe={1} als="h3">
              3,9 Millionen Beschäftigte im März 2025
            </Ueberschrift>
            <Ueberschrift stufe={2} als="h3">
              Der Bau verliert im Vormonatsvergleich
            </Ueberschrift>
            <Ueberschrift stufe={3}>Lieferung 2025-03 ist vollständig eingelesen</Ueberschrift>
            <Fliesstext>
              Fließtext in 16 px. Jede Zahl auf dieser Seite ist erfunden und dient nur dazu, die Elemente zu zeigen.
            </Fliesstext>
            <Fliesstext groesse={14} ton="gedaempft">
              Nebentext in 14 px, zum Beispiel für Quellenangaben unter einer Grafik.
            </Fliesstext>
            <Fliesstext groesse={12} ton="gedaempft">
              Kleinster Text in 12 px für Fußnoten.
            </Fliesstext>
            <Fliesstext>
              Zahlen stehen in Mono: <Zahl wert={3912874} /> Beschäftigte, <Zahl wert={-1.2} einheit="%" /> im Bau.
            </Fliesstext>
          </div>
        </Abschnitt>

        <Abschnitt id="knoepfe" titel="Knöpfe">
          <div className="flex flex-wrap items-center gap-4">
            <Knopf>Lieferung freigeben</Knopf>
            <Knopf art="sekundaer">Bericht ansehen</Knopf>
            <Knopf art="sekundaer" disabled>
              Export läuft
            </Knopf>
            <a href="#tabelle" className={knopfKlassen("sekundaer")}>
              Zur Tabelle
            </a>
          </div>
        </Abschnitt>

        <Abschnitt id="feld" titel="Feld">
          <form className="flex max-w-md flex-col gap-6">
            <Feld
              label="Name der freigebenden Person"
              name="freigabe-name"
              hinweis="Vor- und Nachname, zum Beispiel Anna Beispiel"
              autoComplete="off"
            />
            <Feld
              label="Lieferung"
              name="lieferung"
              defaultValue="2025-13"
              hinweis="Format JJJJ-MM"
              fehler="Einen Monat 13 gibt es nicht."
            />
          </form>
        </Abschnitt>

        <Abschnitt id="tabelle" titel="Tabelle">
          <Tabelle
            beschriftung="Beschäftigte nach Wirtschaftsabschnitt, März 2025, erfundene Werte"
            beschriftungZeigen
            spalten={spalten}
            zeilen={zeilen}
          />
        </Abschnitt>

        <Abschnitt id="status" titel="Status">
          <ul className="flex flex-col gap-2">
            <li>
              <Status art="ok">Prüfung bestanden</Status>
            </li>
            <li>
              <Status art="warnung">Drei Werte auffällig</Status>
            </li>
            <li>
              <Status art="fehler">Lieferung unvollständig</Status>
            </li>
            <li>
              <Status art="info">Regel gilt seit 1. März 2025</Status>
            </li>
          </ul>
        </Abschnitt>

        <Abschnitt id="leerzustand" titel="Leerzustand">
          <Leerzustand
            satz="Für April 2025 liegt noch keine Lieferung vor."
            aktion={<Knopf art="sekundaer">Lieferung einlesen</Knopf>}
          />
        </Abschnitt>

        <Abschnitt id="akzente" titel="Akzente">
          <div className="flex flex-col gap-6">
            <Akzent art="beleg">
              <Fliesstext groesse={14}>
                <strong className="text-gruen">Beleg:</strong> Zahl aus roh.lieferung 2025-03, Zeile 4.211.
              </Fliesstext>
            </Akzent>
            <Akzent art="ki">
              <Fliesstext groesse={14}>
                <strong className="text-violett">KI-Vorschlag:</strong> Regel R-12 auf Abschnitt F ausweiten. Wartet
                auf Freigabe.
              </Fliesstext>
            </Akzent>
            <Akzent art="warnung">
              <Fliesstext groesse={14}>
                <strong className="text-warn-fg">Warnung:</strong> Abweichung von 4,1 % zum Vorjahresmonat.
              </Fliesstext>
            </Akzent>
            <Akzent art="fehler">
              <Fliesstext groesse={14}>
                <strong className="text-err-fg">Fehler:</strong> Für ÖNACE-Code 43.99 fehlt eine Zuordnung.
              </Fliesstext>
            </Akzent>
          </div>
        </Abschnitt>
      </div>
    </main>
  );
}
