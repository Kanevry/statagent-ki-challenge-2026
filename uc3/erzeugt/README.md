# erzeugt/: Code-Dateien der Agenten

Hier liegen Code-Dateien, die eine Agenten-Rolle (meist „reporting“, z. B. die Ministeriums-Lieferung)
geschrieben und ein Mensch mit Vor- und Nachnamen freigegeben hat.

- Name: `<vorschlag-id>_<name>.py` oder `.sql`. Die Nummer ist die Vorschlags-ID in `meta.vorschlag`
  und im Commit-Trailer `Vorschlag: uc3/<id>`.
- Jede Datei beginnt mit einem Kopfkommentar: Rolle, Vorschlag, Anweisung, Hinweis auf die Freigabe.
- Python-Dateien haben `def run(conn, lieferung) -> dict`. SQL-Dateien sind eine einzelne Leseabfrage
  (SELECT oder WITH) mit dem Platzhalter `%(lieferung)s`.
- Eine Datei startet nur, wenn ihr Vorschlag freigegeben ist und ihr Inhalt genau dem freigegebenen
  entspricht (sha256 bzw. Freigabe-Commit). Sonst kommt `NichtFreigegeben` (Technische Regel 6d).
  Wer eine Datei hier von Hand ändert, braucht eine neue Freigabe.
- Gestartet wird über `statagent.agenten.anwenden.erzeugt_ausfuehren`, in einer Nur-Lese-Transaktion.
  Kein Sprachmodell läuft dabei mit.
