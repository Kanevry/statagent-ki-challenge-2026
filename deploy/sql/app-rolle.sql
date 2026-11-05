-- Rolle der App in der Online-Demo (#68): darf lesen, sonst nichts. Der Superuser `statistik` bleibt für Admin
-- (scripts/deploy.sh daten, inhaltshash, rechte). Läuft als statistik in der DB statistik, idempotent.
-- Das Passwort setzt scripts/deploy.sh getrennt über stdin (nie in dieser Datei, nie als Argument).
\set ON_ERROR_STOP on

do $$
begin
  if not exists (select from pg_roles where rolname = 'kic_app') then
    create role kic_app login;
  end if;
end
$$;

alter role kic_app nosuperuser nocreatedb nocreaterole noreplication nobypassrls;
-- lesend als Voreinstellung: selbst eine vergessene Schreibberechtigung scheitert ohne ausdrückliches
-- `set transaction read write`. Braucht eine UC später INSERT (etwa meta.protokoll), dann gezielt per GRANT
-- und mit Begründung im Issue.
alter role kic_app set default_transaction_read_only = on;
alter role kic_app connection limit 20;
