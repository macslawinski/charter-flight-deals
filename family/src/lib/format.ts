// Small formatters shared by build-time pages and client scripts. Must not import family.json:
// anything imported from a <script> ends up in the browser bundle.

export const duration = (min: number) =>
  min < 60 ? `${min} min` : `${Math.floor(min / 60)} h ${String(min % 60).padStart(2, "0")} min`;

// "z Warszawy": origin cities of the access times, in the genitive.
export const CITY_FROM: Record<string, string> = {
  Gdańsk: "Gdańska",
  Katowice: "Katowic",
  Kraków: "Krakowa",
  Poznań: "Poznania",
  Warszawa: "Warszawy",
  Wrocław: "Wrocławia",
};

export const MODE_LABEL: Record<string, string> = { car: "Autem", train: "Pociągiem" };

// Comparison selection, shared by /hotele/ and /hotele/porownaj/ (per tab, survives back/forward).
export const COMPARE_MAX = 4;
const KEY = "porownaj";
export function loadCompare(): string[] {
  try {
    const v = JSON.parse(sessionStorage.getItem(KEY) ?? "[]");
    return Array.isArray(v) ? v.filter((s): s is string => typeof s === "string").slice(0, COMPARE_MAX) : [];
  } catch {
    return [];
  }
}
export function saveCompare(slugs: string[]) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(slugs));
  } catch {
    // Storage blocked: the selection just won't survive navigation.
  }
}
