# Product B, extended: a "just facts" service for parents (ages 0–6)

Status: **documentation only**, 2026-11-07. No application code yet. Background: `PLAN.md` (Product B, family
travel 0–3), `ROADMAP.md` (steps). Data model: `docs/family-data-model.md`. Sources: `docs/family-data-sources.md`.

**Decisions (2026-11-07):** this is an **extension of Product B**, not a new product: the same site (`family/`,
working name "Pieluchy i paszporty"), the same Supabase project and migration series. Age scope grows from
**0–3 to 0–6** for now. B's existing hotels, airline rules and Poznań playgrounds stay valid and move under
the new sections (below). Everything in `PLAN.md` that is not contradicted here still holds (private site,
no affiliates or ads until testing ends, facts only from official or own sources).

## Vision

One place where a parent in Poland finds **checkable facts** about going out, travelling and the official side of
having a small child: where to go today, what it costs, whether there is a changing table, what the rules say.
No opinions, no reviews, no marketing copy. Every fact shows where it comes from and when we last checked it.

## "Just facts" principle

- A fact is a statement that can be checked against a source: a price, opening hours, an age limit, a legal rule,
  a water quality result. Adjectives ("great", "cosy", "recommended") are not facts and are never published.
- Every fact has a **source** (a URL, or "submitted by the venue") and a **last-verified date**, and **both are
  visible to users** next to the fact (B already does this with the `Stamp` / `FactTile` components).
- Facts are written in our own words; no copied text, no photos without permission (same as `PLAN.md` §3).
- Where sources disagree or are unclear, the fact is shown as "do potwierdzenia" (`to_confirm`), never guessed.
- Stale facts are flagged, not hidden silently: each category has a staleness period (prices and hours: 6 months,
  others: 12 months, as in `PLAN.md` §3). TODO: staleness for legal topics (benefit amounts change on fixed
  dates, e.g. each year's indexation; should they expire on that date instead of after N months?).
- No ranking by quality. Sorting is by facts only (distance, price, age fit, opening hours).

## Audience

Parents and carers of children from newborns up to 6 years, living in Poland. UI in Polish only. Mobile first
(parents check on the go). No accounts, no logins.

## Sections (UI names in Polish)

### 1. "Gdzie z dzieckiem" (main section: map + filters)

Places to go with a child, on a map with filters that work across categories (shared attributes, see the
data model). Categories:

| Category (UI) | Examples | Category-specific facts (extensions) |
|---|---|---|
| Sale zabaw | indoor playgrounds ("bawialnie", already curated for Poznań) | baby zone age, socks rule, adult fee, café |
| Baseny, aquaparki, termy | pools, aquaparks, thermal baths | paddling pool, water temperature, swim nappies rule, minimum age |
| Atrakcje | major attractions | minimum height/age per ride |
| Zoo i zwierzęta | zoos, petting zoos, educational farms | feeding allowed, guided programmes |
| Parki linowe | rope parks | minimum height/age, kids' route |
| Kultura | cinema screenings for parents with babies, children's theatres, museums with family programmes | schedule pattern, age of the show, booking rule |
| Zimą | ice rinks, sledding hills, ski schools | skate rental sizes, helper frames, ski school minimum age, season dates |
| Kąpieliska | supervised bathing sites | water quality (GIS), season dates, lifeguard |
| Szlaki górskie | mountain trails | length, elevation, stroller-passable (from a source only) |
| Urodziny | kids' birthday party venues | capacity, price, what the package includes |

TODO: is a "mountain trail" a place (a point on the map) or a route (a line)? Probably a separate later
category with a start point on the map; to decide before its stage.

### 2. "Wyjazdy" (trips)

| Topic | Notes |
|---|---|
| Hotels for families | B's existing curated hotels (`data/curated/hotels/`). **Poland only at first**; foreign hotels stay hidden (`SHOW_FOREIGN_HOTELS`). |
| Airlines: rules for children | B's existing `child_rules` and `/linie/` pages |
| Airports | play areas, family security lanes, stroller handover at the aircraft door |
| Children's travel documents | passport / ID card for a child, EHIC (EKUZ), consent of the other parent |
| Car seats abroad | car-seat laws in popular destination countries |

### 3. "Niezbędnik rodzica" (parent essentials)

| Topic | Notes |
|---|---|
| Medical care | including NFZ night and holiday care (nocna i świąteczna opieka zdrowotna, NiŚOZ) |
| Nurseries and preschools | żłobki, kluby dziecięce, dzienni opiekunowie (MRiPS register); przedszkola (TODO: source, see data sources) |
| Official deadlines | e.g. registering the birth, PESEL, applying for benefits |
| Leave and benefits | maternity, parental and paternity leave, childcare allowance (zasiłek opiekuńczy), 800+, Dobry Start |
| Vaccinations | the official schedule (mandatory vs recommended) |
| Product recalls | recalled children's products (UOKiK, Safety Gate) |
| Car-seat test results | e.g. ADAC (TODO: licence, see data sources) |

Medical and legal topics are **facts with an official source only** (the act, the agency's page). The site never
gives medical or legal advice; each such page links to the official source as the authority.

## MVP

1. Categories based on **open data**: nurseries and kids' clubs (MRiPS register), supervised bathing sites with
   water quality (GIS), NFZ night and holiday care points. Nationwide import if the source allows it; the UI may
   start with Poznań only (TODO: confirm).
2. **Section 1 for Poznań**: the existing playgrounds plus the other categories, curated from venues' own
   websites and Poznań city sources.
3. Shared filters across categories (age, stroller access, changing table, parking, toilet, price, hours,
   location), map view.

Hotels (already partly built) and air travel come in later stages: see `ROADMAP.md`, "Extension: parents'
service".

## Out of scope for the first version

- An e-mail agent that asks hotels/venues to fill in missing data and updates the site from their replies.
- User accounts, comments, ratings, reviews.
- Monetization (donations, affiliate links). The data model must not block it (B's planned `affiliate_*`
  tables in `PLAN.md` §2 can target venues too), but nothing is built now.

## Where it lives in the repo

| Path | Content |
|---|---|
| `family/` | the site (Astro, static). New pages for the three sections; routes: TODO (see open questions in `ROADMAP.md`) |
| `data/curated/venues/<city>/<slug>.toml` | hand-curated places (already used for Poznań playgrounds), extended to all section 1 categories |
| `data/curated/hotels/`, `data/curated/child_rules/` | unchanged, now under "Wyjazdy" |
| `data/curated/essentials/` | TODO (proposal): curated facts for "Niezbędnik" topics (benefits, documents, deadlines), one file per topic |
| `ingest/opendata/` | proposal: one module per open-data source, CLI `python -m ingest.opendata --source <id>` with `--dry-run` and `--from-file`, like `ingest.market` |
| `db/migrations/` | new numbered migrations from the next free number (now `012_`) |
| `scripts/export_family.py` | extended to export venues and open-data records to `family/src/data/` |
