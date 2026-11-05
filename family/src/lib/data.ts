// Typed access to src/data/family.json (written by scripts/export_family.py) plus Polish labels and
// icons. Every lookup that misses throws: a new key without a label must fail the build, not render
// a raw key to parents.
import raw from "../data/family.json";

export type Value = Record<string, unknown>;

export interface Fact {
  key: string;
  age_band: string | null;
  value: Value;
  note: string | null;
  short: string | null;
  source: string;
  url: string | null;
  verified_at: string;
  to_confirm: boolean;
}

export interface Access {
  from_kind: string;
  from_code: string;
  mode: string;
  minutes: number;
  note: string | null;
  url: string | null;
  verified_at: string;
}

export interface Place {
  slug: string;
  name: string;
  country: string;
  kind: "flight" | "domestic";
  region: string | null;
  dest_iata: string | null;
}

export interface Hotel {
  slug: string;
  place: string;
  name: string;
  status: string;
  official_url: string | null;
  address: string | null;
  lat: number | null;
  lon: number | null;
  features: Fact[];
  access: Access[];
}

export interface Carrier {
  carrier_iata: string;
  rules: Fact[];
}

export interface Venue {
  slug: string;
  city: string;
  name: string;
  status: string;
  official_url: string | null;
  address: string | null;
  lat: number | null;
  lon: number | null;
  osm: string | null;
  features: Fact[];
}

interface Data {
  feature_keys: string[];
  rule_keys: string[];
  venue_keys: string[];
  venue_cities: Record<string, string>;
  places: Place[];
  hotels: Hotel[];
  carriers: Carrier[];
  venues: Venue[];
}

export const data = raw as unknown as Data;

function must<T>(table: Record<string, T>, key: string, what: string): T {
  const v = table[key];
  if (v === undefined) throw new Error(`No ${what} for '${key}' (family/src/lib/data.ts)`);
  return v;
}

// One-line headline for cards: the curated `short`, else the note's first sentence.
export function short(f: Fact): string {
  if (f.short) return f.short;
  const note = f.note ?? "";
  const m = note.match(/^.*?[.!?](\s|$)/);
  return (m ? m[0] : note).trim();
}

// --- carriers ---------------------------------------------------------------------------------

const CARRIERS: Record<string, { name: string; slug: string }> = {
  E4: { name: "Enter Air", slug: "enter-air" },
  FR: { name: "Ryanair", slug: "ryanair" },
  LO: { name: "LOT", slug: "lot" },
  QS: { name: "Smartwings", slug: "smartwings" },
  RR: { name: "Buzz", slug: "buzz" },
  W6: { name: "Wizz Air", slug: "wizz-air" },
};
export const carrierName = (code: string) => must(CARRIERS, code, "carrier name").name;
export const carrierSlug = (code: string) => must(CARRIERS, code, "carrier slug").slug;

export const carriers = [...data.carriers].sort((a, b) =>
  carrierName(a.carrier_iata).localeCompare(carrierName(b.carrier_iata), "pl"),
);

const RULES: Record<string, { label: string; icon: string }> = {
  infant_fee: { label: "Opłata za niemowlę", icon: "ticket" },
  child_fare: { label: "Bilet dziecka", icon: "ticket" },
  infant_min_age: { label: "Od jakiego wieku", icon: "calendar" },
  infants_per_adult: { label: "Dzieci na jednego dorosłego", icon: "people" },
  twins: { label: "Bliźnięta", icon: "people" },
  lap_infant: { label: "Na kolanach", icon: "seat" },
  infant_seat: { label: "Własne miejsce", icon: "seat" },
  bassinet: { label: "Kołyska w samolocie", icon: "cot" },
  child_seating: { label: "Miejsce obok dziecka", icon: "seat" },
  infant_baggage: { label: "Bagaż niemowlęcia", icon: "bag" },
  child_baggage: { label: "Bagaż dziecka", icon: "bag" },
  baby_food: { label: "Jedzenie dla dziecka", icon: "bottle" },
  stroller: { label: "Wózek", icon: "stroller" },
  car_seat: { label: "Fotelik", icon: "carseat" },
  travel_cot: { label: "Łóżeczko turystyczne", icon: "cot" },
  priority_boarding: { label: "Wejście na pokład", icon: "door" },
};
export const ruleLabel = (key: string) => must(RULES, key, "rule label").label;
export const ruleIcon = (key: string) => must(RULES, key, "rule icon").icon;

