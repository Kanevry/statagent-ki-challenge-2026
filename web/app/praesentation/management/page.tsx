import type { Metadata } from "next";
import path from "node:path";
import { PraesentationSeite } from "@/components/praesentation/praesentation-seite";

// Management-Fassung: 11 Folien, 10 Minuten, Titel als ganze Sätze. Quelle: web/content/slides-management/.
export const metadata: Metadata = { title: "Präsentation Management · OneShotAndy" };

const ORDNER = path.join(process.cwd(), "content", "slides-management");

type Props = { searchParams: Promise<{ folie?: string | string[] }> };

export default async function PraesentationManagement({ searchParams }: Props) {
  return <PraesentationSeite ordner={ORDNER} folieParam={(await searchParams).folie} />;
}
