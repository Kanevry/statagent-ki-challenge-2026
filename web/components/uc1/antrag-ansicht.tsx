"use client";

import Link from "next/link";
import { Fliesstext, Knopf, knopfKlassen, Leerzustand, Status, Tabelle, Ueberschrift } from "@kic/ui/basis";
import { antragUnterzeile, offenNachSeite, type AntragBeleg, type WebAntrag } from "./antrag";
import type { Traeger } from "./antwort";
import { EntwurfPruefung } from "./entwurf-pruefung";
import { antragLeistung, antragName } from "./leistungen";
import { useLotse } from "./lotse-kontext";
import { BelegChip } from "./beleg-chip";
import { StelleKasten, stellenGruppen } from "./stelle";
import { Kopf, SeitenKennzeichnung } from "./teile";

// Schritt 3 „Antrag vorbereitet“ (Pen-Frame ZHSFO, Urteil ui-regie-32). Der Lotse füllt aus, was im Gespräch gesagt
// wurde; abgeschickt wird nichts (`eingereicht: false` aus dem Kern). Rechts stehen „Entwurf prüfen“ (ab md beim
// Scrollen fest) und die zuständige Stelle; eine eigene Stelle-Seite gibt es nicht mehr.

function QuellenBeleg({ kurz, beleg }: { kurz: string; beleg: AntragBeleg | null }) {
  if (!beleg) return null;
  return <BelegChip quelle={`${kurz}, S. ${beleg.seite}`} zitat={beleg.wortlaut} />;
}

/** Titel eines vorbereiteten Antrags, wie im Pen-Frame ZHSFO. */
export function antragTitel(antrag: Pick<WebAntrag, "art">): string {
  return `${antragName(antrag.art)}: Antrag vorbereitet`;
}

const ZUSAMMENFASSUNG =
  "inline-flex min-h-11 cursor-pointer items-center font-sans text-14 font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gruen";