// Comparison topics: the questions a parent asks, in the order they ask them.
export const TOPICS: { id: string; title: string; icon: string; keys: string[] }[] = [
  { id: "cena", title: "Ile płacisz", icon: "ticket", keys: ["infant_fee", "child_fare"] },
  { id: "wiek", title: "Od jakiego wieku", icon: "calendar", keys: ["infant_min_age"] },
  { id: "dorosli", title: "Ilu dorosłych", icon: "people", keys: ["infants_per_adult", "twins"] },
  {
    id: "miejsce",
    title: "Gdzie siedzi dziecko",
    icon: "seat",
    keys: ["lap_infant", "infant_seat", "bassinet", "child_seating"],
  },
  { id: "bagaz", title: "Bagaż i jedzenie", icon: "bag", keys: ["infant_baggage", "child_baggage", "baby_food"] },
  { id: "sprzet", title: "Wózek i fotelik", icon: "stroller", keys: ["stroller", "car_seat", "travel_cot"] },
  { id: "wejscie", title: "Wejście na pokład", icon: "door", keys: ["priority_boarding"] },
];

// Ages in the checker. A rule applies when its band overlaps the chosen age.
export const AGES = [
  { id: "niemowle", label: "do 2 lat", bands: [null, "0-1", "0-2", "1-2", "0-3"] },
  { id: "maluch", label: "2–3 lata", bands: [null, "2+", "2-3", "0-3"] },
] as const;
export type AgeId = (typeof AGES)[number]["id"];
export const rulesFor = (c: Carrier, keys: string[], age: AgeId) => {
  const bands: readonly (string | null)[] = must(
    Object.fromEntries(AGES.map((a) => [a.id, a.bands])),
    age,
    "age",
  );
  return keys.flatMap((k) => c.rules.filter((r) => r.key === k && bands.includes(r.age_band)));
};

const BANDS: Record<string, string> = {
  "0-1": "do 1. roku",
  "0-2": "do 2 lat",
  "1-2": "1–2 lata",
  "2-3": "2–3 lata",
  "0-3": "do 3 lat",
  "2+": "od 2 lat",
  "3+": "od 3 lat",
};
export const bandLabel = (band: string | null) => (band ? must(BANDS, band, "age band") : null);

const SOURCES: Record<string, string> = {
  carrier_official: "strona przewoźnika",
  hotel_website: "strona hotelu",
  hotel_written: "odpowiedź hotelu na piśmie",
  own_visit: "nasza wizyta",
  operator_page: "strona biura podróży",
  review_hint: "opinie gości",
  venue_website: "strona bawialni",
  osm: "OpenStreetMap",
};
export const sourceLabel = (s: string) => must(SOURCES, s, "source label");

// --- hotels -----------------------------------------------------------------------------------

const FEATURES: Record<string, { label: string; icon: string }> = {
  cot: { label: "Łóżeczko", icon: "cot" },
  child_free_stay: { label: "Pobyt dziecka", icon: "bed" },
  baby_monitor: { label: "Elektroniczna niania", icon: "monitor" },
  high_chair: { label: "Krzesełko do karmienia", icon: "chair" },
  kids_menu: { label: "Menu dla dzieci", icon: "utensils" },
  toddler_food: { label: "Posiłki dla maluchów", icon: "bottle" },
  bottle_warmer: { label: "Podgrzewacz do butelek", icon: "bottle" },
  baby_bath: { label: "Wanienka", icon: "bath" },
  changing_table: { label: "Przewijak", icon: "diaper" },
  potty: { label: "Nocnik", icon: "potty" },
  playroom: { label: "Bawialnia", icon: "blocks" },
  playground: { label: "Plac zabaw", icon: "slide" },
  kids_animation: { label: "Animacje", icon: "star" },
  paddling_pool: { label: "Brodzik", icon: "wave" },
  kids_pool: { label: "Basen dla dzieci", icon: "wave" },
  shade: { label: "Cień przy basenie", icon: "sun" },
  lift: { label: "Winda", icon: "lift" },
  step_free_access: { label: "Bez schodów", icon: "ramp" },
  stroller_rental: { label: "Wypożyczenie wózka", icon: "stroller" },
  beach_walk_minutes: { label: "Do plaży", icon: "umbrella" },
  parking: { label: "Parking", icon: "parking" },
};
export const featureLabel = (key: string) => must(FEATURES, key, "feature label").label;
export const featureIcon = (key: string) => must(FEATURES, key, "feature icon").icon;

