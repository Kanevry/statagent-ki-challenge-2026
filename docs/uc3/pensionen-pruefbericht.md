# Prüfbericht Pensionen 2018 bis 2025

Die Zahlen sind die Meldungen der Träger. Geprüft wird, was man aus den Dateien nachrechnen kann. Geändert oder geglättet wird nichts.

- **Dateien:** 28 von 28 geladen, 9 Formate erkannt.
- **Werte:** 880 je Bereich, Pensionsart und Geschlecht.
- **Summen der Dateien:** 394 nachgerechnet, 0 weichen ab.
- **Stand:** vorläufig, noch nicht mit Namen freigegeben. Hash a52e55ebcec6b8cb, Regelstand 348e935f3dd077f2.

## Summen über alle Träger

**Stand der Pensionen**

| Gliederung | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| Insgesamt | 2.350.828 | 2.379.509 | 2.419.281 | 2.450.203 | 2.484.478 | 2.524.184 | 2.556.516 | 2.584.909 |
| PV der Unselbständigen | 1.989.467 | 2.015.224 | 2.050.966 | 2.077.840 | 2.108.013 | 2.142.660 | 2.169.692 | 2.192.607 |
| PV der Selbständigen | 361.361 | 364.285 | 368.315 | 372.363 | 376.465 | 381.524 | 386.824 | 392.302 |

**Vorzeitige Alterspensionen, Teil der Alterspensionen**

| Gliederung | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| Insgesamt | 76.113 | 74.906 | 79.726 | 83.550 | 85.051 | 84.279 | 85.373 | 87.996 |
| PV der Unselbständigen | 65.106 | 63.450 | 67.302 | 70.635 | 72.332 | 72.472 | 73.687 | 75.635 |
| PV der Selbständigen | 11.007 | 11.456 | 12.424 | 12.915 | 12.719 | 11.807 | 11.686 | 12.361 |

## Formate

| Format | Jahre | Dateien | Aufbau |
|---|---|--:|---|
| P01_format_pva_bis_2021 | 2018 bis 2021 | 4 | PVA 2018 bis 2021: Kreuztabelle mit zweizeiligem Kopf, Männer vor Frauen. |
| P02_format_pva_ab_2022 | 2022 bis 2025 | 4 | PVA ab 2022: neue Blätter, flacher Kopf in Zeile 1, Frauen vor Männern. |
| P03_format_sva | 2018 bis 2019 | 2 | SVA 2018 und 2019: eine Datenzeile, Kürzel mit Suffix _M und _F. |
| P04_format_svb | 2018 bis 2019 | 2 | SVB 2018 und 2019: wie SVA, aber Suffix _m und _w. |
| P05_format_vaeb | 2018 bis 2019 | 2 | VAEB 2018 und 2019: zwei Blöcke in einem Blatt, Zahlen als Text mit Tausenderpunkt. |
| P06_format_bvaeb | 2020 bis 2025 | 6 | BVAEB 2020 bis 2025: Aufbau der VAEB, nur der Titel ist neu. |
| P07_format_van | 2018 bis 2019 | 2 | VAN 2018 und 2019: lange Liste, Jahr im Blattnamen, nur Pensionsstand. |
| P08_format_svs_bis_2022 | 2020 bis 2022 | 3 | SVS 2020 bis 2022: lange Liste, Sparte GW und LW, Geschlecht M und W, keine Summenzeilen. |
| P09_format_svs_ab_2023 | 2023 bis 2025 | 3 | SVS ab 2023: Sparte im Klartext, Geschlecht m und w, neue Spalte Zeitraum. |

- **Formatbruch PVA 2022:** Der Träger wechselt sein Format. Der Männeranteil zeigt in diesem Jahr 0 auffällige Fälle; ein vertauschtes Geschlecht fiele hier auf.
- **Formatbruch SVS 2023:** Der Träger wechselt sein Format. Der Männeranteil zeigt in diesem Jahr 0 auffällige Fälle; ein vertauschtes Geschlecht fiele hier auf.

