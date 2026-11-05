import type { Metadata } from "next";
import { PraesentationSeite } from "@/components/praesentation/praesentation-seite";

// Folienschau vor der Jury (#59). Die Folien liegen als Markdown in web/content/slides/ (Format: README dort).
export const metadata: Metadata = { title: "Präsentation · OneShotAndy" };

type Props = { searchParams: Promise<{ folie?: string | string[] }> };

export default async function Praesentation({ searchParams }: Props) {
  return <PraesentationSeite folieParam={(await searchParams).folie} />;
}
