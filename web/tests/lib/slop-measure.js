/**
 * Anti-Schablonen-Messung der Plattform (Issue #62).
 *
 * Zählt in der gerade gerenderten Seite die Muster, an denen man eine generische, maschinell zusammengesetzte
 * Oberfläche erkennt. Für StatAgent (UC3), den KI-Lotsen (UC1) und den HealthPolicy Simulator (UC2) gilt:
 * Eine Zahl, ein Beleg oder eine Freigabe soll durch Inhalt auffallen, nicht durch Deko. Typische Treffer wären
 * ein Versal-Etikett „LIEFERUNG 2025-03“ über der Überschrift eines Laufs, eine Kachel mit Symbol neben
 * „Qualitätsbericht“, eine Schattenkarte um eine Kennzahl oder eine Überschrift als Frage („Was zählt?“).
 *
 * Läuft als reine Browser-Funktion: `page.addScriptTag({ path })`, dann `page.evaluate(() => measureSlop(...))`.
 * Rückgabe: { counts, fonts, headings, samples }. Zahlen gelten je Seite und Viewport; `samples` nennt bis zu
 * fünf Beispiele je Muster (Element und Textanfang), damit ein Treffer schnell zu finden ist.
 * Das Gate prüft zwölf Schlüssel von `counts` auf 0 (Liste und Behebung: docs/design.md).
 */
