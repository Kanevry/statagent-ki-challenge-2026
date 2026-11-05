**Urteil in 3 Sätzen.**

Die Trennung von Kriterium, Prüfsatz und Ergebnis ist tragfähig, aber der vorliegende Stand ist noch keine zuverlässige Grundlage für Abnahme und automatisches Abhaken.
Die größten Risiken sind veraltete Erfolgsbelege, unvollständig erfasste Kriterien und ein Abschluss-Tor, das trotz offener Pflichtfehler erfüllt sein kann.
In der verbleibenden Zeit lohnt sich ein kleiner, abgesicherter Ablauf für UC3 und E6 mit nachvollziehbaren Messungen auf dem endgültigen Abgabestand.

**Befunde**

Alle zehn Unterlagen wurden gelesen. Die unten genannten Codefälle wurden zusätzlich im Arbeitsspeicher geprüft, ohne Dateien zu ändern oder GitLab aufzurufen; die tatsächlichen Issues, Prüfrechner und Abgabedateien wurden nicht nachgemessen.

**Kritisch**

1. **Ein alter oder unzureichender Beleg kann weiterhin „bestanden“ ergeben.** In [05-matrix.py](05-matrix.py), Funktionen `beleg_pruefen`, `stand` und `abhaken`, fehlen Prüfungen auf gültigen Messstand, tatsächliche Ausgabe und gültige Belegdatei. Ein Beleg mit `sha="alt"`, ungültiger Zeit und lediglich `befehl="echo ok"` wurde im Beispiel akzeptiert.
   **Änderung:** Eine gemeinsame Gültigkeitsprüfung vor Anzeige und Abhaken verwenden. Erforderlich sind vollständige Commit-ID, Prüfungsrevision, tatsächliches Ergebnis, Belegreferenz und nachgewiesene Gültigkeit für den Zielstand; bei fehlender Information bleibt das Kriterium ungeprüft.

2. **Der Hash schützt nicht das vollständige Kriterium.** `kriterien` erfasst nur die erste Listenzeile; Änderungen von „mit E07 und 24 Monaten“ zu „ohne E07 und 12 Monaten“ in der Folgezeile erzeugten denselben Hash. Zusätzlich erlaubt der Messauftrag Korrekturen aus Kommentaren, während die Matrix ausschließlich die Beschreibung auswertet.
   **Änderung:** Den vollständigen Kriterienblock einschließlich verbindlicher Nachschärfungen erfassen. Entscheidungen aus Kommentaren vor der Abnahme in den maßgeblichen Wortlaut übernehmen und ihre Kommentar-ID vermerken; Änderungen an Sollquelle oder Prüfsatz müssen Ergebnisse ebenfalls ungültig machen.

3. **Abhaken kann fremde Änderungen überschreiben und unvollständig bleiben.** `abhaken`, Zeilen 325 bis 350, ersetzt die gesamte Beschreibung aus einem zuvor gelesenen Stand, gegebenenfalls sogar aus `--cache`. Schlägt nach dem erfolgreichen PUT der Kommentar fehl, beendet ein Wiederholungsversuch sich bei „schon abgehakt“, ohne den Kommentar nachzuholen.
   **Änderung:** Schreiben aus Cache verbieten; unmittelbar vorher Beschreibung, Revision und Kriterienhash neu prüfen. Für diese Nacht Beschreibungsänderungen je Issue während der Aktualisierung abstimmen, Kommentar mit eindeutiger Beleg-ID wiederholbar anlegen und danach Haken sowie Kommentar verifizieren; ein erneutes GET allein verhindert das Überschreiben gleichzeitiger Änderungen nicht.

4. **Das Abschluss-Tor ist zu schwach.** „Null nicht geprüft“ lässt beliebig viele Fehlschläge zu; ein Satz im Fragenkatalog behebt weder eine falsche Abgabezahl noch eine fehlende Pflichtdatei. `stand` verdeckt außerdem Fehlschläge durch `prio::nach-abgabe`, obwohl der Messauftrag dafür eine ausdrückliche Entscheidung verlangt.
   **Änderung:** Prüfergebnis und Verschiebungsentscheidung getrennt führen. Pflichtumfang von UC3 und E6 muss aktuell bestanden sein; ausdrücklich akzeptierte Restmängel bleiben sichtbar, und ein abweichender Orakelvergleich bleibt gemäß Lead-Auftrag ein Blocker.

**Hoch**

