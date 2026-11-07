---
name: curate-hotel
description: Read a Polish hotel's own website and turn what it says about children 0-3 (cot, free stay, baby bath, high chair, playroom age, paddling pool, lift, parking, beach distance...) into a verified hotel TOML for Product B, plus car (OSRM) and train access times from the six cities, then export, test and PR. Use whenever the user says "dodaj hotel <nazwa>", "uzupełnij dane hotelu", "wyciągnij informacje z hoteli", "przerób leady z <województwa>", "kolejne hotele z listy", "sprawdź co hotel ma dla dzieci", gives a hotel URL, asks to re-verify a hotel's facts or to add access times - even if they don't say "skill" or "TOML". Works on leads from the find-hotels skill (data/curated/hotel_leads/) or on any hotel the user names. Not for Greek/foreign hotels' airport transfers, airline child rules or playgrounds (find-playgrounds).
---

# Curate a Polish hotel from its own website

Goal: one `data/curated/hotels/<place>/<slug>.toml` per hotel in which every fact a parent of a
0–3-year-old needs is **as the hotel's own website states it**, with the page URL and the date. A
wrong "free cot" or a made-up playroom age is worse than a gap: parents plan trips on this. So:
- Source = the hotel's own pages only (kids section, FAQ, regulamin, cennik/pakiety, rooms, contact /
  dojazd, PDFs it hosts). Never Booking, Tripadvisor, Google, nocowanie.pl, operators' pages, or
  reviews as facts (PLAN.md §3).
- Check `robots.txt` before reading; if it disallows the pages you need, stop for that hotel and tell
  the user (no workaround).
- Write in our own words, in Polish; numbers exactly as on the site. No copied marketing text, no photos.
- Gaps are fine and honest: list them under "Not stated" in the header.

## 0. Pick the hotels
- From leads: `data/curated/hotel_leads/<voivodeship>.toml`, entries with `status = "lead"`. If the
  user says "next N", take those with the most concrete 0–3 items in `why`, spreading across towns.
  Leads marked "Do sprawdzenia" (site unreadable for the probe) need Chrome from the start.
- Or the hotel the user names / links. If it isn't a lead yet, that's fine; no leads entry is needed.
- Already curated? Then this is a re-verification: see §6.
- Read one existing file first for the format: `data/curated/hotels/grzybowo/saltic-resort-spa-grzybowo.toml`.

## 1. Place
Hotels hang off a place (town or resort area) in `data/curated/places.toml`:
```toml
[[place]]
slug = "dzwirzyno"                       # ASCII of the town: ł→l, ż/ź→z, ó→o, ą→a, ę→e, ś→s, ć→c, ń→n
name = "Dźwirzyno"
country = "Polska"
region = "Bałtyk – Pomorze Zachodnie"    # "<landscape> – <region>", reuse an existing string when it fits
kind = "domestic"
```
Region examples to keep the style: `Bałtyk – Pomorze Zachodnie`, `Bałtyk – Pomorze`, `Mazury`,
`Tatry i Podhale`, `Beskidy`, `Karkonosze`, `Bieszczady`, `Kaszuby`. Reuse the place if the town
already exists. A hotel 2 km outside a town goes under that town only if its address says so;
otherwise the village is the place.

