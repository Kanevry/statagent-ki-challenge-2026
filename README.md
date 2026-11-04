# ki-challenge-2026

Arbeitsrepo für die **KI Challenge 2026** des Dachverbands der Sozialversicherungsträger und der WK Wien
(Do 05.11. 10:00 bis Fr 06.11. ca. 13:15, Kundmanngasse 21, 1030 Wien). Team OneShotAndy, solo.

- **Bis Do 12:00 liegt hier kein Code**, nur Plan und Backlog (Issues). Ab 12:00 entsteht der Code hier.
- **Abgabe:** öffentliches GitHub-Repo `KIChallenge/OneShotAndy` als zweiter Remote. Alles, was hier landet,
  muss dort veröffentlicht werden dürfen (keine Secrets, kein Code aus anderen Produkten, nur synthetische
  oder öffentliche Daten). Der Dachverband darf das Abgabe-Repo uneingeschränkt nutzen.
- **Plan:** Vault `05-business/career/hackathons-2026-27/ki-challenge/spielplan.md` (Einstieg), dort auch alle
  Rechercheberichte, das Startkit und die Click-Dummy-Spezifikationen. Vault-Issue agents/vault#427.

## Use Cases (aus `KI-Challenge_UseCase.yaml`, Stand 03.11.)

| Kürzel | Name | Kurz |
|---|---|---|
| uc1 | SV KI-Lotse | Gesundheits- und Sozialversicherungs-Chatbot |
| uc2 | HealthPolicy Simulator | Multi-Agenten-Simulator für politische, organisatorische und finanzielle Entscheidungen |
| uc3 | StatAgent | agentengestützter Statistikprozess |

## Leitlinie

Ein Produkt mit gemeinsamem Kern (Belegschicht, deterministische Rechenschicht, Audit-Trail, Modell-Schalter
EU-Cloud / lokal, Golden Sets) und drei Räumen. Gewertet wird genau ein Use Case, Wahl Do 11:00 bis 12:00 nach
der Tabelle im Spielplan. Kürzungspunkte Do 15:00 und Fr 03:00, Feature-Stopp Fr 07:00.

## Labels

`uc1`, `uc2`, `uc3` (Raum), `kern` (gemeinsam), `ablauf` (Termine, Abgabe, Pitch), `owner` (Handgriff des Owners).