## Lücken in den Meldungen

- **VAN meldet keine vorzeitigen Alterspensionen.** Für VAN 2018 und 2019 gibt es keine Zahl in Tabelle 13. Es wird keine 0 und keine Schätzung eingesetzt. Tabelle 13 der Selbständigen enthält die VAN deshalb nicht. (Beleg: Datei VAN_Pensionsstand_JJJJ.xlsx, Zeile 15, und LIESMICH Zeile 14)
- **BVA liefert keine Pensionsmeldung.** Die Beamten der früheren BVA fehlen in allen Jahren. BVAEB enthält hier nur Eisenbahn und Bergbau und ist nicht der ganze Träger. (Beleg: LIESMICH Zeile 15 und 25; BVAEB-Dateien nennen nur Eisenbahn und Bergbau)
- **SVS meldet keine Summenzeilen.** Für die SVS 2020 bis 2025 gibt es keinen Prüfwert aus der Datei. Geprüft wird nur, dass jede Kombination genau einmal vorkommt. (Beleg: Dateien svs_pensionen_JJJJ.xlsx haben nur Einzelzeilen)

## Übergang 2019 auf 2020

Zum 1.1.2020 wurden Träger zusammengelegt. Die Zeitreihe wird nicht geglättet. 2019 und 2020 stehen unverändert nebeneinander. SVA und VAN werden der Sparte Gewerbliche Wirtschaft gegenübergestellt, SVB der Landwirtschaft. Dass die VAN zur Gewerblichen Wirtschaft kommt, ist eine Annahme: Die Quelle nennt nur die SVS, ohne Sparte.

| Tabelle | Nachfolger | Vorgänger | 2019 | 2020 | Änderung |
|---|---|---|--:|--:|--:|
| T12 | SVS-GW | SVA + VAN | 195.994 | 201.823 | +3,0 % |
| T12 | SVS-LW | SVB | 168.291 | 166.492 | -1,1 % |
| T12 | BVAEB-EB | VAEB-EB | 18.429 | 18.664 | +1,3 % |
| T12 | BVAEB-BB | VAEB-BB | 16.586 | 16.228 | -2,2 % |
| T13 | SVS-GW | SVA + VAN (VAN ohne Meldung) | 5.547 | 6.174 | +11,3 % |
| T13 | SVS-LW | SVB | 5.909 | 6.250 | +5,8 % |
| T13 | BVAEB-EB | VAEB-EB | 900 | 1.033 | +14,8 % |
| T13 | BVAEB-BB | VAEB-BB | 489 | 537 | +9,8 % |

## Auffälligkeiten

Sie sind gemeldet, nicht korrigiert.

- **Sprünge:** 37 Werte ändern sich von einem Jahr aufs nächste um mindestens 15 Prozent (ab 1.000 Pensionen).
- **Männeranteil:** 7 Fälle, in denen er sich um mindestens 5 Prozentpunkte ändert. Ein Spaltentausch ließe alle Summen stimmen und fiele nur hier auf.
- **Tabelle 13 größer als Alterspensionen:** 0 Fälle, Soll ist 0.
- **Bereiche der PVA in der Qualifikation:** 0 Codes, Soll ist 0. Arbeiter und Angestellte der PVA sind frühere Träger, keine Qualifikation.

### Sprünge

