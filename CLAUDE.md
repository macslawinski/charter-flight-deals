# CLAUDE.md — Charter Flight Deals (PoC)

## Project in one paragraph
A free web app that tracks **flight-only charter prices** (no hotels, no packages) from Polish tour
operators and flags flights that are *genuinely* cheap, with a verifiable proof of the discount.
Current phase: **proof of concept with one operator — r.pl (Rainbow Tours)**. Monetization: free site,
optional "buy me a coffee" link and ads. Running costs must stay close to zero.

## Communication
- Talk to the user in **Polish**. Code, identifiers, comments, commit messages and docs in **English**.
- Keep explanations short; the user wants working results, not essays.
- Ask before anything hard to undo (dropping tables, deleting data, changing production config).

## Token economy (how to work in this repo)
- Don't recap diffs or restate what the user can see; report outcome + anything surprising.
- Locate with Grep/Glob first, then Read only the needed range. Don't read whole large files.
- **Raw API responses / JSON samples can be huge**: inspect them with
  `python scripts/json_shape.py <file>` (structure only; `--diff other.json` to compare) instead of
  reading the file.
- Never read generated or vendored files (`node_modules`, `dist`, `.venv`, `coverage`, lockfiles).
- Trim noisy command output (`-q`, `--tb=short`, `| Select-Object -First 50`); run targeted tests
  (`pytest tests/test_x.py -k name`) while iterating, the full suite before calling something done.
- SQL exploration: `LIMIT` and aggregate queries; never `SELECT *` on `raw_fetches` or snapshot tables.
- Don't spawn subagents unless asked.

## Scope of the PoC
In scope:
1. Ingestion of r.pl flight-only offers from their (undocumented) JSON endpoint.
2. Storage of raw responses + normalized flights + daily price snapshots in Postgres.
3. Transformation: rolling baseline, 15% deal rule, sensible-stay filter.
4. A minimal public page listing current deals with the "math proof".

Out of scope (for now): other operators, user accounts, alerts/notifications, hotels/packages,
mobile app. Design so a second operator (e.g. Itaka) can be added later without rewrites.

## Tech stack
| Layer | Choice | Notes |
|---|---|---|
| Ingestion | Python 3.12, `httpx` or `requests`, stdlib `tomllib` | One script, CLI entry point |
| Scheduling | GitHub Actions cron (every 4–6 h) | Free; fall back to a home server/VPS if r.pl blocks Actions IPs |
| Database | Supabase (Postgres, free tier) | Schema via SQL migration files in repo |
| Transform | Plain SQL (views / SQL functions) in Postgres | No dbt/Airflow in the PoC |
| Frontend | Static site (Astro or plain HTML + JS) on Vercel | Reads an exported `deals.json`; no public DB access |
| Secrets | `.env` locally, GitHub/Vercel secrets in CI | Never commit secrets, cookies or tokens |
| Analytics | Vercel Web Analytics (free tier) | No product-analytics tools (Amplitude etc.) in the PoC |

Hosting: Vercel. If the user switches to Cloudflare Pages, use the Cloudflare API MCP server
(`https://mcp.cloudflare.com/mcp`); the old "Cloudflare Developer Platform" connector is deprecated and
disabled for this project.

## Repository layout (target)
```
ingest/            # Python package: config, http client, source parsers, db store, run.py
  sources/r_pl.py  # r.pl request building + JSON → FlightOffer mapping
config/            # sources.toml (URL, method, headers, payload template) — no secrets
db/migrations/     # 001_schema.sql, 002_seed_zones.sql, 003_transform.sql, ...
scripts/           # export_deals.py (DB → deals.json), helpers
web/               # frontend
tests/             # unit tests (parser) + SQL tests on synthetic data
.github/workflows/ # ingest.yml (cron)
```

## Data source rules (r.pl)
- The endpoint is undocumented. Discover it with Claude in Chrome (network requests on r.pl flight
  search), then store URL/payload/headers in `config/sources.toml`; put cookies/tokens in `.env`.
- Be polite: low frequency, random delay between requests, cap requests per run, exponential backoff
  on 429/5xx honoring `Retry-After`, **stop the run on 403** (likely blocked) instead of retrying.
- Always save the raw JSON response (`raw_fetches` table, ~14-day retention) so data can be reparsed
  when the mapping changes.
- Expect the API shape to change without notice: parsing must fail loudly and log, never write garbage.
- Legal note: this is for a PoC. Before going public, the user plans to ask Rainbow for permission
  or an official feed. Don't build features that hide or disguise the scraper.

