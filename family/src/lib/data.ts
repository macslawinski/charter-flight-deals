// Typed access to src/data/family.json (written by scripts/export_family.py) plus Polish labels and
// icons. Every lookup that misses throws: a new key without a label must fail the build, not render
// a raw key to parents.
import raw from "../data/family.json";
import { CITY_FROM, MODE_LABEL } from "./format";

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

// Indoor playground card (built from the map export in lib/map.ts, cityPlaygrounds).
export interface Venue {
  slug: string;
  name: string;
  official_url: string | null;
  address: string | null;
  features: Fact[];
}

// Official topics (travel documents, later "Niezbędnik"): rules, not places. Official sources only.
export interface EssentialFact {
  group: string;
  key: string;
  short: string;
  note: string | null;
  publisher: string;
  url: string;
  verified_at: string;
  to_confirm: boolean;
  also: { label: string; url: string }[];
}

export interface Essential {
  topic: string;
  title: string;
  groups: { id: string; title: string; icon: string; intro: string | null }[];
  facts: EssentialFact[];
}

// Departure airports for parents: facts only from each airport's own site.
export interface AirportFact {
  key: string;
  short: string;
  note: string | null;
  url: string;
  verified_at: string;
  to_confirm: boolean;
}

export interface Airport {
  iata: string;
  name: string;
  city: string;
  official_url: string;
  facts: AirportFact[];
}

interface Data {
  essentials: Record<string, Essential>;
  airport_keys: string[];
  airports: Airport[];
  feature_keys: string[];
  rule_keys: string[];
  venue_keys: string[];
  venue_cities: Record<string, string>;
  places: Place[];
  hotels: Hotel[];
  carriers: Carrier[];
}

export const data = raw as unknown as Data;

function must<T>(table: Record<string, T>, key: string, what: string): T {
  const v = table[key];
  if (v === undefined) throw new Error(`No ${what} for '${key}' (family/src/lib/data.ts)`);
  return v;
}

export const essential = (topic: string) => must(data.essentials, topic, "essentials topic");

// Airport fact keys: label and icon. A key exported without an entry here fails the build.
const AIRPORT_LABELS: Record<string, { label: string; icon: string }> = {
  play_area: { label: "Plac zabaw", icon: "slide" },
  parent_room: { label: "Przewijanie i karmienie", icon: "diaper" },
  family_security: { label: "Kontrola bezpieczeństwa z dzieckiem", icon: "shield" },
  baby_food: { label: "Jedzenie i picie dla dziecka", icon: "bottle" },
  stroller: { label: "Własny wózek", icon: "stroller" },
  airport_stroller: { label: "Wózki lotniskowe", icon: "stroller" },
};
export const airportKey = (key: string) => must(AIRPORT_LABELS, key, "airport fact label");

// One-line headline for cards: the curated `short`, else the note's first sentence.
export function short(f: Fact): string {
  if (f.short) return f.short;
  const note = f.note ?? "";
  const m = note.match(/^.*?[.!?](\s|$)/);
  return (m ? m[0] : note).trim();
}

// --- carriers ---------------------------------------------------------------------------------

const CARRIERS: Record<string, { name: string; slug: string }> = {
  "2W": { name: "World2Fly", slug: "world2fly" },
  "3E": { name: "Electra Airways", slug: "electra-airways" },
  A3: { name: "Aegean", slug: "aegean" },
  BJ: { name: "Nouvelair", slug: "nouvelair" },
  E4: { name: "Enter Air", slug: "enter-air" },
  FR: { name: "Ryanair", slug: "ryanair" },
  LO: { name: "LOT", slug: "lot" },
  NO: { name: "Neos", slug: "neos" },
  QS: { name: "Smartwings", slug: "smartwings" },
  RR: { name: "Buzz", slug: "buzz" },
  SM: { name: "Air Cairo", slug: "air-cairo" },
  W6: { name: "Wizz Air", slug: "wizz-air" },
  XC: { name: "Corendon", slug: "corendon" },
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
  venue_website: "strona miejsca",
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
  transfer: { label: "Transfer z dworca / lotniska", icon: "car" },
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
  { title: "Okolica", keys: ["beach_walk_minutes", "parking", "transfer"] },
];

// --- hotel finder -----------------------------------------------------------------------------

// Region chip for a place: domestic places have a region, flight places only a country.
export const placeRegion = (p: Place) => p.region ?? p.country;
export const placeOf = (h: Hotel) => must(Object.fromEntries(data.places.map((p) => [p.slug, p])), h.place, "place");

// Hotels the site shows. Foreign (flight) places are hidden for now (user, 2026-11-07): their data
// stays in family.json, the pages are just not built. Flip to true to bring them back.
const SHOW_FOREIGN_HOTELS = false;
export const hotels = data.hotels.filter((h) => SHOW_FOREIGN_HOTELS || placeOf(h).kind === "domestic");

// A hotel "has" something only when its own fact says so; an explicit "no" never counts.
const has = (h: Hotel, key: string, ok: (v: Value) => boolean = (v) => v.available !== false) =>
  h.features.some((f) => f.key === key && ok(f.value));
const num = (v: unknown) => (typeof v === "number" ? v : Infinity);
const nearBeach = (v: Value) =>
  v.on_beach === true || v.own_beach === true || num(v.distance_m) <= 300 ||
  (v.distance_m === undefined && num(v.minutes) <= 5);

