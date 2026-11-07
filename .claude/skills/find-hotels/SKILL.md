---
name: find-hotels
description: Find family hotels with a real offer for children 0-3 in one Polish voivodeship (województwo) or a sub-region of it for Product B - OpenStreetMap discovery plus web search, a polite probe of each hotel's own website for baby signals (łóżeczko, brodzik, sala zabaw...), then a checked shortlist saved in data/curated/hotel_leads/<voivodeship>.toml for the curate-hotel skill. Use whenever the user says "znajdź hotele w <województwie>", "hotele dla rodzin nad morzem / w górach / na Mazurach / na Helu", "szukaj hoteli przyjaznych maluchom", "dodaj nowe województwo", "lista kandydatów", "jakie hotele sprawdzić", or wants to refresh the leads of a region - even if they don't say "skill", "OSM" or "leads". Not for reading facts of an already chosen hotel (that is curate-hotel), nor for Greek/foreign hotels.
---

# Find family hotels in a voivodeship

Goal: a shortlist of **hotels whose own website shows an offer for children 0–3** (cot, baby bath,
paddling pool, playroom open to toddlers, baby menu...), each with the page that proves it. The list
feeds the `curate-hotel` skill, which reads the facts. This skill only says *which hotels are worth
reading*; it writes no facts to the site.

Why so strict: Product B is for parents of 0–3s. A hotel that merely says "rodzinny" with nothing
for a toddler wastes a curation run and, once on the site, misleads parents. A short list where
every lead was confirmed on the hotel's own site beats a long list of guesses.

**Hotels only** (user decision 2026-11-05): hotels and hotel resorts. Guest houses (pensjonaty,
wille, domy wczasowe), apartments, cottages and campsites are out even when their kids' offer is
good; mention notable ones in the report so the user can change this later. A place that calls
itself "Resort & SPA" with hotel rooms, a restaurant and a reception counts as a hotel even if OSM
tags it as a guest house or not at all.

Rules (PLAN.md §3): discovery is legal and attributed (OSM, ODbL); facts later come only from the
hotel's own website after a robots.txt check. Booking, Tripadvisor, Google Maps listings,
nocowanie.pl and other portals are never a source; a web search result or a portal listing may
only *point* you to a hotel, whose own site you then check.

## 1. Scope and state
- Slug = ASCII name: `zachodniopomorskie`, `pomorskie`, `warminsko-mazurskie`, `malopolskie`,
  `slaskie`, `dolnoslaskie`, `podkarpackie`... (all 16 are in the script).
- **How many leads**: a whole voivodeship → aim for 20–30. A sub-region (Hel, Podhale, one lake) →
  as many as really exist; don't pad. If a voivodeship has fewer, say so.
- Existing leads: `data/curated/hotel_leads/<slug>.toml`. If present, this is a refresh or a new
  sub-region: keep every entry, add new ones, never drop a `curated` or `skipped` entry, and append
  to `covered`. Curated hotels: `data/curated/hotels/<place>/*.toml`. The script marks both as known.

## 2. Discover and probe (one command; run it in the background, it takes minutes)
```
$env:PYTHONUNBUFFERED="1"; .venv/Scripts/python.exe .claude/skills/find-hotels/scripts/osm_hotels.py <slug> --out <scratchpad>/<slug>.json --probe --top 60 [--bbox s,w,n,e] [--towns "A|B"]
```
- The whole voivodeship (`tourism=hotel` + `leisure=resort`) is fetched once and cached in `--out`.
  `--bbox` / `--towns` only filter what is shown and probed (an object is kept if it matches either).
  **For a sub-region use `--bbox`**: many OSM hotels have no town tag (on Hel: Best Western Jurata,
  Meridian), so a towns-only filter silently loses them. A bbox spills into neighbouring places: drop
  those by hand. Without `--probe` the script just lists the rows (useful to look at a region first).
- An overloaded Overpass server may answer with nothing; the script then retries other endpoints and
  fails loudly rather than caching an empty list. `--refresh` re-queries and re-probes.