| Jahr | Bereich | Art | Geschlecht | Vorjahr | Wert |
|---|---|---|---|--:|--:|
| 2019 | PVA-ANG | LZV | W | 6.878 | 2.643 |
| 2019 | PVA-ANG | SCHWER_APG | M | 1.337 | 1.611 |
| 2019 | PVA-ANG | SCHWER_ASVG | W | 2.233 | 2.728 |
| 2019 | PVA-ARB | LZV | W | 2.585 | 967 |
| 2019 | PVA-ARB | SCHWER_APG | M | 8.352 | 10.330 |
| 2019 | PVA-ARB | SCHWER_ASVG | W | 1.738 | 2.136 |
| 2019 | SVA | LZV | M | 1.930 | 1.623 |
| 2019 | SVA | SCHWER_APG | M | 1.049 | 1.366 |
| 2019 | SVB | SCHWER_APG | M | 1.642 | 2.055 |
| 2019 | SVB | SCHWER_ASVG | W | 3.047 | 3.663 |
| 2020 | PVA-ANG | LZV | M | 9.835 | 11.546 |
| 2020 | PVA-ANG | LZV | W | 2.643 | 1.044 |
| 2020 | PVA-ANG | SCHWER_APG | M | 1.611 | 1.977 |
| 2020 | PVA-ARB | LZV | M | 7.200 | 8.310 |
| 2020 | PVA-ARB | SCHWER_APG | M | 10.330 | 12.451 |
| 2021 | PVA-ANG | LZV | W | 1.044 | 335 |
| 2021 | PVA-ANG | SCHWER_APG | M | 1.977 | 2.286 |
| 2021 | PVA-ANG | SCHWER_ASVG | W | 2.491 | 1.969 |
| 2021 | PVA-ARB | SCHWER_ASVG | M | 2.556 | 1.946 |
| 2021 | PVA-ARB | SCHWER_ASVG | W | 2.018 | 1.638 |
| 2021 | SVS-GW | LZV | M | 1.957 | 2.275 |
| 2021 | SVS-GW | SCHWER_APG | M | 1.726 | 2.016 |
| 2021 | SVS-LW | SCHWER_APG | M | 2.566 | 3.126 |
| 2021 | SVS-LW | SCHWER_ASVG | W | 3.463 | 2.830 |
| 2022 | PVA-ANG | SCHWER_APG | M | 2.286 | 2.672 |
| 2022 | PVA-ANG | SCHWER_ASVG | W | 1.969 | 1.287 |
| 2022 | PVA-ARB | SCHWER_ASVG | M | 1.946 | 1.196 |
| 2022 | PVA-ARB | SCHWER_ASVG | W | 1.638 | 1.059 |
| 2022 | SVS-GW | SCHWER_APG | M | 2.016 | 2.366 |
| 2022 | SVS-LW | SCHWER_ASVG | W | 2.830 | 1.921 |
| 2023 | PVA-ANG | SCHWER_ASVG | W | 1.287 | 450 |
| 2023 | PVA-ARB | SCHWER_ASVG | M | 1.196 | 420 |
| 2023 | PVA-ARB | SCHWER_ASVG | W | 1.059 | 352 |
| 2023 | SVS-GW | SCHWER_APG | M | 2.366 | 2.760 |
| 2023 | SVS-LW | SCHWER_ASVG | W | 1.921 | 671 |
| 2024 | SVS-GW | SCHWER_APG | M | 2.760 | 3.277 |
| 2025 | SVS-LW | GEM | W | 937 | 1.205 |

### Männeranteil

| Jahr | Bereich | Art | Vorjahr | Wert |
|---|---|---|--:|--:|
| 2019 | PVA-ANG | LZV | 60,3 % | 78,8 % |
| 2019 | PVA-ARB | LZV | 75,1 % | 88,2 % |
| 2019 | SVA | LZV | 83,8 % | 92,5 % |
| 2020 | PVA-ANG | LZV | 78,8 % | 91,7 % |
| 2020 | PVA-ARB | LZV | 88,2 % | 95,4 % |
| 2021 | PVA-ANG | LZV | 91,7 % | 97,5 % |
| 2025 | SVS-LW | GEM | 79,7 % | 74,5 % |

## Dateien