5. **Die Vollständigkeit der 245 Kriterien ist nicht belegt.** `kriterien` ignoriert Fließtext und Tabellen unter Abnahmeüberschriften, behandelt nummerierte Checkboxen als Text und erkennt Checkboxen in `~~~`-Codeblöcken fälschlich als Kriterien. Gleichzeitig nimmt es jede Checkbox außerhalb von Abnahmeabschnitten auf, etwa Aufgaben aus einem Arbeitsplan.
   **Änderung:** Jetzt alle UC3- und E6-Beschreibungen einmal gegen den Export abgleichen, auch Issues mit null Treffern. Nicht unterstützte Formen ausdrücklich melden oder gezielt normalisieren; ein vollständiger Markdown-Parser ist für diese Nacht nicht nötig.

6. **Die IDs sind beim normalen Abhaken stabil, bei Strukturänderungen nicht.** Im geprüften Beispiel ändern `[ ]` zu `[x]` weder ID noch Hash; auch `re.sub(..., count=1)` ersetzt auf der erkannten Checkboxzeile korrekt nur den führenden Haken. Ein eingefügtes Kriterium verschiebt dagegen alle folgenden IDs; gleicher Wortlaut unter anderem Kontext kann sogar einen alten Beleg übernehmen.
   **Änderung:** Vorhandene AC-Kennungen als dauerhafte IDs verwenden oder eine kleine feste Zuordnung führen. Umordnung, Ergänzung und Löschung als Strukturänderung melden; nicht allein über die laufende Nummer zuordnen.

7. **Regex-Treffer beweisen keine vollständige Erfüllung.** Eine erwartete Zahl kann aus einer Sollwertausgabe, einem alten Log oder nur einem Teil eines mehrteiligen Kriteriums stammen. Das Ändern des erwarteten Sollwerts prüft den Matcher, aber noch nicht, ob der Prüfsatz einen fachlichen Fehler erkennt.
   **Änderung:** Kleine Prüfskripte sollen konkrete Werte, Mengen, Dateiinhalte und Teilbedingungen vergleichen und erst danach Erfolg melden. Exitcode 0 als Standard, erwartete andere Codes ausdrücklich festlegen; Regexe nur für einfache, eindeutig definierte Ausgaben verwenden und wichtige Prüfungen mit fehlerhaften Eingaben testen.

8. **Der Schnappschuss friert nur den Code ein.** Datenbankzustand, Regeln, Eingabedaten, exportierte Dateien und ein laufendes Deployment können weiterhin aus anderen Ständen stammen. „Ohne Schlüssel und Sprachmodell“ deckt außerdem die geforderten eigenen Agenten, Azure, Voice und echte Freigabeabläufe nicht ab.
   **Änderung:** Je Lauf vollständige Code-ID, Datenstand, Regelversion, Prüfskriptstand und gegebenenfalls Deployment-ID festhalten. Offline-Zählung und echte Integration getrennt prüfen; die bestehenden Schutzprüfungen für Projekt, Port und Cluster-ID vor jedem DB-Schritt beibehalten.

9. **Pfadlisten allein machen Hand-Belege nicht zuverlässig.** Eine Oberfläche kann sich durch gemeinsame Komponenten, Abhängigkeiten, Konfiguration, Daten oder den Dienst hinter der Seite ändern, obwohl die angegebenen Seitenpfade unverändert bleiben.
   **Änderung:** Relevante gemeinsame Pfade und externe Zustände einschließen. Ist die Abhängigkeit unklar, erneut prüfen; vor dem Abschluss-Tor Screens, Sprache, Voice und Vorführablauf einmal auf dem tatsächlichen Abgabestand nachmessen.

10. **Ergebnisgeschichte und Zusammenführung sind ungeklärt.** Der Entwurf überschreibt `lauf.jsonl`, während `belege_lesen` lediglich den zuletzt angehängten Eintrag nimmt, unabhängig von Messzeit und Messstand. Ein später importierter alter Erfolg kann dadurch einen neueren Fehlschlag verdrängen; für leichte und schwere Teilläufe fehlt eine Auswahlregel, und das vorhandene Skript liest `lauf.jsonl` überhaupt nicht.
    **Änderung:** Abgeschlossene Läufe unverändert mit Lauf-ID, Zielstand und geprüftem Umfang aufbewahren. Ergebnisse nur nach einer ausdrücklichen Gültigkeitsregel zusammenführen; unvollständige Läufe dürfen keine fertige Matrix ersetzen und ausgelassene Prüfungen keine weiterhin gültigen Ergebnisse löschen.

11. **Die pauschale Behandlung von Zeitlimits kann Produktfehler verstecken.** Der dokumentierte Hänger in #66 war ein echter Defekt im Jury-Weg, kein bloßer Prüfrechnerfehler. Auch Exit 127 kann einen fehlenden vorgeschriebenen Produktbefehl oder ein fehlendes Prüfwerkzeug bedeuten.
    **Änderung:** Infrastrukturfehler und Produktfehler anhand des betroffenen Schritts unterscheiden. Ein Lauf-Fehler bleibt ohne Erfolgsbeleg und wird sofort bearbeitet; ein nachgewiesener Verstoß gegen eine Laufzeitvorgabe ist „nicht bestanden“. Nach einem begrenzten Wiederholungsversuch eskalieren.

