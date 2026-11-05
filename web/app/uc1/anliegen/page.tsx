import { redirect } from "next/navigation";

// Frühere Anliegen speichert der Lotse nicht; die Seite wäre nur ein Leerzustand (totes Element, Urteil ui-regie-32).
// Alte Links führen zur Situation.
export default function Uc1Anliegen() {
  redirect("/uc1");
}
