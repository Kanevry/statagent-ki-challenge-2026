-- Verhandlung (#44): Fall, Teilnahme, Ereignisse, Positionen. Idempotent: mehrfach anwendbar.
-- Genau ein Schreibprozess je Fall (`uv run uc2 verhandlung`); `seq` zählt je Fall lückenlos ab 1.
create schema if not exists uc2;

create table if not exists uc2.fall (
    fall_id       bigint generated always as identity primary key,
    fall_name     text not null,
    frage         text not null,
    auftrag       jsonb,
    provider      text not null,
    belegquelle   text not null,
    modelle       jsonb not null,
    stichtag      date not null,
    status        text not null default 'laufend' check (status in ('laufend', 'fertig', 'abgebrochen')),
    lebenszeichen timestamptz not null default now(),
    start         timestamptz not null default now(),
    ende          timestamptz
);

create table if not exists uc2.teilnahme (
    fall_id     bigint not null references uc2.fall (fall_id) on delete cascade,
    akteur      text not null,
    eingeladen  boolean not null,
    begruendung text not null,
    belegzahl   int not null,
    primary key (fall_id, akteur)
);

create table if not exists uc2.ereignis (
    fall_id bigint not null references uc2.fall (fall_id) on delete cascade,
    seq     int not null check (seq >= 1),
    runde   int,
    art     text not null,
    akteur  text,
    daten   jsonb not null default '{}',
    zeit    timestamptz not null default now(),
    primary key (fall_id, seq)
);

-- quelle: `zug` (aus einem gültigen Zug) oder `unveraendert` (aus der Vorrunde übernommen, etwa nach
-- `ungueltige_ausgabe` oder wenn ein Zug das Thema nicht nennt).
create table if not exists uc2.position (
    fall_id     bigint not null references uc2.fall (fall_id) on delete cascade,
    runde       int not null check (runde >= 1),
    akteur      text not null,
    thema       text not null,
    wert        int not null check (wert between -2 and 2),
    begruendung text not null,
    beleg_ids   text[] not null default '{}',
    quelle      text not null default 'zug' check (quelle in ('zug', 'unveraendert')),
    primary key (fall_id, runde, akteur, thema)
);

create index if not exists ereignis_art_idx on uc2.ereignis (fall_id, art);
