---
name: reverify-facts
description: Re-verify curated facts whose verified_at has expired or is about to (airline child rules, hotels, venues on the map, airports, Niezbędnik / travel-document topics) - list them with scripts/stale_facts.py, re-read each source, update or confirm the facts, bump verified_at only for what was actually re-read, re-export and open a PR. Use whenever the user says "sprawdź przeterminowane fakty", "co trzeba ponownie sprawdzić", "odśwież zasady linii", "zweryfikuj ponownie", "re-weryfikacja", "czy ceny są aktualne", "odśwież dane lotnisk / świadczeń / bawialni", asks for the monthly staleness check, or before the site goes public - even if they don't say "skill" or "stale".
---

# Re-verify curated facts

Goal: no fact on the site is older than its staleness period (PLAN.md §3: 12 months; 6 months for fees and
prices, every venue fact and airport facilities). A refreshed date on a fact nobody re-read is worse than an
old date: it tells parents something was checked when it was not. So **`verified_at` changes only for facts
whose source was actually opened and read in this session.**

## 1. List what is due
```
python scripts/stale_facts.py                  # expired + due within 30 days, grouped by file
python scripts/stale_facts.py --within-days 0  # only expired
python scripts/stale_facts.py --kind carrier   # carrier | hotel | venue | airport | essential
```
Facts are grouped per file because one source page usually backs several facts. Pick a batch the user agrees to
(default: everything expired, at most ~10 files per PR; carriers and essentials first, they carry money and law).

## 2. Re-read each source
For each file in the batch, open every distinct `url` of its due facts:
- WebFetch first. If it returns 403, a 500 or only menus, use the browser (Playwright): POZ and WRO airport
  sites block plain clients; ZUS pages are ~300 kB of menus, read `.journal-content-article`; many venue
  sites render prices with JavaScript.
- Airlines: their own pages only (help centre, fee tables, conditions of carriage). Reading a page by hand is fine;
  never add automated fetching of Ryanair / Wizz / Google Flights (CLAUDE.md).
- Official topics (`essentials/`): `*.gov.pl` or `www.zus.pl` only; the loader rejects anything else. Airports:
  the airport's own domain only (`AIRPORT_DOMAINS`).
- If the page moved, find the new page on the same site and replace `url`. If the fact is gone from the source,
  do not keep it as verified (see 3).

## 3. Decide per fact
| What the source says now | Change in the TOML |
|---|---|
| Same as the fact | only `verified_at = <today>` |
| Different (new fee, new hours, new rule) | update `value`, `short`, `note`, `url` if moved, `verified_at = <today>` |
| Not said any more / ambiguous / two pages disagree | keep the old value, set `to_confirm = true`, explain in `note` (for essentials: the other source in `also`) |
| Venue or hotel closed (own site says so, or site gone and OSM marks it closed) | `status = "retired"` (never delete the file) |

Never guess a value, never copy from aggregators, reviews or news sites. Write facts in our own words.
Do not touch `verified_at` of facts that were not part of the batch.

## 4. Re-export and check
```
python -m ingest.curated --dry-run              # validation
python -m ingest.curated                        # hotels, child rules, venues -> Supabase
python scripts/export_family.py                 # family.json (carriers, hotels, airports, essentials)
python scripts/export_venues.py --city poznan   # only if venues changed (map JSON from the DB)
python scripts/stale_facts.py --within-days 0   # the batch should be gone from the list
ruff check . ; pyright ; pytest
```

## 5. PR and report
Branch `chore/reverify-<kind>-<yyyy-mm>`, one commit, PR body: files re-checked, facts changed (old -> new),
facts now `to_confirm`, venues retired. Give the user the Vercel preview deep link of a changed page (memory:
always-preview-link). Report in Polish, short: how many facts re-read, what changed, what is left to confirm, and
the next due date (`python scripts/stale_facts.py --within-days 365 | Select-Object -First 3`).