export const FEATURE_GROUPS: { title: string; keys: string[] }[] = [
  { title: "Spanie", keys: ["cot", "child_free_stay", "baby_monitor"] },
  { title: "Jedzenie", keys: ["high_chair", "kids_menu", "toddler_food", "bottle_warmer"] },
  { title: "Kąpiel i przewijanie", keys: ["baby_bath", "changing_table", "potty"] },
  { title: "Zabawa", keys: ["playroom", "playground", "kids_animation"] },
  { title: "Woda i słońce", keys: ["paddling_pool", "kids_pool", "shade"] },
  { title: "Z wózkiem po hotelu", keys: ["lift", "step_free_access", "stroller_rental"] },
  { title: "Okolica", keys: ["beach_walk_minutes", "parking"] },
];

// --- indoor playgrounds -----------------------------------------------------------------------

const VENUE_FEATURES: Record<string, { label: string; icon: string }> = {
  age_range: { label: "Dla kogo", icon: "people" },
  toddler_zone: { label: "Strefa malucha", icon: "blocks" },
  infant_free: { label: "Najmłodsi", icon: "ticket" },
  price_child: { label: "Cena za dziecko", icon: "ticket" },
  price_adult: { label: "Cena za dorosłego", icon: "ticket" },
  opening_hours: { label: "Godziny", icon: "clock" },
  cafe: { label: "Kawiarnia", icon: "coffee" },
  parking: { label: "Parking", icon: "parking" },
  socks_required: { label: "Skarpetki", icon: "socks" },
  supervision: { label: "Opieka", icon: "hand" },
  toddler_classes: { label: "Zajęcia dla maluchów", icon: "star" },
  changing_table: { label: "Przewijak", icon: "diaper" },
};
export const venueLabel = (key: string) => must(VENUE_FEATURES, key, "venue label").label;
export const venueIcon = (key: string) => must(VENUE_FEATURES, key, "venue icon").icon;
export const VENUE_ORDER = [
  "age_range", "toddler_zone", "infant_free", "toddler_classes", "price_child", "price_adult",
  "opening_hours", "socks_required", "cafe", "changing_table", "parking", "supervision",
];

// A venue is "for the youngest" only when its own site says so, never by guess.
export function forToddlers(v: Venue): boolean {
  return v.features.some((f) => {
    if (["toddler_zone", "infant_free", "toddler_classes"].includes(f.key)) return true;
    if (f.key === "age_range") return f.value.min === "infant" || f.value.min_years === 0;
    return false;
  });
}
export const cityName = (slug: string) => must(data.venue_cities, slug, "city");

// --- consistency checks: a key outside its display list would silently vanish from the page ---
{
  const same = (a: string[], b: string[]) => [...a].sort().join() === [...b].sort().join();
  if (!same(FEATURE_GROUPS.flatMap((g) => g.keys), data.feature_keys)) {
    throw new Error("FEATURE_GROUPS out of sync with feature_keys");
  }
  if (!same(TOPICS.flatMap((t) => t.keys), data.rule_keys)) {
    throw new Error("TOPICS out of sync with rule_keys");
  }
  if (!same(VENUE_ORDER, data.venue_keys)) throw new Error("VENUE_ORDER out of sync with venue_keys");
}

const dateFmt = new Intl.DateTimeFormat("pl-PL", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "Europe/Warsaw",
});
export const plDate = (iso: string) => dateFmt.format(new Date(`${iso}T12:00:00Z`));
