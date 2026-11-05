# Invarianten des Produktiv-Stacks (#68), geprüft im CI-Job deploy-check gegen `docker compose config --format json`.
# Ergebnis true = alles erfüllt; jq -e endet sonst mit Exit 1.
.services as $s
| ([$s | to_entries[] | select((.value.ports // []) | length > 0) | .key] == ["caddy"])
and ($s.caddy.cap_drop == ["ALL"])
and ($s.caddy.cap_add == ["NET_BIND_SERVICE"])
and ($s.caddy.read_only == true)
and ($s.app.cap_drop == ["ALL"])
and ($s.app.read_only == true)
and ([$s | to_entries[] | .value.security_opt // [] | any(. == "no-new-privileges:true")] | all)
and ([$s.app.environment | to_entries[] | select(.key | endswith("_DATABASE_URL")) | .value | startswith("postgresql://kic_app:")] | (length == 3 and all))
# Schreibende Wege bleiben in der App zu, auch wenn KIC_ONLINE_FRAGEN die Fragen öffnet
and ($s.app.environment.KIC_ONLINE_LESEND == "1")
# Geld (#100): online gilt der Merker, und das Tagesbudget ist eine ganze Zahl ab 1
and ($s.app.environment.KIC_ONLINE == "1")
and (($s.app.environment.LLM_TAGESBUDGET_AUFRUFE // "") | test("^[1-9][0-9]*$"))
# Budget zählt nur mit beschreibbarem Protokoll: Pfad im Volume app_protokoll
and (($s.app.environment.PLATTFORM_PROTOKOLL // "") | startswith("/app/var/protokoll/"))
and ([$s.app.volumes[]? | select(.type == "volume" and .source == "app_protokoll" and .target == "/app/var/protokoll")] | length == 1)