12. **Das Orakel braucht eine verbindliche fachliche Lesart.** Das Dokument nennt mehrere Varianten und bezeichnet E07 unter Auftrag 2 ausdrücklich als Vorschlag. Für das Ministerium sind 32.741 Zeilen allein kein ausreichender Vergleich; gleiche Zeilenzahlen können unterschiedliche Personen oder TAGE enthalten.
    **Änderung:** Variante, Datenbasis und Entscheidung referenzieren; Tabellen zellweise und die Ministeriumsdatei vollständig vergleichen. Fachliche Abweichungen von LF/CRLF-Unterschieden unterscheiden; das Manifest der Bau-Lane bleibt ein Wiederholbarkeitsbeleg, kein unabhängiger Nachweis fachlicher Richtigkeit.

13. **Bisherige Erfolgsurteile müssen enger gefasst werden.** Die README meldet den Fix von 66-6 als behoben und nachgemessen, während Übergabe und Einzelprotokoll die Nachmessung auf main noch offenlassen. Außerdem wurde der nicht vorhandene Pflichtbefehl `regeln laden` übersprungen; die Netzsperre erfasst laut Beschreibung Python-Sockets, nicht nachweislich sämtliche Prozesskommunikation.
    **Änderung:** Vorabnahme, Messung auf main und Abschlussabnahme ausdrücklich trennen. Abweichungen vom vorgeschriebenen Weg brauchen eine dokumentierte Entscheidung oder einen korrigierten Kriterienwortlaut; die Offline-Aussage auf den tatsächlich geprüften Umfang begrenzen.

**Mittel**

14. **Die Paginierung ist grundsätzlich vorhanden, aber kein konsistenter Schnappschuss garantiert.** `issues_holen` fragt Seiten bis zur leeren Antwort ab; der simulierte Fall mit 140 Issues lieferte korrekt drei Seitenaufrufe. Bei Änderungen während des Abrufs können jedoch Seitengrenzen wandern; außerdem hat der Cache keine erkennbare Frischeprüfung.
    **Änderung:** Stabile Reihenfolge anfordern, doppelte IDs erkennen und Anzahl sowie Abrufzeit protokollieren. Den Issue-Abzug je Lauf aufbewahren; ein alter Cache muss sichtbar sein. Ein pauschaler Vorwurf „glab lädt nur 100 Issues“ wäre hier falsch.

15. **Der Zähler eignet sich noch nicht für das E6-Tor.** `zaehlen` fasst E6 mit E0, E5, UC4 und E4 zusammen; `main_sha` liest lediglich die lokale Referenz `origin/main`. Die Überschrift kann dadurch Aktualität suggerieren, obwohl die einzelnen Belege ältere Stände betreffen.
    **Änderung:** Zusätzlich nach `teil` zählen und E6 gesondert ausweisen. Zielstand, Messstand und Zeitpunkt der Berichtserzeugung unterscheidbar anzeigen; veraltete oder unvollständige Läufe sichtbar markieren.

16. **Der Rhythmus erzeugt unnötige Last und lässt zu wenig Reparaturzeit.** Schwere Läufe nach jedem UC3-Merge können sich überschneiden; gemeinsame Plattformänderungen werden vom Trigger hingegen nicht erfasst. Das erste verbindliche Tor um 06:30 liegt genau am Merge-Stopp.
    **Änderung:** Nur einen schweren Lauf gleichzeitig zulassen, Änderungen bündeln und gemeinsame Abhängigkeiten berücksichtigen. Vorprüfung um 05:00, geplanter Abschlusslauf etwa 05:30 mit gemessener Laufzeitreserve; danach nur gezielte Nachprüfungen freigegebener Änderungen.

17. **Der Messauftrag und die Ausgabekontrolle sind nicht durchgehend abgesichert.** `pytest`, Ruff und `uv run` können trotz des Schreibverbots Caches oder Umgebungen anlegen. `VERBOTEN` erkennt einige Pfade und Adressen, aber keine beliebigen Zugangsdaten oder Personendaten.
    **Änderung:** Mess-Agents in getrennten, festgelegten Schnappschüssen mit externen Cacheverzeichnissen arbeiten lassen. Nur ausgewählte, aggregierte Ergebnisfelder übernehmen und öffentliche Belege vor Veröffentlichung prüfen; die Regex lediglich als zusätzliche Kontrolle behandeln.

