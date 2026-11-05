import type { Metadata } from "next";
import { fragenGesperrt } from "@/components/uc3/cli";
import { lies } from "@/components/uc3/db";
import { type Definition, FragenFormular } from "./_teile/fragen-formular";

// Fragen an die Daten (#18, Frame DbY1q; UI-Regie v1): eine Frage in eigenen Worten, die Antwort rechnet `uc3 frage` bzw.
// `uc3 antwort` ohne Sprachmodell (POST /api/uc3/frage). Die Seite liest nur die Definitionen der Variablen aus
// stat.variable, damit „Details“ die Definition zeigt, solange die CLI sie nicht mitliefert (#74).
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
  // Überschrift, Erklärsatz und Bühne stehen im Formular, weil sie nach der ersten Frage nach oben rücken.
  return <FragenFormular definitionen={definitionen} nurLesen={fragenGesperrt()} />;
}