## 2. Read the hotel's pages
- Start from `official_url` and the lead's `kids_url`; then find: dla dzieci / rodzina, FAQ,
  regulamin (often a PDF with cot fees, child age rules, parking), cennik / pakiety rodzinne
  (free-stay ages), pokoje (lift, family rooms), SPA/basen (brodzik, kids' pool hours, min age),
  restauracja (krzesełka, menu dziecięce, kącik malucha), kontakt / dojazd (parking, transfer,
  coordinates link).
- `WebFetch` first, and ask it for **exact quotes** of numbers, ages and conditions (it paraphrases
  otherwise, and a paraphrased "do 3 lat" vs "poniżej 3 lat" matters). On 403 / empty JS pages use
  Claude in Chrome: load its tools in one ToolSearch,
  new tab, read only (never click cookie banners, forms or booking widgets), close the tab at the end.
  `get_page_text` for short pages; `javascript_tool` output is cut at ~1000 chars, so filter:
  `document.querySelector('main').innerText.split(/\n+/).filter(l=>/dzie|łóżecz|wanien|brodzik|zabaw|lat|zł|parking|wind/i.test(l)).join('\n')`.
  Collapsed FAQ answers are often in `script[type="application/ld+json"]` (FAQPage).
- **PDFs (regulamin hotelu, regulamin basenu, cennik) are worth reading**: they often hold the only
  statement that a cot or baby bath is free, the child age rules and parking. WebFetch can't read
  them. Use the bundled script (pypdf goes into the scratchpad, not `.venv`):
  ```
  python -m pip install --target <scratchpad>/pylib pypdf      # once per session
  .venv/Scripts/python.exe -I .claude/skills/curate-hotel/scripts/pdf_text.py <pdf-url> --lib <scratchpad>/pylib --save <scratchpad>/pdf/<hotel>/<name>.pdf --grep "dzie|łóżecz|wanien|niemowl|parking|zł"
  ```
  It checks robots.txt, keeps the download in its own folder, and prints matching lines with page
  numbers (cite them in the note: "regulamin hotelu, s. 2").
- **Language versions and dates**: prefer the Polish page; seasonal facts (outdoor pool, animations
  "w sezonie") must say the season if given, or say it isn't.
- **Live pages only**: use what the site shows on the day you check. Old promotions found by search
  that now 404 or are past their dates are not facts. Prefer permanent pages (dla dzieci, FAQ,
  regulamin) over seasonal packages. **Package-only facts** (a cot or free stay that appears only in
  a "pakiet rodzinny" offer) are not hotel rules: mention them in the header ("Also on the site: in
  the <name> package 2026 ...") and don't record them as features. A hotel whose only 0–3 items
  are in packages → skip it (`skip_reason`), as with Bartan (2026-11-07). A rule printed in a
  general policy box on an offer page (not tied to that package) may be recorded with `to_confirm = true`.
- **Chains**: use a chain-wide page or document only if it names this location or is hosted under
  this location's path (e.g. `/download/golebiewski-karpacz/...`). A page covering several hotels at
  once ("nasze hotele w górach") is a pointer, not a fact: confirm on the location's own page, else
  mention it in the header or record it with `to_confirm = true`.
- **Contradiction vs. different scope**: two pages giving incompatible values for the same thing
  (FAQ: cot free; cennik: 30 zł) → keep the more specific/newer one, mention the other in the note,
  `to_confirm = true`. Never pick the friendlier reading. Pages describing different things (regular
  kids' club vs. winter-holiday childcare; low vs. high season parking) are not a contradiction:
  record both in the value/note, no `to_confirm`.

## 3. Map to feature keys
Read `references/features.md` (keys, what counts, value shapes). Essentials:
- Only facts the site states. "Hotel przyjazny rodzinom" alone is not a fact.
- `age_band` where the site gives an age (free stay to 3 → `0-3`; animations from 4 → `3+`). Allowed
  bands are only `0-1`, `0-2`, `1-2`, `2-3`, `0-3`, `2+`, `3+` (`AGE_BANDS` in `ingest/curated.py`).
  Another age (free stay "do 4 lat", "do 6 lat") → no `age_band`, put `max_age_years = 4` in the
  value and the exact wording in the note.
- Playroom / kids club / animations: the minimum age and whether a parent must stay is what matters
  to a 0–3 parent. If the site doesn't say, the note says "Minimalnego wieku strona nie podaje."
- `source = "hotel_website"`, `url` = the exact page (or PDF) the fact is on, `verified_at` = today.
- A fact only implied (a photo of a brodzik, no text) → `to_confirm = true` with the reason in note.
- **Ages exactly as written**: "dzieci do lat 3 gratis" and "dzieci 4–12 lat 50%" leave the year
  between the 3rd and 4th birthday open. Don't close the gap: record the free stay with
  `age_band = "0-3"` and say in the note what the site says and that it doesn't cover age 3.

## 4. Coordinates and access
- `lat`/`lon`, first that works (comment the source):
  1. the hotel's own map link ("Wyznacz trasę", a Google Maps `@lat,lon` or `?q=lat,lon` in the HTML);
  2. the lead's OSM centre (`OpenStreetMap way/…, ODbL`);
  3. OSM Nominatim search by name + town (`https://nominatim.openstreetmap.org/search?format=json&q=<name>, <town>`,
     one request, check the address matches; ODbL). Go straight here when the hotel's map is a
     short link (goo.gl, maps.app.goo.gl) or an embedded widget without coordinates.
- **Address** (street, number, postal code) only as the hotel's own site writes it. Never fill a
  missing postal code or number from Nominatim, OSM or a guess: leave it out and add
  "# the site gives no postal code" next to `address`.
- **Access, one command per hotel or per group of hotels near the same station** (writes the blocks
  into the files; refuses a file that already has `[[access]]`):
  ```
  .venv/Scripts/python.exe .claude/skills/curate-hotel/scripts/add_access.py <hotel.toml>... --station <lat> <lon> --train-from <hotel near that station.toml>
  .venv/Scripts/python.exe .claude/skills/curate-hotel/scripts/add_access.py <hotel.toml> --station <lat> <lon> --train "Ustka" "Warszawa|352|1 przesiadka; Poznań|236|bezpośredni; ..." --train-date 2026-11-12
  ```
  Car blocks come from OSRM (same method as Saltic; `osrm_access.py <lat> <lon>` alone just prints
  them). Write the header line as `Station -> hotel: TBD`; `--station` replaces TBD with the OSRM
  distance and time, so the header never disagrees with the route. No sensible train: leave out
  `--train*` (car only).
- **Train**: nearest station with regular long-distance trains (the hotel's dojazd page often names
  it). rozklad-pkp.pl in Chrome: a Thursday ~1 week ahead, departures 05:00–14:00, the fastest
  connection with at most one change, from each of the six cities; `note` = "bezpośredni" or
  "1 przesiadka · bezpośredni X h YY min" when a slower direct train exists; `url = "https://rozklad-pkp.pl/"`.
  Train times belong to the station, so **reuse** them for every hotel near the same station
  (`--train-from` a hotel already curated there; `Grep "Access: train to <Station>" data/curated/hotels`
  finds one). Station → hotel distance/time and how to get there (taxi, the hotel's transfer)
  goes into the header comment and, if the hotel runs a transfer, into
  the `transfer` fact. No sensible train (station > ~25 km, or > 2 changes): skip train and say so
  in the header; don't invent a bus.
- Batch of hotels: do the train part once per station at the end, not per hotel.

## 5. Write the TOML
`data/curated/hotels/<place>/<slug>.toml`; slug = hotel name in ASCII, with the town if the name is
generic or a chain (`gorzelanny-dzwirzyno`). Header comment, in English:
```toml
# Facts from the hotel's own website (<domain>; robots.txt allows <what>, checked YYYY-MM-DD):
# <pages used>. Written in our words.
# Also on the site, no feature key for it: <...>.
# Not stated (so not recorded yet): <keys a 0-3 parent would ask about that the site doesn't cover>.
#
# Coordinates: <source>.
# Access (checked YYYY-MM-DD):
# - car: OSRM public router (OpenStreetMap data), city centre -> hotel, free-flow time rounded to 5 min.
# - train: rozklad-pkp.pl, <weekday date>, departures 05:00-14:00; fastest connection with at most one
#   change, to <station>. Station -> hotel: <km, minutes, how>.
slug = "..."
place = "..."
name = "..."
official_url = "https://..."
address = "ul. ..., 00-000 Miasto"
lat = 54.0
lon = 15.0
status = "draft"
```
then `[[feature]]` blocks in the order of `FEATURE_GROUPS` (Spanie, Jedzenie, Kąpiel, Zabawa, Woda,
Z wózkiem, Okolica), then car access, then train access. `status` stays `"draft"`; publishing is the
user's call. PLAN.md §4: a hotel page is meant to be published only with **≥ 8 verified facts**
(without `to_confirm`); if a hotel has fewer, say so in the report.

When the hotel came from a lead, set the lead's `status = "curated"` in `hotel_leads/<voivodeship>.toml`.
Skip a hotel (`status = "skipped"` + `skip_reason`, no hotel file) when:
- its site has nothing concrete for 0–3 any more (kids page empty or just a heading, items gone);
- its only 0–3 items are in packages (see §2);
- robots.txt disallows the pages, or the site refuses even `robots.txt` (403/blocked): no
  workaround, not even Chrome (Villa Verdi, 2026-11-07).
Mention skipped hotels in the report and ROADMAP line.

**Batches** ("kolejne 4 hotele"): read all sites first, write the TOMLs, then access per station
(one `add_access.py` call per station group), mark the leads, ROADMAP, ship once per batch.

## 6. Re-verifying an existing hotel
Re-read the same pages; update values, `verified_at`, and the header. Drop `to_confirm` only when the
site now settles it. A fact the site no longer states: remove it and mention that in the commit
message (the site would otherwise show something the hotel withdrew).

## 7. Ship
Update `ROADMAP.md` first, then one command (validate, export, ruff, pyright, pytest, site build,
Supabase upsert, commit of `ROADMAP.md` + `data/curated` + `family.json`, push; creates the branch
if needed; stops at the first failure and prints its output):
```
powershell -File .claude/skills/curate-hotel/scripts/ship.ps1 -Branch feat/<voivodeship>-hotels-<n> -Message "<Voivodeship> hotels batch <n>: A, B, C; skip D"
```
Then open the PR with the GitHub connector (and merge it when the user asked for that). The steps
by hand, if needed: `python -m ingest.curated --dry-run`, `python scripts/export_family.py`,
`pytest -q`, `ruff check .`, `pyright`, `cd family; npm run build`, `python -m ingest.curated`.
Note: the Bash/PowerShell cwd may reset to `family/`; the script resolves the repo root itself.

A `CuratedError` names the file and field (unknown key, `short` > 60 chars, city not in the six,
place missing in places.toml): fix the data, not the validator. Update `ROADMAP.md` (hotels added,
leads left, facts "do potwierdzenia"). Branch `feat/<voivodeship>-hotels` (or the current hotels
branch), commit, push, PR, then give the user the Vercel preview deep links
`/<place>/<hotel-slug>/` (project `pieluchy-i-paszporty`), and the production link after merge.

## 8. Report (Polish, short)
Per hotel: name, place, number of verified facts (and whether it reaches 8), the one or two facts
that matter most for a 0–3 parent (free stay age, cot fee, playroom from what age, brodzik), what is
"do potwierdzenia" (worth a phone or e-mail), what the site doesn't say. Then skipped hotels and why,
leads left in the voivodeship, PR and preview links.
