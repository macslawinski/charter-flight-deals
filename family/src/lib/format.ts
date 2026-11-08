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

// Facts past their re-verification date (PLAN.md §3). The exports give each fact a `due` date
// (ingest/staleness.py); source lines carry it as data-due, and the browser compares it with today,
// so a page built months ago still flags old facts without a rebuild.
export const STALE_TEXT = "do ponownego sprawdzenia";

const todayIso = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

export function flagStale(el: HTMLElement, today = todayIso()) {
  const due = el.dataset.due;
  if (!due || due > today || el.classList.contains("stale")) return;
  el.classList.add("stale");
  const note = document.createElement("span");
  note.className = "stale-note";
  note.textContent = STALE_TEXT;
  el.append(note);
}

export function markStale(root: ParentNode = document) {
  const today = todayIso();
  root.querySelectorAll<HTMLElement>("[data-due]").forEach((el) => flagStale(el, today));
}

// Comparison selection, shared by the finder on / and /hotele/porownaj/ (per tab, survives back/forward).
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
