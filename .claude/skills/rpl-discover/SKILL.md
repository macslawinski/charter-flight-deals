---
name: rpl-discover
description: Discover or re-verify the undocumented r.pl (Rainbow Tours) flight-only JSON endpoint with Claude in Chrome and turn it into config/sources.toml, a test fixture and the parser in ingest/sources/r_pl.py. Use whenever the task is finding the r.pl API, filling in the r.pl source, the ingest starts failing with ParseError / unexpected shape / 4xx, r.pl changed its site, or the user says things like "znajdź endpoint", "r.pl przestało działać", "zmienił się format odpowiedzi". Also the template for adding another operator (Itaka etc.).
---

# r.pl endpoint discovery / re-verification

Goal: a reproducible request (method, URL, headers, payload) that returns flight-only offers as JSON,
a small committed fixture, and a parser that maps it to `FlightOffer` and fails loudly on surprises.

Two modes — pick from the situation:
- **Discover**: `config/sources.toml` still has `url = "TODO"`.
- **Re-verify**: the source is configured but runs fail (ParseError, 4xx, empty results). Go straight to
  step 5 after capturing one fresh response; often only the mapping changed.

## Ground rules (why they matter)
- The user plans to ask Rainbow for permission before going public. Behave like a polite, honest
  client: keep the existing `User-Agent`, no rotating IPs/headers, no captcha or anti-bot bypassing.
  If the site blocks or challenges, **stop and report** — working around it would undermine that plan.
- Cookies/tokens are secrets: they go to `.env` (`RPL_COOKIE`), never into `sources.toml`, fixtures,
  commits or chat summaries. Scrub them from anything you save.
- Raw responses are large. Never Read them whole — inspect with
  `python scripts/json_shape.py <file>` (structure only) to save context.

## Steps

1. **Load the browser skill** (`anthropic-skills:chrome-browser`) and open r.pl in a **new tab**.
   Navigate to the flight-only search ("tylko przelot" / "loty czarterowe"), pick a common route
   (e.g. Warszawa → popular destination), run a search.
2. **Find the data request** in network requests: filter to XHR/fetch, look for JSON responses that
   contain prices, dates and airport codes. Note: method, full URL, query params, request body,
   and which headers look required (content-type, custom `x-` headers, auth). Check whether results
   are paginated and which params control origin, destination, dates/month, number of passengers.
3. **Replay outside the browser** with one request via `httpx` (respecting the delay rules), first
   *without* cookies. Only if that fails, add the cookie from `.env`. Record whether it is required —
   it decides whether GitHub Actions can run without secrets that expire.
4. **Save samples**:
   - full response → `data/r_pl_raw_<YYYYMMDD>.json` (gitignored, for reparsing and diffs);
   - trimmed fixture → `tests/fixtures/r_pl_sample.json`: keep the envelope but cut lists to ~5 items,
     including at least one one-way and one round-trip offer if they exist, and any odd case seen
     (missing price, sold out). Small fixtures keep the repo and every future test read cheap.
5. **Map the shape** with `python scripts/json_shape.py <raw> --items 2`. Identify the fields for every
   `FlightOffer` attribute. Confirm: price is **per person in PLN** (check against the site for
   2 passengers), dates are local dates, airport codes are IATA. In re-verify mode compare old vs new
   with `python scripts/json_shape.py <old_raw> --diff <new_raw>`.
6. **Write config + code**:
   - `config/sources.toml`: url, method, headers (non-secret), payload template, `enabled = true` only
     once the parser tests pass.
   - `ingest/sources/r_pl.py`: `build_requests()` (the set of requests per run — keep it within
     `max_requests_per_run`) and `parse()`. Validate required fields and raise `ParseError` with the
     offending path instead of guessing defaults — a loud failure is cheaper than garbage in
     `price_snapshots`, which would silently poison the baselines.
   - Tests in `tests/test_r_pl.py` against the fixture: field mapping, one-way handling, flight_key,
     and a malformed-input case that raises `ParseError`.
7. **Dry run**: `python -m ingest.run --dry-run --from-file tests/fixtures/r_pl_sample.json`, then
   one real `--dry-run` fetch. Report counts.

## Report to the user (Polish, short)
- endpoint found/changed (method + path, no secrets), cookie required yes/no,
- requests per run needed for full coverage,
- what changed in the mapping (re-verify mode),
- open questions (e.g. price per person unclear).

## New operator
Same procedure; create `ingest/sources/<operator>.py`, a `[sources.<operator>]` block, its own
fixture, and register it in `PARSERS` in `ingest/run.py`.