- The probe visits each hotel website once: robots.txt (disallowed → skipped), the home page, and up
  to four kids / family / FAQ / price-list pages linked from it (legal "ochrona małoletnich" pages
  are ignored). It prints per site: score, kids page, baby and kids signals, **NEGATED** phrases ("nie
  mamy brodzika", "brak łóżeczek"; they lower the score), **flags** and status:
  - `portal` (status) / `portal_domain`: OSM points to a portal or agency, not the hotel;
  - `name_not_on_site`: the hotel's name isn't on the pages: another property, a renamed hotel, or a
    portal; find the real site before trusting anything;
  - `redirect_to:<host>`: the site moved (OSM has an old domain); use the new one;
  - `parked_domain`: the domain is for sale; the hotel's site is elsewhere or gone;
  - `blocked_*`, `little_text` (JS-rendered), `error_*`: the probe saw nothing, which says nothing.
- Score = 2 × baby signals + 1 × kids signals − 2 × negations. It's a keyword count: it finds
  candidates, it proves nothing.

## 3. Web search (not optional)
OSM misses many of the biggest family resorts or tags them as something else (on Hel: Gwiazda
Morza, Belmar, Maloves, Stella). Always run a few searches such as `hotel dla rodzin z małymi
dziećmi <region>`, `hotel z brodzikiem i salą zabaw <miejscowość>`, `resort rodzinny <region>
łóżeczko`, and for each hotel named in the results find its **own** domain and check it like the
others (WebFetch the kids page; the probe script only takes OSM rows).

## 4. Triage
Go down the scored list plus the search finds and decide per hotel:
- **Not a hotel stay** (see "Hotels only"), roadside/business/airport hotels, wedding venues: drop.
- **Is this really the hotel's own site?** Check the address or town on the site matches. Watch for:
  a same-name property elsewhere (wojciech.com.pl is a different place than Pensjonat Wojciech
  in Władysławowo), a local portal named after the town (juratahotel.pl), an old domain that
  redirects, a domain for sale. Chains on one domain (Gorzelanny, Gołębiewski, Arka): the kids page
  must belong to *this* location.
- **Signals from a different context**: "brodzik" in a nearby aquapark ad, "animacje" only for
  weddings, "dzieci do 3 lat" only in a price-list footnote, "baseny dla dzieci" meaning the resort
  next door, text copied from a sister hotel. Open the kids page before believing it.
- **Unreadable but promising** (name or stars suggest a family resort): WebFetch; if that fails too,
  keep it as "do sprawdzenia" (Claude in Chrome can read it later).

**Confirm each kept lead on its own site**: open the kids page and see at least one concrete
**physical item or space for under-3s**: a cot, baby bath, bottle warmer, changing table, potty,
high chair, a paddling pool (brodzik), a playroom or kids' club open to under-3s (with a parent is
fine), a baby menu or toddler food. "Dziecko do 3 lat gratis" alone, a playground alone, or
animations from 4 years are not enough on their own (they can be mentioned alongside).
Record the page as `kids_url`; if the proof is spread over pages, add `evidence_urls`.

## 5. Write the leads file
`data/curated/hotel_leads/<slug>.toml` (not loaded by `ingest.curated` and not on the site; it is
the to-do list for `curate-hotel`):
```toml
# Leads for Product B: hotels in województwo <name> whose own website shows an offer for children
# 0-3. Discovered via OpenStreetMap (tourism=hotel, leisure=resort; (c) OpenStreetMap contributors,
# ODbL) and web search pointing to the hotels' own sites; each lead confirmed on its own kids page.
# Not facts: the curate-hotel skill reads the facts.
voivodeship = "<slug>"
checked_at = YYYY-MM-DD
covered = ["Półwysep Helski (bbox 54.58,18.44,54.82,18.82), 2026-11-05"]   # or ["całe województwo, ..."]

[[lead]]
name = "Hotel Gorzelanny"
town = "Dźwirzyno"             # the locality in the hotel's postal address (Chłapowo, not Władysławowo)
official_url = "https://gorzelanny.pl/hotel-dzwirzyno/"
kids_url = "https://gorzelanny.pl/hotel-dzwirzyno/dla-dzieci/"
evidence_urls = []             # optional: more pages with the proof
osm = "way/123456789"          # omit if found by web search only
lat = 54.15                    # OSM centre; omit if unknown
lon = 15.40
signals = ["łóżeczko", "sala zabaw", "brodzik"]   # what you saw on the hotel's pages, not the probe list
why = "Strona dla dzieci: łóżeczka, krzesełka, sala zabaw, brodzik w strefie basenowej."
status = "lead"                # lead | curated | skipped
```
- `why` in Polish, one line, our words: what concretely is there for 0–3 (prices if stated).
- `status = "skipped"` + `skip_reason` for notable hotels you checked and rejected (a big "family"
  resort with nothing for under-3s, a portal in OSM, a dead site): it saves the next run from
  re-checking them. Don't list every rejected roadside hotel.
- Promising but unreadable: `status = "lead"`, no `kids_url`, `why = "Do sprawdzenia: ..."`. Few.
- Order: leads sorted by town then name, then the skipped entries at the end.
- Check it parses: `.venv/Scripts/python.exe -c "import tomllib,sys;tomllib.load(open(sys.argv[1],'rb'))" <file>`.

## 6. Ship
- `ROADMAP.md`, in the B content step next to the hotels items: one line `C: hotel leads <region>
  (<date>): N leads, M do sprawdzenia; not covered yet: ...`.
- Branch `feat/<slug>-hotel-leads` (or the current hotels branch), commit the leads file + ROADMAP,
  push, PR. No site build is needed (leads are not rendered).
- If the user also asked to curate some of them, continue with the `curate-hotel` skill.

## 7. Report (Polish, short)
Numbers: hotels in OSM for the area / probed / unusable; hotels found only by web search. The leads
grouped by town (name + the one 0–3 item that convinced you); skipped and why; "do sprawdzenia";
strong guest houses left out by the hotels-only rule; which hotels to curate first (most 0–3 items,
variety of places); the PR link.
