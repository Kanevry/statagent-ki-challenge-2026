import { clientSchluessel, erstelleRatenlimit, FENSTER_MS, grenzeAus } from "./ratenlimit";

// Fängt ab: ein Limit, das nicht je IP zählt, kein Retry-After, ein Fenster, das nie abläuft, falsche IP-Quelle,
// ein ungültiger Wert als „unbegrenzt“ und ein Speicher, der mit jeder neuen IP wächst.

function anfrage(kopf: Record<string, string> = {}): Request {
  return new Request("http://lokal/api/uc4/frage", { method: "POST", headers: kopf });
}
const von = (ip: string) => anfrage({ "x-forwarded-for": ip });

it("N=3: die vierte Anfrage einer IP in der Minute bekommt 429, eine andere IP nicht, nach dem Fenster wieder frei", async () => {
  const pruefe = erstelleRatenlimit({ proMinute: 3 });
  for (const t of [0, 1_000, 2_000]) expect(pruefe(von("203.0.113.7"), t)).toBeNull();

  const gesperrt = pruefe(von("203.0.113.7"), 10_000);
  expect(gesperrt?.status).toBe(429);
  expect(gesperrt?.headers.get("retry-after")).toBe("50");
  expect(typeof (await gesperrt?.json()).fehler).toBe("string");

  expect(pruefe(von("198.51.100.2"), 10_000)).toBeNull();
  expect(pruefe(von("203.0.113.7"), FENSTER_MS)).toBeNull();
});

it("IP aus dem ersten Eintrag von x-forwarded-for, sonst x-real-ip, sonst ein fester Schlüssel", () => {
  expect(clientSchluessel(anfrage({ "x-forwarded-for": "203.0.113.7, 10.0.0.1", "x-real-ip": "10.0.0.9" }))).toBe("203.0.113.7");
  expect(clientSchluessel(anfrage({ "x-real-ip": "10.0.0.9" }))).toBe("10.0.0.9");
  expect(clientSchluessel(anfrage())).toBe("unbekannt");
});

it("RATENLIMIT_PRO_MINUTE: fehlend oder ungültig gilt der Standard 10", () => {
  expect(grenzeAus({ RATENLIMIT_PRO_MINUTE: "3" })).toBe(3);
  for (const wert of [undefined, "", "0", "-1", "abc", "2.5"]) expect(grenzeAus({ RATENLIMIT_PRO_MINUTE: wert })).toBe(10);
});

it("der Speicher bleibt begrenzt: die älteste IP fliegt, wenn die Obergrenze erreicht ist", () => {
  const pruefe = erstelleRatenlimit({ proMinute: 1, maxSchluessel: 2 });
  expect(pruefe(von("a"), 0)).toBeNull();
  expect(pruefe(von("b"), 1)).toBeNull();
  expect(pruefe(von("c"), 2)).toBeNull();
  // "a" wurde verdrängt und darf wieder; "c" ist noch gemerkt und bleibt gesperrt.
  expect(pruefe(von("a"), 3)).toBeNull();
  expect(pruefe(von("c"), 4)?.status).toBe(429);
});
