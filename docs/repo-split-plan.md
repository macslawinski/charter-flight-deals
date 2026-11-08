# Plan: split Product B ("Pieluchy i paszporty") into its own repo and database

Decided 2026-11-08 (user): B gets **its own GitHub repo and its own Supabase project**. Work starts 2026-11-09.
Product A (charter flight deals) stays in `charter-flight-deals`.

## Why
- A can go public (permission e-mails, end of November) while B stays private; a public repo also gets free
  Actions minutes, so Itaka can go back to 2×/day (memory: actions-minutes-budget).
- Separate CLAUDE.md, roadmap, skills and migration series: each repo only carries its own context.
- Product B was already planned as "same repo, same Supabase" only for speed (CLAUDE.md, Product B extension).

## What couples A and B today (checked 2026-11-08)
| Area | Coupling | After the split |
|---|---|---|
| Python | `ingest/config.py`, `http_client.py`, `store.py` (connect), `models.py` (`ParseError`) used by both; `curated.py`, `opendata/` are B; `sources/`, `run.py`, `market.py` are A | copy the small shared core into both repos (no shared package) |
| Scripts | `export_family.py`, `export_venues.py` = B; `export_deals.py` = A; `db_local.py`, `json_shape.py` = both | copy the shared ones |
| Tests | `test_curated`, `test_export_family`, `test_export_venues`, `test_opendata`, `test_stale_facts` = B; the rest A; `test_config`, `test_http_client`, `test_store`, `test_models` = core (keep the parts each repo uses) | split |
| DB | one Supabase project, one migration series 001–015. B tables: `airports`, `child_rules`, `places`, `hotels`, `hotel_child_features`, `hotel_access` (009), `venue_categories`, `data_sources`, `import_runs`, `venues`, `venue_category_links`, `fact_keys`, `venue_facts` (012–015); types `age_band`, `fact_source`. B depends on A: `child_rules.carrier_iata → airlines`, `places.dest_iata → destinations`; 009 added `airlines.website`, `family_rules_url`, `destinations.slug`; 011 seeded charter airlines into `airlines` | B: new project, one `001_baseline.sql` with only B tables + its own `carriers` table (the airlines B has rules for); `places.dest_iata` becomes a plain column (no FK) |
| Sites | `family/` reads only committed JSON; links to A in the footer; A never reads B | unchanged (footer link stays) |
| Vercel | two projects on the same repo (`web/`, `family/` root dirs) | relink `pieluchy-i-paszporty` (prj_kO1Ag8JIX2PthiKPDQat5oYljoah) to the new repo; `ssoProtection: all` stays |
| CI | `tests.yml` runs everything; `ingest.yml`, `web.yml` = A | B gets its own `tests.yml` (+ later the open-data schedule) |
| Docs | `CLAUDE.md` (both), `ROADMAP.md` (both, B = Step 4 + "Extension"), `PLAN.md`, `docs/family-*.md` = B | split; each repo its own CLAUDE.md and ROADMAP |
| Skills | `rpl-discover`, `check-deals` = A; `curate-hotel`, `find-hotels`, `find-playgrounds`, `reverify-facts` = B; `apply-migration` = both | move / copy |
| Memory | project memory lives under this repo's path | copy the B entries (product-b-family-plan, vercel-protection, always-preview-link) to the new repo's memory |

## Steps (2026-11-09)
1. **Freeze** (C): merge open PRs (#64 `reverify-facts`), tag `pre-split` on `main`, no new B work until step 5.
2. **New repo** (C): `git clone` → `git filter-repo` keeping only B paths (history kept), push as a private repo
   (name to confirm, proposal `pieluchy-i-paszporty`). Kept paths: `family/`, `data/curated/`, `ingest/{__init__,
   config,http_client,store,models,curated}.py`, `ingest/opendata/`, `config/` (open-data sources only),
   `scripts/{export_family,export_venues,stale_facts,db_local,json_shape}.py`, B tests + fixtures, `PLAN.md`,
   `docs/family-*.md`, B skills, `pyproject.toml`. Then trim what B does not use (A models, A tables in `store.py`).
3. **New database** (C, user creates or approves the project): new Supabase project (free tier: 2 projects).
   - `db/migrations/001_baseline.sql`: B tables and types as they are after 015, `carriers` instead of `airlines`,
     RLS on every table with no policies (as now). Test with `db_local.py` on a fresh local DB.
   - Fill it from sources, not by copying: `python -m ingest.curated` (TOML), `python -m ingest.opendata --source
     nfz_nisoz|poznan_place_zabaw`, `python scripts/export_venues.py --city poznan`; the committed JSON must
     come out the same as before (diff it). Lost on purpose: old `import_runs` and raw responses.
   - Secrets: `.env` and GitHub secret `DATABASE_URL` of the new project (never committed).
4. **Vercel** (user approves, production config): connect `pieluchy-i-paszporty` to the new repo, root `family/`;
   check a preview and production; protection still `all`.
5. **Clean up A** (user approves, deletes data):
   - repo A: remove `family/`, `data/curated/`, `ingest/curated.py`, `ingest/opendata/`, B scripts, tests, docs, skills;
     CLAUDE.md and ROADMAP keep only A (one line pointing to the B repo).
   - DB A: export the B tables to a file first, then a new migration that drops them and the 009/011 additions
     A does not use (`airlines.website`, `family_rules_url`; keep `destinations.slug` if A uses it, check first).
6. **Docs and memory** (C): new CLAUDE.md for B (from CLAUDE.md "Product B extension" + working conventions),
   ROADMAP for B (Step 4 + Extension sections), memory copied; footer link B → A unchanged.

## Still to decide
- Repo name and visibility (proposal: `pieluchy-i-paszporty`, private).
- Order: split first, then make A public (proposal), or both at once.

## Rollback
Until step 5 nothing is deleted: tag `pre-split` and the old DB stay usable; Vercel can be relinked back.
