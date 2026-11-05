"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Akzent, Fliesstext, Knopf, knopfKlassen, Leerzustand, Status, Tabelle, Ueberschrift } from "@kic/ui/basis";
import { antragUnterzeile, type AntragBeleg, type WebAntrag } from "./antrag";
import { traegerName, type Traeger } from "./antwort";
import { EntwurfPruefung } from "./entwurf-pruefung";
import { antragLeistung, antragName, leistungName } from "./leistungen";
import { useLotse } from "./lotse-kontext";
import { BelegChip } from "./beleg-chip";
import { AufnahmeHinweis, Kopf } from "./teile";

// Schritt 3 „Antrag vorbereitet“ (Pen-Frame ZHSFO) und Schritt 4 „Stelle“. Der Lotse füllt aus, was im Gespräch
// gesagt wurde; abgeschickt wird nichts (`eingereicht: false` aus dem Kern).

function QuellenBeleg({ kurz, beleg }: { kurz: string; beleg: AntragBeleg | null }) {
  if (!beleg) return null;
  return <BelegChip quelle={`${kurz}, S. ${beleg.seite}`} zitat={beleg.wortlaut} />;
}

function Kasten({ titel, als, children }: { titel: string; als: "h2" | "h3"; children: ReactNode }) {
  return (
    <section aria-label={titel} className="flex flex-col gap-3 rounded border border-line bg-white p-4 md:p-6">
      <Ueberschrift stufe={3} als={als}>
        {titel}
      </Ueberschrift>
      {children}
    </section>
  );
}

function StelleText({ stelle }: { stelle: Pick<Traeger, "name" | "fundstelle" | "zitat"> }) {
  return (
    <div className="flex flex-col items-start gap-2">
      <Fliesstext className="font-semibold">{stelle.name}</Fliesstext>
      {stelle.zitat && stelle.fundstelle && <BelegChip quelle={stelle.fundstelle} zitat={stelle.zitat} />}
    </div>
  );
}

/** Titel eines vorbereiteten Antrags, wie im Pen-Frame ZHSFO. */
export function antragTitel(antrag: Pick<WebAntrag, "art">): string {
  return `${antragName(antrag.art)}: Antrag vorbereitet`;
}

