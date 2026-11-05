# Werkzeug für Screenshots und Folien (#88, #89)

| Datei | Zweck |
|---|---|
| `slides_check.py` | Prüft `web/content/slides/*.md`: 11 Folien, Frontmatter, Sprechernotizen, Summe `dauer_s` ≤ 600, Nennung im Storyboard, Belege im Belegregister, keine Gedankenstriche als Stilmittel. |
| `screens_manifest.py` | Liest `screens/quellen.json` und `screens/SC01.png` bis `SC12.png`, schreibt `screens-manifest.md` (Größe, SHA-256, Herkunft, Art). |
| `aufnahme.mjs` | Nimmt die Bilder über `dev-browser` auf (Desktop 1920 × 1080 nach `screens/`, Mobil 390 × 844 @3x nach `screens/mobil/`). |

| `folien_pdf.mjs` | Macht aus den Folien eine fertige PDF-Datei (eine Seite je Folie, Endzustand) für den USB-Stick. |

## PDF für den USB-Stick (auf dem Zweitrechner, aus `web/`)

```bash
BASIS_URL=<url> AUSGABE=<ordner>/folien-jury.pdf node ../docs/praesentation/werkzeug/folien_pdf.mjs
BASIS_URL=<url>/praesentation/management AUSGABE=<ordner>/folien-management.pdf node ../docs/praesentation/werkzeug/folien_pdf.mjs
```

Die Dateien gehören nicht ins Repo. Auf den Stick kommen beide PDF-Dateien und das Backup-Video. Nach dem Kopieren die SHA-256 vergleichen und einmal öffnen.

## Aufrufe (aus der Repo-Wurzel)

```bash
python3 docs/praesentation/werkzeug/slides_check.py            # Exit 0 nur bei 11/11 gültig
python3 docs/praesentation/werkzeug/screens_manifest.py        # Manifest schreiben, Stand melden
python3 docs/praesentation/werkzeug/screens_manifest.py --check  # Abnahme: Exit 0 nur bei 12/12 gültig
BASIS_URL=<url der Demo> node docs/praesentation/werkzeug/aufnahme.mjs
```

`BASIS_URL` ist standardmäßig `http://localhost:3000`; die Adresse der öffentlichen Demo steht bewusst nicht im Repo.
Das Aufnahmeskript nutzt den eigenen Browser `e5-screens` (headless) und beendet nur diesen. Ein unerwarteter Dialog bricht ab.
Neue Bilder: Eintrag in `ZIELE` in `aufnahme.mjs` ergänzen, danach `quellen.json` (Commit, Lauf, Art, Zeit) pflegen und jedes Bild in `screens-sichtpruefung.md` von einer zweiten Person prüfen lassen.
