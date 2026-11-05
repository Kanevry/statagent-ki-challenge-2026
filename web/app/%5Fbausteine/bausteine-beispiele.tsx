"use client";

import type { ReactNode } from "react";
import { Fliesstext, Knopf, Leerzustand, Ueberschrift } from "@kic/ui/basis";
import {
  Begriff,
  FehlerChip,
  formatZahl,
  FreigabeKarte,
  HerkunftChip,
  WarnChip,
  type FreigabeEintrag,
} from "@kic/ui/bausteine";

// Beispiele der Bausteine (#60) mit erfundenen Inhalten. Client-Komponente, weil die Freigabe-Karten
// Funktionen als Handler brauchen, die aus der Server-Seite nicht übergeben werden können.

const sql = `select count(distinct person_id) as beschaeftigte
from roh.lieferung
where lieferung = '2025-03'
  and beschaeftigungsart = 'voll'`;

const eintrag: FreigabeEintrag = {
  anweisung: "Prüfregel P07 (Beschäftigungsbeginn vor Geburtsdatum) ab 2025-01 als Fehler statt Warnung führen",
  name: "Anna Beispiel",
  zeit: "2026-11-05T09:12:30+00:00",
  wirkung: "Regel P07 Version 2; betrifft keinen veröffentlichten Monat",
  modell: "gpt-5-mini",
  ref: "regel:P07@2",
};

const diff = ` regel: P07 Beschäftigungsbeginn vor Geburtsdatum
-schwere: warnung
+schwere: fehler
 gilt_ab: 2025-01`;

const kurzWarten = () => new Promise<void>((fertig) => setTimeout(fertig, 400));

function Teil({ titel, children }: { titel: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-4">
      <Ueberschrift stufe={3}>{titel}</Ueberschrift>
      {children}
    </div>
  );
}

export function BausteineBeispiele() {
  const gemeinsam = {
    eintrag,
    vorher: 387390,
    nachher: 387130,
    groesse: "Beschäftigte",
    diff,
    ebene: "h4" as const,
  };

  return (
    <div className="flex flex-col gap-12">
      <Teil titel="Herkunft-Chip">
        <div className="flex flex-col items-start gap-2">
          <span className="font-mono text-32 tabular-nums text-ink">{formatZahl(387130)}</span>
          <HerkunftChip sql={sql} lieferung="2025-03" lauf="L-0412" />
        </div>
      </Teil>

      <Teil titel="Warn- und Fehler-Chip">
        <div className="flex flex-wrap items-center gap-4">
          <WarnChip>3 Werte auffällig</WarnChip>
          <WarnChip />
          <FehlerChip>Lieferung unvollständig</FehlerChip>
          <FehlerChip />
        </div>
      </Teil>

      <Teil titel="Begriff">
        <Fliesstext>
          Für März 2025 besteht <Begriff wort="Revisionsbedarf" />. Der <Begriff wort="Qualitätsbericht" /> nennt die
          betroffenen Zellen, jede Zahl trägt einen <Begriff wort="Beleg" />.
        </Fliesstext>
        <div className="flex flex-wrap gap-8 font-sans text-16 font-semibold text-ink">
          <Begriff wort="Lieferung" untertitel />
          <Begriff wort="Freigabe" untertitel />
        </div>
      </Teil>

      <Teil titel="Freigabe-Karte, offen">
        <FreigabeKarte
          {...gemeinsam}
          beleg={{ sql, lieferung: "2025-03", lauf: "L-0412" }}
          onFreigeben={async () => {
            await kurzWarten();
            return { zeitpunkt: "2026-11-05T09:20:00+00:00" };
          }}
          onAblehnen={kurzWarten}
        />
      </Teil>

      <Teil titel="Freigabe-Karte, Server nimmt nicht an">
        <Fliesstext groesse={14} ton="gedaempft">
          Namen eingeben und freigeben: die Karte zeigt den Fehler und bleibt offen.
        </Fliesstext>
        <FreigabeKarte
          {...gemeinsam}
          onFreigeben={async () => {
            await kurzWarten();
            throw new Error("Die Datenbank ist gerade nicht erreichbar.");
          }}
          onAblehnen={kurzWarten}
        />
      </Teil>

      <Teil titel="Freigabe-Karte, freigegeben">
        <FreigabeKarte
          {...gemeinsam}
          onFreigeben={kurzWarten}
          onAblehnen={kurzWarten}
          entscheidung={{ art: "freigegeben", name: "Anna Beispiel", zeit: "2026-11-05T09:20:00+00:00" }}
        />
      </Teil>

      <Teil titel="Freigabe-Karte, abgelehnt">
        <FreigabeKarte
          {...gemeinsam}
          onFreigeben={kurzWarten}
          onAblehnen={kurzWarten}
          entscheidung={{
            art: "abgelehnt",
            name: "Clara Beispiel",
            zeit: "2026-11-05T09:25:00+00:00",
            begruendung: "Erst mit der Lieferung 2025-04 prüfen.",
          }}
        />
      </Teil>

      <Teil titel="Keine offene Freigabe">
        <Leerzustand
          satz="Keine Regeländerung wartet auf Freigabe."
          aktion={<Knopf art="sekundaer">Protokoll öffnen</Knopf>}
        />
      </Teil>
    </div>
  );
}