/** `mitTitel`: eigene Überschrift, nur wenn mehrere Anträge auf der Seite stehen; sonst trägt die Seite den Titel. */
function AntragVorbereitet({ antrag, live, mitTitel }: { antrag: WebAntrag; live: boolean; mitTitel: boolean }) {
  const titelId = `uc1-antrag-${antrag.art}`;
  // Überschriften ohne Sprung: unter der h1 der Seite h2, unter dem eigenen h2-Titel h3.
  const ebene = mitTitel ? "h3" : "h2";
  const pdf = `/api/uc1/antrag/pdf?art=${encodeURIComponent(antrag.art)}&sitzung=${encodeURIComponent(antrag.sitzung_id)}`;
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

      {!antrag.eingereicht && (
        <Akzent art="warnung">
          <Fliesstext className="font-semibold">Abgeschickt wird nichts. Sie prüfen, unterschreiben und senden selbst.</Fliesstext>
        </Akzent>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="flex min-w-0 flex-col gap-6">
          {antrag.befuellt.length > 0 && (
            <div className="overflow-x-auto">
              <Tabelle
                beschriftung="Diese Angaben stehen schon im Formular"
                beschriftungZeigen
                spalten={[
                  { schluessel: "feld", titel: "Feld" },
                  { schluessel: "wert", titel: "Wert" },
                  { schluessel: "herkunft", titel: "Herkunft" },
                ]}
                zeilen={antrag.befuellt.map((f) => ({ feld: f.feld, wert: f.wert, herkunft: "Ihre Angabe" }))}
                zeilenSchluessel={(zeile, i) => `${String(zeile.feld)}-${i}`}
              />
            </div>
          )}

          {antrag.noch_offen.length > 0 && (
            <section aria-labelledby={`${titelId}-offen`} className="flex flex-col gap-3">
              <Ueberschrift stufe={3} als={ebene} id={`${titelId}-offen`}>
                Das ergänzen Sie selbst
              </Ueberschrift>
              <ul className="flex flex-col gap-3">
                {antrag.noch_offen.map((punkt) => (
                  <li key={punkt.id} data-uc1-offen={punkt.id}>
                    <Akzent art="warnung" className="flex flex-col items-start gap-1 py-1">
                      <Status art="warnung" klein>
                        bitte ergänzen
                      </Status>
                      <Fliesstext>{punkt.text}</Fliesstext>
                      <QuellenBeleg kurz={antrag.kurz} beleg={punkt.beleg} />
                    </Akzent>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>

        <div className="flex min-w-0 flex-col gap-4">
          {antrag.unterlagen.length > 0 && (
            <Kasten titel="Unterlagen" als={ebene}>
              <ul className="flex flex-col gap-3">
                {antrag.unterlagen.map((u) => (
                  <li key={u.text} className="flex flex-col items-start gap-1 border-b border-line pb-3 last:border-b-0 last:pb-0">
                    <Fliesstext groesse={14}>{u.text}</Fliesstext>
                    {u.bedingung && (
                      <Fliesstext groesse={12} ton="gedaempft">
                        {`Nur nötig ${u.bedingung}.`}
                      </Fliesstext>
                    )}
                    <QuellenBeleg kurz={antrag.kurz} beleg={u.beleg} />
                  </li>
                ))}
              </ul>
            </Kasten>
          )}
          {antrag.stelle && (
            <Kasten titel="Zuständige Stelle" als={ebene}>
              <StelleText stelle={antrag.stelle} />
              <Fliesstext groesse={14}>
                {`Weg: Sie unterschreiben den Antrag und schicken ihn selbst an die ${antrag.stelle.kurz ?? antrag.stelle.name}.`}
              </Fliesstext>
              {antrag.begruendung && (
                <div className="flex flex-col items-start gap-1">
                  <Fliesstext groesse={12} ton="gedaempft">{`Warum dieses Formular: ${antrag.begruendung}`}</Fliesstext>
                  <QuellenBeleg kurz={antrag.kurz} beleg={antrag.begruendung_beleg} />
                </div>
              )}
            </Kasten>
          )}
        </div>
      </div>

      <EntwurfPruefung antrag={antrag} live={live} pdf={pdf} ebene={ebene} />

      <div className="flex flex-wrap items-center gap-4">
        <Link href="/uc1/stelle" className={knopfKlassen("sekundaer", "min-h-11")}>
          Weiter zur zuständigen Stelle
        </Link>
      </div>
    </article>
  );
}

/** /uc1/antrag: Schritt 3. Ohne Antwort ein ehrlicher Leerzustand; mit Antrag-Angebot der Knopf zum Vorbereiten. */
export function AntragSeite() {
  const { antrag, verlauf, aufnahme, aufgezeichnet, antragVorbereiten } = useLotse();
  const letzte = verlauf.at(-1)?.antwort;
  const angebot = letzte?.verhalten === "antwort" ? letzte.antraege : [];
  // Im Beispiel gibt es nur aufgezeichnete Anträge; die anderen nennt ein ehrlicher Satz.
  const ohneAufnahme = aufgezeichnet === null ? [] : angebot.filter((art) => !aufgezeichnet.includes(art));
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
        <AufnahmeHinweis aufnahme={aufnahme} />
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
            <AntragVorbereitet key={`${a.art}-${a.sitzung_id}`} antrag={a} live={aufnahme === null} mitTitel={!einer} />
          ))}
        {antrag.art === "bereit" && ohneAufnahme.length > 0 && (
          <Fliesstext groesse={14} ton="gedaempft" data-testid="uc1-ohne-aufnahme">
            {`Für ${ohneAufnahme.map(antragName).join(" und ")} gibt es auch einen Antrag. Im Beispiel ist er nicht aufgezeichnet. Im echten Gespräch füllt der Lotse ihn auch aus.`}
          </Fliesstext>
        )}
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

/** Die passenden nächsten Schritte: die, die die Stelle beim Namen oder Kürzel nennen; sonst alle. */
function schritteFuer(schritte: readonly string[], stelle: Pick<Traeger, "name" | "stelle">): string[] {
  const namen = [stelle.name, stelle.stelle].filter((n): n is string => Boolean(n));
  const passend = schritte.filter((s) => namen.some((n) => s.includes(n)));
  return passend.length > 0 ? passend : [...schritte];
}

/** /uc1/stelle: Schritt 4, die zuständige Stelle aus der Antwort (traeger) oder aus dem Antrag. */
export function StelleSeite() {
  const { verlauf, antrag, aufnahme } = useLotse();
  const letzte = verlauf.at(-1)?.antwort;
  // Dieselbe Stelle für zwei Leistungen (Pflegegeld und Reha bei der PVA) nur einmal, mit beiden Fundstellen.
  const stellen: Traeger[] = [];
  for (const t of letzte?.verhalten === "antwort" ? letzte.traeger : []) {
    const da = stellen.find((s) => traegerName(s) === traegerName(t));
    if (!da) stellen.push({ ...t });
    else if (t.fundstelle && !da.fundstelle?.includes(t.fundstelle)) {
      da.fundstelle = da.fundstelle ? `${da.fundstelle}; ${t.fundstelle}` : t.fundstelle;
    }
  }
  if (antrag.art === "bereit") {
    for (const a of antrag.antraege) {
      if (a.stelle && !stellen.some((s) => traegerName(s) === a.stelle?.name)) {
        stellen.push({ leistung: antragLeistung(a.art), stelle: a.stelle.kurz, name: a.stelle.name, fundstelle: a.stelle.fundstelle, zitat: a.stelle.zitat });
      }
    }
  }
  const schritte = letzte?.naechste_schritte ?? [];
  return (
    <>
      <Kopf
        titel={stellen.length === 1 ? "Diese Stelle ist zuständig" : "Zuständige Stelle"}
        unter={stellen.length > 0 ? "Dort stellen Sie den Antrag und klären Ihre Fragen." : "Hier steht die Stelle, die für Sie zuständig ist."}
        schritt={4}
      />
      <AufnahmeHinweis aufnahme={aufnahme} />
      {stellen.length === 0 ? (
        <Leerzustand
          satz="Erst eine Situation erzählen, dann steht hier die zuständige Stelle."
          aktion={
            <Link href="/uc1" className={knopfKlassen("sekundaer", "min-h-11")}>
              Zur Situation
            </Link>
          }
        />
      ) : (
        <div className="flex max-w-3xl flex-col gap-6">
          {stellen.map((stelle) => {
            const passend = schritteFuer(schritte, stelle);
            return (
              <section
                key={traegerName(stelle)}
                aria-label={traegerName(stelle)}
                data-uc1-stelle=""
                className="flex flex-col gap-4 rounded border border-line bg-white p-4 md:p-6"
              >
                {stelle.leistung && (
                  <Fliesstext groesse={14} ton="gedaempft">{`Für ${leistungName(stelle.leistung)}`}</Fliesstext>
                )}
                <StelleText stelle={stelle} />
                {passend.length > 0 && (
                  <div className="flex flex-col gap-2">
                    <Ueberschrift stufe={3} als="h2">
                      So geht es weiter
                    </Ueberschrift>
                    <ol className="flex list-decimal flex-col gap-1 pl-6 font-sans text-16 text-ink">
                      {passend.map((s, i) => (
                        <li key={`${i}-${s}`}>{s}</li>
                      ))}
                    </ol>
                  </div>
                )}
              </section>
            );
          })}
          <Fliesstext>Einen Termin vereinbaren Sie direkt bei der Stelle.</Fliesstext>
        </div>
      )}
    </>
  );
}