/** `mitTitel`: eigene Überschrift, nur wenn mehrere Anträge auf der Seite stehen; sonst trägt die Seite den Titel. */
function AntragVorbereitet({
  antrag,
  traeger,
  live,
  mitTitel,
}: {
  antrag: WebAntrag;
  traeger: readonly Traeger[];
  live: boolean;
  mitTitel: boolean;
}) {
  const titelId = `uc1-antrag-${antrag.art}`;
  // Überschriften ohne Sprung: unter der h1 der Seite h2, unter dem eigenen h2-Titel h3.
  const ebene = mitTitel ? "h3" : "h2";
  const pdf = `/api/uc1/antrag/pdf?art=${encodeURIComponent(antrag.art)}&sitzung=${encodeURIComponent(antrag.sitzung_id)}`;
  const leistung = antragLeistung(antrag.art);
  const gruppen = stellenGruppen(
    traeger.filter((t) => t.leistung === leistung),
    [antrag],
  );
  const mitDetails = antrag.unterlagen.length > 0 || Boolean(antrag.begruendung);
  return (
    <article aria-label={antragTitel(antrag)} className="flex flex-col gap-6" data-uc1-antrag={antrag.art}>
      {mitTitel && (
        <div className="flex flex-col gap-1">
          <Ueberschrift stufe={3} als="h2" id={titelId}>
            {antragTitel(antrag)}
          </Ueberschrift>
          <Fliesstext ton="gedaempft">{antragUnterzeile(antrag)}</Fliesstext>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] md:items-start">
        {/* Mobil direkt unter der Überschrift, ab md rechts oben und beim Scrollen fest. */}
        <aside aria-label="Prüfen und zuständige Stelle" className="flex min-w-0 flex-col gap-4 md:sticky md:top-4 md:col-start-2 md:row-start-1">
          <EntwurfPruefung antrag={antrag} live={live} pdf={pdf} ebene={ebene} />
          <div className="hidden md:block">
            <StelleKasten gruppen={gruppen} als={ebene} />
          </div>
        </aside>

        <div className="flex min-w-0 flex-col gap-6 md:col-start-1 md:row-start-1">
          {!antrag.eingereicht && (
            <Fliesstext className="font-semibold">Abgeschickt wird nichts. Sie prüfen, unterschreiben und senden selbst.</Fliesstext>
          )}

          {antrag.befuellt.length > 0 && (
            <div className="overflow-x-auto">
              <Tabelle
                beschriftung="Diese Angaben stammen aus Ihrem Gespräch."
                beschriftungZeigen
                spalten={[
                  { schluessel: "feld", titel: "Feld" },
                  { schluessel: "wert", titel: "Wert" },
                ]}
                zeilen={antrag.befuellt.map((f) => ({ feld: f.feld, wert: f.wert }))}
                zeilenSchluessel={(zeile, i) => `${String(zeile.feld)}-${i}`}
              />
            </div>
          )}

          {antrag.noch_offen.length > 0 && (
            <section aria-labelledby={`${titelId}-offen`} className="flex flex-col gap-3">
              <Ueberschrift stufe={3} als={ebene} id={`${titelId}-offen`}>
                Das ergänzen Sie selbst
              </Ueberschrift>
              {/* Je Formularseite eine Gruppe mit genau einem Beleg an der Gruppenzeile; die Nummern laufen durch. */}
              {offenNachSeite(antrag.noch_offen).map((gruppe) => {
                const name = gruppe.seite === null ? "Ohne Seitenangabe" : `Seite ${gruppe.seite}`;
                return (
                  <div key={gruppe.seite ?? "ohne"} role="group" aria-label={name} className="flex flex-col gap-2" data-uc1-offen-seite={gruppe.seite ?? ""}>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                      <Fliesstext className="font-semibold">{name}</Fliesstext>
                      {gruppe.seite !== null && gruppe.wortlaut && (
                        <BelegChip
                          quelle={`${antrag.kurz}, S. ${gruppe.seite}`}
                          zitat={gruppe.wortlaut}
                          className="[&_blockquote]:whitespace-pre-line"
                        />
                      )}
                    </div>
                    <ol start={gruppe.start} className="flex list-decimal flex-col gap-3 pl-6 font-sans text-16 text-ink">
                      {gruppe.punkte.map((punkt) => (
                        <li key={punkt.id} data-uc1-offen={punkt.id}>
                          <Fliesstext>{punkt.text}</Fliesstext>
                        </li>
                      ))}
                    </ol>
                  </div>
                );
              })}
            </section>
          )}

          {mitDetails && (
            <details className="border-t border-line pt-2" data-uc1-unterlagen="">
              <summary className={ZUSAMMENFASSUNG}>
                {antrag.unterlagen.length > 0 ? "Details: Unterlagen" : "Details: Formular"}
              </summary>
              <div className="flex flex-col gap-4 pt-2">
                {antrag.unterlagen.length > 0 && (
                  <ul className="flex flex-col gap-3" aria-label="Unterlagen">
                    {antrag.unterlagen.map((u) => (
                      <li key={u.text} className="flex flex-col items-start gap-1 border-b border-line pb-3 last:border-b-0 last:pb-0">
                        <Fliesstext groesse={14}>{u.text}</Fliesstext>
                        {u.bedingung && (
                          <Fliesstext groesse={14} ton="gedaempft">
                            {`Nur nötig ${u.bedingung}.`}
                          </Fliesstext>
                        )}
                        <QuellenBeleg kurz={antrag.kurz} beleg={u.beleg} />
                      </li>
                    ))}
                  </ul>
                )}
                {antrag.begruendung && (
                  <div className="flex flex-col items-start gap-1">
                    <Fliesstext groesse={14} ton="gedaempft">{`Warum dieses Formular: ${antrag.begruendung}`}</Fliesstext>
                    <QuellenBeleg kurz={antrag.kurz} beleg={antrag.begruendung_beleg} />
                  </div>
                )}
              </div>
            </details>
          )}

          <div className="md:hidden">
            <StelleKasten gruppen={gruppen} als={ebene} />
          </div>
        </div>
      </div>
    </article>
  );
}

/** /uc1/antrag: Schritt 3. Ohne Antwort ein ehrlicher Leerzustand; mit Antrag-Angebot der Knopf zum Vorbereiten. */
export function AntragSeite() {
  const { antrag, verlauf, aufnahme, antragVorbereiten } = useLotse();
  const traeger = verlauf.at(-1)?.antwort.traeger ?? [];
  const letzte = verlauf.at(-1)?.antwort;
  const angebot = letzte?.verhalten === "antwort" ? letzte.antraege : [];
  const einer = antrag.art === "bereit" && antrag.antraege.length === 1 ? antrag.antraege[0] : undefined;
  return (
    <>
      <Kopf
        titel={einer ? antragTitel(einer) : "Antrag vorbereiten"}
        unter={einer ? antragUnterzeile(einer) : "Der Lotse füllt aus, was Sie erzählt haben. Den Rest ergänzen Sie selbst."}
        schritt={3}
      />
      <div className="flex flex-col gap-6" aria-busy={antrag.art === "laden"}>
        <p role="status" aria-live="polite" className="sr-only">
          {antrag.art === "laden" ? "Der Lotse füllt den Antrag aus." : antrag.art === "fehler" ? antrag.meldung : ""}
        </p>
        <SeitenKennzeichnung />
        {antrag.art === "laden" && <Fliesstext ton="gedaempft">Der Lotse füllt den Antrag aus. Das dauert einen Moment.</Fliesstext>}
        {antrag.art === "fehler" && (
          <div className="flex flex-col items-start gap-4" data-testid="uc1-antrag-fehler">
            <Status art="fehler">{antrag.meldung}</Status>
            {antrag.replay ? (
              <Link href="/uc1?beispiel=pflege" className={knopfKlassen("sekundaer", "min-h-11")}>
                Beispiel ansehen
              </Link>
            ) : angebot.length > 0 ? (
              <Knopf art="sekundaer" className="min-h-11" onClick={() => void antragVorbereiten(angebot)}>
                Noch einmal versuchen
              </Knopf>
            ) : null}
          </div>
        )}
        {antrag.art === "bereit" &&
          antrag.antraege.map((a) => (
            <AntragVorbereitet key={`${a.art}-${a.sitzung_id}`} antrag={a} traeger={traeger} live={aufnahme === null} mitTitel={!einer} />
          ))}
        {antrag.art === "bereit" &&
          antrag.fehler.map((f) => (
            <div key={f.art} className="flex flex-col items-start gap-4" data-testid="uc1-antrag-fehler" data-uc1-antrag-fehler={f.art}>
              <Status art="fehler">{`Antrag auf ${antragName(f.art)}: ${f.meldung}`}</Status>
              <Knopf art="sekundaer" className="min-h-11" onClick={() => void antragVorbereiten([f.art])}>
                {`${antragName(f.art)} noch einmal versuchen`}
              </Knopf>
            </div>
          ))}
        {antrag.art === "leer" &&
          (angebot.length > 0 ? (
            <Leerzustand
              satz={`Für ${angebot.map(antragName).join(" und ")} gibt es einen Antrag. Der Lotse kann ihn vorausfüllen.`}
              aktion={<Knopf className="min-h-11" onClick={() => void antragVorbereiten(angebot)}>Antrag vorbereiten</Knopf>}
            />
          ) : (
            <Leerzustand
              satz="Erst eine Situation erzählen. Wenn es dafür einen Antrag gibt, bereitet der Lotse ihn hier vor."
              aktion={
                <Link href="/uc1" className={knopfKlassen("sekundaer", "min-h-11")}>
                  Zur Situation
                </Link>
              }
            />
          ))}
      </div>
    </>
  );
}
