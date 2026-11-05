-- Inhalts-Hash eines Schemas, unabhängig von physischer Zeilenfolge und Rechner (#68).
-- Aufruf: psql -X -At -v schema=uc2 -f deploy/sql/inhaltshash.sql
-- Je Tabelle: Zeilenzahl und md5 über die sortierten md5 der Zeilentexte. Gesamt: md5 über "tabelle:zeilen:hash"
-- in Namensfolge. Gleiche Daten ergeben auf jedem Rechner denselben Wert, wenn die Ausgabeformate gleich sind;
-- deshalb Zeitzone, Datumsformat und Gleitkomma-Ausgabe fest und jede Sortierung mit COLLATE "C" (glibc und macOS
-- sortieren sonst verschieden).
\set ON_ERROR_STOP on
set timezone = 'UTC';
set datestyle = 'ISO, YMD';
set intervalstyle = 'postgres';
set extra_float_digits = 1;
set bytea_output = 'hex';

with tabellen as (
  select c.relname, format('%I.%I', n.nspname, c.relname) as voll
  from pg_class c
  join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = :'schema' and c.relkind in ('r', 'p')
),
je_tabelle as (
  select
    t.relname,
    (xpath('/row/n/text()', x))[1]::text::bigint as zeilen,
    (xpath('/row/h/text()', x))[1]::text as hash
  from tabellen t,
  lateral query_to_xml(
    format(
      'select count(*) as n, md5(coalesce(string_agg(z, '''' order by z collate "C"), '''')) as h from (select md5(t::text) as z from %s t) s',
      t.voll
    ),
    false, true, ''
  ) as x
)
select zeile from (
  select relname || ' ' || zeilen || ' ' || hash as zeile from je_tabelle
  union all
  select 'GESAMT ' || coalesce(sum(zeilen), 0) || ' '
         || md5(coalesce(string_agg(relname || ':' || zeilen || ':' || hash, ',' order by relname collate "C"), ''))
  from je_tabelle
) ausgabe
order by zeile collate "C";
