// City map ("Gdzie z dzieckiem"): open-data venues from src/data/map/<city>.json (written by
// scripts/export_venues.py from the DB) plus the curated indoor playgrounds from family.json.
// Everything is resolved at build time into one compact payload for the client-side map; a
// category, tag or source without a label here fails the build.
import { data, forToddlers, plDate, short, sourceLabel, venueLabel, type Value } from "./data";

interface ExportRef {
  src: string | null;
  type: string;
  url: string | null;
  verified_at: string;
}
interface ExportFact {
  key: string;
  value: Value;
  short: string;
  note: string | null;
  to_confirm: boolean;
  ref: number;
}
interface ExportVenue {
  id: string;
  source: string;
  name: string;
  address: string | null;
  lat: number | null;
  lon: number | null;
  official_url: string | null;
  categories: string[];
  location_ref: number | null;
  facts: ExportFact[];
}
export interface ExportSource {
  name: string;
  url: string;
  licence: string;
  attribution: string;
  data_as_of: string | null;
  imported_at: string | null;
}
interface CityExport {
  city: string;
  locality: string;
  categories: Record<string, string>;
  fact_labels: Record<string, string>;
  sources: Record<string, ExportSource>;
  refs: ExportRef[];
  venues: ExportVenue[];
}

const files = import.meta.glob<CityExport>("../data/map/*.json", { eager: true, import: "default" });
export const cityExports: CityExport[] = Object.values(files);

function must<T>(table: Record<string, T>, key: string, what: string): T {
  const v = table[key];
  if (v === undefined) throw new Error(`No ${what} for '${key}' (family/src/lib/map.ts)`);
  return v;
}

// Short publisher name for the source line under each fact.
const OPEN_SOURCES: Record<string, string> = {
  nfz_nisoz: "pacjent.gov.pl (NFZ)",
  poznan_place_zabaw: "Plan Poznania (poznan.pl)",
};
export const openSourceLabel = (id: string) => must(OPEN_SOURCES, id, "open-data source label");

// Map categories: chip label, marker colour, marker radius. Order = order of the chips.
export const CATEGORIES: { id: string; chip: string; color: string; radius: number }[] = [
  { id: "plac_zabaw", chip: "Place zabaw", color: "#0f7a74", radius: 5 },
  { id: "sala_zabaw", chip: "Sale zabaw (bawialnie)", color: "#d4472f", radius: 8 },
  { id: "nisoz", chip: "Nocna i świąteczna pomoc lekarska", color: "#5b3cc4", radius: 8 },
];
const CAT_IDS = CATEGORIES.map((c) => c.id);

// Narrowing filters inside one category. Ids are stable (they may go into the URL later).
export const TAGS: { id: string; cat: string; chip: string; test: (facts: ExportFact[]) => boolean }[] = [
  { id: "unrestricted", cat: "plac_zabaw", chip: "Dostęp bez ograniczeń",
    test: (fs) => fs.some((f) => f.key === "access" && f.value.unrestricted === true) },
  ...(
    [["zipline", "Tyrolka"], ["rope_course", "Elementy linowe"], ["natural", "Plac naturalny"],
     ["pumptrack", "Pumptrack"]] as const
  ).map(([id, chip]) => ({
    id, cat: "plac_zabaw", chip,
    test: (fs: ExportFact[]) => fs.some((f) => f.key === "equipment" && f.value[id] === true),
  })),
  { id: "toddler", cat: "sala_zabaw", chip: "Z ofertą dla 0–3 lat", test: () => false }, // curated venues: set from forToddlers() in cityMap()
];

export interface MapRef {
  text: string;
  url: string | null;
}
export interface MapFact {
  label: string;
  short: string;
  note: string | null;
  ask: boolean;
  ref: number;
}
export interface MapVenue {
  id: string;
  name: string;
  address: string | null;
  lat: number | null;
  lon: number | null;
  cat: string;
  tags: string[];
  url: string | null;
  loc: number | null;
  facts: MapFact[];
}
export interface MapPayload {
  center: [number, number];
  refs: MapRef[];
  venues: MapVenue[];
}

const CENTERS: Record<string, [number, number]> = { poznan: [52.4064, 16.9252] };

export function cityMap(ex: CityExport): MapPayload {
  const refs: MapRef[] = [];
  const seen = new Map<string, number>();
  const ref = (text: string, url: string | null) => {
    const key = `${text}\u0000${url ?? ""}`;
    if (!seen.has(key)) {
      seen.set(key, refs.length);
      refs.push({ text, url });
    }
    return seen.get(key)!;
  };
  // Open data: "publisher, data z <data_as_of>, pobrane <date>". Curated: "strona bawialni, sprawdzone <date>".
  const openRef = (r: ExportRef) => {
    if (r.type !== "open_data" || !r.src) return ref(`${sourceLabel(r.type)}, sprawdzone ${plDate(r.verified_at)}`, r.url);
    const asOf = must(ex.sources, r.src, "source").data_as_of;
    const parts = [openSourceLabel(r.src), asOf ? `dane z ${plDate(asOf)}` : null, `pobrane ${plDate(r.verified_at)}`];
    return ref(parts.filter(Boolean).join(", "), r.url);
  };
  const exRefs = ex.refs.map(openRef);

  const venues: MapVenue[] = ex.venues.map((v) => {
    const cat = v.categories.find((c) => CAT_IDS.includes(c));
    if (!cat) throw new Error(`Venue ${v.id}: no map category for ${v.categories.join(",")} (lib/map.ts)`);
    return {
      id: v.id,
      name: v.name,
      address: v.address,
      lat: v.lat,
      lon: v.lon,
      cat,
      tags: TAGS.filter((t) => t.cat === cat && t.test(v.facts)).map((t) => t.id),
      url: v.official_url,
      loc: v.location_ref === null ? null : exRefs[v.location_ref]!,
      facts: v.facts.map((f) => {
        const label = must(ex.fact_labels, f.key, "fact label");
        // Open-data one-liners often repeat the label ("Dostęp: ..."); the card prints it already.
        const bare = (s: string) =>
          s.startsWith(`${label}: `) ? s.slice(label.length + 2) : f.key === "phone" ? s.replace(/^Tel\. /, "") : s;
        return { label, short: bare(f.short), note: f.note && bare(f.note), ask: f.to_confirm, ref: exRefs[f.ref]! };
      }),
    };
  });

  // Curated indoor playgrounds of this city (facts from the venues' own websites).
  for (const v of data.venues.filter((x) => x.city === ex.city)) {
    venues.push({
      id: `curated:${v.slug}`,
      name: v.name,
      address: v.address,
      lat: v.lat,
      lon: v.lon,
      cat: "sala_zabaw",
      tags: forToddlers(v) ? ["toddler"] : [],
      url: v.official_url,
      loc: v.osm ? ref("OpenStreetMap", `https://www.openstreetmap.org/${v.osm}`) : null,
      facts: v.features.map((f) => ({
        label: venueLabel(f.key),
        short: short(f),
        note: f.note,
        ask: f.to_confirm,
        ref: ref(`${sourceLabel(f.source)}, sprawdzone ${plDate(f.verified_at)}`, f.url),
      })),
    });
  }
  return { center: must(CENTERS, ex.city, "map centre"), refs, venues };
}

// Safe to drop into <script type="application/json">.
export const jsonForScript = (x: unknown) => JSON.stringify(x).replace(/</g, "\\u003c");
