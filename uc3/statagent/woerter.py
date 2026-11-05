"""Welche Wörter eine Datenfrage enthalten darf, ohne dass sie etwas anderes meint (#186).

Jedes Wort einer Frage muss bekannt sein: ein Füllwort, ein Wort für die gezählte Sache, ein Zeitwort oder ein
erkanntes Merkmal. Bleibt ein Wort übrig („mit Kindern“, „Betriebe“, „Pizza“, „employees“), kann die Zahl zu einer
anderen Frage gehören; dann gibt es keine Zahl. Sprachverständnis, kein Rechenregelwerk. Die Liste ist bewusst
eine Positivliste: Ein fehlendes Füllwort kostet eine Zahl, ein fehlendes Merkmal kostete die Wahrheit.
„höchste“ steht nicht darin: Nur die Fluktuation kennt einen Höchstwert, sie gibt das Wort selbst frei.
"""

from __future__ import annotations

import re

from statagent.zeitraum import MONATSNAMEN

#: Ziffern am Wort zählen mit: „v2“ ist kein einzelner Buchstabe, sondern eine Angabe, die sonst still wegfiele.
_WORT = re.compile(r"[a-zäöüß]+(?:-[a-zäöüß]+)*\d*")


#: Eine kurze Zahl ohne Monat und ohne Datum schränkt etwas ein, das wir nicht kennen („ab 50“, „unter 25“, „50+“).
#: Ausgenommen: „31.“ vor einem Monat, Zahlen mit Punkt oder Komma, Jahre und lange Mengen („über 10000“).
_LOSE_ZAHL = re.compile(r"(?<![\d.,/-])\d{1,3}(?![\d.,/-]|\.\d)(?!\.)")


def _liste(text: str) -> frozenset[str]:
    return frozenset(text.split())


_FUELLWOERTER = _liste(
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
    servus grüß gott könnt könntet könntest ihr euch bräuchte bräuchten hätten würde würden nennen nenne nennt
    angeben ausgeben liefern auskunft info information interessiert interessieren eigentlich überhaupt denn wohl
    gabs gibts betrachtet betrachten soweit wohlgemerkt jeweilig insbesondere bezogen bezug
    """
)
_SACHE = _liste(
    """
    anzahl gesamtzahl gesamtanzahl gesamtbestand bestand bestands bestandes bestanden unselbständig unselbständige
    unselbständigen unselbstständig unselbstständige unselbstständigen bestehen besteht beschäftigtenstand
    beschäftigtenzahl beschäftigtenzahlen tätig tätige tätigen arbeit arbeite arbeiten arbeitend arbeitende arbeitenden arbeitet arbeitete arbeiteten arbeitnehmer
    arbeitnehmerinnen beschäftigung beschaeftigung beschäftigungen beschäftigt beschaeftigt beschäftigte beschäftigten
    beschaeftigte beschaeftigten beschäftigter beschäftigungsverhältnis beschäftigungsverhältnisse
    beschäftigungsverhältnissen daten datenbank dienstnehmer dienstverhältnis dienstverhältnisse job jobs leute
    menschen mitarbeiter mitarbeiterinnen personen stelle stellen statistik verhältnis verhältnisse verhältnissen zahl
    zahlen
    """
)
_ZEIT = _liste(
    """
    aktuell aktuelle aktuellen derzeit gegenwärtig gegenwaertig heute momentan zurzeit zuletzt jeweils letzte letzten
    letzter letztes vergangene vergangenen vergangener
    jahr jahre jahren jahres monat monate monaten monats monatsletzten monatsletzter monatsende monatsweise stichtag
    stichtage ende anfang mitte beginn zeitraum
    """
)
_AUSWERTUNG = _liste(
    """
    abgang abgänge abgängen abgaenge abschnitt abschnitte abschnitten anteil anteile anteils aufgeteilt aufteilung
    bereich bereichen branche branchen bundesland bundesländer bundesländern bundeslaender durchschnitt durchschnitte
    durchschnittlich durchschnittliche durchschnittlicher durchschnittliches durchschnittlichen verteilen verteilt
    verteilung gegliedert gliederung aufgeschlüsselt aufgegliedert aufschlüsselung entwicklung entwickelt entwickelte fluktuation frauenanteil gegenüber
    gegenueber geschlecht geschlechter ganz ganzen gesamt gesamte gesamten hoch insgesamt
    jahresdurchschnitt jahresmittel kategorie kategorien mittel mittelwert monatsdurchschnitt männeranteil oenace
    önace österreich oesterreich prozent regel summe tabelle verglichen vergleich vergleichen verlauf vs
    wirtschaftsbereich wirtschaftsbereiche wirtschaftsbereichen wirtschaftsabschnitt wirtschaftszweig zeitreihe
    zugang zugänge zugängen zugaenge veränderung veraenderung verändert stieg sank gestiegen gesunken gewachsen
    vormonat vormonats vorjahr
    beschäftigungskategorie beschäftigungskategorien über ueber unter alter
    """
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
        if len(wort) > 1 and wort not in BEKANNT and not all(t in BEKANNT or len(t) < 2 for t in wort.split("-")):
            return _wie_getippt(frage, wort)
    zahl = _LOSE_ZAHL.search(text)
    return zahl.group(0) if zahl else None


def _wie_getippt(frage: str, wort: str) -> str:
    """Das Wort so, wie es in der Frage steht („Kindern“, nicht „kindern“)."""
    fund = re.search(re.escape(wort), frage, re.IGNORECASE)
    return fund.group(0) if fund else wort
