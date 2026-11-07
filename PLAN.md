# PLAN: Product B (family travel, ages 0–3) next to Product A (charter deals)

Status: **draft for review**, 2026-11-04. No implementation until the open questions (§8) are answered.

**Decisions (2026-11-04):** both products stay **private** (not promoted, not public) during development and
testing. **No affiliate links and no ads** until testing is finished; they are added later. As long as that holds,
the Vercel Hobby plan is fine (non-commercial), and the permission requests to Rainbow/Itaka are needed before
going public, not before building.
Effort unit: **1 evening ≈ 2–3 h** of solo work.

---

## 0. Current state (Product A), as found in the repo

| Area | Today |
|---|---|
| Stack | Python 3.12 (`httpx`, `psycopg` 3), plain SQL in Postgres; no web framework |
| Ingestion | `python -m ingest.run --source r_pl|itaka`. r.pl: undocumented JSON API (`r.pl/api/czartery`, ~110 req/run). Itaka: Next.js RSC payload of `itaka.pl/bilety-lotnicze/` (~150 pages). Polite client (random 3–8 s delay, cap, backoff, stop on 403). Raw bundles kept 14 days in `raw_fetches` |
| Reference prices | `python -m ingest.market`: Travelpayouts/Aviasales Data API, display-only |
| Scheduling | GitHub Actions (private repo, 2000 min/month): r.pl 3×/day, Itaka 1×/day, parallel jobs |
| Database | Supabase Postgres (free tier), migrations `db/migrations/001–008`, RLS on with no policies; browser never talks to the DB |
| Transform | SQL functions `compute_deals(as_of)` / `refresh_deals` (rolling 30-day per-flight baseline, 15% rule, sensible-stay filter), `market_reference(as_of)` |
| Frontend | Static `web/public` (plain HTML + JS, no build), reads `deals.json` exported by `scripts/export_deals.py`; deployed to **Vercel** (charter-flight-deals.vercel.app) by the `web` job after each ingest |
| Data model | `flights` (key `operator|origin|dest|out|ret|flight_no`), `price_snapshots` (daily, per person PLN), `destinations` (IATA, name, country, zone), `zones`, `pipeline_params`, `deals`, `airlines` (iata, name, is_charter), `market_fares`, `market_fetches` |
| In production? | Live PoC: data collection started 2026-11-04, cold start (no deals yet, first baselines from 2026-11-05). Not yet promoted; donation link and ad slot not filled |

**Child prices: not collected.** Both crawls ask for **one adult only** (r.pl: one `dataUrodzenia=1990-01-01`; Itaka:
`participants[0][adults]=1`), and every stored price is the adult per-person price.
r.pl's API prices by passenger birth dates, so an infant or child date *probably* returns a family price. Itaka's
`participants[0][...]` structure suggests a children parameter. **Neither is tested yet** (see §5, task A1).
Also missing for the "flying with kids" toggle: **departure time and flight duration are in the raw responses
(r.pl `Wylot`/`Przylot`/`CzasLotu`, Itaka `departure.time`) but not in `flights`**.

**Findings that affect both products (independent of B):**
1. **r.pl `robots.txt` disallows `/api`**, which is the path our r.pl ingestion uses. Itaka's robots.txt does not
   disallow `/bilety-lotnicze/`. This strengthens the existing plan to ask Rainbow for permission/an official feed
   *before going public*. It should probably happen before Product B builds on A's data.
2. **Vercel Hobby forbids commercial use**, and the fair-use guidelines explicitly list ads and "affiliate linking is
   the primary purpose of the site" (donations are fine). A with ads, and B with affiliate links, need **Vercel Pro
   (~$20/month)** or another host, e.g. Cloudflare Pages (verify its terms; CLAUDE.md already anticipates the switch).

---

## 1. Structure: shared core vs. per-product code

### Recommendation: one monorepo, two static sites, two Vercel/Cloudflare projects

```
ingest/                 # shared: crawlers, market, store (unchanged) + curated.py (loader for data/curated)
db/migrations/          # shared schema (one Supabase project)
scripts/
  export_deals.py       # A: deals.json (+ family fields)
  export_family.py      # NEW B: content JSON for the B build (rules, places, hotels, family deals)
data/curated/           # NEW human-curated sources of truth, reviewed in PRs (TOML, stdlib tomllib):
  places.toml           #   B places (flight + domestic)
  child_rules/*.toml    #   one file per carrier
  hotels/<place>/*.toml #   one file per hotel
web/                    # A: unchanged (not moved, so A's deploy and Vercel project stay as they are)
family/                 # B: Astro static site, working name pieluchyipaszporty.pl
.github/workflows/      # ingest.yml (shared), web.yml (A), family.yml (B, path filters)
```

