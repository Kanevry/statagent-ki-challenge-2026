import type { Metadata } from "next";
import { StartSeite } from "@/components/uc1/seiten";

// /uc1 Situation erzählen. `?beispiel=pflege` spielt den aufgezeichneten Pflege-Durchlauf ohne Netz ab
// (Screenshots, Online-Demo). Dynamisch wegen searchParams, deshalb steht uc1 in EIGENE_ROUTE von [uc]/page.tsx.
export const metadata: Metadata = { title: "KI-Lotse · OneShotAndy" };
export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ beispiel?: string | string[] }> };

export default async function Uc1Start({ searchParams }: Props) {
  const { beispiel } = await searchParams;
  // Online-Demo lesend: Der Lotse antwortet nicht live (/api/uc1/frage → 403). Dann wird kein Formular angeboten,
  // sondern das aufgezeichnete Gespräch als Hauptaktion (UI-Regie 05.11.: kein Klick endet in einer roten Sperre).
  // KIC_ONLINE_UC1=1 zeigt online nur das Formular; die API bleibt trotzdem bei 403 (#173). Der Schalter ist nicht
  // gesetzt und darf es nicht werden: UC1 bleibt online aus, einen Entscheid für online gibt es nicht.
  const nurAufzeichnung = process.env.KIC_ONLINE_LESEND === "1" && process.env.KIC_ONLINE_UC1 !== "1";
  return <StartSeite beispiel={beispiel === "pflege"} nurAufzeichnung={nurAufzeichnung} />;
}
