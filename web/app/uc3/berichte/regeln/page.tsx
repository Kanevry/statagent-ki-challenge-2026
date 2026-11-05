import { redirect } from "next/navigation";
import { regelsatzAus } from "@/components/uc3/navigation";

// Die Regeln stehen seit der UI-Regie v1 auf „Regeln und Klassifikationen“ (Anker #regeln). Die alte Route bleibt
// erreichbar und leitet weiter; der Regelsatz aus dem Such-Parameter geht mit.
export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ regelsatz?: string | string[] }> };

export default async function Regeln({ searchParams }: Props) {
  const regelsatz = regelsatzAus((await searchParams).regelsatz);
  redirect(`/uc3/klassifikationen${regelsatz === "v2" ? "?regelsatz=v2" : ""}#regeln`);
}
