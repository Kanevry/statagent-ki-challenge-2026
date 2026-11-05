-- Freigabe des Berichts einer fertigen Verhandlung durch einen Menschen mit Vor- und Nachnamen.
-- Idempotent: mehrfach anwendbar. Höchstens eine Entscheidung je Fall (die Einreichung ist endgültig).
-- `plattform.freigabe.freigeben` legt für „ja“ immer einen Git-Commit an und passt daher nicht zu einer reinen
-- Entscheidung zu einem Fall in PG. Darum steht die Entscheidung hier, und zusätzlich (Vertrag P, in derselben
-- Transaktion, ohne Commit) je eine Zeile in `meta.protokoll` (`protokoll_id`) und in `meta.freigabe`
-- (`ja|nein`, `objekt_typ` 'antwort', `objekt_ref` 'uc2/fall/<id>'), damit Ablehnungen in `protokoll.md` stehen.
create schema if not exists uc2;

create table if not exists uc2.freigabe (
    fall_id      bigint primary key references uc2.fall (fall_id) on delete cascade,
    name         text not null check (name <> ''),
    entscheidung text not null check (entscheidung in ('freigegeben', 'abgelehnt')),
    begruendung  text,
    zeitpunkt    timestamptz not null default now(),
    protokoll_id bigint,
    constraint freigabe_ablehnung_mit_begruendung
        check (entscheidung = 'freigegeben' or coalesce(begruendung, '') <> '')
);
