# Vertragsnutzung UC3 (Issue #13, AC4)

Review-Beleg: UC3 nutzt die E0-Verträge, statt sie nachzubauen. Jede Aussage steht mit dem Befehl und der gemessenen Ausgabe (05.11.2026, Branch `feat/uc3-betrieb`, Repo-Wurzel).

## 1. Keine eigenen Definitionen von `complete()` oder `freigeben()`

```console
$ grep -rn "def complete\|def freigeben" uc3/statagent; echo "exit $?"
exit 1
```

0 Treffer. `regeln_freigeben` in `uc3/statagent/regeln.py` ist ein UC3-Ablauf, der `plattform.freigabe.freigeben` aufruft. Es ist keine zweite Definition.

## 2. Keine DDL-Neudefinition der zwei E0-Protokolltabellen

Die zwei Tabellen aus Vertrag P stehen in `shared/py/plattform/sql/meta.sql`: `meta.protokoll` und `meta.freigabe`.

```console
$ grep -n "CREATE TABLE" shared/py/plattform/sql/meta.sql
9:CREATE TABLE IF NOT EXISTS meta.protokoll (
31:CREATE TABLE IF NOT EXISTS meta.freigabe (

$ grep -rlnE "CREATE TABLE[^;]*meta\.(protokoll|freigabe)\b" uc3/db uc3/statagent; echo "exit $?"
exit 1
```

0 Treffer. In `uc3/db` kommen die Namen nur in Kommentaren und als Verweis vor (`001_schemas.sql`, `045_freigabe_schutz.sql`, `140_vorschlag.sql`).

## 3. Welche E0-Verträge UC3 nutzt

| Vertrag | E0-Modul | Nutzung in UC3 (Datei: Funktion) |
|---|---|---|
| M | `plattform.llm.complete` | `uc3/statagent/agenten/plattform_bruecke.py: lade_complete`, aufgerufen in `uc3/statagent/agenten/koordinator.py` (Zeile 302). Der Import geschieht erst beim ersten Agentenaufruf. |
| M | `plattform.llm.LlmFehler` | `uc3/statagent/cli.py` (Zeile 449, nur Agenten-Befehle) |
| P | `plattform.freigabe.freigeben`, `ablehnen` | `plattform_bruecke.py: lade_freigabe`, `lade_ablehnung`, genutzt in `uc3/statagent/agenten/anwenden.py`; außerdem `uc3/statagent/regeln.py: regeln_freigeben` und `uc3/statagent/lauf.py: veroeffentlichen` |
| P | `plattform.freigabe.pruefe_name`, `NameUngueltig` | `uc3/statagent/regeln.py` (Import oben) |
| P | `plattform/sql/meta.sql` | `uc3/statagent/db.py: plattform_ddl`, eingespielt über `schema_einrichten` (CLI `uc3 db init`) |
| P | `plattform.protokoll` (Modellaufrufe) | indirekt: jeder `complete`-Aufruf schreibt genau eine Zeile über `plattform.protokoll.modellaufruf` |

```console
$ grep -rn "from plattform\|import plattform" uc3/statagent
uc3/statagent/db.py:37:        import plattform
uc3/statagent/regeln.py:16:from plattform.freigabe import NameUngueltig as NameUngueltig  # Vertrag P, re-exportiert
uc3/statagent/regeln.py:17:from plattform.freigabe import pruefe_name
uc3/statagent/regeln.py:170:        from plattform.freigabe import freigeben
uc3/statagent/cli.py:421:        from plattform import freigabe as plattform_freigabe
uc3/statagent/cli.py:449:        from plattform.llm import LlmFehler
uc3/statagent/lauf.py:478:        from plattform.freigabe import freigeben
uc3/statagent/uc4.py:265:        from plattform.antwortform import UcAntwort
```

`plattform_bruecke.py` lädt `plattform.llm` und `plattform.freigabe` über `importlib.import_module` und taucht deshalb in diesem grep nicht auf.

## 4. Adapter-Smoke und Offline-Lauf

`uc3/tests/test_llm_smoke.py` enthält zwei Tests:

- `test_complete_mit_mock_fuer_agent_koordinator`: ruft `plattform.llm.complete` mit `provider="mock"` für den Zweck `agent.koordinator` auf. Die Fixture liegt in einem Wegwerf-Ordner (`PLATTFORM_FIXTURES`). Der Test prüft Antwort, Provider und genau eine Protokollzeile.
- `test_lauf_laedt_kein_modell`: importiert in einem frischen Prozess `statagent.cli` und `statagent.lauf` (der Befehl `lauf` lädt nur diese beiden) und prüft, dass kein Modul `plattform.llm*` in `sys.modules` steht (Regel R2).

```console
$ cd uc3 && uv run pytest -q -m "not daten" tests/test_llm_smoke.py
..                                                                       [100%]
2 passed in 0.49s
```

Produktions-CLI `uc3 lauf`: 0 Modellaufrufe, weil `plattform.llm` beim Lauf gar nicht geladen wird.
