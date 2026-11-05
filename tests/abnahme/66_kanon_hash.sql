-- Abnahme #66 (EA-4): unabhängiger Hash über das Ergebnis der Lieferung 2024-08 (Regelsatz v1).
-- Nur lesen. Aufruf: psql -At -v ON_ERROR_STOP=1 < 66_kanon_hash.sql
--
-- 1. Läufe in meta.lauf (voller ergebnis_hash).
-- 2. Eigener sha256 über ein CSV der 11 Zellspalten, eigene Sortierung (alle Spalten, COLLATE "C"),
--    eigenes Trennzeichen. Er ist bewusst NICHT die Formel aus zaehlung.py, damit er unabhängig misst.
-- 3. Gegenprobe: die Formel aus zaehlung.py:186-199 neu gerechnet, muss gleich meta.lauf.ergebnis_hash sein.

\echo == laeufe
select id, lieferung, regelsatz, status, ergebnis_status, gelesen, gezaehlt, nicht_gezaehlt, ausgeschlossen,
       zellen, ergebnis_hash
from meta.lauf
order by id;

\echo == zellen
select count(*) as zellen, sum(wert) as summe_wert
from stat.stat_beschaeftigte
where regelsatz = 'v1' and zeitraum_bis between date '2024-08-01' and date '2024-08-31';

\echo == csv_sha256
select encode(sha256(convert_to(coalesce(string_agg(zeile, E'\n' order by zeile collate "C"), ''), 'UTF8')), 'hex')
from (
  select concat_ws(',', zeitraum_art, zeitraum_von, zeitraum_bis, region, oenace, oenace_version,
                   geschlecht, qualifikation, "alter", variable, wert) as zeile
  from stat.stat_beschaeftigte
  where regelsatz = 'v1' and zeitraum_bis between date '2024-08-01' and date '2024-08-31'
) z;

\echo == formel_zaehlung
select encode(sha256(convert_to(coalesce(string_agg(
         concat_ws('|', zeitraum_art, zeitraum_von, zeitraum_bis, region, oenace, oenace_version,
                   geschlecht, qualifikation, "alter", variable, wert), E'\n'
         order by zeitraum_art collate "C", zeitraum_von, zeitraum_bis, region collate "C",
                  oenace collate "C", oenace_version collate "C", geschlecht collate "C",
                  qualifikation collate "C", "alter", variable collate "C"), ''), 'UTF8')), 'hex')
from stat.stat_beschaeftigte
where regelsatz = 'v1' and zeitraum_bis between date '2024-08-01' and date '2024-08-31';
