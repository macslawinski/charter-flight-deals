---
name: check-deals
description: Health and plausibility check of the charter-flight-deals data in Supabase - is ingestion fresh and parsing cleanly, how far is the cold start, and are the flagged deals actually correct (independent recomputation of baseline, threshold and stay filter for a sample of deals). Use whenever the user asks "czy dane się zbierają", "sprawdź deale", "czy to się zgadza", "co dziś wyszło", before publishing/exporting deals, after transform changes, or when a deal looks suspicious.
---

# Check data and deals

Two questions, answered in order: **is the data healthy?** and **are the deals right?**
Use the Supabase connector (`execute_sql`). Always aggregate or `LIMIT` — the raw tables are large.
For deeper profiling, `data:validate-data` / `data:explore-data` can be layered on top.

`as_of` defaults to today in Europe/Warsaw unless the user names a date.

## 1. Ingestion health
```sql
select date_trunc('day', fetched_at at time zone 'Europe/Warsaw') as day,
       count(*) as fetches,
       count(*) filter (where http_status <> 200) as http_errors,
       count(*) filter (where parse_ok is false) as parse_failures,
       max(fetched_at) as last_fetch
from raw_fetches
where fetched_at > now() - interval '7 days'
group by 1 order by 1 desc;
```
```sql
select snapshot_date, count(*) as flights, sum(n_obs) as obs,
       min(price_last) as min_price, max(price_last) as max_price
from price_snapshots
where snapshot_date > current_date - 14
group by 1 order by 1 desc;
```
Red flags: no fetch in the last ~8 h (cron broken or blocked — see `rpl-discover`), any
`parse_failures`, a sudden drop in flights per day, prices ≤ 0 or absurd (e.g. < 50 zł or > 20 000 zł).

## 2. Cold-start progress
How many segments (origin, destination, departure month) already have `min_baseline_flights`
distinct, stay-eligible flights with snapshots in the window. Few or none is expected in the first
weeks — report it plainly; never suggest lowering thresholds or inventing data to get deals sooner
unless the user asks to tune parameters.

## 3. Deals
```sql
select count(*) as deals, min(discount_pct), max(discount_pct)
from deals where as_of = '{{as_of}}';
```
If the `deals` table or transform doesn't exist yet, say so and stop after sections 1–2.

## 4. Independent verification of a sample
Pick 3 deals: the biggest discount, a median one, and one from the smallest qualifying segment.
For each, run `references/verify_deal.sql` (replace `{{as_of}}` and `{{flight_key}}`). It recomputes
from raw snapshots — deliberately *not* reusing the transform's views — so a bug in the transform
can't confirm itself. Compare with the stored row; check:
- stay filter: `stay_days >= min_stay` (override → zone → default), one-way excluded unless allowed;
- window is `[as_of - window_days, as_of - 1]` (today's prices excluded);
- one vote per flight (per-flight average first, then across flights);
- `current_price <= baseline_used * (1 - discount_threshold)` and departure is after `as_of`;
- proof fields (avg, median, threshold price, %, flights, obs, window) match.

Mismatch beyond rounding (> 1 zł or > 0.1 pp) = bug: report the flight_key, both values, and which
rule differs. Don't fix the transform inside this skill; propose the fix (via `apply-migration`).

## Report (Polish, short)
```
Ingest:   OK / PROBLEM — last fetch …, failures …, flights/day …
Cold start: N/M segments with baseline
Deals (as_of): N, discount range …
Weryfikacja: 3/3 zgodne  |  rozbieżność: <flight_key> …
Do decyzji: …
```
