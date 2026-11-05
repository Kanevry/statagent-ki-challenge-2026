import Link from "next/link";
import type { ReactNode } from "react";
import { knopfKlassen, Leerzustand } from "@kic/ui/basis";
import { inlineText, parseInline, type Block, type Inline } from "../../lib/praesentation/markdown";
import { istInterneRoute, type Folie } from "../../lib/praesentation/folien";
import { liveKomponente } from "../../lib/praesentation/live";
import { BUEHNE } from "./buehne-klassen";

// Server-Komponenten: aus den Daten des Parsers entstehen React-Elemente, nie HTML-Text.

export function InlineText({ inline }: { inline: readonly Inline[] }) {
  return (
    <>
      {inline.map((teil, i) =>
        teil.art === "fett" ? (
          <strong key={i} className="font-bold">
            {teil.text}
          </strong>
        ) : teil.art === "code" ? (
          <code key={i} className="font-mono text-[0.85em]">
            {teil.text}
          </code>
        ) : (
          <span key={i}>{teil.text}</span>
        ),
      )}
    </>
  );
}

/** Sprechtext unter der Bühne: erbt die Farbe, damit er hell und im Vollbild dunkel stehen kann. */
export function NotizBlocks({ blocks }: { blocks: readonly Block[] }) {
  return (
    <div className="flex flex-col gap-2 font-sans text-14">
      {blocks.map((b, i) => {
        switch (b.art) {
          case "ueberschrift":
            return (
              <h3 key={i} className="font-bold">
                <InlineText inline={b.inline} />
              </h3>
            );
          case "liste": {
            const Tag = b.geordnet ? "ol" : "ul";
            return (
              <Tag key={i} className={`flex flex-col gap-1 pl-5 ${b.geordnet ? "list-decimal" : "list-disc"}`}>
                {b.punkte.map((p, j) => (
                  <li key={j}>
                    <InlineText inline={p} />
                  </li>
                ))}
              </Tag>
            );
          }
          case "tabelle":
            return null;
          default:
            return (
              <p key={i}>
                <InlineText inline={b.inline} />
              </p>
            );
        }
      })}
    </div>
  );
}

const TEXT = "font-sans text-[44px] leading-[1.3] text-paper";

