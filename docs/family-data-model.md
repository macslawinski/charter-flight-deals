# Data model: parents' service (Product B extension)

Status: 2026-11-07, **migration `012_venues_core.sql` implements the core** (`venue_categories`,
`data_sources`, `import_runs`, `venues`, `venue_category_links`, `fact_keys`, `venue_facts`, new `fact_source`
values), with two importers in `ingest/opendata/`. The SQL below is the original draft; where they differ, the
migration wins (e.g. `venues` has `locality`/`voivodeship` instead of `city`/`teryt`, `data_sources` has
`auto_publish`, raw downloads go to the existing `raw_fetches` with `operator` = source id). Product context:
`docs/family-product.md`. Sources: `docs/family-data-sources.md`.

Decisions taken in the implementation (2026-11-07): official sources publish on import
(`data_sources.auto_publish`), OSM-discovered places will not; a human-set status survives re-imports,
except `retired`, which is lifted when a record comes back.

## Principles

1. **Every record has a source and a verified date.** No exceptions: a place's location, each of its facts, each
   open-data record. Shown to users next to the fact.
2. **Facts, not columns of opinion.** A place is a thin identity row; everything about it is a fact row with its
   own source, date and `to_confirm` flag (the same pattern as `hotel_child_features` in migration 009).
3. **Open-data importers are idempotent.** Each imported record has a stable key `(source_id, external_id)`;
   re-running an import upserts, never duplicates. A record missing from a later full import is marked
   `retired`, not deleted (history stays). Raw responses are stored so data can be re-parsed (as `raw_fetches`
   does for Product A).
4. **Additive only.** Existing tables (A's and B's) are not altered destructively; new columns are nullable,
   new enum values are added with `alter type ... add value`. Every change is a new numbered migration.
5. **Business parameters in tables**, not in code: categories, staleness periods, filter definitions.
6. **Same access model**: RLS on, no policies; the browser never talks to the DB; the site reads an exported JSON
   (`scripts/export_family.py`).

## How it relates to the current schema

| Existing (migration) | Role in the extension |
|---|---|
| `places` (009): B destinations, e.g. `rodos`, `grzybowo` | Unchanged: trip destinations for hotels. **Not** reused for section 1 venues (different meaning; name clash noted) |
| `hotels`, `hotel_child_features`, `hotel_access` (009) | Unchanged; "Wyjazdy" section. Hotel facts reuse the shared fact keys below where they mean the same thing (e.g. `parking`, `changing_table`) |
| `child_rules`, `airlines` (009, 011) | Unchanged; "Wyjazdy", airlines |
| `airports` (009): Polish departure airports | Extended later with airport family facts (stage 3) |
| `age_band` enum (009): `0-1, 0-2, 1-2, 2-3, 0-3, 2+, 3+` | Kept for hotels and airline rules. Venues use numeric months instead (below) |
| `fact_source` enum (009) | Extended with new values (below) |
| `raw_fetches` (001): A's raw responses, 14-day retention | TODO: reuse for open-data raw responses or a separate `opendata_raw` table? (A's table is keyed by operator) |
| PLAN.md §3a: planned `venues` + `venue_child_features` | Superseded by the generalized `venues` / `venue_facts` below; the Poznań playground TOMLs map onto it |

## New tables (draft)