function measureSlop(opts) {
  const o = Object.assign({ samples: true, root: 'main' }, opts || {});
  const root = document.querySelector(o.root) || document.body;
  const all = Array.from(root.querySelectorAll('*'));
  const samples = {};
  const note = (metric, el) => {
    if (!o.samples) return;
    const list = samples[metric] || (samples[metric] = []);
    if (list.length >= 5) return;
    const text = (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 60);
    list.push(el.tagName.toLowerCase() + ' "' + text + '"');
  };

  const canvas = document.createElement('canvas');
  canvas.width = 1; canvas.height = 1;
  const c2d = canvas.getContext('2d', { willReadFrequently: true });
  const cache = new Map();
  const rgba = (css) => {
    if (!css || css === 'transparent' || css === 'none') return [0, 0, 0, 0];
    if (cache.has(css)) return cache.get(css);
    let v = [0, 0, 0, 0];
    if (c2d) {
      c2d.clearRect(0, 0, 1, 1); c2d.fillStyle = '#000000'; c2d.fillStyle = css; c2d.fillRect(0, 0, 1, 1);
      const d = c2d.getImageData(0, 0, 1, 1).data; v = [d[0], d[1], d[2], d[3] / 255];
    }
    cache.set(css, v); return v;
  };
  const chroma = (c) => Math.max(c[0], c[1], c[2]) - Math.min(c[0], c[1], c[2]);
  const lum = (c) => (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255;
  const px = (v) => { const n = parseFloat(v); return Number.isFinite(n) ? n : 0; };
  const shown = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width <= 1 || r.height <= 1) return false;
    return typeof el.checkVisibility === 'function' ? el.checkVisibility({ visibilityProperty: true }) : true;
  };
  const ovX = (a, b) => Math.min(a.right, b.right) - Math.max(a.left, b.left);
  const ovY = (a, b) => Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
  const squash = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const ownText = (el) => Array.from(el.childNodes).some((n) => n.nodeType === 3 && (n.textContent || '').trim());

  const titleLike = (el) => {
    if (!ownText(el)) return false;
    const cs = getComputedStyle(el);
    if (px(cs.fontWeight) < 600 || px(cs.fontSize) < 15 || /mono/i.test(cs.fontFamily)) return false;
    const len = squash(el.textContent).length;
    return len >= 2 && len <= 100 && !el.closest('button,[role="button"]');
  };
  const heads = all.filter((el) => el.matches('h1,h2,h3,h4,[role="heading"]') || titleLike(el))
    .filter(shown).map((el) => ({ el, r: el.getBoundingClientRect() }));
  const aboveHeading = (el) => {
    const r = el.getBoundingClientRect();
    return heads.some((h) => !h.el.contains(el) && !el.contains(h.el) && h.r.top >= r.bottom - 4 && h.r.top - r.bottom <= 64 && ovX(r, h.r) > 0);
  };
  const isUpper = (el, cs) => {
    const t = squash(el.textContent);
    if (!t || !/[A-Za-zÄÖÜäöü]/.test(t)) return false;
    return cs.textTransform === 'uppercase' || (t === t.toUpperCase() && t !== t.toLowerCase());
  };
  const serif = (ff) => { const f = ff.toLowerCase(); return /fraunces|georgia|times|ui-serif|playfair|instrument serif/.test(f) || /(^|,)\s*serif\s*(,|$)/.test(f); };
  const shadowBlur = (s) => {
    if (!s || s === 'none') return 0;
    let best = 0;
    for (const layer of s.split(/,(?![^(]*\))/)) {
      const col = /(?:rgba?|oklch|oklab|lab|lch|hsla?|color)\([^)]*\)|#[0-9a-f]{3,8}/i.exec(layer);
      if (col && rgba(col[0])[3] === 0) continue;
      const rest = col ? layer.replace(col[0], '') : layer;
      const nums = Array.from(rest.matchAll(/(-?[\d.]+)px/g)).map((m) => parseFloat(m[1]));
      if (nums.length >= 3 && nums[2] > best) best = nums[2];
    }
    return best;
  };
  const blurPx = (f) => { const m = /blur\(([\d.]+)px\)/.exec(f || ''); return m ? parseFloat(m[1]) : 0; };
  const lightBehind = (el) => {
    let n = el.parentElement;
    while (n) { const c = rgba(getComputedStyle(n).backgroundColor); if (c[3] >= 0.5) return lum(c) > 0.6; n = n.parentElement; }
    return true;
  };
  const aiWord = (s) => /(^|[^A-Za-zÀ-ÿ])(KI|AI)(?![A-Za-zÀ-ÿ])/.test(s) || /künstlich|artificial intelligence/i.test(s);

  const c = { kickersMono: 0, kickersCaps: 0, italicSerifLines: 0, iconTiles: 0, ghostCards: 0, shadowCards: 0,
    sideStripes: 0, lightOrbs: 0, pulsingDecor: 0, sparklesNonAi: 0, gradientText: 0, glassBlur: 0,
    pureWhiteBg: 0, pureBlackText: 0 };
  const tiles = [];
  const fontUse = new Map();

  for (const el of all) {
    const cs = getComputedStyle(el);
    // Unsichtbares zählt nicht: display none und visibility hidden/collapse einheitlich ausschließen.
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.visibility === 'collapse') continue;
    const parent = el.parentElement && el.parentElement !== root ? el.parentElement : null;
    const r = el.getBoundingClientRect();
    const visible = r.width > 1 && r.height > 1;

    if (visible && ownText(el)) {
      const fam = cs.fontFamily.split(',')[0].replace(/["']/g, '').trim();
      fontUse.set(fam, (fontUse.get(fam) || 0) + squash(el.textContent).length);
      const col = rgba(cs.color);
      if (col[3] > 0.9 && col[0] === 0 && col[1] === 0 && col[2] === 0) { c.pureBlackText++; note('pureBlackText', el); }
    }

    // Etikett über einer Überschrift: Mono-Variante und Versal-Variante (klein, Großbuchstaben, gesperrt).
    // Zählt auch eine eigene Block-Zeile INNERHALB der Überschrift, über deren restlichem Text
    // (z. B. <h2><span>LIEFERUNG</span>März 2025</h2>), sonst bleibt das Muster unsichtbar.
    const hostHeading = el.closest('h1,h2,h3,h4,h5,h6,[role="heading"]');
    const inHeadingKicker = hostHeading && hostHeading !== el && !cs.display.startsWith('inline') &&
      squash(hostHeading.textContent).length > squash(el.textContent).length &&
      el.getBoundingClientRect().bottom <= hostHeading.getBoundingClientRect().bottom - 8;
    if (visible && !el.closest('button,a,nav') && (!hostHeading || inHeadingKicker) && ownText(el) && isUpper(el, cs)) {
      const text = squash(el.textContent);
      const pcs = parent ? getComputedStyle(parent) : null;
      if (text.length <= 80 && !(parent && pcs && isUpper(parent, pcs) && squash(parent.textContent) === text) && (inHeadingKicker || aboveHeading(el))) {
        if (/mono/i.test(cs.fontFamily)) { c.kickersMono++; note('kickersMono', el); }
        else if (px(cs.fontSize) <= 14 && (px(cs.letterSpacing) >= 0.5 || cs.textTransform === 'uppercase')) { c.kickersCaps++; note('kickersCaps', el); }
      }
    }

    if (cs.fontStyle !== 'normal' && serif(cs.fontFamily) && squash(el.textContent) && !(parent && getComputedStyle(parent).fontStyle !== 'normal' && serif(getComputedStyle(parent).fontFamily)) && visible) {
      c.italicSerifLines++; note('italicSerifLines', el);
    }

    if (visible && (cs.backgroundClip === 'text' || cs.webkitBackgroundClip === 'text') && cs.backgroundImage.includes('gradient')) {
      c.gradientText++; note('gradientText', el);
    }
    if (visible && blurPx(cs.backdropFilter || cs.webkitBackdropFilter) >= 4) { c.glassBlur++; note('glassBlur', el); }
    if (visible && r.width >= 200 && r.height >= 80) {
      const bg = rgba(cs.backgroundColor);
      if (bg[3] > 0.95 && bg[0] === 255 && bg[1] === 255 && bg[2] === 255) { c.pureWhiteBg++; note('pureWhiteBg', el); }
    }
    if (!visible) continue;

    if (r.width >= 32 && r.width <= 128 && r.height >= 32 && r.height <= 128) {
      const ratio = r.width / r.height;
      const bg = rgba(cs.backgroundColor);
      const tinted = (bg[3] >= 0.08 && Math.min(bg[0], bg[1], bg[2]) < 245) || cs.backgroundImage.includes('gradient');
      if (ratio >= 0.7 && ratio <= 1.4 && tinted && el.querySelector('svg') && !el.querySelector('img,video,picture,canvas') &&
          squash(el.textContent).length <= 3 && !el.closest('button,[role="button"],input,select,textarea,label,nav') && !tiles.some((t) => t.contains(el))) {
        const near = heads.some((h) => {
          if (h.el.contains(el)) return false;
          const gap = h.r.top - r.bottom;
          const beside = ovY(r, h.r) > 0 && ((h.r.left - r.right >= -2 && h.r.left - r.right <= 32) || (r.left - h.r.right >= -2 && r.left - h.r.right <= 32));
          return (gap >= -2 && gap <= 48 && ovX(r, h.r) > 0) || beside;
        });
        if (near) { c.iconTiles++; tiles.push(el); note('iconTiles', el); }
      }
    }

    const sides = ['top', 'right', 'bottom', 'left'].map((s) => {
      const st = cs.getPropertyValue('border-' + s + '-style');
      const w = px(cs.getPropertyValue('border-' + s + '-width'));
      const col = rgba(cs.getPropertyValue('border-' + s + '-color'));
      const on = st !== 'none' && st !== 'hidden' && w > 0 && col[3] > 0.05;
      return { on, w: on ? w : 0, col };
    });
    const blur = shadowBlur(cs.boxShadow);
    if (r.width >= 80 && r.height >= 48) {
      if (sides.filter((s) => s.on && s.w <= 1.5).length >= 2 && blur >= 16) { c.ghostCards++; note('ghostCards', el); }
      if (px(cs.borderTopLeftRadius) >= 12 && blur >= 8 && rgba(cs.backgroundColor)[3] > 0.5) { c.shadowCards++; note('shadowCards', el); }
    }
    if (r.height >= 16) {
      const [t, rt, b, l] = sides;
      const stripe = (a, z) => a.w >= 2 && chroma(a.col) >= 30 && z.w < 2 && t.w < 2 && b.w < 2;
      if (stripe(l, rt) || stripe(rt, l)) { c.sideStripes++; note('sideStripes', el); }
    }
    if ((cs.position === 'absolute' || cs.position === 'fixed') && r.width >= 40 && r.height >= 40) {
      const rad = cs.borderTopLeftRadius;
      const round = rad.endsWith('%') ? px(rad) >= 40 : px(rad) >= (Math.min(r.width, r.height) / 2) * 0.9;
      if (round && blurPx(cs.filter) >= 24 && lightBehind(el)) { c.lightOrbs++; note('lightOrbs', el); }
    }
    if (/(^|,\s*)(pulse|ping)(\s*,|$)/.test(cs.animationName) && !squash(el.textContent) && !el.querySelector('img,video,picture,canvas')) {
      c.pulsingDecor++; note('pulsingDecor', el);
    }
  }

  for (const icon of Array.from(root.querySelectorAll('svg.lucide-sparkles, svg.lucide-sparkle'))) {
    if (!shown(icon)) continue;
    let n = icon, labelled = false;
    for (let d = 0; d < 4 && n; d++) {
      const t = squash(n.textContent);
      if (t.length > 160) break;
      if (aiWord((n.getAttribute('title') || '') + ' ' + (n.getAttribute('aria-label') || '') + ' ' + t)) { labelled = true; break; }
      n = n.parentElement;
    }
    if (!labelled) { c.sparklesNonAi++; note('sparklesNonAi', icon.parentElement || icon); }
  }

  // Nur sichtbarer Text (innerText): ein Rückfall auf textContent würde versteckten Text mitzählen.
  const text = squash(root.innerText || '');
  const words = text ? text.split(' ').length : 0;
  const emDashes = (text.match(/\u2014/g) || []).length;
  const headings = Array.from(root.querySelectorAll('h1,h2,h3')).filter(shown).map((h) => squash(h.innerText || ''));
  const questionHeadings = headings.filter((h) => /\?\s*$/.test(h)).length;
  const dotLines = Array.from(root.querySelectorAll('*')).filter((el) => ownText(el) && (squash(el.textContent).split('·').length - 1) >= 2 && squash(el.textContent).length <= 160 && shown(el)).length;

  const GENERIC = /^(inter|roboto|arial|helvetica|helvetica neue|open sans|system-ui|-apple-system|blinkmacsystemfont|segoe ui|sans-serif|ui-sans-serif)$/i;
  const fonts = Array.from(fontUse.entries()).sort((a, b) => b[1] - a[1]).map(([f, n]) => ({ family: f, chars: n, generic: GENERIC.test(f) }));
  const genericShare = fonts.length ? fonts.filter((f) => f.generic).reduce((s, f) => s + f.chars, 0) / fonts.reduce((s, f) => s + f.chars, 0) : 0;

  return {
    url: location.href,
    viewport: innerWidth + 'x' + innerHeight,
    counts: Object.assign(c, { emDashes, emDashesPer1000Words: words ? Math.round((emDashes / words) * 10000) / 10 : 0, questionHeadings, dotLines, genericFontShare: Math.round(genericShare * 100) / 100 }),
    fonts: fonts.slice(0, 5),
    headings: headings.slice(0, 30),
    samples,
  };
}

window.measureSlop = measureSlop;
