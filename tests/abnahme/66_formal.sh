#!/bin/bash
# Formale Abnahme #66 gegen main: ruft nur die Schritte des Mess-Skripts auf.
S="$(cd "$(dirname "$0")" && pwd)/66_jury_weg.sh"
. "$(dirname "$0")/abnahme.env"
echo "== kopf $(git -C "$ABNAHME_REPO" rev-parse HEAD)"
bash "$S" frisch
bash "$S" sync
bash "$S" init > /dev/null && echo "init ok"
bash "$S" lauf
bash "$S" lauf
bash "$S" eichen; echo "eichen_exit=$?"
bash "$S" goldenset
bash "$S" hash
bash "$S" frisch
bash "$S" init > /dev/null && echo "init ok"
bash "$S" lauf
bash "$S" eichen; echo "eichen_exit=$?"
bash "$S" hash
echo "== ende"
