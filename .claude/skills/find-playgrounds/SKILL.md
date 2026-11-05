---
name: find-playgrounds
description: Find and curate indoor playgrounds ("bawialnie", "sale zabaw") for Product B in a given Polish city - OpenStreetMap discovery, facts only from each venue's own website, one TOML per venue in data/curated/venues/<city>/, export to the family site and a PR. Use whenever the user says "znajdź bawialnie w <mieście>", "dodaj bawialnie", "sale zabaw w Krakowie/Warszawie/...", "uzupełnij bawialnie", "sprawdź cenniki bawialni", "odśwież listę bawialni", asks to resolve "do potwierdzenia" facts on a venue, or wants the monthly OSM refresh of venues - even if they don't say "skill" or "OSM".
---

# Find indoor playgrounds in a city

Goal: a short, trustworthy list of indoor playgrounds where a parent of a 0–3-year-old learns the
youngest age, the price for a toddler, hours and the rules, each fact with its source. A wrong price
or a made-up "free for babies" is worse than a missing fact, so every fact comes from the venue's
own website (or its own PDF rules), with URL and `verified_at`. Rules: `PLAN.md` §3a.

## 1. Setup and the city
- City slug = key of `VENUE_CITIES` in `ingest/curated.py` (`poznan`, later `warszawa`, `krakow`,
  `wroclaw`, `gdansk`, `katowice`). A new city: add it there (slug → Polish name). The site is not
  fully multi-city yet: `family/src/pages/[city]/bawialnie.astro` builds the title locative only for
  Poznań, its closing note lists Poznań venues, and the nav/home links (`Base.astro`, `index.astro`)
  point to `/poznan/bawialnie/`. Fix the locative (e.g. store it next to the name) and **ask the user**
  before changing navigation (it changes what parents see on every page).
- Existing venues: `data/curated/venues/<city>/*.toml`. Read one first (e.g. `fikolki-stary-browar.toml`)
  for the format; the open items for the city may be in `ROADMAP.md` step 4.

## 2. Discover in OpenStreetMap (one query per city)
```
.venv/Scripts/python.exe .claude/skills/find-playgrounds/scripts/osm_playgrounds.py <city> [--names "A|B"] [--bbox s,w,n,e]
```
It queries `leisure=indoor_play` and `leisure=playground`+`indoor=yes` in a bbox (presets for the six
cities; area queries by name time out on the public server), retries/falls back to a second endpoint,
and marks `KNOWN(<slug>)` for osm ids we already curate, plus curated venues that vanished from OSM
(possibly closed: check their site, set `status = "retired"` if so). Use `--names` for venues the user
or the roadmap names that may be tagged differently.

Triage the `new` lines: drop noise (climbing walls, go-karts, unnamed ways, trampoline parks for big
kids are borderline: keep only if they have a toddler zone). Bbox spills into neighbouring towns:
check the address. OSM is a starting point, not the truth: names and website tags go stale (a
`website` tag can 404 because the venue was renamed; e.g. Kinderlandia became "Pobawimy się?").

## 3. Find each venue's own website
- OSM `website` tag first (the script also shows `facebook=` and `operator=`: a venue with only a
  Facebook page has no usable source); else a web search with name + city + "sala zabaw"; else guess
  a domain.
- A chain branch: check the chain's own location list. If the city is not there, the OSM object is
  probably stale (closed); skip it, don't list it as "czeka na sprawdzenie".
- **Verify it is the same venue**: the address or district on the site must match the OSM location.
  A guessed domain can be an unrelated business (monsterkowo.pl is a clothing shop).
- Not a venue website (so not a source): a shopping-mall tenant page, Facebook/Instagram, Google Maps,
  review sites and aggregators. Reviews quoted on the venue's own site are opinions, not facts.
- No own website with prices → skip the venue and name it in the page's closing note
  ("czekają na sprawdzenie") and in `ROADMAP.md`, so the user can phone or check later.
- Chains (Fikołki etc.) share a price list: the same fact goes on every club, each with the chain's URL.

