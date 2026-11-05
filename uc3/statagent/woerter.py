"""Welche Wörter eine Datenfrage enthalten darf, ohne dass sie etwas anderes meint (#186).

Jedes Wort einer Frage muss bekannt sein: ein Füllwort, ein Wort für die gezählte Sache, ein Zeitwort oder ein
erkanntes Merkmal. Bleibt ein Wort übrig („mit Kindern“, „Betriebe“, „Pizza“, „employees“), kann die Zahl zu einer
anderen Frage gehören; dann gibt es keine Zahl. Sprachverständnis, kein Rechenregelwerk. Die Liste ist bewusst
eine Positivliste: Ein fehlendes Füllwort kostet eine Zahl, ein fehlendes Merkmal kostete die Wahrheit.
"""

from __future__ import annotations

import re

from statagent.zeitraum import MONATSNAMEN

_WORT = re.compile(r"[a-zäöüß]+(?:-[a-zäöüß]+)*")

_FUELLWOERTER = frozenset(
    """
    ab alle allen aller alles als am an auch auf aus bei beim bin bis bitte da damit dann das dass dem den denn der des
    dessen die dies diese diesem diesen dieser dieses doch dort du durch ein eine einem einen einer eines er es für fuer
    gab gegeben gerne gern gibt gäbe guten geben habe haben hallo hat hatte hatten hätte hätten ich ihre ihrer ihnen im
    in ist ja je jetzt kann können koennen könnten laut mal man mehr meine mich mir mit möchte möchten moechte müsste
    nach nur oder pro schon sehr seien sein seit sich sie sind so soll sollen sollte tag um und uns von vom vor war
    waren was welche welchem welchen welcher welches wenn wer werden wie wieviel wieviele wir wird wissen
    wurde wurden wäre wären zu zum zur zwar danke dank vielen voraus hilfe frage fragen wüsste wuesste gerade bericht
    abteilung präsentation vorstand brauche brauchen benötige möglich möglichst genau ungefähr etwa rund handelt
    viel viele vieler sagen sag zeig zeige zeigen steht stehen stand
    """.split()
)
_SACHE = frozenset(
    """
    anzahl arbeit arbeite arbeiten arbeitend arbeitende arbeitenden arbeitet arbeitete arbeiteten arbeitnehmer
    arbeitnehmerinnen beschäftigung beschaeftigung beschäftigungen beschäftigt beschaeftigt beschäftigte beschäftigten
    beschaeftigte beschaeftigten beschäftigter beschäftigungsverhältnis beschäftigungsverhältnisse
    beschäftigungsverhältnissen daten datenbank dienstnehmer dienstverhältnis dienstverhältnisse job jobs leute
    menschen mitarbeiter mitarbeiterinnen personen stelle stellen statistik verhältnis verhältnisse verhältnissen zahl
    zahlen
    """.split()
)
_ZEIT = frozenset(
    """
    aktuell aktuelle aktuellen derzeit gegenwärtig gegenwaertig heute momentan zurzeit zuletzt jeweils letzte letzten
    letzter letztes vergangene vergangenen vergangener
    jahr jahre jahren jahres monat monate monaten monats monatsletzten monatsletzter monatsende monatsweise stichtag
    stichtage ende anfang mitte beginn jahresende jahresanfang jahresmitte zeitraum
    """.split()
)
_AUSWERTUNG = frozenset(
    """
    abgang abgänge abgängen abgaenge abschnitt abschnitte abschnitten anteil anteile anteils aufgeteilt aufteilung
    bereich bereichen branche branchen bundesland bundesländer bundesländern bundeslaender durchschnitt durchschnitte
    durchschnittlich durchschnittliche entwicklung entwickelt entwickelte fluktuation frauenanteil gegenüber
    gegenueber geschlecht geschlechter ganz ganzen gesamt gesamte gesamten hoch höchste höchsten hoechste insgesamt
    jahresdurchschnitt jahresmittel kategorie kategorien mittel mittelwert monatsdurchschnitt männeranteil oenace
    önace österreich oesterreich prozent regel summe tabelle verglichen vergleich vergleichen verlauf vs
    wirtschaftsbereich wirtschaftsbereiche wirtschaftsbereichen wirtschaftsabschnitt wirtschaftszweig zeitreihe
    zugang zugänge zugängen zugaenge
    beschäftigungskategorie beschäftigungskategorien über ueber unter alter
    """.split()
)
BEKANNT = _FUELLWOERTER | _SACHE | _ZEIT | _AUSWERTUNG | frozenset(MONATSNAMEN)


def unbekanntes_wort(frage: str, erkannt: list[str]) -> str | None:
    """Das erste Wort der Frage, das weder bekannt noch Teil eines erkannten Merkmals ist, sonst None.

    ``erkannt`` sind die Textstellen, die ein Merkmal der Frage getroffen haben („Wien“, „Gesundheitswesen“).
    """
    text = frage.lower()
    for stelle in sorted(erkannt, key=len, reverse=True):
        text = text.replace(stelle.lower(), " ")
    for treffer in _WORT.finditer(text):
        wort = treffer.group(0)
        if len(wort) > 1 and wort not in BEKANNT:
            return wort
    return None
