/**
 * Barrierefreiheit (Antrag #135, Punkt 135-8): axe-core prüft jede Hauptroute auf WCAG 2.1 A und AA.
 * Hart sind nur Verstöße mit Wirkung „critical“ oder „serious“; alle Verstöße hängen als JSON am Test, damit
 * „moderate“ und „minor“ sichtbar bleiben, ohne eine Lane zu sperren.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { bereiche } from "../../shared/ui/src/ucs";

const ROUTEN: string[] = ["/", ...bereiche.map((uc) => uc.route), "/praesentation", "/_bausteine"];
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
const HART = new Set(["critical", "serious"]);

test.use({ reducedMotion: "reduce" });

for (const route of ROUTEN) {
  test(`axe ${route}: keine schweren Verstöße gegen WCAG 2.1 AA`, async ({ page }, testInfo) => {
    const antwort = await page.goto(route);
    expect(antwort?.status(), `${route} lädt nicht`).toBe(200);
    // Kein networkidle: im Produktions-Build halten Link-Prefetches das Netz aktiv (wie slop.spec.ts).
    await page.waitForLoadState("load");
    await page.locator("main").first().waitFor({ state: "visible" });

    const ergebnis = await new AxeBuilder({ page }).withTags(TAGS).analyze();
    const kurz = ergebnis.violations.map((v) => ({
      regel: v.id,
      wirkung: v.impact,
      hilfe: v.help,
      stellen: v.nodes.slice(0, 5).map((n) => n.target.join(" ")),
      anzahl: v.nodes.length,
    }));
    await testInfo.attach(`axe${route === "/" ? "-start" : route.replaceAll("/", "-")}`, {
      body: JSON.stringify(kurz, null, 2),
      contentType: "application/json",
    });

    const schwer = kurz.filter((v) => v.wirkung && HART.has(v.wirkung));
    expect(schwer, `Schwere axe-Verstöße auf ${route} (${testInfo.project.name})`).toEqual([]);
  });
}