| Datei | Format | Werte | Summen | Hash |
|---|---|--:|--:|---|
| 2018/PVA_Jahresmeldung_2018.xlsx | P01_format_pva_bis_2021 | 36 | 24 | 00f7893fbb60 |
| 2018/SVA_PV_2018.xlsx | P03_format_sva | 18 | 2 | 2ce6443998e8 |
| 2018/SVB Pensionen 2018.xlsx | P04_format_svb | 18 | 2 | e076512d7115 |
| 2018/VAEB_Pensionen_2018.xlsx | P05_format_vaeb | 36 | 24 | 68c334a73ae1 |
| 2018/VAN_Pensionsstand_2018.xlsx | P07_format_van | 8 | 1 | 9c64ec3ab8c3 |
| 2019/PVA_Jahresmeldung_2019.xlsx | P01_format_pva_bis_2021 | 36 | 24 | f6ebeafae2ad |
| 2019/SVA_PV_2019.xlsx | P03_format_sva | 18 | 2 | 95ae45de89fa |
| 2019/SVB Pensionen 2019.xlsx | P04_format_svb | 18 | 2 | b98b6439332e |
| 2019/VAEB_Pensionen_2019.xlsx | P05_format_vaeb | 36 | 24 | 37c7999d512a |
| 2019/VAN_Pensionsstand_2019.xlsx | P07_format_van | 8 | 1 | 912e1e27ea2f |
| 2020/BVAEB_Pensionen_2020.xlsx | P06_format_bvaeb | 36 | 24 | c9097dd30cd7 |
| 2020/PVA_Jahresmeldung_2020.xlsx | P01_format_pva_bis_2021 | 36 | 24 | 4456812c72fa |
| 2020/svs_pensionen_2020.xlsx | P08_format_svs_bis_2022 | 36 | 0 | 7a6d9184344c |
| 2021/BVAEB_Pensionen_2021.xlsx | P06_format_bvaeb | 36 | 24 | a25053d7c052 |
| 2021/PVA_Jahresmeldung_2021.xlsx | P01_format_pva_bis_2021 | 36 | 24 | 014c03027c05 |
| 2021/svs_pensionen_2021.xlsx | P08_format_svs_bis_2022 | 36 | 0 | d291d729a646 |
| 2022/BVAEB_Pensionen_2022.xlsx | P06_format_bvaeb | 36 | 24 | d675457d801f |
| 2022/PVA_Jahresmeldung_2022.xlsx | P02_format_pva_ab_2022 | 36 | 24 | 569e3522825c |
| 2022/svs_pensionen_2022.xlsx | P08_format_svs_bis_2022 | 36 | 0 | d84194a708b4 |
| 2023/BVAEB_Pensionen_2023.xlsx | P06_format_bvaeb | 36 | 24 | c294c3698391 |
| 2023/PVA_Jahresmeldung_2023.xlsx | P02_format_pva_ab_2022 | 36 | 24 | 16d445c48407 |
| 2023/svs_pensionen_2023.xlsx | P09_format_svs_ab_2023 | 36 | 0 | 7033bc5ea859 |
| 2024/BVAEB_Pensionen_2024.xlsx | P06_format_bvaeb | 36 | 24 | 3c22b651a9f8 |
| 2024/PVA_Jahresmeldung_2024.xlsx | P02_format_pva_ab_2022 | 36 | 24 | c192a12c94c8 |
| 2024/svs_pensionen_2024.xlsx | P09_format_svs_ab_2023 | 36 | 0 | 0b3401e181fa |
| 2025/BVAEB_Pensionen_2025.xlsx | P06_format_bvaeb | 36 | 24 | 12ee31beb168 |
| 2025/PVA_Jahresmeldung_2025.xlsx | P02_format_pva_ab_2022 | 36 | 24 | 41aeda15d00c |
| 2025/svs_pensionen_2025.xlsx | P09_format_svs_ab_2023 | 36 | 0 | 0beb2d4e9c19 |
