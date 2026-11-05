-- Leserechte für die Rolle kic_app in der aktuellen Datenbank (#68). Läuft als statistik je App-Datenbank,
-- nach jedem `scripts/deploy.sh daten` und `up` erneut (idempotent): neue Schemata und Tabellen aus einem Dump
-- bekommen so ebenfalls nur SELECT.
\set ON_ERROR_STOP on

do $$
declare
  s text;
begin
  execute format('grant connect on database %I to kic_app', current_database());
  for s in
    select nspname from pg_namespace
    where nspname not like 'pg\_%' and nspname <> 'information_schema'
  loop
    execute format('grant usage on schema %I to kic_app', s);
    execute format('grant select on all tables in schema %I to kic_app', s);
    execute format('grant select on all sequences in schema %I to kic_app', s);
    execute format('alter default privileges for role statistik in schema %I grant select on tables to kic_app', s);
  end loop;
end
$$;

-- Gegenprobe: kic_app darf in keinem Schema anlegen und hat keine Schreibrechte auf Tabellen
select 'rechte ' || current_database() || ': '
  || (select count(*) from information_schema.role_table_grants
      where grantee = 'kic_app' and privilege_type = 'SELECT') || ' Tabellen lesbar, '
  || (select count(*) from information_schema.role_table_grants
      where grantee = 'kic_app' and privilege_type in ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE')) || ' Schreibrechte, '
  || (select count(*) from pg_namespace
      where has_schema_privilege('kic_app', oid, 'CREATE') and nspname not like 'pg\_%') || ' Schemata mit CREATE';
