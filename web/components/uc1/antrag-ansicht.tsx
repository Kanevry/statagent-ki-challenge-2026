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
import { AufnahmeHinweis, einmal, Fundstelle, Kopf, OHNE_STELLE, SeitenKennzeichnung } from "./teile";

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
      <Fundstelle fundstelle={stelle.fundstelle} zitat={stelle.zitat} />
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
            <AntragVorbereitet key={`${a.art}-${a.sitzung_id}`} antrag={a} live={aufnahme === null} mitTitel={!einer} />
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

/** Die passenden nächsten Schritte: die, die die Stelle beim Namen oder Kürzel nennen; sonst alle. Jeder nur einmal. */
function schritteFuer(schritte: readonly string[], stelle: Pick<StellenGruppe, "name" | "kurz">): string[] {
  const namen = [stelle.name, stelle.kurz].filter((n): n is string => Boolean(n));
  const passend = schritte.filter((s) => namen.some((n) => s.includes(n)));
  return einmal(passend.length > 0 ? passend : schritte);
}

/** Eine Stelle mit allen Leistungen, für die sie zuständig ist; je Leistung die eigene Fundstelle mit eigenem Zitat. */
interface StellenGruppe {
  name: string;
  kurz: string | null;
  leistungen: Array<Pick<Traeger, "leistung" | "fundstelle" | "zitat">>;
}

/** Stellen aus der Antwort (traeger) und aus vorbereiteten Anträgen, gleiche Stelle einmal. */
function stellenGruppen(traeger: readonly Traeger[], antraege: readonly WebAntrag[]): StellenGruppe[] {
  const gruppen: StellenGruppe[] = [];
  const dazu = (name: string, kurz: string | null, eintrag: StellenGruppe["leistungen"][number]) => {
    let gruppe = gruppen.find((g) => g.name === name);
    if (!gruppe) {
      gruppe = { name, kurz, leistungen: [] };
      gruppen.push(gruppe);
    }
    // Dieselbe Leistung nur einmal; ein Eintrag mit Zitat ersetzt einen ohne.
    const da = gruppe.leistungen.findIndex((l) => l.leistung === eintrag.leistung && l.fundstelle === eintrag.fundstelle);
    if (da < 0) gruppe.leistungen.push(eintrag);
    else if (!gruppe.leistungen[da]?.zitat && eintrag.zitat) gruppe.leistungen[da] = eintrag;
  };
  for (const t of traeger) dazu(traegerName(t), t.stelle, { leistung: t.leistung, fundstelle: t.fundstelle, zitat: t.zitat });
  for (const a of antraege) {
    if (!a.stelle) continue;
    const leistung = antragLeistung(a.art);
    // Nennt die Antwort die Leistung schon bei dieser Stelle, kommt sie aus dem Antrag nicht doppelt dazu.
    if (gruppen.some((g) => g.name === a.stelle?.name && g.leistungen.some((l) => l.leistung === leistung))) continue;
    dazu(a.stelle.name, a.stelle.kurz ?? null, { leistung, fundstelle: a.stelle.fundstelle ?? null, zitat: a.stelle.zitat ?? null });
  }
  return gruppen;
}

/** /uc1/stelle: Schritt 4, die zuständige Stelle aus der Antwort (traeger) oder aus dem Antrag. */
export function StelleSeite() {
  const { verlauf, antrag, aufnahme } = useLotse();
  const letzte = verlauf.at(-1)?.antwort;
  const mitAntwort = letzte?.verhalten === "antwort";
  const stellen = stellenGruppen(mitAntwort ? letzte.traeger : [], antrag.art === "bereit" ? antrag.antraege : []);
  const schritte = letzte?.naechste_schritte ?? [];
  return (
    <>
      <Kopf
        titel={stellen.length === 1 ? "Diese Stelle ist zuständig" : "Zuständige Stelle"}
        unter={stellen.length > 0 ? "Dort stellen Sie den Antrag und klären Ihre Fragen." : "Hier steht die Stelle, die für Sie zuständig ist."}
        schritt={4}
      />
      <AufnahmeHinweis aufnahme={aufnahme} />
      <SeitenKennzeichnung />
      {stellen.length === 0 && mitAntwort ? (
        <Leerzustand
          satz={`${OHNE_STELLE} Fragen Sie bei Ihrer Sozialversicherung nach.`}
          aktion={
            <Link href="/uc1" className={knopfKlassen("sekundaer", "min-h-11")}>
              Zurück zur Antwort
            </Link>
          }
        />
      ) : stellen.length === 0 ? (
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
                key={stelle.name}
                aria-label={stelle.name}
                data-uc1-stelle=""
                className="flex flex-col gap-4 rounded border border-line bg-white p-4 md:p-6"
              >
                <Fliesstext className="font-semibold">{stelle.name}</Fliesstext>
                {stelle.leistungen.length > 0 && (
                  <ul className="flex flex-col gap-3" aria-label="Zuständig für">
                    {stelle.leistungen.map((l) => (
                      <li
                        key={`${l.leistung ?? ""}-${l.fundstelle ?? ""}`}
                        data-uc1-stelle-leistung={l.leistung ?? ""}
                        className="flex flex-col items-start gap-1 border-b border-line pb-3 last:border-b-0 last:pb-0"
                      >
                        {l.leistung && <Fliesstext groesse={14} className="font-semibold">{leistungName(l.leistung)}</Fliesstext>}
                        <Fundstelle fundstelle={l.fundstelle} zitat={l.zitat} />
                      </li>
                    ))}
                  </ul>
                )}
                {passend.length > 0 && (
                  <div className="flex flex-col gap-2">
                    <Ueberschrift stufe={3} als="h2">
                      So geht es weiter
                    </Ueberschrift>
                    <ol className="flex list-decimal flex-col gap-1 pl-6 font-sans text-16 text-ink">
                      {passend.map((s) => (
                        <li key={s}>{s}</li>
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
