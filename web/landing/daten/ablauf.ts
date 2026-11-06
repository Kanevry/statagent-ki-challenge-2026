/**
 * Inhalte der Seite „Ablauf“: nur belegte Zeitpunkte und Zahlen, jede mit Quelle in Worten.
 * Quellen: GitLab-API (Abruf 06.11.2026, 06:34 bis 06:38), Lage-Log der Flotte, Git-Verlauf von main,
 * abgabe/protokoll.md, Qualitätsberichte, Annahmen und Rückfragen im Repo. Keine Rechner- oder Sitzungsnamen.
 */
export interface AblaufPunkt {
  /** Anzeige, „etwa“ bleibt „etwa“ */
  zeit: string;
  /** für <time> und die Reihenfolge */
  iso: string;
  satz: string;
  /** Beleg in Worten, wird nicht angezeigt */
  quelle: string;
}

const zeitleiste: readonly AblaufPunkt[] = [
  {
    zeit: "5. Nov., 10:36",
    iso: "2026-11-05T10:36:00+01:00",
    satz: "Der Hackathon beginnt, alle anderen Projekte ruhen ab jetzt.",
    quelle: "Lage-Log",
  },
  {
    zeit: "10:54",
    iso: "2026-11-05T10:54:00+01:00",
    satz: "Die Wahl fällt auf Use Case 3, den die Jury bewertet.",
    quelle: "GitLab, Kommentar im Issue zur Wahl; als Commit festgehalten um 12:10",
  },
  {
    zeit: "gegen 14:35",
    iso: "2026-11-05T14:35:00+01:00",
    satz: "Die Startseite ist zum ersten Mal öffentlich erreichbar.",
    quelle: "Lage-Log etwa 14:35, GitLab-Kommentar 14:37",
  },
  {
    zeit: "16:12",
    iso: "2026-11-05T16:12:00+01:00",
    satz: "Ein Mensch gibt die ersten Regeln frei, danach 22 Monate; März und Oktober 2025 bleiben angehalten.",
    quelle: "abgabe/protokoll.md, 16:12 bis 16:14",
  },
  {
    zeit: "20:05",
    iso: "2026-11-05T20:05:00+01:00",
    satz: "Die geprüfte Abgabe für Use Case 3 liegt vollständig im Hauptstand des Repos.",
    quelle: "Git-Verlauf: Merge auf main, der abgabe/manifest.json erstmals enthält",
  },
  {
    zeit: "23:26",
    iso: "2026-11-05T23:26:00+01:00",
    satz: "Die Generalprobe bricht beim Festschreiben ab, um 23:46 besteht sie mit einem Fix.",
    quelle: "Lage-Log",
  },
  {
    zeit: "6. Nov., etwa 00:35",
    iso: "2026-11-06T00:35:00+01:00",
    satz: "Der Zweitrechner fällt aus, weil er keinen Strom hat; die Prüfungen ziehen auf den CI-Server um.",
    quelle: "Lage-Log, die Ursache steht dort ab 05:34",
  },
  {
    zeit: "03:04",
    iso: "2026-11-06T03:04:00+01:00",
    satz: "Der Weg der Jury besteht: von einer frischen Kopie des Repos bis zur geprüften Abgabe in 50 Minuten.",
    quelle: "Lage-Log, 03:04 bis 03:59",
  },
];

export const ABLAUF = {
  titel: "So lief der Hackathon",
  satz: "Am 5. November um 10:36 begann die Arbeit an der Aufgabe, am 6. November um 09:00 ist Abgabe.",
  /** GitLab-API, 06.11.2026, 06:34 bis 06:38 */
  zahlen:
    "Stand 6. November 2026, 06:38: 298 von 323 Änderungen (Merge Requests) sind im Hauptstand, 58 von 202 Aufgaben (Issues) sind erledigt, 144 offen.",
  standIso: "2026-11-06T06:38:00+01:00",
  ueberschriften: { zeitleiste: "Zeitleiste" },
  zeitleiste,
  abschnitte: [
    {
      id: "arbeit",
      titel: "Wie wir gearbeitet haben",
      saetze: [
        // Lage-Log; Arbeitsweise der Plugins
        "Der Session Orchestrator führt eine einzelne KI-Sitzung: Sie plant ihre Arbeit in Wellen, parallele Agenten schreiben Code und Regeln und prüfen einander.",
        // 13: Lage-Log 22:54 und 06:31; 87: GitLab, alle Schreibweisen der Züge; 7: Lage-Log bis 06:18
        "Der Lead Session Orchestrator führt viele Sitzungen zugleich, zeitweise 13: Er bündelt fertige Arbeit (87 gebündelte Merges), spielt sie ein und übergibt bei vollem Kontext an einen Nachfolger, bis 06:18 siebenmal.",
        "Ein Mensch entscheidet und gibt mit Namen frei, die KI schreibt den Code, gerechnet wird ohne KI.",
      ],
    },
    {
      id: "schwierig",
      titel: "Was schwierig war",
      saetze: [
        // abgabe/qualitaetsberichte/2025-10.md
        "Im Oktober 2025 fehlen in der Lieferung 78.949 von 394.200 Beschäftigungsverhältnissen des Vormonats, das Programm hält den Monat deshalb an.",
        // abgabe/qualitaetsberichte/2025-01.md
        "Im Jänner 2025 wechselt die Branchenliste: 189.170 von 386.299 Beschäftigungsverhältnissen tragen einen anderen Abschnitt, der Bericht weist das als Umstellung aus, nicht als echte Entwicklung.",
        // Annahme A13, Vergleich der fünf Lesarten im Repo
        "Die Liste fürs Ministerium ergibt je nach Lesart der Aufgabe andere Personenzahlen, von 32.639 bis 32.741; wir nehmen 32.741 und legen die Annahme als Rückfrage offen.",
      ],
    },
    {
      id: "offen",
      titel: "Was offen ist",
      saetze: [
        // abgabe/rueckfragen/R1.md bis R10.md
        "Zehn Rückfragen an die Fachabteilung sind geschrieben, aber noch nicht gestellt; bis zur Antwort gilt je eine begründete Annahme.",
        // abgabe/protokoll.md
        "März und Oktober 2025 bleiben angehalten, ihre Zahlen sind vorläufig.",
      ],
    },
  ],
} as const;
