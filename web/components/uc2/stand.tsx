import { Fliesstext, Status, Ueberschrift, type StatusArt } from "@kic/ui/basis";
import { abbruchSatz, akteurName, kategorieWort, themaKurz } from "./namen";
import { endstand, zwischenstand, type FallZustand, type ThemaStand } from "./zustand";

// "Was gilt" (Owner-Vorgabe, auf einen Blick): je Thema Einigung, Mehrheit dafür, Mehrheit dagegen oder noch strittig,
// mit n dafür, m dagegen, k enthalten. Während der Verhandlung als Zwischenstand, nach dem Ende als Ergebnis.

const ART: Record<string, StatusArt> = { konsens: "ok", mehrheit: "ok", abgelehnt: "fehler", offener_konflikt: "warnung" };

function namen(ids: string[]): string {
  return ids.length === 0 ? "niemand" : ids.map(akteurName).join(", ");
}

/** Ein Satz über alle Themen: wo es Einigung gibt und was strittig bleibt. */
export function zusammenfassung(themen: ThemaStand[], titel: (id: string) => string): string {
  const gruppen: [string, string][] = [
    ["konsens", "Einig"],
    ["mehrheit", "Mehrheit dafür"],
    ["abgelehnt", "Mehrheit dagegen"],
    ["offener_konflikt", "Noch strittig"],
  ];
  return gruppen
    .map(([k, wort]) => {
      const ids = themen.filter((t) => t.kategorie === k).map((t) => titel(t.thema));
      return ids.length > 0 ? `${wort}: ${ids.join(", ")}.` : "";
    })
    .filter(Boolean)
    .join(" ");
}

export function Stand({ zustand }: { zustand: FallZustand }) {
  const ende = endstand(zustand);
  const zwischen = zwischenstand(zustand);
  const themen = ende ?? zwischen?.themen;
  if (!themen) return null;

  const fertig = ende !== null && zustand.status === "fertig";
  const titelVon = (id: string) => themaKurz(id, zustand.themen.find((t) => t.id === id)?.titel);
  const gesamt = themen[0] ? themen[0].dafuer.length + themen[0].dagegen.length + themen[0].enthalten.length : 0;
  const bewegte = new Set(zustand.ergebnis?.aenderungen.map((a) => a.akteur) ?? []);
  const ueberschrift = fertig
    ? "Am Ende gilt"
    : zustand.status === "abgebrochen"
      ? `Stand nach Runde ${zwischen?.runde ?? 0}, vor dem Abbruch`
      : `Zwischenstand nach Runde ${zwischen?.runde ?? 0}`;

  return (
    <section className="flex flex-col gap-4 border-t border-line pt-6" aria-labelledby="uc2-stand" data-spur="stand" data-fertig={fertig ? "ja" : "nein"}>
      <div className="flex flex-col gap-1">
        <Ueberschrift stufe={3} als="h2" id="uc2-stand">
          {ueberschrift}
        </Ueberschrift>
        <Fliesstext data-teil="zusammenfassung">{zusammenfassung(themen, titelVon)}</Fliesstext>
        {fertig && zustand.ergebnis && (
          <Fliesstext groesse={14} ton="gedaempft" data-teil="schluss">
            {`${abbruchSatz(zustand.ergebnis.runden, zustand.ergebnis.abbruch)} ${
              bewegte.size === 0
                ? "Niemand hat die Position geändert."
                : `${zustand.ergebnis.aenderungen.length === 1 ? "Eine Position hat" : `${zustand.ergebnis.aenderungen.length} Positionen haben`} sich bewegt, bei ${bewegte.size} von ${gesamt} Gruppen.`
            }`}
          </Fliesstext>
        )}
      </div>
      <ul className="grid gap-x-8 gap-y-5 md:grid-cols-2">
        {themen.map((t) => (
          <li key={t.thema} className="flex flex-col gap-2" data-thema={t.thema} data-kategorie={t.kategorie}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-display text-20 font-bold text-ink">{titelVon(t.thema)}</h3>
              <Status art={ART[t.kategorie] ?? "info"}>{kategorieWort(t.kategorie)}</Status>
            </div>
            <div className="flex h-3 gap-0.5" role="img" aria-label={`${t.dafuer.length} dafür, ${t.dagegen.length} dagegen, ${t.enthalten.length} enthalten`}>
              {t.dafuer.length > 0 && <span className="rounded-sm bg-gruen" style={{ flexGrow: t.dafuer.length }} />}
              {t.enthalten.length > 0 && <span className="rounded-sm bg-line" style={{ flexGrow: t.enthalten.length }} />}
              {t.dagegen.length > 0 && <span className="rounded-sm bg-err-fg" style={{ flexGrow: t.dagegen.length }} />}
            </div>
            <p className="font-sans text-14 font-medium text-ink" data-teil="zaehlung">
              {`${t.dafuer.length} von ${gesamt} dafür, ${t.dagegen.length} dagegen, ${t.enthalten.length} enthalten`}
            </p>
            <p className="font-sans text-12 text-slate">
              {`Dafür: ${namen(t.dafuer)}. Dagegen: ${namen(t.dagegen)}. Enthalten: ${namen(t.enthalten)}.`}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}