function BuehnenBlocks({ blocks, schritte = false }: { blocks: readonly Block[]; schritte?: boolean }) {
  return (
    <>
      {blocks.map((b, i) => {
        switch (b.art) {
          case "ueberschrift":
            return (
              <h2 key={i} className="font-display text-[56px] font-bold leading-[1.15] text-paper">
                <InlineText inline={b.inline} />
              </h2>
            );
          case "liste":
            if (schritte && b.geordnet) {
              return (
                <ol key={i} className="flex flex-col">
                  {b.punkte.map((p, j) => (
                    <li key={j} className={`flex items-baseline gap-[40px] border-b py-[28px] ${BUEHNE.linie}`}>
                      <span className="w-[80px] font-display text-[64px] font-bold tabular-nums text-gelb">{j + 1}</span>
                      <span className={TEXT}>
                        <InlineText inline={p} />
                      </span>
                    </li>
                  ))}
                </ol>
              );
            }
            return b.geordnet ? (
              <ol key={i} className={`flex list-decimal flex-col gap-[20px] pl-[64px] ${TEXT}`}>
                {b.punkte.map((p, j) => (
                  <li key={j}>
                    <InlineText inline={p} />
                  </li>
                ))}
              </ol>
            ) : (
              <ul key={i} className={`flex list-disc flex-col gap-[20px] pl-[64px] ${TEXT}`}>
                {b.punkte.map((p, j) => (
                  <li key={j}>
                    <InlineText inline={p} />
                  </li>
                ))}
              </ul>
            );
          case "tabelle":
            return (
              <table key={i} className="w-full border-collapse text-left font-sans text-[34px] text-paper">
                <thead>
                  <tr className={`border-b ${BUEHNE.linie}`}>
                    {b.kopf.map((z, j) => (
                      <th key={j} scope="col" className={`py-[16px] pr-[32px] text-[28px] font-normal ${BUEHNE.gedaempft}`}>
                        <InlineText inline={z} />
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {b.zeilen.map((zeile, j) => (
                    <tr key={j} className={`border-b ${BUEHNE.linie}`}>
                      {zeile.map((z, k) => (
                        <td key={k} className="py-[16px] pr-[32px]">
                          <InlineText inline={z} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            );
          default:
            return (
              <p key={i} className={TEXT}>
                <InlineText inline={b.inline} />
              </p>
            );
        }
      })}
    </>
  );
}

/** Die Hauptüberschrift ist die erste Zeile mit `#`; fehlt sie, gilt der Titel aus dem Frontmatter. */
function zerlege(folie: Folie): { kopf: Inline[]; rest: Block[] } {
  const erste = folie.inhalt[0];
  return erste?.art === "ueberschrift"
    ? { kopf: erste.inline, rest: folie.inhalt.slice(1) }
    : { kopf: parseInline(folie.titel), rest: folie.inhalt };
}

function LiveInhalt({ route }: { route: string | undefined }) {
  const Live = liveKomponente(route);
  if (Live) return <Live />;
  return (
    <Leerzustand
      satz={route ? "Diese Seite ist nicht für die Präsentation freigegeben." : "Für diese Folie fehlt die Route."}
      aktion={
        istInterneRoute(route) ? (
          <Link href={route} className={knopfKlassen("sekundaer")}>
            Seite öffnen
          </Link>
        ) : undefined
      }
    />
  );
}

const RAHMEN = "flex h-full w-full flex-col";

/** Eine Folie auf der 1920 × 1080 Bühne, je nach Layout. */
export function FolieAnsicht({ folie }: { folie: Folie }): ReactNode {
  const { kopf, rest } = zerlege(folie);
  const nebentext = BUEHNE.gedaempft;

  if (folie.layout === "titel") {
    const [erster, ...weitere] = rest;
    return (
      <div data-layout="titel" className={`${RAHMEN} justify-center gap-[48px] px-[160px] py-[120px]`}>
        <h1 className="max-w-[1500px] text-balance font-display text-[148px] font-bold leading-[1.02] text-paper">
          <InlineText inline={kopf} />
        </h1>
        {erster?.art === "absatz" && (
          <p className="max-w-[1400px] text-pretty font-sans text-[56px] leading-[1.25] text-paper">
            <InlineText inline={erster.inline} />
          </p>
        )}
        <div className={`flex flex-col gap-[16px] font-sans text-[36px] ${nebentext}`}>
          {weitere.map((b, i) =>
            b.art === "absatz" ? (
              <p key={i}>
                <InlineText inline={b.inline} />
              </p>
            ) : null,
          )}
        </div>
      </div>
    );
  }

  if (folie.layout === "zahl") {
    const herkunft = rest.findIndex((b) => b.art === "absatz" && /^(Herkunft|Beleg):/i.test(inlineText(b.inline)));
    const belegBlock = herkunft === -1 ? undefined : rest[herkunft];
    const belegZeile = folie.beleg ?? (belegBlock?.art === "absatz" ? inlineText(belegBlock.inline) : undefined);
    const uebrig = rest.filter((_, i) => i !== herkunft);
    return (
      <div data-layout="zahl" className={`${RAHMEN} justify-center gap-[40px] px-[160px] py-[120px]`}>
        {folie.zahl !== undefined && (
          <h1 className="font-display text-[56px] font-bold leading-[1.15] text-paper">
            <InlineText inline={kopf} />
          </h1>
        )}
        {folie.zahl !== undefined ? (
          <p className="font-display text-[260px] font-bold leading-none tabular-nums text-gelb">{folie.zahl}</p>
        ) : (
          <h1 className="font-display text-[260px] font-bold leading-none tabular-nums text-gelb">
            <InlineText inline={kopf} />
          </h1>
        )}
        <div className="flex max-w-[1500px] flex-col gap-[24px]">
          <BuehnenBlocks blocks={uebrig} />
        </div>
        {belegZeile && (
          <p className={`mt-auto border-t pt-[24px] font-mono text-[28px] ${BUEHNE.linie} ${nebentext}`}>{belegZeile}</p>
        )}
      </div>
    );
  }

  if (folie.layout === "live") {
    return (
      <div data-layout="live" className={`${RAHMEN} gap-[32px] px-[96px] py-[72px]`}>
        <div className="flex items-baseline gap-[48px]">
          <h1 className="shrink-0 font-display text-[64px] font-bold leading-[1.1] text-paper">
            <InlineText inline={kopf} />
          </h1>
          {rest[0]?.art === "absatz" && (
            <p className={`font-sans text-[32px] leading-[1.3] ${nebentext}`}>
              <InlineText inline={rest[0].inline} />
            </p>
          )}
        </div>
        <div data-live-route={folie.route} className="min-h-0 flex-1 overflow-auto rounded bg-paper p-[56px] text-ink">
          <LiveInhalt route={folie.route} />
        </div>
      </div>
    );
  }

  return (
    <div data-layout={folie.layout} className={`${RAHMEN} justify-center gap-[36px] px-[160px] py-[100px]`}>
      <h1 className="max-w-[1500px] text-balance font-display text-[88px] font-bold leading-[1.08] text-paper">
        <InlineText inline={kopf} />
      </h1>
      <div className="flex max-w-[1500px] flex-col gap-[28px]">
        <BuehnenBlocks blocks={rest} schritte={folie.layout === "schritte"} />
      </div>
    </div>
  );
}
