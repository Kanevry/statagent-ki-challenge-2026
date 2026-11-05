# Lotse-Set: Suche (Recall@k)

- Zeitpunkt: 2026-11-05T14:52:27+01:00
- Befehl: `lotse eval --nur-suche --weg volltext --erweiterung aus,thesaurus,llm --grep-grundlinie --ausgabe docs/plan/uc1/messung.md`
- Blick 2 von 3 auf das Test-Set (testset-blicke.json)
- Stand: 23c0d11, vor Persona-Änderung (28f97e0), mit diesem Stand nicht nachrechenbar (Stand-Zeile nachgetragen, Review !46)
- Zählende Fälle (mit Korpusquelle, n=15): g02, g03, g05, g06, g07, g10, g18, g20, g21, g24a, g24b, g25, w01, s-pflege, s-casemanager
- Intervall: Wilson 95 %. MRR über die ersten 10 Treffer (Rang darüber zählt 0).

| Weg | Recall@k | Wilson 95 % | MRR@10 | k | Latenz p50 (ms) | Latenz p95 (ms) |
|---|---|---|---|---|---|---|
| volltext+aus | 6/15 | 20 %–64 % | 0.264 | 5 | 60.3 | 77.1 |
| volltext+thesaurus | 6/15 | 20 %–64 % | 0.364 | 5 | 65.3 | 81.0 |
| volltext+llm | 6/15 | 20 %–64 % | 0.266 | 5 | 100.4 | 142.2 |
| grep | 4/15 | 11 %–52 % | 0.233 | 5 | 16.3 | 42.9 |

Gepaarte Vergleiche (B gegen A, je Fall Treffer in Top k): gewonnen = B trifft, A nicht.

| B | gegen A | gewonnen : verloren | gleich | McNemar exakt p |
|---|---|---|---|---|
| volltext+thesaurus | volltext+aus | 1 : 1 | 13 | 1.000 |
| volltext+llm | volltext+aus | 2 : 2 | 11 | 1.000 |

| Fall | erwartete Quellen | Rang volltext+aus | ms volltext+aus | Rang volltext+thesaurus | ms volltext+thesaurus | Rang volltext+llm | ms volltext+llm | Rang grep | ms grep |
|---|---|---|---|---|---|---|---|---|---|
| g02 | ASVG § 139; ASVG § 138 | 8 | 52.4 | 6 | 72.5 | 2 | 108.4 | 2 | 13.9 |
| g03 | GSVG § 106; GSVG § 104a | 10 | 49.4 | 10 | 48.6 | – | 125.3 | – | 42.9 |
| g05 | ASVG § 162 | 5 | 76.6 | 5 | 71.8 | 1 | 84.7 | 1 | 11.0 |
| g06 | ASVG § 136 | – | 50.1 | 1 | 59.1 | – | 72.2 | – | 13.9 |
| g07 | BPGG § 4; BPGG § 22 | – | 64.7 | – | 67.7 | – | 126.9 | – | 20.1 |
| g10 | ASVG § 45; GSVG § 36 | – | 77.1 | – | 69.1 | – | 100.4 | – | 18.8 |
| g18 | ASVG § 253; Altersgrenzen-BVG § 3 | 1 | 27.9 | 1 | 27.4 | 8 | 110.3 | – | 10.6 |
| g20 | ASVG § 367 | – | 64.8 | – | 81.0 | – | 73.7 | – | 15.1 |
| g21 | ASVG § 175 | 3 | 49.1 | – | 57.5 | 6 | 74.8 | – | 33.4 |
| g24a | ASVG § 138; ASVG § 139 | 1 | 66.7 | 1 | 67.5 | 2 | 122.9 | 1 | 16.3 |
| g24b | ASVG § 138; ASVG § 139 | 1 | 65.9 | 1 | 65.3 | 1 | 142.2 | 1 | 15.3 |
| g25 | ASVG § 367 | – | 24.3 | – | 24.0 | – | 43.7 | – | 15.0 |
| w01 | ASVG § 131 | – | 60.3 | – | 57.4 | – | 98.0 | – | 16.8 |
| s-pflege | BPGG § 4; BPGG § 22; PAL080_0125_Mpfl_052026.pdf; fsw-antrag-auf-foerderung-von-leistungen.1779095804.pdf; Serviceratgeber-2026_Broschuere_A5_OEAM_99-19_klein_korr.pdf | 5 | 40.6 | 1 | 63.7 | 2 | 80.0 | – | 16.9 |
| s-casemanager | Antrag Kur und Reha.pdf | – | 63.6 | – | 66.2 | 5 | 126.2 | – | 26.0 |

Begriffe der Erweiterung thesaurus:

- g02: Arbeitsunfähigkeit
- g03: –
- g05: –
- g06: Heilmittel
- g07: –
- g10: –
- g18: –
- g20: Arbeitsunfähigkeit
- g21: Versehrtenrente
- g24a: –
- g24b: –
- g25: –
- w01: –
- s-pflege: Pflegegeld, Pflegebedarf
- s-casemanager: –

Begriffe der Erweiterung llm:

- g02: Anspruchsdauer, Fortbezug, Höchstdauer, Arbeitsunfähigkeit
- g03: Versehrtenrente, Arbeitsunfähigkeit, Leistungsanspruch, Versicherungsfall
- g05: Schutzfrist, Mutterschutz, Entbindung, Geburt
- g06: Befreiung, Zuzahlung, soziale Schutzbedürftigkeit, Rezeptgebührenbefreiung
- g07: Hilfe und Pflege, Antragstellung, zuständiger Pensionsversicherungsträger, Sachverständigengutachten
- g10: Rückerstattung, Überzahlung, Beitragsrückerstattung, Beitragsnachsicht, Antrag, Doppelte Beitragszahlung
- g18: Alterspension, Pensionsalter, Versicherungszeit, Anwartschaft, Anspruchsvoraussetzungen
- g20: Rücknahme des Krankenstandes, Einstellung der Leistung, Bescheid, Beschwerde
- g21: Wegunfall, Unfallversicherung, Weg von der Arbeitsstätte
- g24a: Arbeitsunfähigkeit, Versicherungsfall, Entgeltfortzahlung, Vollversicherung
- g24b: Arbeitsunfähigkeit, Versicherungsfall, Geldleistung, Vollversicherung
- g25: Zustellung, Rechtsmittelbelehrung, Beschwerde, Mitwirkungspflicht
- w01: Wahlarztkosten, Kostenerstattung, Rückerstattung, Einreichung, Honorarnote
- s-pflege: Pflegegeld, Pflegebedarf, Hilflosigkeit, Dauerpflege, Betreuungserfordernis
- s-casemanager: medizinische Rehabilitation, ambulanter Rehabilitationsaufenthalt, Bewilligungsantrag, zuständiger Krankenversicherungsträger, ärztliche Verordnung
