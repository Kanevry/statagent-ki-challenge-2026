/**
 * GLSL ES 3.0 für die Partikel. Alle Übergänge rechnet der Vertex-Shader aus uFortschritt;
 * die CPU schreibt pro Bild nur Uniforms. Punkte sind scharfe runde Scheiben (1 px Antialias),
 * Ausgabe vormultipliert, NormalBlending, kein Glow, keine additive Mischung.
 */
import { SCHRITTE } from "../vertrag";
import { ZEITPLAN as Z } from "./zeitplan";

const f = (x: number) => (Number.isInteger(x) ? `${x}.0` : `${x}`);

export const VERTEX = /* glsl */ `
precision highp float;

#define S2_VON ${f(SCHRITTE[1].von)}
#define S2_LAENGE ${f(SCHRITTE[1].bis - SCHRITTE[1].von)}
#define S3_VON ${f(SCHRITTE[2].von)}
#define S3_LAENGE ${f(SCHRITTE[2].bis - SCHRITTE[2].von)}
#define S4_VON ${f(SCHRITTE[3].von)}
#define S4_LAENGE ${f(SCHRITTE[3].bis - SCHRITTE[3].von)}

in vec2 position;
in vec2 aPruef;
in vec2 aKarte;
in vec2 aTabelle;
in vec4 aZufall;
in vec4 aInfo;
in float aDichte;
in vec2 aStil;

uniform vec2 uAufloesung;
uniform float uPR;
uniform float uFortschritt;
uniform float uLaden;
uniform float uZeit;
uniform float uAtmen;
uniform float uScan;
uniform float uGroesse;
uniform float uAlpha;
uniform vec2 uSaeulen;
uniform float uTabPunkt;

out vec4 vFarbe;
out float vGroesse;
out float vRing;

const vec3 PAPIER = vec3(0.95686, 0.96863, 0.96078); // #F4F7F5
const vec3 MINT = vec3(0.23922, 0.86275, 0.59216);   // #3DDC97
const vec3 GELB = vec3(0.96078, 0.83529, 0.30980);   // #F5D54F
const float PI = 3.14159265;

// Gestaffeltes Fenster: jedes Partikel startet um verz * streu später und braucht (1 - streu) der Zeit.
float fenster(float s, float a, float b, float verz, float streu) {
  float start = a + verz * streu * (b - a);
  float dauer = (b - a) * (1.0 - streu);
  return clamp((s - start) / dauer, 0.0, 1.0);
}

float sanft(float t) {
  return t < 0.5 ? 4.0 * t * t * t : 1.0 - pow(-2.0 * t + 2.0, 3.0) * 0.5;
}

// Weg von a nach b mit leichtem Bogen quer zur Richtung (organischer Fluss statt Gerade)
vec2 weg(vec2 a, vec2 b, float e, float bogen) {
  vec2 d = b - a;
  return mix(a, b, e) + vec2(-d.y, d.x) * sin(PI * e) * bogen;
}

void main() {
  float art = aInfo.x;
  float ziel = aInfo.y;
  float sx = aInfo.z;
  float hn = aInfo.w;

  float s2 = clamp((uFortschritt - S2_VON) / S2_LAENGE, 0.0, 1.0);
  float s3 = clamp((uFortschritt - S3_VON) / S3_LAENGE, 0.0, 1.0);
  float s4 = clamp((uFortschritt - S4_VON) / S4_LAENGE, 0.0, 1.0);

  bool istBefund = art > 0.5;
  bool istRing = art > 1.5;
  bool zurKarte = ziel > 0.5 && ziel < 1.5;
  bool unbekannt = ziel > 1.5;

  // Prüflinie: markiert, sobald sie die Säulenmitte passiert hat
  float markiert = istBefund ? smoothstep(sx - 3.0, sx + 9.0, uScan) : 0.0;
  float e2 = istBefund ? sanft(fenster(s2, ${f(Z.gruppeVon)}, ${f(Z.gruppeBis)}, aZufall.x, 0.5)) : 0.0;

  // Schritt 3: 2024-08 (erste Säule) führt, die übrigen Säulen folgen von links nach rechts
  float spalte = clamp((sx - uSaeulen.x) / max(uSaeulen.y - uSaeulen.x, 1.0), 0.0, 1.0);
  float start3 = spalte < 0.001
    ? ${f(Z.fuehrungVon)} + ${f(Z.fuehrungStreu)} * (0.7 * aZufall.y + 0.3 * (1.0 - hn))
    : ${f(Z.folgeVon)} + ${f(Z.folgeStaffel)} * spalte + ${f(Z.folgeStreu)} * aZufall.y;
  float e3 = istRing ? 0.0 : sanft(clamp((s3 - start3) / ${f(Z.flug)}, 0.0, 1.0));
  float e4 = istRing ? 0.0 : sanft(fenster(s4, ${f(Z.tabelleVon)}, ${f(Z.tabelleBis)}, aZufall.z, 0.5));

  float bogen = (aZufall.w - 0.5) * 0.5;
  vec2 p = position;
  p = weg(p, aPruef, e2, bogen);
  p = weg(p, aKarte, e3, bogen * 0.3);
  p = weg(p, aTabelle, e4, bogen * 0.4);

  // Laden: Partikel fallen von oben in ihre Säule, links zuerst, unten zuerst
  float lad = 1.0;
  if (uLaden < 1.0) {
    float verz = 0.38 * (sx / uAufloesung.x) + 0.2 * hn + 0.1 * aZufall.x;
    float t = clamp((uLaden - verz) / 0.32, 0.0, 1.0);
    lad = 1.0 - pow(1.0 - t, 3.0);
    vec2 start = p + vec2((aZufall.y - 0.5) * 24.0, -(80.0 + aZufall.z * 260.0));
    p = mix(start, p, lad);
  }

  // Leerlauf: minimales Atmen (uAtmen ≤ 0,6 px, 0 bei reduzierter Bewegung), nicht in den Balken
  p += uAtmen * (1.0 - e4) * vec2(sin(uZeit * 0.9 + aZufall.x * 6.2832), cos(uZeit * 0.7 + aZufall.y * 6.2832));

  gl_Position = vec4(p.x / uAufloesung.x * 2.0 - 1.0, 1.0 - p.y / uAufloesung.y * 2.0, 0.0, 1.0);

  vec3 farbe = PAPIER;
  float alpha = uAlpha;
  float groesse = uGroesse;
  if (istRing) {
    farbe = GELB;
    alpha = 0.95 * markiert * (1.0 - smoothstep(0.0, ${f(Z.ringeAusBis)}, s3));
    groesse = aDichte;
  } else if (istBefund) {
    farbe = mix(PAPIER, GELB, markiert);
    alpha = mix(uAlpha, 1.0, markiert);
    groesse = uGroesse * mix(1.0, 1.45, max(markiert * 0.7, e2));
  }

  if (zurKarte) {
    // gezählt: Mint; Größe und Deckkraft aus der örtlichen Dichte (Wien: klein und blass)
    farbe = mix(farbe, MINT, e3);
    alpha = mix(alpha, aStil.y, e3);
    groesse = mix(groesse, aStil.x, e3);
    // Balken: Punkte decken sich knapp, damit die Fläche gleichmäßig wird (kein Moiré)
    alpha = mix(alpha, 1.0, e4);
    groesse = mix(groesse, uTabPunkt * 1.35, e4);
  } else if (unbekannt) {
    // ohne Bundesland: gelbe Gruppe neben der Karte, dann zehnter Balken
    farbe = mix(farbe, GELB, e3);
    alpha = mix(alpha, 1.0, e3);
    groesse = mix(groesse, uGroesse * 1.45, e3);
    groesse = mix(groesse, uTabPunkt * 1.35, e4);
  }

  alpha *= lad;
  vFarbe = vec4(farbe * alpha, alpha);
  vGroesse = groesse * uPR + 1.0;
  vRing = istRing ? 1.0 : 0.0;
  gl_PointSize = vGroesse;
}
`;

export const FRAGMENT = /* glsl */ `
precision highp float;

in vec4 vFarbe;
in float vGroesse;
in float vRing;

uniform float uPR;

out vec4 fragColor;

void main() {
  float r = length(gl_PointCoord - 0.5) * vGroesse;
  float aussen = (vGroesse - 1.0) * 0.5;
  float a = clamp(aussen - r + 0.5, 0.0, 1.0);
  if (vRing > 0.5) {
    float innen = aussen - max(1.0, 1.1 * uPR);
    a *= clamp(r - innen + 0.5, 0.0, 1.0);
  }
  if (a < 0.004) discard;
  fragColor = vFarbe * a;
}
`;
