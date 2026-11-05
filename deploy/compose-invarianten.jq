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