// "Must have" filters. Ids go into the URL, so keep them stable.
export const HOTEL_FILTERS: { id: string; label: string; icon: string; test: (h: Hotel) => boolean }[] = [
  { id: "darmowy", label: "Maluch za darmo", icon: "bed", test: (h) => has(h, "child_free_stay", (v) => v.free === true) },
  { id: "lozeczko", label: "Łóżeczko", icon: "cot", test: (h) => has(h, "cot") },
  { id: "wanienka", label: "Wanienka", icon: "bath", test: (h) => has(h, "baby_bath") },
  { id: "krzeselko", label: "Krzesełko", icon: "chair", test: (h) => has(h, "high_chair") },
  { id: "bawialnia", label: "Bawialnia", icon: "blocks", test: (h) => has(h, "playroom") },
  { id: "plac", label: "Plac zabaw", icon: "slide", test: (h) => has(h, "playground") },
  { id: "brodzik", label: "Brodzik lub basen dla dzieci", icon: "wave", test: (h) => has(h, "paddling_pool") || has(h, "kids_pool") },
  { id: "winda", label: "Winda lub bez schodów", icon: "lift", test: (h) => has(h, "lift") || has(h, "step_free_access") },
  { id: "plaza", label: "Plaża do 300 m", icon: "umbrella", test: (h) => has(h, "beach_walk_minutes", nearBeach) },
  { id: "parking", label: "Parking", icon: "parking", test: (h) => has(h, "parking") },
];

// "Wyjazdy" hub: landscape groups over the place regions. Every shown region must belong to a group
// (checked at build time below), so a new region fails the build instead of silently disappearing.
export const TRIP_GROUPS: {
  id: string;
  title: string;
  tone: "sea" | "sun" | "coral";
  icon: string;
  regions: string[];
}[] = [
  { id: "morze", title: "Nad morzem", tone: "sea", icon: "umbrella",
    regions: ["Bałtyk – Pomorze", "Bałtyk – Pomorze Zachodnie", "Zalew Wiślany"] },
  { id: "gory", title: "W górach", tone: "sun", icon: "mountain",
    regions: ["Tatry i Podhale", "Beskidy", "Gorce", "Pieniny", "Karkonosze", "Kotlina Kłodzka", "Góry Sowie", "Bieszczady"] },
  { id: "jeziora", title: "Jeziora i lasy", tone: "sea", icon: "tree",
    regions: ["Mazury", "Warmia", "Pojezierze Iławskie", "Kaszuby", "Bory Tucholskie", "Kociewie", "Podkarpacie"] },
  { id: "jura", title: "Jura i Małopolska", tone: "coral", icon: "castle",
    regions: ["Jura Krakowsko-Częstochowska", "Małopolska"] },
  { id: "mazowsze", title: "Warszawa i Mazowsze", tone: "sun", icon: "pin",
    regions: ["Mazowsze"] },
  { id: "kujawy", title: "Toruń, Kujawy i Pałuki", tone: "coral", icon: "pin",
    regions: ["Toruń i Kujawy", "Pałuki"] },
  { id: "wielkopolska", title: "Poznań i Wielkopolska", tone: "sea", icon: "pin",
    regions: ["Wielkopolska", "Pojezierze Leszczyńskie"] },
  { id: "wyzyny", title: "Wyżyny i uzdrowiska", tone: "coral", icon: "castle",
    regions: ["Lubelszczyzna", "Góry Świętokrzyskie", "Ponidzie", "Ziemia Sandomierska"] },
  { id: "lodzkie", title: "Łódź, Uniejów i Sulejów", tone: "sun", icon: "pin",
    regions: ["Łódź i okolice", "Termy Uniejów", "Zalew Sulejowski"] },
  { id: "podlasie", title: "Podlasie i Augustów", tone: "sea", icon: "pin",
    regions: ["Białystok i Podlasie", "Puszcza Białowieska", "Pojezierze Augustowskie"] },
  { id: "opolskie", title: "Opolszczyzna i Góry Opawskie", tone: "coral", icon: "castle",
    regions: ["Opolszczyzna", "Góry Opawskie"] },
];
const GROUP_OF = Object.fromEntries(TRIP_GROUPS.flatMap((g) => g.regions.map((r) => [r, g.id])));
export const tripGroupOf = (h: Hotel) => must(GROUP_OF, placeRegion(placeOf(h)), "trip group of region");

// Origin cities of the access times (car/train), sorted for the chips.
export const ORIGIN_CITIES = [
  ...new Set(hotels.flatMap((h) => h.access.filter((a) => a.from_kind === "city").map((a) => a.from_code))),
].sort((a, b) => a.localeCompare(b, "pl"));

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
  birthday_parties: { label: "Urodziny", icon: "star" },
};
export const venueLabel = (key: string) => must(VENUE_FEATURES, key, "venue label").label;
export const venueIcon = (key: string) => must(VENUE_FEATURES, key, "venue icon").icon;
export const VENUE_ORDER = [
  "age_range", "toddler_zone", "infant_free", "toddler_classes", "price_child", "price_adult",
  "opening_hours", "socks_required", "birthday_parties", "cafe", "changing_table", "parking", "supervision",
];

// A venue is "for the youngest" only when its own site says so, never by guess.
export const forToddlers = (v: Venue) => toddlerFacts(v.features);
export function toddlerFacts(facts: { key: string; value: Value }[]): boolean {
  return facts.some((f) => {
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
  for (const c of ORIGIN_CITIES) must(CITY_FROM, c, "genitive of origin city (lib/format.ts)");
  for (const h of data.hotels) {
    for (const a of h.access) if (a.from_kind === "city") must(MODE_LABEL, a.mode, "access mode label");
  }
}

const dateFmt = new Intl.DateTimeFormat("pl-PL", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "Europe/Warsaw",
});
export const plDate = (iso: string) => dateFmt.format(new Date(`${iso}T12:00:00Z`));
