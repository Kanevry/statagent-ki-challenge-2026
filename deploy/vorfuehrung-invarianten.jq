# Invarianten der Vorführ-Instanz, geprüft im CI-Job deploy-check gegen `docker compose config --format json`.
# Ergebnis true = alles erfüllt; jq -e endet sonst mit Exit 1.
.services as $s
# Kein Dienst veröffentlicht Ports: von außen nur über Caddy mit Basic-Auth
| ([$s | to_entries[] | select((.value.ports // []) | length > 0)] | length == 0)
# Die Datenbank mit Rohdaten hängt nur am eigenen Netz, nie am Netz der öffentlichen Demo
and (($s["vorfuehrung-db"].networks | keys) == ["intern"])
# Postgres darf nicht PID 1 sein: Ein verwaister Prozess mit Exit-Code ungleich 0 löst sonst einen Crash-Neustart aus
and ($s["vorfuehrung-db"].init == true)
and ($s["vorfuehrung-app"].cap_drop == ["ALL"])
and ($s["vorfuehrung-app"].read_only == true)
# Schreiben nur in die eigene Kopie, nie in die Abgabe-DB; UC1 und UC2 bleiben lesend
and ($s["vorfuehrung-app"].environment.UC3_DATABASE_URL | test("@vorfuehrung-db:5432/statistik_vorfuehrung$"))
and ($s["vorfuehrung-app"].environment.UC1_DATABASE_URL | startswith("postgresql://kic_app:"))
and ($s["vorfuehrung-app"].environment.UC2_DATABASE_URL | startswith("postgresql://kic_app:"))
# Geld (#100): Merker, Tagesbudget und beschreibbares Protokoll gelten auch hier
and ($s["vorfuehrung-app"].environment.KIC_ONLINE == "1")
and (($s["vorfuehrung-app"].environment.LLM_TAGESBUDGET_AUFRUFE // "") | test("^[1-9][0-9]*$"))
and ($s["vorfuehrung-app"].environment.PLATTFORM_PROTOKOLL | startswith("/app/var/protokoll/"))
