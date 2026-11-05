-- Leserechte für die Rolle kic_app in der aktuellen Datenbank (#68). Läuft als statistik je App-Datenbank,
-- nach jedem `scripts/deploy.sh daten` und `up` erneut (idempotent): neue Schemata und Tabellen aus einem Dump
-- bekommen so ebenfalls nur SELECT.
\set ON_ERROR_STOP on

do $$
declare
  s text;
begin
  execute format('grant connect on database %I to kic_app', current_database());
  -- kein Anlegen von Schemata oder temporären Tabellen über PUBLIC
  execute format('revoke create, temporary on database %I from public', current_database());
  for s in
    select nspname from pg_namespace
    where nspname not like 'pg\_%' and nspname <> 'information_schema'
  loop
    -- PUBLIC bekommt nichts: ein Dump mit `grant ... to public` brächte sonst still Schreibrechte mit (#108a)
    execute format('revoke create on schema %I from public', s);
    execute format('revoke insert, update, delete, truncate on all tables in schema %I from public', s);
    execute format('revoke usage, update on all sequences in schema %I from public', s);
    -- ein reiner SQL-Dump bringt seine eigenen GRANTs mit, auch an kic_app: hier wieder auf Lesen zurück
    execute format('revoke insert, update, delete, truncate on all tables in schema %I from kic_app', s);
    execute format('revoke usage, update on all sequences in schema %I from kic_app', s);
    execute format('grant usage on schema %I to kic_app', s);
    execute format('grant select on all tables in schema %I to kic_app', s);
    execute format('grant select on all sequences in schema %I to kic_app', s);
    execute format('alter default privileges for role statistik in schema %I grant select on tables to kic_app', s);
  end loop;
end
$$;

-- Gegenprobe (#108a, fail-closed): kic_app darf in keinem Schema anlegen und auf keiner Tabelle schreiben, auch nicht
-- über PUBLIC. has_table_privilege zählt direkte Rechte, Rollen und PUBLIC zusammen.
do $$
declare
  schreibend int;
  anlegend int;
begin
  select count(*) into schreibend
  from pg_class c join pg_namespace n on n.oid = c.relnamespace
  where c.relkind in ('r', 'p', 'v', 'm', 'f')
    and n.nspname not like 'pg\_%' and n.nspname <> 'information_schema'
    and (has_table_privilege('kic_app', c.oid, 'INSERT, UPDATE, DELETE, TRUNCATE')
         or has_any_column_privilege('kic_app', c.oid, 'INSERT, UPDATE'));
  select schreibend + count(*) into schreibend
  from pg_class c join pg_namespace n on n.oid = c.relnamespace
  where n.nspname not like 'pg\_%' and n.nspname <> 'information_schema'
    -- CASE statt AND: der Planer darf has_sequence_privilege sonst auch für Tabellen auswerten (Fehler)
    and case when c.relkind = 'S' then has_sequence_privilege('kic_app', c.oid, 'USAGE, UPDATE') else false end;
  select count(*) into anlegend
  from pg_namespace
  where has_schema_privilege('kic_app', oid, 'CREATE') and nspname not like 'pg\_%';
  if has_database_privilege('kic_app', current_database(), 'CREATE') then
    anlegend := anlegend + 1;
  end if;
  if schreibend > 0 or anlegend > 0 then
    raise exception 'rechte %: kic_app hat % Schreibrechte und % Schemata mit CREATE', current_database(), schreibend, anlegend;
  end if;
end
$$;

select 'rechte ' || current_database() || ': '
  || (select count(*) from information_schema.role_table_grants
      where grantee = 'kic_app' and privilege_type = 'SELECT') || ' Tabellen lesbar, 0 Schreibrechte, 0 Schemata mit CREATE';