18. **Die Matrix verliert den Bezug zur Jurywertung.** Gerade #19-1 mit der Zuordnung der sechs Bewertungsbereiche steht im Auszug auf „nach Abgabe“. Ein hoher Anteil abgehakter interner Kriterien sagt wenig über die erreichbaren 120 Punkte aus.
    **Änderung:** Die vorhandene Rasterzuordnung jetzt herstellen, ohne daraus eine automatische Punkteschätzung abzuleiten. Juryrelevant sind insbesondere unabhängige Zahlenvergleiche, deterministische Wiederholung, echte Agentenaufträge mit menschlicher Freigabe, nachvollziehbare Ergebnisse und vollständig zurückgelesene Abgabedateien.

**Verbesserter Prozess**

- Die drei Teile beibehalten. Ergänzt wird ein kleines Laufmanifest mit Kriterienstand, vollständigem Commit, Prüfungsrevision, Datenstand, Umfang und Abschlussstatus; kein weiteres Verwaltungssystem.
- Sofort UC3 und E6 vollständig inventarisieren. Pflichtumfang, dauerhafte IDs und offene Auslegungsentscheidungen festhalten; spätere Änderungen erhalten Grund, Entscheider und betroffene Nachprüfungen.
- Einen Prüflauf für mehrere Kriterien zulassen. Jedes Kriterium verweist auf die zugehörigen Teilprüfungen und Belege; bei mehrteiligen Kriterien müssen alle Teile erfüllt sein.
- Zuerst Beleggültigkeit, Parserlücken und Ergebniszusammenführung absichern. Automatische Beschreibungsänderungen erst nach Behebung der Schreibfehler aktivieren; bis dahin belegte Urteile ausgeben und Haken kontrolliert setzen.
- Parallel zur kleinen Prozessreparatur die schweren UC3-Prüfungen und E6-Abgabeprüfung starten. Diese dürfen nicht hinter der Erstellung vieler TOML-Einträge warten.
- Stündlich leichte Prüfungen und eine Aktualitätsprüfung durchführen. Schwere Prüfungen nach relevanten gebündelten Änderungen und vor dem Abschluss-Tor ausführen; Laufkonflikte verhindern.
- Zuständigkeiten festhalten: Bau-Lane repariert, Mess-Agents liefern Beobachtungen, Abnahme entscheidet über Prüfurteile, Lead verantwortet Priorität und Merge, Owner beziehungsweise ausdrücklich zuständiger Entscheider akzeptiert fachliche Ausnahmen.
- Definition of Done: Kriterium vollständig geprüft, Beleg gültig, Messstand nachvollziehbar, erforderliche Nachprüfung auf main erledigt. Geschlossenes Issue, grüner MR oder vorhandener Haken genügt nicht.
- Jeden fünften Prüfsatz und alle Abgabezahlen unabhängig nachprüfen, wie beauftragt. Zusätzlich alle mehrdeutigen Pflichtkriterien und kritischen negativen Fälle prüfen.
- Rückfälle umfassen auch „bestanden → veraltet/ungeprüft“. Haken und Kommentare wiederholbar abgleichen; Pflichtblocker sofort an Lane und Lead melden, weitere Zähler zu den vereinbarten Zeiten.
- Beim Abschluss-Tor UC3 und E6 gesondert beurteilen. Abgabedateien, Vorführsystem und geprüften Commit eindeutig zuordnen; nachträgliche Änderungen lösen gezielte Nachprüfungen aus.
- Protokolle je Issue, Mess-Agents, unabhängiges Orakel und generierte Matrix behalten. Für die Präsentation daraus eine kurze Belegübersicht je Bewertungsbereich mit Ergebnis, Einschränkung und Verweis erzeugen.

**Streichliste**

- Heute Nacht keine vollständige universelle Prüfsprache und keinen vollständigen Markdown-Parser bauen.
- Keine neue Prüfung pro Kriterium erzwingen, wenn ein vorhandener Lauf mehrere Kriterien sauber belegt.
- Keine schweren Vollprüfungen nach jedem einzelnen Merge.
- Keine pauschale Einstufung jedes Timeouts als Infrastrukturfehler.
- Keine automatische Verschiebung von Pflichtfehlern allein durch ein Label.
- Keine ungeprüften Erfolgsübernahmen aus alten Protokollen oder später importierten Belegen.
- Keine Behauptung vollständiger Abnahme allein aufgrund von Haken, Zählerständen oder Dateihashes.
- CI-Zeitplanung und breite Automatisierung von UC1, UC2 und allgemeinen Plattformkriterien nachrangig behandeln, bis UC3 und E6 belastbar abgesichert sind.