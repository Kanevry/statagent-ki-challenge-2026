import type { Metadata } from "next";
import { Fliesstext, Ueberschrift } from "@kic/ui/basis";
import { fragenGesperrt } from "@/components/uc3/cli";
import { lies } from "@/components/uc3/db";
import { type Definition, FragenFormular } from "./_teile/fragen-formular";

// Fragen an die Daten (#18, Frame DbY1q): eine Frage in eigenen Worten, die Antwort rechnet `uc3 frage` bzw.
// `uc3 antwort` ohne Sprachmodell (POST /api/uc3/frage). Die Seite liest nur die Definitionen der Variablen aus
// stat.variable, damit „So haben wir gerechnet“ die Definition zeigt, solange die CLI sie nicht mitliefert (#74).
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Fragen an die Daten · StatAgent" };

async function leseDefinitionen(): Promise<Definition[]> {
  const lesung = await lies(async (sql) => {
    const [da] = await sql`SELECT to_regclass('stat.variable') IS NOT NULL AS da`;
    if (!da?.da) return [];
    const zeilen = await sql`
      SELECT code, beschreibung FROM stat.variable
      WHERE statistik = 'beschaeftigte' AND beschreibung IS NOT NULL ORDER BY code`;
    return zeilen.map((z) => ({ code: String(z.code), beschreibung: String(z.beschreibung) }));
  });
  // Ohne Datenbank bleibt die Definition weg; die Antwort selbst kommt über die CLI.
  return lesung.ok ? lesung.daten : [];
}

export default async function FragenAnDieDaten() {
  const definitionen = await leseDefinitionen();
  return (
    <>
      <header className="flex max-w-3xl flex-col gap-4">
        <Ueberschrift stufe={2} als="h1" className="hyphens-auto break-words">
          Fragen Sie die Daten in eigenen Worten; das Programm rechnet die Antwort ohne KI.
        </Ueberschrift>
        <Fliesstext>
          Das Programm erkennt Monat, Bundesland und Geschlecht in Ihrer Frage, holt die Zahl mit einer Abfrage aus
          der Datenbank und zeigt diese Abfrage mit an.
        </Fliesstext>
      </header>
      <FragenFormular definitionen={definitionen} nurLesen={fragenGesperrt()} />
    </>
  );
}
