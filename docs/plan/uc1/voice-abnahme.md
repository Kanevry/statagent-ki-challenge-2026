# UC1: Voice-Abnahme und Fallback

## Zweck und Bezug

Dieses Blatt hält den Stand und den Vorführablauf für Abnahme-Issue #36 fest.
Bezug: #34 (Voice-Anbindung), #35 (UC1-Webseite), Epic #23.
Grundlage: `docs/plan/uc1/2026-11-05-prd-e2-uc1-ki-lotse.md`, § 3, insbesondere E und External Acceptance A1.
Es ersetzt keine Qualitätskriterien des PRD.

## Kriterium, Oracle und Frist

Kriterium wörtlich: Szenario komplett, ≥ 1 Quelle je Antwort sichtbar, Median der Antwortpause ≤ 2,0 s.
Oracle: Der Owner spricht das Pflege-Szenario am Rechner im Veranstaltungs-WLAN.
Er prüft die Antwortzeit-Uhr und die Vapi-Turn-Latenz aus `GET /call/{id}`.
Der PRD verlangt mindestens 10 Wechsel und dieselben sichtbaren Quellen im Text- und Sprachpfad.
Beleg: `docs/plan/uc1/2026-11-05-prd-e2-uc1-ki-lotse.md`, § 3 E und A1.

Feature-Stopp: **Fr 06.11.2026 07:00 Europe/Vienna**. Abgabe: **Fr 06.11.2026 09:00 Europe/Vienna**.
Nach 07:00 wird kein Feature mehr gebaut. Fehlende Teile werden als fehlend gezeigt.
Die ursprünglichen Qualitätskriterien bleiben bestehen. Ein Fallback ist kein bestandener Voice-Nachweis.

## Stand im Checkout

- Kern: `uc1/uc1/kern.py` bietet `frage(..., modus="sprache")` und `MAX_AUSSAGEN_SPRACHE = 2`.
  Der Sprachmodus nutzt Regeln und Thesaurus statt eines Analyse-Aufrufs.
  `sprach_modell` ruft das Antwortmodell mit niedrigem Aufwand auf.
  Zitate, Träger und Schritte bleiben strukturiert erhalten. Beleg: auch `docs/plan/uc1/kern.md`, Abschnitt Modus `sprache`.
- Gemeinsamer Voice-Baustein: `shared/py/plattform/voice/kern.py` bietet den Custom-LLM-Router,
  den Webhook und Belege je Call-ID. `shared/py/plattform/voice/app.py` stellt bisher nur UC4 bereit.
  Das belegt keine fertige UC1-Voice-Anbindung.
- UC1-API: `uc1/uc1/api.py` ist nicht gebaut. Die Suche nach `voice` und `erstelle_router` in `uc1/`
  findet keine UC1-Anbindung. `uc1/uc1/cli.py` nennt den Dienst nur als Einstieg.
  Gebaut ist die Text-Route `web/app/api/uc1/frage/route.ts`.
  Sie nutzt `web/components/uc1/lotse.ts` und darüber `lotse frage --json` mit demselben Kern.
- Web: `shared/ui/src/voice/voice-knopf.tsx` enthält den gemeinsamen `VoiceKnopf` mit Transkript-Ereignissen.
  In `web/components/uc1/` und `web/app/uc1/` ist seine Einbindung nicht gebaut.
  Eine UC1-Antwortzeit-Uhr für Sprachpausen ist dort nicht gebaut.
  Der Sekundenzähler im gemeinsamen VoiceKnopf zählt die Gesprächsdauer, keine Antwortpausen.
- Messung: `docs/plan/uc1/kern.md` nennt für den Sprachmodus zwei Läufe mit je drei Wechseln.
  Die Mediane betragen 2.054 ms und 2.115 ms. Schon der Kern verfehlt damit ≤ 2,0 s.
  Die vollständige UC1-Sprachkette im Veranstaltungs-WLAN ist nicht gemessen.
  `docs/plan/uc1/messung-ende.md` nennt für den Text-Rauchtest p50 3,1 s und p95 4,1 s je Wechsel.
  `docs/plan/uc1/sprache.md` misst Textverständlichkeit und Satzlängen, keine Voice-Antwortpause.