## 4. Read the pages
- `WebFetch` is often blocked (403) on these sites. Then use Claude in Chrome: load the tools in one
  ToolSearch, work in a new tab, read only, never click cookie banners or forms, close the tab at the end.
- `get_page_text` returns the whole page (fine for short pages). `javascript_tool` output is cut at
  ~1000 characters: filter first, e.g.
  `document.querySelector('main').innerText.split(/\n+/).filter(l=>/cennik|zł|mies|lat|godzin|skarpet/i.test(l)).join('\n')`.
  `document.body.textContent` may be refused (cookie data); use `main.innerText`. Collapsed FAQ
  answers are often in `script[type="application/ld+json"]` (FAQPage).
- Price tables rendered as cards lose their labels in text: list the leaf elements in order to see
  which label belongs to which number. If it stays ambiguous, record it with `to_confirm = true` and
  say what is ambiguous; don't pick the friendlier reading.
- Rules as PDF (e.g. IKEA Småland): WebFetch saves the PDF even when it can't read it. Copy it into
  its own scratchpad folder and extract text with pypdf installed into the scratchpad
  (`python -m pip install --target <scratchpad>/pylib pypdf`, run with `python -I`), not into `.venv`.

What to look for (keys = `VENUE_KEYS` in `ingest/curated.py`): `age_range`, `toddler_zone`,
`infant_free` (free or discounted entry for the youngest, with the conditions), `toddler_classes`,
`price_child`, `price_adult`, `opening_hours`, `socks_required`, `cafe`, `changing_table`, `parking`,
`supervision`. A venue shows as "Dla maluchów" only through `toddler_zone`, `infant_free`,
`toddler_classes` or `age_range` with `min = "infant"` / `min_years = 0`, so set those only when the
site says so. A venue for 3+ only (e.g. IKEA Småland, 3–10 years) is still listed, honestly aged.

## 5. Write the TOML
`data/curated/venues/<city>/<slug>.toml`, one file per location:
```toml
# Discovered via OpenStreetMap (node/123, © OpenStreetMap contributors, ODbL); facts from the
# venue's own pages (/, /cennik/), read YYYY-MM-DD. Written in our words.
# <anything ambiguous and why it is to_confirm>
# Not stated: <keys the site doesn't cover>
slug = "name-district"
city = "<city>"
name = "..."
official_url = "https://..."
address = "ul. ..., Poznań"
lat = 52.0
lon = 16.0
osm = "node/123"
status = "draft"

[[feature]]
key = "price_child"
value = { weekday_1h_pln = 40, weekend_1h_pln = 45 }
short = "40 zł za godzinę (pon.–czw.)"      # max 60 chars, one line on a phone
note = "Full sentence(s) in Polish, our own words, with the conditions."
source = "venue_website"                   # or "osm" (then to_confirm = true) / "own_visit"
url = "https://.../cennik/"
verified_at = YYYY-MM-DD
```
- Polish, plain, in our words (no copying of the venue's marketing). Numbers exactly as on the site.
- Hours missing on the site but present in OSM: `source = "osm"`, OSM node URL, `to_confirm = true`.
- When the site and OSM disagree, prefer the site and mention the conflict with `to_confirm = true`.
- Re-checking an existing venue: update `verified_at`, drop `to_confirm` only when the site now settles
  it, and fix the header comment.

## 6. Ship
```
python scripts/export_family.py           # data/curated -> family/src/data/family.json
.venv/Scripts/python.exe -m pytest -q     # includes the curated loader checks
ruff check . ; pyright
cd family; npm run build
```
Venues are TOML + site only (no DB table yet), so no migration and no `ingest.curated` run is
needed for them. Update `ROADMAP.md` (done items, what is left for a phone call) and the page's
closing note. Branch `feat/<city>-playgrounds`, commit, push, PR, then give the user the Vercel
preview deep link `/<city>/bawialnie/` (project `pieluchy-i-paszporty`).

## 7. Report (Polish, short)
Added venues (name, the one fact a parent cares most about), skipped ones and why, facts left
"do potwierdzenia" (worth a phone call), new OSM leads not yet checked, PR and preview links.
