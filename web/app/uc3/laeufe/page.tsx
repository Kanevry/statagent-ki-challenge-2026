import { redirect } from "next/navigation";

// /uc3/laeufe hat keine eigene Übersicht: alle Monatsläufe stehen auf /uc3.
export default function Laeufe() {
  redirect("/uc3");
}
