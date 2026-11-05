# Abgabe-Checkliste UC3 StatAgent (Team OneShotAndy)

Stand 05.11.2026 20:00 (Wiener Zeit). Abgabe **Fr 06.11.2026 09:00** doppelt: SV-Box-Teamordner und öffentliches
GitHub-Repo `KIChallenge/OneShotAndy`. **Freeze:** Merge-Stopp 06:30, Feature-Stopp **07:00**. Der **GitHub**-Push
kommt erst kurz vor 09:00, vorher nicht.

Prüfbefehl für alles unten: `cd uc3 && uv run uc3 pruefe-abgabe --mit-db` (Soll: alle Punkte `[ok]`,
„Abgabe vollständig.“, Exit 0). `--manifest` schreibt vorher `abgabe/manifest.json` neu.

## Pflichtteile laut Aufgabenstellung

| Teil | Datei | Stand | Beleg |
|---|---|---|---|
| Aggregations-Sheet nach den Regeln der Fachbeschreibung | `abgabe/aggregationen_v1.xlsx` | erledigt | pruefe-abgabe „Aggregations-Sheet v1“ |
| Aggregations-Sheet nach den Änderungsaufträgen | `abgabe/aggregationen_v2.xlsx` | erledigt | pruefe-abgabe „Aggregations-Sheet v2“ |
| 24 Qualitätsberichte 2024-08 bis 2026-07 | `abgabe/qualitaetsberichte/`, `abgabe/qualitaetsberichte_v2/` | erledigt | pruefe-abgabe, je 24 Berichte |
| Ministeriums-Lieferung 07/2026 | `ministerium_2026-07.csv` (außerhalb des Repos), Beleg `abgabe/ministerium_2026-07.beleg.md` | erzeugt und freigegeben 05.11. 19:35 (Bernhard Götzendorfer, Commit `1b0f799`); Upload offen, siehe unten | 32.741 Personen, sha256 `d8492f46dd5f…86379` |
| Protokoll der Änderungen und Freigaben | `abgabe/protokoll.md` | erledigt, neu nach der Lieferung | Abschnitt 1 Freigaben, Abschnitt 5 Lieferung nach außen |
| Angabe zu den Modellen | `abgabe/modelle.md` | erledigt | Betrieb ohne Modell, Agenten Azure `gpt-5-4-mini` |
| Manifest aller Abgabedateien | `abgabe/manifest.json` | erledigt | Name, Größe, sha256, Regelsatz, Stand je Datei, auch `ministerium_2026-07.csv` |

## Ablauf Fr 06.11. (wer, wann)

| Schritt | Wer | Wann | Stand |
|---|---|---|---|
| Use-Case-Mail und YAML (`uc3`) | Owner | 05.11. | erledigt, keine neue Mail |
| Letzter Merge auf main | Lead | bis 06:30 | geplant |
| Feature-Stopp, danach nur noch Prüfen | alle | 07:00 | geplant |
| `uv run uc3 pruefe-abgabe --mit-db` auf main, Ausgabe in die Übergabe | UC3-Session | 07:00 bis 07:30 | geplant |
| `ministerium_2026-07.csv` und `abgabe/` in den SV-Box-Teamordner (Ergebnisdateien) laden, über den WebDAV-Weg des Teamordners, Zugang `SVBOX_TEAM_*` aus `.env.local`; sha256 nach dem Upload gegen den Beleg prüfen | Lead (Upload ist Außenwirkung, Freigabe des Owners) | 08:00 bis 08:30 | geplant |
| GitHub-Push von main nach `KIChallenge/OneShotAndy` | Lead | kurz vor 09:00 | geplant |
| Abgabe-Zeitpunkt | | 09:00 | |

Die CSV enthält Einzeldaten (PERSON_ID) und kommt nie ins Repo und nie nach GitHub, nur in den SV-Box-Teamordner.
Die Daten sind synthetisch.
