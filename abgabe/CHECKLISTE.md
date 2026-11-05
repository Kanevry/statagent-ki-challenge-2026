# Abgabe-Checkliste UC3 StatAgent (Team OneShotAndy)

Stand 05.11.2026 21:15 (Wiener Zeit). Abgabe **Fr 06.11.2026 09:00** doppelt: SV-Box-Teamordner und öffentliches
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
| Voraussetzung für den Push: Trockenlauf von `github_push.py` auf dem letzten main endet mit Exit 0, Sperrmuster-Treffer in Dateien sind 0, in Commits höchstens 12. Es gilt genau eine Sperrmuster-Datei außerhalb des Repos, Entscheid Lead. Zuletzt gemessen auf `b3eb4e5`: 0 Dateien, 3 von 888 Commits. Die Historie bleibt unverändert (Entscheid Lead, #92) | Lead | bis 06:30 | geplant |
| `ministerium_2026-07.csv` und `abgabe/` in den SV-Box-Teamordner (Ergebnisdateien) laden: `python3 -I scripts/abgabe/svbox_upload.py --csv … --env-datei … --erwarteter-kopf … --ausfuehren`. Das Skript liest danach Größe und sha256 jeder Datei zurück und schreibt `docs/abgabe/transfernachweis.json`. Laufzeit rund 7 min im 2-s-Takt (lesend gemessen: 143 Anfragen in 407 s, 0 Abweisungen; der Schreibweg ist mit einer einzelnen Testdatei belegt, die Laufzeit beim Schreiben vieler Dateien erst Fr). Dateien im Teamordner, die nicht im Manifest stehen, ergeben schon im Trockenlauf Exit 1 und werden nicht gelöscht. Nennt `abweichend` im Nachweis nur solche fremden Dateien und sind alle Manifest-Dateien `gleich`, ist der Upload vollständig: Die fremde Datei im Browser entfernen oder von Hand erklären, nicht neu hochladen und nicht auf den Browser-Upload ausweichen. `fremd_im_teamordner` muss vor 09:00 leer oder erklärt sein. Scheitert der Upload selbst, Rückfall über das Browser-Profil `svbox` | Lead (Upload ist Außenwirkung, Freigabe des Owners) | Start 08:00, fertig bis 08:30 | geplant |
| Nur `docs/abgabe/transfernachweis.json` auf main committen, damit er auch auf GitHub liegt; danach gilt für den Push der neue Kopf. `abgabe/` nicht anfassen: Die Checkliste steht im Manifest, ein Häkchen bricht Prüfung und Upload | Lead | bis 08:45, sonst Push auf dem bisherigen Kopf | geplant |
| GitHub-Push von main (Branch `main`, Commit aus `--erwarteter-kopf`) nach `KIChallenge/OneShotAndy`: `python3 -I scripts/abgabe/github_push.py --sperrmuster … --erwarteter-kopf … --ausfuehren` (nicht vor 08:30) | Lead | kurz vor 09:00 | geplant |
| Abgabe-Zeitpunkt | | 09:00 | |

## Erledigt und gegengeprüft

- [x] Use-Case-Mail an die Veranstalter: vom Owner am 05.11. erledigt, keine neue Mail.
- [x] YAML `KI-Challenge_UseCase.yaml` mit `uc3`: im Repo und auf GitHub gleich (`github_push.py`, Prüfung „pflicht“).
- [x] Alle Pflichtteile da: `statagent pruefe-abgabe` meldet „Abgabe vollständig.“, Exit 0 (05.11. abends).
- [x] Manifest mit Größe und sha256 jeder Abgabedatei, auch `ministerium_2026-07.csv`: `abgabe/manifest.json` (auch unter `docs/abgabe/manifest.json`).
- [x] gitleaks über die ganze zu veröffentlichende Historie: 0 Befunde auf `b3eb4e5` (`github_push.py`, Bericht als JSON außerhalb des Repos neben dem Arbeitsordner).
- [x] Dateiliste ohne `.env.local`, Schlüsseldateien und Einzeldaten, im Baum und über die ganze Historie (`github_push.py`, Prüfungen „dateiliste“ und „dateiliste historie“).
- [x] Trockenlauf SV-Box: alle Dateien stimmen mit dem Manifest, Teamordner leer, Rechte zum Anlegen gemeldet (`svbox_upload.py`).
- [x] Schreibprobe im Teamordner 05.11. 21:12 nach Freigabe des Owners: eine Testdatei geschrieben, zurückgelesen, Datei und Ordner gelöscht, Teamordner danach wieder leer (`svbox_upload.py --probe`).
- [x] Trockenlauf GitHub auf `b3eb4e5`: Exit 0, Fast-Forward, `git push --dry-run` angenommen (`github_push.py`). Bedienung: `docs/abgabe/README.md`.

Die CSV enthält Einzeldaten (PERSON_ID) und kommt nie ins Repo und nie nach GitHub, nur in den SV-Box-Teamordner.
Die Daten sind synthetisch.