## Fallback

Text-Fallback: Auf `/uc1` die erfundene Pflege-Situation eintippen und Rückfragen beantworten.
Die Antwort kommt aus demselben Lotse-Kern. Belege: `web/components/uc1/lotse-kontext.tsx`,
`web/components/uc1/lotse.ts`, `uc1/uc1/kern.py`.

Replay-Fallback: Auf `/uc1` „Aufgezeichnetes Gespräch ansehen“ wählen.
Die Fixture `web/components/uc1/fixtures/pflege.json` enthält das aufgezeichnete Pflege-Gespräch.
Das Abspielen läuft ohne Netz und ohne Modell aus der geladenen Web-Anwendung.
Belege: `web/components/uc1/seiten.tsx`, `web/components/uc1/lotse-kontext.tsx`, `web/components/uc1/replay.ts`.
Der Replay-Code prüft den Hash der Zitat-Belege. Die Fixture nennt zwei von Hand angeglichene Aussagetexte.
Das Replay ist daher kein unveränderter Live-Lauf und kein Voice-Latenznachweis.

Online ohne Freigabe-Schalter `KIC_ONLINE_UC1=1` zeigt `/uc1` nur das Replay,
wenn der Online-Lesemodus `KIC_ONLINE_LESEND=1` gilt.
Diese genaue Bedingung steht in `web/app/uc1/page.tsx`.

## Ablauf für den Owner am Vorführtag

1. Vor Beginn den Stand prüfen. Voice nur versuchen, wenn die UC1-Anbindung gebaut und gemessen ist.
   Nach dem hier belegten Stand direkt den Fallback wählen. Nach 07:00 keinen Featurebau beginnen.
2. Bei belegtem Voice-Weg am Rechner im Veranstaltungs-WLAN das Pflege-Szenario sprechen.
   Rückfragen beantworten und je Antwort mindestens eine sichtbare Quelle öffnen.
3. Bei diesem Voice-Lauf mindestens 10 Wechsel mit der Antwortzeit-Uhr messen.
   Die Pausen mit `GET /call/{id}` abgleichen und den Median gegen ≤ 2,0 s prüfen.
   Fehlt die Uhr oder ein Messbeleg, das Ergebnis als „nicht gemessen“ festhalten.
4. Im Text-Fallback `/uc1` zeigen, die Situation eingeben und Rückfragen beantworten.
   Leistungen, sichtbare Quellen und den vorbereiteten Antrag zeigen.
   Eine Textlaufzeit ersetzt keine gemessene Sprachpause.
5. Ist live nicht verfügbar, „Aufgezeichnetes Gespräch ansehen“ wählen.
   Den aufgezeichneten Ablauf mit Quellen und Antrag zeigen und ausdrücklich als Replay benennen.
   Die Abspielpausen sind keine Live-Antwortzeiten. Den Voice-Oracle als „nicht gemessen“ festhalten.

## Datenschutz

Der PRD nennt externe Sprachdienste Vapi, Deepgram und ElevenLabs in den USA.
Daher nur erfundene Personas sprechen. Beleg: `docs/plan/uc1/2026-11-05-prd-e2-uc1-ki-lotse.md`, § 4.
Der aktuelle gemeinsame Assistant nutzt Vapi, Deepgram und eine Azure-Stimme, nicht ElevenLabs.
`recordingEnabled: false` ist sowohl direkt als auch im `artifactPlan` gesetzt.
Beleg: `shared/py/plattform/voice/assistant.py`.
Das schaltet die Audioaufnahme aus, nicht die Verarbeitung durch externe Dienste.
`docs/voice.md` hält fest, dass Vapi das Transkript nach eigenen Regeln aufbewahrt.