## Data model (essentials)
- `flights` — one row per distinct flight offer. Natural key `flight_key` =
  `operator|origin_iata|dest_iata|outbound_date|return_date[|flight_no]`.
  `stay_days = return_date - outbound_date`; one-way flights have `return_date = NULL`.
- `price_snapshots` — one row per flight per day (`snapshot_date` in Europe/Warsaw), upserted on each
  run: `price_last`, `price_min`, `seats_left`, `n_obs`, first/last observation timestamps.
  Prices are **per person, in PLN**.
- `destinations` (IATA → name, country, zone, optional `min_stay_override`) and
  `zones` (zone → `min_sensible_stay_days`).
- `pipeline_params` — single-row config: `window_days` (30), `discount_threshold` (0.15),
  `min_baseline_flights` (5), `baseline_stat` ('avg' | 'median'), `default_min_stay_days`,
  `include_one_way` (false).
- `deals` — materialized result per `as_of` date, used for export and deal history.

## Business logic (must stay exactly like this unless the user changes it)
**Segment** = same origin airport + same destination airport + same departure month.

**Sensible stay filter** (applied in the transform layer, before anything else):
- Resolve min stay: destination override → zone value → `default_min_stay_days`.
- Drop flights with `stay_days < min_stay`. Drop one-way flights unless `include_one_way`.
- Filtered-out flights do not count toward the baseline either.
- Seed zones roughly by flight time from Poland: short (≤3 h) 3 days, medium (3–5.5 h) 5 days,
  long (5.5–8 h) 7 days, exotic (>8 h) 9 days. Values live in the table, not in code.

**Baseline (rolling average)** for a flight on date D:
- Use snapshots of flights in the same segment from `[D - window_days, D - 1]` — today's prices never
  pull the baseline down.
- **One vote per flight**: average each flight's prices over the window first, then aggregate across
  flights (avg, plus median shown alongside). A flight seen 30 times must not outweigh one seen once.
- No baseline (and no deal) if the segment has fewer than `min_baseline_flights` distinct flights.

**Deal rule**: `current_price <= baseline * (1 - discount_threshold)` and the flight departs after D.

**Proof** shown for every deal: current price, baseline (avg and median), threshold price,
discount %, number of flights and observations in the baseline, window dates. Example:
`1 249 zł ≤ 0.85 × 1 612 zł = 1 370 zł → 22.5% below average (14 flights, 312 obs, 2026-10-05…2026-11-03)`.

Cold start is expected: the first deals appear only after enough history accumulates. Don't fake them.

## Tools available in this environment
- **Claude in Chrome** — API discovery on r.pl (read network requests). Work in a new tab.
- **Supabase connector** — inspect tables before changing schema; apply migrations from
  `db/migrations/` files (keep repo and DB in sync); check advisors/logs when debugging.
  Prefer testing SQL locally (local Postgres or Supabase CLI) before applying to the remote project.
- **Vercel connector** — deployments and logs for the frontend.
- **Data plugin skills** — `data:sql-queries` / `data:write-query` for SQL, `data:explore-data` and
  `data:validate-data` for checking ingested data, `data:statistical-analysis` for tuning the
  threshold/window once there are 2–3 weeks of data.
- **dataviz** skill — the price-vs-baseline chart; **frontend-design** plugin — the deals page.
- **context7** plugin — current docs for Astro, Supabase, httpx, psycopg; use it instead of guessing APIs.
- **pyright-lsp** plugin — type errors on edit; config in `pyproject.toml` (`[tool.pyright]`, uses `.venv`).
- **Supabase CLI** (`supabase`, v3) is installed, but Docker is not, so `supabase start` / `db reset`
  don't work locally yet. Test SQL in a `begin; … rollback;` transaction instead (see `apply-migration`).

## Working conventions
- Every schema change = a new numbered migration file; never edit an applied migration.
- SQL logic must be testable with an `as_of` date parameter (no hidden `now()` inside core logic).
- Keep business parameters in `pipeline_params` / reference tables, not hardcoded.
- Write tests for: JSON → FlightOffer mapping (with a saved sample response), dedupe within a run,
  and the transform on synthetic data (planted deal is found; 3-day long-haul flight is dropped;
  segment with too few flights yields no deal; a 10% drop is not flagged).
- Ingestion supports `--dry-run` and `--from-file sample.json` for testing without the network/DB.
- Before calling something done: `ruff check .`, `pyright`, `pytest`, and for SQL changes run them against real data
  in Supabase and sanity-check a few results by hand.

## Definition of done for the PoC
- Cron run collects r.pl flight-only offers reliably for 2+ weeks without manual fixes.
- Deals view returns plausible results with the proof fields filled.
- Public page shows current deals and their proof; donation link and ad slot in place.
