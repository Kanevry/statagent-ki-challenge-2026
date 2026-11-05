import type { Metadata } from "next";
import { StartSeite } from "@/components/uc1/seiten";

// /uc1 Situation erzählen. `?beispiel=pflege` spielt den aufgezeichneten Pflege-Durchlauf ohne Netz ab
// (Screenshots, Online-Demo). Dynamisch wegen searchParams, deshalb steht uc1 in EIGENE_ROUTE von [uc]/page.tsx.
export const metadata: Metadata = { title: "KI-Lotse · OneShotAndy" };

type Props = { searchParams: Promise<{ beispiel?: string | string[] }> };

export default async function Uc1Start({ searchParams }: Props) {
  const { beispiel } = await searchParams;
  return <StartSeite beispiel={beispiel === "pflege"} />;
}