```sql
-- Categories and their sections; staleness lives here, not in code.
create table venue_categories (
    slug              text primary key,            -- 'sala_zabaw', 'basen', 'kapielisko', 'zlobek', 'nisoz', ...
    section           text not null check (section in ('gdzie', 'wyjazdy', 'niezbednik')),
    label_pl          text not null,
    stale_after_months int not null default 12
);

-- Where a record comes from (an open-data set, OSM, a venue's website, a venue's own submission).
create table data_sources (
    id               text primary key,             -- 'mrips_zlobki', 'gis_kapieliska', 'nfz_nisoz', 'osm', ...
    name             text not null,
    url              text not null check (url ~ '^https://'),
    kind             text not null check (kind in ('open_data', 'osm', 'website', 'venue_submitted')),
    licence          text,                         -- 'CC0 1.0', 'CC BY 4.0', 'ODbL', ...
    attribution_pl   text                          -- shown on pages that use it, e.g. '© OpenStreetMap contributors'
);

-- One row per import run (idempotent upserts; counts for monitoring).
create table import_runs (
    id           bigint generated always as identity primary key,
    source_id    text not null references data_sources (id),
    started_at   timestamptz not null,
    finished_at  timestamptz,
    status       text not null check (status in ('ok', 'parse_error', 'http_error', 'partial')),
    n_seen int, n_inserted int, n_updated int, n_retired int
);

-- A place on the map (section 1 venues, nurseries, NiŚOZ points, bathing sites).
create table venues (
    id            bigint generated always as identity primary key,
    slug          text not null unique check (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    name          text not null,
    city          text not null,                   -- slug, e.g. 'poznan'
    teryt         text,                            -- TODO: municipality code, if sources provide it
    address       text,
    lat numeric(9, 6), lon numeric(9, 6),
    official_url  text check (official_url ~ '^https://'),
    location_source_url text, location_verified_at date not null,
    source_id     text not null references data_sources (id),
    external_id   text,                            -- id in that source (register no., OSM 'node/123', GIS id)
    status        text not null default 'draft' check (status in ('draft', 'published', 'retired')),
    unique (source_id, external_id)                -- the idempotency key for importers
);
create table venue_category_links (                -- a place can be in several categories (aquapark + sauna)
    venue_id bigint not null references venues (id) on delete cascade,
    category text not null references venue_categories (slug),
    primary key (venue_id, category)
);

-- The vocabulary of facts: shared keys (filterable across categories) and category extensions.
create table fact_keys (
    key       text primary key check (key ~ '^[a-z_]+$'),
    scope     text not null,                       -- 'shared' or a venue_categories.slug
    label_pl  text not null,
    value_schema jsonb                             -- informal shape, checked by the loader
);

-- One fact about a venue; same columns as hotel_child_features + a numeric age range.
create table venue_facts (
    venue_id       bigint not null references venues (id) on delete cascade,
    fact_key       text not null references fact_keys (key),
    age_min_months int, age_max_months int,        -- null = applies to all ages
    value          jsonb not null,
    short_pl       text not null,                  -- one line shown on cards
    note_pl        text,
    source_type    fact_source not null,
    source_url     text check (source_url ~ '^https://'),   -- null only for venue_submitted (TODO: proof?)
    verified_at    date not null,
    to_confirm     boolean not null default false,
    unique nulls not distinct (venue_id, fact_key, age_min_months, age_max_months)
);
```

Enum extension (new migration): `alter type fact_source add value 'venue_website'`, `'venue_submitted'`,
`'open_data'`, `'osm'`. The Poznań playground TOMLs already use `source = "venue_website"`.
`venue_submitted` is the venue analogue of the existing `hotel_written`.

## Shared attributes (filterable across all categories)

| Fact key | Value shape (draft) | Filter in UI |
|---|---|---|
| `age_range` | `age_min_months`, `age_max_months` columns + `{ "baby_zone": true }` | "dla dziecka w wieku…" (0–6 years) |
| `stroller_access` | `{ "step_free": true, "lift": true, "stroller_parking": true }` | "z wózkiem" |
| `changing_table` | `{ "available": true, "where": "womens_and_mens" }` | "przewijak" |
| `parking` | `{ "available": true, "free": false, "fee_pln_per_h": 3 }` | "parking" |
| `toilet` | `{ "available": true, "kids_seat": true }` | "toaleta" |
| `price` | `{ "child_pln": 20, "adult_pln": 0, "under_months_free": 12, "unit": "hour" }` | price range |
| `opening_hours` | `{ "osm": "Mo-Su 10:00-20:00" }` (OSM `opening_hours` syntax) | "otwarte teraz / w weekend" |
| location | `venues.address`, `lat`, `lon` + `location_source_url`, `location_verified_at` | map, distance |
| source, verified date | on every fact and on the location | shown, not filtered |

