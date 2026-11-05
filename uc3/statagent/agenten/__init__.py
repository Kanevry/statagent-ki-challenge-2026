"""Eigene Agenten von StatAgent (GitLab #15): Anweisung → Koordinator → Rolle → Vorschlag → Probe → Freigabe.

Die Agenten schlagen nur vor. Zahlen rechnet das Programm (``probe_rechnen``), wirksam wird ein Vorschlag
erst nach der Freigabe durch einen Menschen mit Vor- und Nachnamen (``freigabe_ausfuehren``), dann mit
einem Git-Commit, der die Anweisung als Nachricht und ``Freigegeben-von: <Name>`` als Trailer trägt.

Module: ``werkzeuge`` (nur lesen, keine Einzeldaten), ``rollen`` (Prompts und Antwortformate),
``koordinator`` (``agent_ausfuehren``), ``vorschlag`` (anlegen, lesen, ``diff_text``, Probe),
``anwenden`` (Freigabe, Ablehnung, Anwenden, ``erzeugt_ausfuehren``), ``plattform_bruecke`` (Modell und
Freigabe der Plattform E0, erst beim Gebrauch geladen). Der Monatslauf importiert nichts davon.
"""
