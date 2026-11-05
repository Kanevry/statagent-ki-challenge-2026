-- Belege (#40): Quellen, Artikel, Abschnitte mit deutschem Volltextindex und Vektor als float32-Bytes.
-- Idempotent: mehrfach anwendbar. Kein pgvector, kein unaccent (Kosinus rechnet numpy).
create schema if not exists uc2;

create table if not exists uc2.quelle (
    md5           text primary key,
    datei         text not null,
    ausgabedatum  date not null,
    seiten        int,
    uebersprungen boolean not null default false,
    grund         text
);

create table if not exists uc2.artikel (
    artikel_id    text primary key,
    quelle_md5    text not null references uc2.quelle (md5),
    pdf_seite     int not null,
    zeitungsseite text,
    artikeldatum  date not null,
    medium        text not null,
    typ           text,
    titel         text not null,
    -- Titel durchsuchbar: der Titel steht nicht im Abschnittstext (die Suche verbindet beide tsvector).
    tsv           tsvector generated always as (to_tsvector('german'::regconfig, titel)) stored
);

create table if not exists uc2.abschnitt (
    abschnitt_id  text primary key,
    artikel_id    text not null references uc2.artikel (artikel_id),
    nr            int not null,
    text          text not null,
    text_hash     text not null unique,
    institutionen text[] not null default '{}',
    tsv           tsvector generated always as (to_tsvector('german'::regconfig, text)) stored,
    vektor        bytea,
    modell        text,
    dim           int
);

create index if not exists abschnitt_tsv_idx on uc2.abschnitt using gin (tsv);
create index if not exists artikel_tsv_idx on uc2.artikel using gin (tsv);
create index if not exists abschnitt_artikel_idx on uc2.abschnitt (artikel_id);
create index if not exists artikel_datum_idx on uc2.artikel (artikeldatum);

create table if not exists uc2.index_lauf (
    zeit        timestamptz not null default now(),
    anzahl      int not null,
    inhalt_hash text not null,
    modell      text
);