| Option | For | Against |
|---|---|---|
| **Monorepo, two apps** (recommended) | Brands fully separate (CSS, layout, analytics, domain); A untouched and keeps its zero-build setup; each deploys alone (a B build error can't take A down); shared data via export scripts, same as today | Two deploy targets; small duplication (footer, disclosure component) |
| One app, per-hostname routing | One build and deploy | Needs SSR or middleware (today A is pure static); brand bleed risk; one bug breaks both; harder per-site SEO, analytics and cache control |
| Two repos | Hard separation | Shared schema and ingestion would need a package or submodule; drift between repo and DB, which is exactly what we avoid today |

Why Astro for B: B is content-heavy (hundreds of rule and hotel facts, destination pages, sitemap, JSON-LD). Astro
builds static HTML from JSON/YAML with no runtime cost. The wizard is a small client-side island. A stays plain HTML.

**Admin, phase 1**: no admin UI. Curated data lives in TOML in `data/curated/` (stdlib `tomllib`, no new
dependency), and a loader validates it and upserts it into Postgres. Edits are reviewed as PRs, with diffs and
history for free. A web admin comes only if the files become the bottleneck (e.g. with parent surveys in phase 3).

---

## 2. Data model draft (new migrations from `009_`; nothing existing is altered destructively)

Existing tables stay. New columns are nullable. A keeps working throughout.

```sql
-- 009: extend what A already has
alter table destinations add column slug text unique;       -- shared slugs, e.g. 'rodos', backfilled from name
alter table airlines     add column website text,
                         add column family_rules_url text;  -- `airlines` = our carriers table, reused
create table airports (iata char(3) primary key, name text not null, city text not null,
                       country text not null, is_polish_origin boolean not null default false);
                       -- replaces the hardcoded ORIGINS map in export_deals.py

-- 010: flight details for the "flying with kids" toggle (parsers fill them; old rows stay null)
alter table flights add column out_dep_time time, add column out_duration_min int,
                    add column ret_dep_time time, add column ret_duration_min int,
                    add column carrier_iata text references airlines(iata);

-- 011: child rules
create type age_band as enum ('0-1', '1-2', '2-3', '3+');   -- airline rules often split at 2 years
create table child_rules (
    id bigint generated always as identity primary key,
    carrier_iata text not null references airlines(iata),
    rule_key text not null,      -- infant_fee | lap_infant | infants_per_adult | twins | stroller | car_seat
                                 -- | bassinet | priority_boarding | infant_baggage | child_baggage | infant_seat
    age_band age_band,           -- null = applies to all children
    value jsonb not null,        -- structured: {"allowed": true, "fee_pln": 99, "per": "leg", "max": 1, ...}
    summary_pl text not null,    -- one human sentence shown on the site
    source_url text not null,
    verified_at date not null,
    verified_by text not null,   -- 'owner' for now
    valid_from date, valid_to date,
    unique (carrier_iata, rule_key, age_band)
);

-- 012: places and hotels. B also covers Polish hotels reached by car/train (e.g. Grzybowo on the Baltic
-- coast), which have no IATA code, so hotels hang off a B-level `places` table instead of `destinations`.
create table places (
    slug text primary key,                  -- 'rodos', 'kreta-heraklion', 'grzybowo'
    name text not null, country text not null, region text,
    kind text not null check (kind in ('flight', 'domestic')),
    dest_iata char(3) references destinations(iata),   -- set for 'flight' places: links to A's data
    check ((kind = 'flight') = (dest_iata is not null))
);
create table hotels (
    id bigint generated always as identity primary key,
    slug text not null unique,
    place_slug text not null references places(slug),
    name text not null, official_url text, lat numeric(9,6), lon numeric(9,6),
    status text not null default 'draft'    -- draft | published | retired
);
create table hotel_access (                 -- how to get there: airport transfer abroad, drive/train in Poland
    hotel_id bigint not null references hotels(id) on delete cascade,
    from_kind text not null check (from_kind in ('airport', 'city', 'station')),
    from_code text not null,                -- 'RHO' / 'Warszawa' / 'Kołobrzeg'
    mode text not null check (mode in ('transfer', 'car', 'train', 'bus')),
    minutes int not null, source_url text, verified_at date not null,
    primary key (hotel_id, from_kind, from_code, mode)
);
create table hotel_child_features (
    hotel_id bigint not null references hotels(id) on delete cascade,
    feature_key text not null,   -- cot | cot_count | baby_bath | bottle_warmer | heated_kids_pool | paddling_pool
                                 -- | shade | high_chair | toddler_food | playroom | lift | step_free_access
    age_band age_band,           -- '0-1', '1-2', '2-3', '3+' or null
    value jsonb not null,        -- {"available": true, "count": 2, "fee_eur": 0, "on_request": true}
    source_type text not null,   -- hotel_written | hotel_website | operator_page | own_visit | parent_survey
    source_url text, verified_at date not null,
    primary key (hotel_id, feature_key, age_band)
);

-- 013: monetisation and cross-links (data, not hardcoded in templates)
create table affiliate_programs (id text primary key, network text, name text not null,
                                 terms_url text, active boolean not null default true, checked_at date);
create table affiliate_links (
    id bigint generated always as identity primary key,
    program_id text not null references affiliate_programs(id),
    target_type text not null, target_id text not null,  -- 'hotel' / 'destination' / 'carrier'
    url text not null, active boolean not null default true, checked_at date
);
create table cross_link_placements (
    id text primary key,          -- e.g. 'a_deal_to_b_destination'
    site text not null check (site in ('deals', 'family')),
    page_type text not null,      -- deal_card | destination_page | ...
    rule jsonb not null,          -- e.g. {"requires": "published_hotels >= 5"}: only link where B has content
    enabled boolean not null default true
);
```
All new tables: RLS on, no policies (same as today). Read access only through the export scripts.

**Family deals for B** are a SQL view or function on top of `deals` and `flights`. Example filters: `out_duration_min <= 240`,
departure 07:00–15:00, off-season month. It is parameterized by `as_of` like the rest, and its thresholds live in
`pipeline_params` or a new `family_params` row, not in code.

---

## 3. Collecting hotel data legally and sustainably

1. **Manual curation from the hotel's own website (MVP, decision 2026-11-04: no questionnaire for now).** Facts
   come from the hotel's official pages (kids section, FAQ, guest guide, room pages), with URL and date per fact
   (`source_type = hotel_website`), after checking the site's robots.txt. Facts are written in our own words, with
   no copied text and no photos without permission. Where the hotel's pages contradict each other, both sources
   are kept and the fact is marked `to_confirm`. Guest reviews are used only as a hint for what to check
   (`source_type = review_hint`, never shown as a verified fact). They are read only where the platform allows it,
   not scraped, and never quoted. A written answer from the hotel (`hotel_written`) can come later and outranks
   the website.
2. **Operator pages (r.pl, Itaka)**: robots.txt doesn't block hotel pages, but their terms most likely restrict
   reusing content. Use them only as a pointer for which hotels to check, never as a copied data source. Include
   this in the permission request to Rainbow and Itaka.
3. **Booking.com, Tripadvisor, Google**: **no scraping.** Booking's terms forbid automated extraction and commercial
   reuse of content, and its affiliate terms forbid programmatic extraction too. Use only what an affiliate
   agreement explicitly allows (links, widgets).
4. **Official feeds later**: content APIs through affiliate approval (Booking via CJ, Expedia Rapid, Agoda) only if
   approved, and only for the fields their terms allow (names, coordinates). Child features still come from our
   own verification. That is the product.
5. **Staleness rule**: every fact has `verified_at`. After 12 months (6 for fees), the site shows "to re-verify". A
   project skill `reverify-hotel` and a monthly SQL report list what has expired.

### 3a. Indoor playgrounds per city ("bawialnie"), PoC Poznań (idea 2026-11-04)

Parents of 0–3s in our six origin cities need a rainy-day list at home too, and it gives B local, repeat-visit
pages. Same rules as hotels: discovery is legal and attributed, facts come from the venue's own website.

- **Discovery: OpenStreetMap** (ODbL; credit "© OpenStreetMap contributors" on the page, no other obligations
  for a list we enrich by hand). Overpass query on 2026-11-04 for Poznań (`leisure=indoor_play`, plus
  `leisure=playground` + `indoor=yes`) returned 14 objects: ~10 real indoor playgrounds (Kraina Piratów,
  Fikołki ×2, Mlecz, Bawialnia Bawimy, Monsterkowo, Smålandia, Madagaskar, Pobawimysię?, Holiday Park), the rest
  noise (climbing wall, go-karts, unnamed). About half have a website tag. OSM is incomplete, so the list is a
  starting point; missing venues get added by hand from their own sites (and can be contributed back to OSM).
- **Facts from the venue's website only** (no Google Maps, Facebook or review scraping): youngest age / baby zone
  (0–3), price for an under-3 and for the adult, opening hours, café, changing table, stroller parking, parking,
  socks rule, birthday-party only days. Each with URL + `verified_at`, like `hotel_child_features`.
- **Data model (new migration, after the PoC page works from TOML)**: `venues(id, slug, city, kind
  'indoor_play', name, official_url, address, lat, lon, osm_type, osm_id, status)` + `venue_child_features`
  with the same fact columns as hotels; TOML in `data/curated/venues/<city>/<slug>.toml`, loaded by
  `ingest.curated`. `osm_id` lets a monthly check flag venues that closed (deleted in OSM).
- **Page**: `/poznan/bawialnie/`: list with youngest age, price for a toddler, hours, and the same source stamp;
  filter by "has a baby zone". Staleness: 6 months (prices and hours change often).
- **Refresh**: one Overpass query per city per month (cheap, polite), diffed against our list; never automatic
  publishing of new venues.

---

## 4. SEO basics for B

- Own domain, Polish only for now; `lang="pl"`, canonical URLs, no hreflang yet.
- Page templates: home with the wizard · `/linie/<carrier>` (rules per carrier) · `/porownanie` (rules table) ·
  `/<destination-slug>` (destination with hotels plus a family-deals widget) · `/<destination-slug>/<hotel-slug>`.
- Structured data: `Hotel` with `amenityFeature` (`LocationFeatureSpecification`) for verified features,
  `BreadcrumbList`, `Dataset`/`Table` semantics for the comparison. `FAQPage` is fine as markup, but Google limits
  FAQ rich results to authoritative sites, so don't count on them.
- `sitemap.xml` generated at build time, `robots.txt`, and a visible "last verified" date on every page.
- **No thin content**: a hotel page is published only with ≥ 8 verified features. A destination page is published
  only with ≥ 5 published hotels. Below that, `noindex` or not built at all. Pages are built from structured data
  plus written context (transfer time, what to watch out for), not boilerplate.
- Performance: static HTML, no heavy widgets above the fold, affiliate widgets lazy-loaded.

---

## 5. Roadmap (solo, evenings)

### Phase 0: prerequisites (≈ 3–5 evenings + waiting time)
- P1: A reaches its own definition of done (2+ weeks of reliable cron, plausible deals). Ongoing.
- P2: Permission request to Rainbow (r.pl `/api` is disallowed in robots.txt) and Itaka. Not code; blocks
  **going public** only (both sites stay private for now).
- P3: Hosting for ads/affiliate (Vercel Pro vs. Cloudflare Pages): **deferred** until affiliates/ads are added.
  Private vs. public repo (Actions minutes) still open.
- P4: ~~Move `web/`~~: dropped. A stays in `web/` and B goes to `family/`, so A's deploy is untouched.

### Phase 1: "flying with kids" toggle in A + B MVP (≈ 35–55 evenings, ~3–5 months)
**A**
- A1 (1–2 ev.): test whether r.pl and Itaka return infant/child prices (a handful of manual requests, logged).
  Outcome decides A2.
- A2 (3–6 ev., only if A1 is positive): family price. Prefer deriving it from a fixed infant fee per operator
  (stored in `child_rules`, no extra crawl) over a second crawl, which would double requests and Actions minutes.
- A3 (3–4 ev.): migration 010 + parsers fill departure times, durations and carrier; export; tests on fixtures.
- A4 (2–3 ev.): toggle UI (off by default, remembered in localStorage): highlights departure time and duration,
  shows the family price if available, shows the contextual link to B when B has content for that destination. No
  change to A's look when the toggle is off.

**B**
- B1 (3–4 ev.): Astro skeleton, brand (frontend-design), domain, deploy workflow, disclosure and owner pages
  ("O nas": the same owner as the deals site, said openly).
- B2 (2 ev.): migrations 009/011/012, YAML schema and loader with validation (unknown keys or missing source = error).
- B3 (8–12 ev.): child rules for ~8–10 carriers flying charters and regular routes from Poland (Enter Air,
  Smartwings, Buzz, Corendon, SunExpress, LOT, Ryanair, Wizz Air…) × ~10 rules, each with source URL and date. A
  project skill `reverify-child-rules` makes re-checks repeatable.
- B4 (4–6 ev.): wizard (carrier, adults, infants and children with ages) → applicable rules, fees and warnings
  (e.g. one lap infant per adult, so twins with one adult need a seat). Pure client-side logic plus unit tests.
- B5 (10–18 ev.): **Rodos + Crete-Heraklion** (flight places, linked to A's data) and a **Polish hotels** section
  (domestic places, starting with Saltic Resort & Spa in Grzybowo) × 10–20 hotels each: questionnaire, entry,
  pages. Mostly waiting for hotel replies. Domestic places have no flights, so no family-deals widget and no
  airline rules; `hotel_access` shows drive/train times instead of an airport transfer.
- B6 (2–3 ev.): SEO basics (§4), sitemap, JSON-LD validation.
- B7 (2–3 ev.): cross-links (A → B on deal cards, B → A widget from the family-deals view), governed by
  `cross_link_placements`.

### Phase 2: affiliates + family deal alerts (≈ 15–25 evenings)
**On hold (decision 2026-11-04): no affiliates until testing is finished.** Phase 1 builds no affiliate code; the
`affiliate_*` tables (migration 013) wait for this phase too.
- Affiliate applications and approvals (§7 Q4), `affiliate_links` management, a disclosure label next to every
  link, a link checker (monthly job: dead/inactive programs).
- Family deal alerts: e-mail provider (free tier), double opt-in, unsubscribe, GDPR notice. **This changes A's
  current scope** ("no alerts/notifications"), so it needs your explicit go.

### Phase 3: parent surveys + B2B badge (≈ 20–35 evenings + non-dev work)
- Structured post-stay survey (no free-text personal data, child age as a band only), moderation, anti-spam, GDPR.
- "Toddler-friendly verified" badge: public criteria, verification process, renewal date, terms. Badge status must
  never depend on payment, or the site's independence is gone. Paid tiers, if any, are separate and labeled.

---

## 6. Risks and mitigations

| Risk | Mitigation |
|---|---|
| **Inaccurate or stale rules** (a parent relies on a wrong fee or lap-infant rule) | Source + date on every fact, staleness flags, "check with the carrier before booking" note on every rule, re-verification skill, an easy "report an error" link |
| **Legal basis of A's data** (robots.txt disallows r.pl `/api`; B builds on it) | Permission request before going public (P2); B's own content (rules, hotels) doesn't depend on A, so B can launch with fewer A-derived widgets if needed |
| **Affiliate program changes** (Booking cut small direct partners in 2025 and moved to CJ; Hotellook closed 2025-10-20) | Several programs and networks; links stored as data (`affiliate_links`) so a program can be swapped without template changes; the monthly link checker |
| **Hosting terms** (Vercel Hobby: no ads, no affiliate-primary sites) | Pro plan or Cloudflare Pages before ads/affiliates go live |
| **SEO traffic loss to AI overviews** | Value that a summary can't replace: the interactive wizard, verified first-party hotel data, alerts/newsletter as an owned channel; measure with Vercel Analytics and Search Console |
| **Scope creep** (two products, solo, evenings) | Phase gates: Phase 1 is done only when B has 2 destinations live and A's toggle shipped; nothing from Phase 2/3 starts before. A's definition of done comes first |
| **Brand bleed / A gets a "kids" feel** | Separate apps and CSS; A's family features only behind the toggle, off by default |
| **Privacy (children's data)** | Never store children's names or birth dates, only age bands; surveys anonymous by default; GDPR notice before Phase 2 |
| **Cost creep** (Actions minutes, hosting) | B builds only on content changes (path filters); monthly cost check; see the memory note on Actions minutes |

---

## 7. Monetization research (state as of 2026-11, to verify at sign-up)

- **Booking.com**: no direct program for small publishers since mid-2025 (partners under ~$1,000/month were cut,
  links stopped earning after 2025-06-20); applications are routed to **CJ**. Reports about the Awin route
  (ending 2026-06-30) conflict. Check the current region rules on Booking's partner page.
- **Stay22**: one account and links/maps for Booking, Expedia, Hotels.com, Agoda, Vrbo and others. Reported share
  ~30% of the partner commission (unofficial figures); 24 h cookie at Booking reported. A good fit for hotel pages.
- **Travelpayouts** (already used for A's reference prices): Hotellook closed on 2025-10-20. Still listed: Agoda,
  Trip.com, Booking (check availability), **DiscoverCars** (car rental, child seats as an add-on), **EKTA** (travel
  insurance). Check each program's allowed traffic types.
- **Itaka**: affiliate program on **Tradedoubler** (award-winning in 2026 per Tradedoubler). A natural fit for
  "book this flight/package" links. **r.pl**: no public affiliate program found. Ask in the permission email.
- **Travel gear**: Amazon.pl Associates, Ceneo partner program (verify).
- **Insurance (PL-specific)**: comparison sites with affiliate programs in Polish networks; to research in Phase 2.

Sources: [Booking ends direct affiliates (Affiverse)](https://www.affiversemedia.com/booking-com-suddenly-ends-affiliate-partnerships-what-travel-bloggers-need-to-know/) ·
[Booking program explained (makeinfluence)](https://www.makeinfluence.com/en/academy/booking-coms-affiliate-program-how-travel-creators-earn-commission) ·
[Awin end (Kosupa Travel)](https://en.kosupatravel.com/entry/2026/09/15/booking-com-affiliate-program-ends-on-awin-why-im-not-worried-why-stay22-could-be-the-game-changer-june-2026) ·
[Stay22 review (dreambigtravelfarblog)](https://www.dreambigtravelfarblog.com/blog/stay22-review) ·
[Stay22 review (autovylet)](https://www.autovylet.cz/en/stay22-review/) ·
[Hotellook closure FAQ (Travelpayouts)](https://support.travelpayouts.com/hc/en-us/articles/29534131568530-FAQ-on-the-closure-of-Hotellook) ·
[EKTA on Travelpayouts](https://travelpayouts.com/en/offers/ekta-affiliate-program) ·
[Itaka affiliate case study (Tradedoubler)](https://www.tradedoubler.com/post/inside-itaka-s-award-winning-travel-affiliate-marketing-program) ·
[Booking terms on commercial reuse (conductatlas)](https://conductatlas.com/platform/bookingcom/bookingcom-terms-and-conditions/prohibition-on-commercial-use-of-platform-content/) ·
[Vercel fair use: commercial usage](https://vercel.com/docs/limits/fair-use-guidelines) ·
[r.pl robots.txt](https://r.pl/robots.txt) · [itaka.pl robots.txt](https://www.itaka.pl/robots.txt)

---

## 8. Open questions

1. ~~Destinations~~: **Rodos + Crete-Heraklion + Polish hotels** (first: Saltic Resort & Spa, Grzybowo).
   Polish hotels: ~~Baltic coast only at first~~ **any voivodeship** (decision 2026-11-05; discovery per
   województwo with the `find-hotels` skill, facts with `curate-hotel`), **hotels only** (no guest houses,
   apartments or cottages for now), each with a concrete offer for 0–3 on its own site; access times
   **by car and by train** from Warszawa, Poznań, Gdańsk, Wrocław, Kraków and Katowice.
2. ~~Hosting~~: **deferred**. Private and without ads/affiliates, Vercel Hobby is fine; revisit before monetizing.
3. ~~Permission emails~~: **before going public** (both sites private for now). Still open: should they also ask
   about using hotel facts (and later an affiliate deal)?
4. ~~Affiliate accounts~~: **on hold** until testing is finished.
5. ~~Domain and brand~~: working name **pieluchyipaszporty.pl** (domain not bought; the site stays private).
   Still open, later: own analytics project.
6. ~~Family price~~: **derived** (adult price × adults + infant/child fee from `child_rules`), labeled as an
   estimate with the rule's source. No second crawl. A1 still checks what the operators charge, to seed the fees.
7. **Alerts (Phase 2)** change A's current "no notifications" scope. Go or not yet?
8. ~~Hotel questionnaire~~: **not for now**. Data comes from the hotels' own websites (§3).
9. ~~Repo visibility~~: publishing the curated data with the repo is **fine**.
10. ~~Timeline~~: **B in parallel** with A's cold start (A mostly waits for history to accumulate).

---

## 9. Extension (2026-11-07): parents' service, ages 0–6

B grows into a "just facts" service for parents with three sections ("Gdzie z dzieckiem", "Wyjazdy",
"Niezbędnik rodzica"), same site and database. Details: `docs/family-product.md`, `docs/family-data-model.md`,
`docs/family-data-sources.md`; steps in `ROADMAP.md` ("Extension: parents' service").