The existing playground keys (`price_child`, `infant_free`, `cafe`, `socks_required`, `supervision`) become either
shared keys (`price_child` → `price`) or `sala_zabaw` extensions. Decided (migration 013): the TOML keys are kept
as `sala_zabaw` fact keys; `age_range`, `opening_hours`, `parking`, `changing_table` are already shared. Curated
venues load under data source `curated` (external_id = slug, location = the OSM object, age_band → month columns).

## Category extensions (examples)

| Category | Extension facts |
|---|---|
| `kapielisko` | `water_quality` (from GIS, per sampling date), `season` (dates), `lifeguard` |
| `zlobek` / `klub_dzieciecy` | `places_total`, `fee_monthly_pln`, `meal_fee_pln`, `hours`, `accepts_disabled` (if the register provides them) |
| `nisoz` | `hours` (statutory 18:00–8:00 weekdays, 24 h holidays), `phone`, `paediatrician` (TODO: is this in any source?) |
| `basen` / `aquapark` | `paddling_pool`, `water_temp_c`, `swim_nappies_required`, `min_age_months` |
| `urodziny` | `capacity_children`, `package_price_pln`, `package_includes` (list of plain items) |
| `kino_dla_rodzicow` | `schedule_pattern` (e.g. "wtorki 11:00"), `sound_and_light` (quieter/dimmed) |
| `szkolka_narciarska` | `min_age_years`, `season` |

Recurring events (baby cinema screenings, museum family workshops): TODO: model as venue facts with a schedule
pattern (simple) or as a separate `venue_events` table with dates (precise, but needs frequent updates)?

## Verification and display

- `verified_at` = the day we (or an importer) read the source; for open data, the import date, plus the source's
  own "data as of" date when it gives one (stored in `value`).
- Staleness: `venue_categories.stale_after_months`; a fact older than that shows "do ponownego sprawdzenia".
- `to_confirm` facts are shown with a "do potwierdzenia" label, never as plain facts.
- Publishing: curated venues need a human `published` (as hotels). TODO: may importer records from official
  registers (nurseries, NiŚOZ, bathing sites) publish automatically? Proposal: yes for official registers, no
  for OSM-discovered places (as in `PLAN.md` §3a).
- Attribution: pages show `data_sources.attribution_pl` for every source they use (OSM, CC BY sets).

## "Niezbędnik" content (not places)

Benefits, documents, deadlines and vaccinations are rules, not map points. Proposal: curated TOML in
`data/curated/essentials/<topic>.toml`, one fact per rule (amount, deadline, condition) with `source_url` (the act
on ISAP/ELI or the agency page), `verified_at`, `valid_from` / `valid_to` (amounts change on fixed dates).
Decided (2026-11-08): JSON export straight from TOML, no DB table until something needs to query it. Built for
the first topic, `essentials/travel_documents.toml` (page `/wyjazdy/dokumenty/`): `[[group]]` (id, title, icon,
intro) and `[[fact]]` (group, key, short, note, publisher, url, verified_at, to_confirm, also = [{label, url}]).
The loader (`ingest/curated.py`) accepts only `*.gov.pl` https URLs and known topics (`ESSENTIAL_TOPICS`);
disagreeing official sources go into one fact with `to_confirm = true` and the other source in `also`.
`valid_from` / `valid_to` are not built yet (no dated amounts so far).

Recalled products (UOKiK, Safety Gate) are a feed, not curated: a separate table `product_recalls(source_id,
external_id, published_at, product, category, hazard_pl, url)`, filtered to children's products (TODO: how?
Safety Gate has product categories, e.g. "toys", "childcare articles"; UOKiK: to check).

## Monetization (not built; not blocked)

`PLAN.md` §2 plans `affiliate_links(target_type, target_id)`. `target_type = 'venue'` with `target_id =
venues.slug` fits without changes. Facts never depend on monetization (`PLAN.md` §5, badge rule).

## Privacy

No user data at all (no accounts). Open registers can contain names of natural persons (e.g. a sole trader
running a kids' club or a day carer, "dzienny opiekun"). TODO: publish only place-level fields (name of the
facility, address, facts) and skip personal names, or is the register's own publication enough? Check before the
nursery import.
