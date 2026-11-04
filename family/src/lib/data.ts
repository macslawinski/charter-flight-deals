// Typed access to src/data/family.json (written by scripts/export_family.py) plus Polish labels.
// Every lookup that misses throws: a new rule or feature key without a label must fail the build,
// not render a raw key to parents.
import raw from "../data/family.json";

export type Value = Record<string, unknown>;

export interface Fact {
  key: string;
  age_band: string | null;
  value: Value;
  note: string | null;
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

interface Data {
  feature_keys: string[];
  rule_keys: string[];
  places: Place[];
  hotels: Hotel[];
  carriers: Carrier[];
}

export const data = raw as unknown as Data;

function must<T>(table: Record<string, T>, key: string, what: string): T {
  const v = table[key];
  if (v === undefined) throw new Error(`No ${what} label for '${key}' (family/src/lib/data.ts)`);
  return v;
}

const CARRIERS: Record<string, { name: string; slug: string }> = {
  E4: { name: "Enter Air", slug: "enter-air" },
  FR: { name: "Ryanair", slug: "ryanair" },
  LO: { name: "LOT", slug: "lot" },
  QS: { name: "Smartwings", slug: "smartwings" },
  RR: { name: "Buzz", slug: "buzz" },
  W6: { name: "Wizz Air", slug: "wizz-air" },
};
export const carrierName = (code: string) => must(CARRIERS, code, "carrier").name;
export const carrierSlug = (code: string) => must(CARRIERS, code, "carrier").slug;

export const carriers = [...data.carriers].sort((a, b) =>
  carrierName(a.carrier_iata).localeCompare(carrierName(b.carrier_iata), "pl"),
);

const RULES: Record<string, string> = {
  infant_fee: "Opłata za niemowlę",
  child_fare: "Bilet dziecka",
  infant_min_age: "Od jakiego wieku",
  infants_per_adult: "Niemowlęta na jednego dorosłego",
  twins: "Bliźnięta",
  lap_infant: "Niemowlę na kolanach",
  infant_seat: "Własne miejsce dla niemowlęcia",
  bassinet: "Kołyska w samolocie",
  child_seating: "Miejsce obok dziecka",
  infant_baggage: "Bagaż niemowlęcia",
  child_baggage: "Bagaż dziecka",
  baby_food: "Jedzenie dla dziecka",
  stroller: "Wózek",
  car_seat: "Fotelik samochodowy",
  travel_cot: "Łóżeczko turystyczne",
  priority_boarding: "Pierwszeństwo wejścia na pokład",
};
export const ruleLabel = (key: string) => must(RULES, key, "rule");

// Comparison topics: the questions a parent asks, in the order they ask them.
export const TOPICS: { id: string; title: string; keys: string[] }[] = [
  { id: "cena", title: "Ile płacisz za dziecko", keys: ["infant_fee", "child_fare"] },
  { id: "wiek", title: "Od jakiego wieku dziecko może lecieć", keys: ["infant_min_age"] },
  { id: "dorosli", title: "Ile dzieci na jednego dorosłego", keys: ["infants_per_adult", "twins"] },
  {
    id: "miejsce",
    title: "Gdzie siedzi dziecko",
    keys: ["lap_infant", "infant_seat", "bassinet", "child_seating"],
  },
  { id: "bagaz", title: "Bagaż i jedzenie", keys: ["infant_baggage", "child_baggage", "baby_food"] },
  { id: "sprzet", title: "Wózek, fotelik i łóżeczko", keys: ["stroller", "car_seat", "travel_cot"] },
  { id: "wejscie", title: "Wejście na pokład", keys: ["priority_boarding"] },
];

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
};
export const sourceLabel = (s: string) => must(SOURCES, s, "source");

const FEATURES: Record<string, string> = {
  cot: "Łóżeczko",
  child_free_stay: "Pobyt dziecka",
  baby_monitor: "Elektroniczna niania",
  high_chair: "Krzesełko do karmienia",
  kids_menu: "Menu dla dzieci",
  toddler_food: "Posiłki dla maluchów",
  bottle_warmer: "Podgrzewacz do butelek",
  baby_bath: "Wanienka",
  changing_table: "Przewijak",
  potty: "Nocnik",
  playroom: "Bawialnia",
  playground: "Plac zabaw",
  kids_animation: "Animacje dla dzieci",
  paddling_pool: "Brodzik",
  kids_pool: "Basen dla dzieci",
  shade: "Cień przy basenie i placu zabaw",
  lift: "Winda",
  step_free_access: "Dojście bez schodów",
  stroller_rental: "Wypożyczenie wózka",
  beach_walk_minutes: "Spacer na plażę",
  parking: "Parking",
};
export const featureLabel = (key: string) => must(FEATURES, key, "feature");

export const FEATURE_GROUPS: { title: string; keys: string[] }[] = [
  { title: "Spanie", keys: ["cot", "child_free_stay", "baby_monitor"] },
  { title: "Jedzenie", keys: ["high_chair", "kids_menu", "toddler_food", "bottle_warmer"] },
  { title: "Kąpiel i przewijanie", keys: ["baby_bath", "changing_table", "potty"] },
  { title: "Zabawa", keys: ["playroom", "playground", "kids_animation"] },
  { title: "Woda i słońce", keys: ["paddling_pool", "kids_pool", "shade"] },
  { title: "Z wózkiem po hotelu", keys: ["lift", "step_free_access", "stroller_rental"] },
  { title: "Okolica", keys: ["beach_walk_minutes", "parking"] },
];

// Every feature key must sit in exactly one group, or a fact would silently vanish from the page.
{
  const grouped = FEATURE_GROUPS.flatMap((g) => g.keys).sort();
  const known = [...data.feature_keys].sort();
  if (grouped.join() !== known.join()) {
    throw new Error(`FEATURE_GROUPS out of sync with feature_keys: ${grouped} vs ${known}`);
  }
  const topical = TOPICS.flatMap((t) => t.keys).sort();
  if (topical.join() !== [...data.rule_keys].sort().join()) {
    throw new Error("TOPICS out of sync with rule_keys");
  }
}

const dateFmt = new Intl.DateTimeFormat("pl-PL", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "Europe/Warsaw",
});
export const plDate = (iso: string) => dateFmt.format(new Date(`${iso}T12:00:00Z`));

// Short answers for the "w skrócie" table. Unknown shapes fall back to null ("see details"),
// never to a guess.
export function feeShort(v: Value | undefined): string | null {
  if (!v) return null;
  if (typeof v.amount_eur === "number") {
    return `${v.amount_eur} € za lot${v.per === "one_way" ? " w jedną stronę" : ""}`;
  }
  if (typeof v.discount_pct_international === "number") {
    return `${v.discount_pct_international}% zniżki od ceny dorosłego`;
  }
  if (v.set_by_tour_operator === true) return "cenę ustala biuro podróży";
  if (v.amount_published === false) return v.discounted ? "zniżka, kwoty nie podaje" : "płatne, kwoty nie podaje";
  return null;
}

export function minAgeShort(v: Value | undefined): string | null {
  if (!v) return null;
  if (typeof v.min_hours === "number") return `od ${v.min_hours} godzin`;
  if (typeof v.min_days === "number") return `od ${v.min_days} dni`;
  return null;
}

export function perAdultShort(v: Value | undefined): string | null {
  if (!v || typeof v.max !== "number") return null;
  return v.max === 1 ? "1 niemowlę" : `${v.max} niemowlęta`;
}

export const ruleOf = (c: Carrier, key: string) => c.rules.filter((r) => r.key === key);
