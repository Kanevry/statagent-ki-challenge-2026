# Grenzen, Herkunft und Lizenzen, Langfassung

Diese Seite ist die Langfassung der Abschnitte „Grenzen und offene Punkte“, „Vorab Entstandenes“ und „Lizenzen“ aus dem README.
Sie nennt, was StatAgent und die anderen Use Cases nicht können, was aus früherer Arbeit stammt und welche Lizenzen gelten.

Zurück zum [README](../../README.md#grenzen-und-offene-punkte).

## Grenzen und offene Punkte

- **Daten:** Es sind nur die synthetischen Daten des Veranstalters und öffentliche Quellen. Sie liegen nicht im
  Repo. Einzige Ausnahme: Die Rückfragen in `abgabe/rueckfragen/` nennen als Beispiel einige synthetische
  Kennungen (`VVH_ID`), damit die Fachabteilung den Fall findet. Personenbezogene Daten gibt es keine. An ein Modell
  gehen nie Einzeldaten, nur Schema, Aggregate und Prüfergebnisse.
- **UC1:** Der Lotse ersetzt keine Beratung. Er gibt keine Diagnose und keine Therapie- oder Medikamentenempfehlung;
  bei solchen Fragen verweist er an Ärztin, Arzt oder die Gesundheitsberatung 1450, im Notfall an 144. Eine
  Aussage ohne passendes Zitat aus der Quelle lässt er weg.
- **UC2:** Die Akteure spielt ein Sprachmodell. Das ist eine Simulation, keine echte Verhandlung. Die Antwort auf
  `/uc4` sagt das in einem eigenen Satz.
- **UC4:** Die drei Antworten kommen nacheinander. Mit Azure dauerte die ganze Frage online 13 Sekunden, gemessen
  am 06.11. um 05:01; die Seite wartet höchstens drei Minuten und zeigt jede Antwort, sobald sie da ist. Fällt ein Bereich
  aus, nennt die Seite ihn als „fehlt“ und zeigt die anderen. Online kann UC2 statt echter Presse-Belege
  gekennzeichnete Beispielbelege zeigen, solange dort die Namensliste zur Maskierung von Personennamen fehlt.
- **Voice:** Server und Sprechknopf sind gebaut. Ein Anruf geht erst nach der Einrichtung (Tunnel, Vapi-Konto mit
  Zahlungsmittel, Schlüssel). Die Tunnel-Adresse wechselt bei jedem Start, danach muss der Assistent neu
  eingetragen werden (`docs/voice.md`). Vapi ist ein US-Dienst. Der Text-Weg ersetzt Voice vollständig.
- **UC3 Rückfragen:** Offene Fragen an die Fachabteilung stehen in `abgabe/rueckfragen/`. Für Berichtsmonate vor
  Juli hängt das Alter bei Geburtsmonat 13 von der Antwort auf Rückfrage R1 ab.

## Vorab Entstandenes

Das Voice-Konzept (Vapi Custom LLM, Webhook, Text-Fallback) folgt einem früheren eigenen Projekt des Teams,
einem Sprach-Interview mit Vapi. **Übernommen sind nur Konzept und Schnittstellen. Der Code ist hier neu
geschrieben.** Das belegt eine Suche im Repo: Der Name des früheren Projekts kommt im Quelltext nicht vor.
Die Liste aller übernommenen Teile mit Herkunft, Version und Rechtebeleg: `docs/abgabe/herkunft.md`.

## Lizenzen

Der eigene Code dieses Repos steht unter der MIT-Lizenz (`LICENSE`). Nach den Teilnahmebedingungen der
KI Challenge 2026 stehen die Ergebnisse (dieses Repository) neben dem Team auch dem Dachverband der
österreichischen Sozialversicherungsträger uneingeschränkt zur Verfügung. Ausgenommen von der MIT-Lizenz sind:

- die Daten des Veranstalters. Sie liegen nicht im Repo.
- die Gewichte fremder Modelle, etwa `google/embeddinggemma-2` unter den Gemma Terms of Use. Sie werden getrennt
  geladen und hier nicht verteilt.
- Logos und Marken Dritter: das Logo des Dachverbands und das Logo der Wirtschaftskammer Wien in
  `web/public/landing/logos/`. Sie gehören den beiden Organisationen und nennen auf der Startseite nur die
  Veranstalter. Quellen stehen in `docs/landing/logos-quellen.md`.

Fremde Bibliotheken behalten ihre eigenen Lizenzen. Die Schriften Inter, Space Grotesk und JetBrains Mono kommen
über `@fontsource-variable/*` unter der OFL-1.1. `three` steht noch in `web/package.json`, wird nicht mehr importiert und steht unter MIT. Die Messfunktion des Anti-Schablonen-Gates
(`web/tests/lib/slop-measure.js`) folgt dem impeccable-Katalog von Paul Bakaus und steht unter Apache-2.0
(Lizenztext `web/tests/lib/LICENSE-impeccable`). Einzelheiten: `docs/abgabe/herkunft.md`.
