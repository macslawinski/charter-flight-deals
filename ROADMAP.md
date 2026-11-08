# ROADMAP: step by step (as of 2026-11-05)

Operational checklist for both products. Background and rationale: `PLAN.md` (Product B), `CLAUDE.md`
(Product A rules). Owner: **U** = user, **C** = Claude. Tick items off here when done.

## Step 1. This week: close open work (2026-11-05 … 11-08)
- [x] U: review and merge PR #7 (B redesign, Poznań playgrounds).
- [x] U: pick a look for B: **A, illustrated** (2026-11-05); `/proby/` removed.
- [x] U: merge PR #8 (`min_history_days` = 7). Migration 010 is already applied in Supabase.
- [ ] C: every morning `check-deals`: cron ran (the 00:17 UTC run may start hours late; the Itaka crawl
      runs only on that one, so a dropped run = an Itaka day missing), no parse failures, flights/day stable.

## Step 2. First real deals in A (from ~2026-11-11)
- Snapshots started 2026-11-04, so segments reach 7 days of history on **2026-11-11**.
- [ ] C: on 11-11 run `check-deals` with full verification of 3 deals; also check how many deals are real
      price drops vs. "cheaper than the segment average" (stay length, holiday dates).
- [ ] U: look at the private A site and judge whether the deals make sense to a human.
- [ ] Decide (U): if most deals are still "short stay vs. long stay" effects, consider splitting segments by
      stay length band (business-rule change, needs your go).

## Step 3. A reaches its definition of done (~2026-11-18 … 11-25)
- [ ] 2+ weeks of cron without manual fixes (from 2026-11-04 → earliest **2026-11-18**).
- [ ] C: after 2–3 weeks of data (~**2026-11-25**) tune `discount_threshold` / `window_days` /
      `baseline_stat` with `data:statistical-analysis`; you decide on changes.
- [ ] C: A1 from PLAN.md: a handful of logged manual requests to see whether r.pl / Itaka return
      infant/child prices (decides the family price, A2).
- [ ] C: donation link + ad slot placeholder on A (definition of done), still private.

## Step 4. B content, in parallel with A's waiting time
- [x] C: Saltic access times by car and train from the 6 cities (2026-11-05: car = OSRM free flow,
      train = rozklad-pkp.pl to Kołobrzeg station, ≤1 change; page shows both with source).
- [x] C: more carriers' child rules: Corendon, Aegean, Electra, Neos, Nouvelair, World2Fly, Air Cairo
      (2026-11-05, official pages only; migration 011 adds NO/2W/3E to `airlines`). Infant fee is not
      published by 6 of the 7 (only Aegean: 90% off in Family fare): the site says "check with the operator".
- [x] C: remaining Poznań playgrounds (2026-11-05): added Bawimy Jeżyce and Smålandia (IKEA, 3–10 lat).
      Kinderlandia is now "Pobawimy się?" (Galeria A2) and Monsterkowo (monsterkowo.pl is a shop): no own site
      with prices, skipped. Fikołki Karta Malucha resolved from /cennik/ (both clubs).
- [x] C: new Poznań leads from OSM checked (2026-11-05), none added: Dino Lino has only Facebook (OSM);
      Kinderplaneta's own site lists no Poznań location (probably closed, OSM node is stale);
      "Holiday Park Education & Fun" has no tags beyond the name and no site found. Use the
      `find-playgrounds` skill for other cities.
- [ ] U (phone, optional): Mlecz hours (regulamin 10–19 daily vs. OSM Fr–Su until 20) and Mlecz under-6-month
      discount (page shows −70% / −100% ambiguously); Bawimy hours (OSM only).
- [x] C: Rodos + Crete-Heraklion hotels, first batch (2026-11-05, hotel websites only, robots.txt checked):
      Mitsis Rodos Village, Mitsis Rodos Maris (Rodos), Mitsis Selection Rinela, Lyttos Beach (Heraklion);
      car time from the airport (OSRM). Skipped: Lindos Imperial and Aldemar Knossos Royal (no working
      official site found), Kipriotis Village (Kos, not our place). None states a free stay for 0–3.
- [ ] C (optional): more Greek hotels once the first batch is reviewed (more family resorts sold by r.pl/Itaka).
- [x] C: hotel leads zachodniopomorskie (2026-11-07, `find-hotels`): 24 leads (+ Saltic curated), 0 do sprawdzenia,
      15 skipped (non-hotels: SOLEO, Natura, Holiday Park, Villa Mare, DUKAT sanatorium; hotels with nothing for 0–3).
      Not covered yet: Szczecin / inland lakes (no hotel with a confirmed 0–3 offer), 82 OSM sites the probe couldn't read.
- [x] C: zachodniopomorskie hotels, first batch (2026-11-07, `curate-hotel`): Lidia Spa (Darłowo), Linea Mare
      (Pobierowo), Unitral (Mielno), Villa Hoff (Trzęsacz); car from the 6 cities, train only for Unitral
      (Koszalin, 13 km); the others' stations are 26-31 km away (Sławno, Gryfice), so no train times.
- [x] C: zachodniopomorskie hotels, second batch (2026-11-07): HAVET (Dźwirzyno), Factory Resort (Kołobrzeg),
      Hotel Wolin (Międzyzdroje, only 6 facts: below the 8-fact publishing threshold), Grand Laola (Pobierowo).
      Trains: Kołobrzeg (reused from Saltic) for HAVET and Factory, Międzyzdroje for Wolin; none for Laola.
- [x] C: zachodniopomorskie hotels, batch 3 (2026-11-07): Seaside Park (Kołobrzeg, 10 facts), Wodnik (Ustronie
      Morskie, 7), Cesarskie Ogrody (Świnoujście, 7), Amber Park (Niechorze, 6). The last three are below the
      8-fact threshold (their sites say little about 0-3). Trains: Kołobrzeg (reused), Ustronie Morskie,
      Świnoujście PKP (Świnoujście Centrum needs 2-3 changes), Trzebiatów (19 km from Niechorze).
- [x] C: zachodniopomorskie hotels, batch 4 (2026-11-07): Gorzelanny (Dźwirzyno, 8 facts), Neptuno (Dźwirzyno,
      11), Aquarius SPA (Kołobrzeg, 13), Diva SPA (Kołobrzeg, 9). Trains: Kołobrzeg (reused). Diva's regulamin
      PDF is a scan without text, not used.
- [x] C: zachodniopomorskie hotels, batch 5 (2026-11-07): Trofana (Międzyzdroje, 6 facts), Wave (Międzyzdroje, 7),
      Dworek Morski (Mielno, 9; address without house number, the site gives none), Imperiall (Sianożęty, 9).
      Trains reused: Międzyzdroje (Wolin), Koszalin (Unitral), Ustronie Morskie (Wodnik).
- [x] C: zachodniopomorskie hotels, batch 6 (2026-11-07): Blue & Green Baltic (Kołobrzeg, 10 facts), Baltic Plaza
      (Kołobrzeg, 7, all from a family package page: no permanent kids page), Zalewski (Mrzeżyno, 3), Sandra SPA
      (Pogorzelica, 4). Trains: Kołobrzeg (reused), Trzebiatów (reused from Amber Park). All 25 zachodniopomorskie
      leads are now curated; 10 of the 25 hotels have fewer than 8 facts.
- [x] C: hotel leads pomorskie (2026-11-07, `find-hotels`): 31 leads, 2 do sprawdzenia (Gwiazda Morza, Stella:
      JS sites), 7 skipped. Not covered yet: Belmar Park, Maloves, Lech Resort, Aubrecht Country (no own site found
      or unreadable), 57 OSM sites the probe couldn't read; guest houses/ośrodki left out (Sargus, Magra, Adler).
- [x] C: pomorskie hotels, batch 1 (2026-11-07): Hotel 77 (Chałupy, 9 facts), Astor (Jastrzębia Góra, 10),
      Wodnik (Łeba, 9), Royal Baltic (Ustka, 14). Trains: Chałupy, Władysławowo (for Jastrzębia Góra, 7 km), Ustka;
      none for Łeba (rozklad-pkp.pl shows no trains to Łeba on the test day; Lębork is ~28 km).
- [x] C: pomorskie hotels, batch 2 (2026-11-07): Faltom (Rumia, 11 facts), Kiston (Kistowo, 8), Villa Baltica
      (Sopot, 9), Primavera (Jastrzębia Góra, 11). Trains: Rumia, Sopot, Władysławowo (reused); none for Kiston
      (Kościerzyna ~30 km). Faltom's Klub Malucha is for 4-12 by its rules.
- [x] C: pomorskie hotels, batch 3 (2026-11-07): Best Western Jurata (8 facts), Hotel Jastarnia (6), Łeba Hotel &
      Spa (10), Nadmorski (Łeba, 6). Trains: Jurata, Jastarnia; none for Łeba. Łeba Hotel's free stay to 3 is
      for September-June only.
- [x] C: pomorskie hotels, batch 4 (2026-11-07, all Ustka): Grand Lubicz (13 facts), Lubicz (7), Jantar (8, free
      stay to 6), Hotel Ustka (6). Trains: Ustka (reused).
- [x] C: pomorskie hotels, batch 5 (2026-11-07): Forest Family Resort (Ustka, 4 facts: play areas only), Dolina
      Charlotty (Strzelinko, 14 + free stay to 3 to confirm), Notera (Charzykowy, 10), Skipper (Rewa, 6). Trains:
      Ustka, Słupsk (11 km), Chojnice (9 km), Rumia (14 km).
- [x] C: pomorskie hotels, batch 6 (2026-11-07): La Siesta (Jastrzębia Góra, 13 facts), Zamek Gniew (7), Grano Life
      (Gdańsk, 10), Platan (Gdańsk, 10). Trains: Władysławowo, Pelplin (16 km from Gniew), Gdańsk Główny. Skipped:
      Morski Widok (no baby items left on the site), Villa Verdi (site answers 403, robots.txt unreadable).
- [x] C: pomorskie hotels, batch 7 (2026-11-07): Wichrowe Wzgórze (Chmielno, 5 facts), Miłosz (Kartuzy, 6, free
      stay to 4), Pod Orłem (Kartuzy, 3: free cot, bath, WC seat), River Style (Reda, 4: two brodziki 30/50 cm).
      Trains: Kartuzy, Reda. Skipped Bartan (cot and bath only in packages).
- [x] C: pomorskie hotels, batch 8 (2026-11-07, read in Chrome): Gwiazda Morza (Władysławowo, 12 facts: free stay
      to 4, cot, baby bath, bottle warmer, playroom, brodzik, animations all year). Train: Władysławowo. Skipped
      Stella (kids page empty). All 40 pomorskie leads processed: 29 curated, 11 skipped.
- [ ] U (phone/e-mail, optional): Gwiazda Morza baby-item fees, playroom minimum age, brodzik depth.
- [x] C: hotel curation parked (2026-11-07, user); site features instead. The home page `/` is now the hotel finder (`/hotele/` redirects there; the
      airline checker moved to `/linie/`) (origin
      city + car/train + max time, region, "hotel podaje" filters, sort, state in the URL) and
      `/hotele/porownaj/?h=…` compares 2–4 hotels side by side. Foreign hotels (Rodos, Heraklion) hidden
      for now: `SHOW_FOREIGN_HOTELS` in `family/src/lib/data.ts`, data stays in the export.
- [x] U (2026-11-07): publish all hotels (58 `published`; foreign ones stay hidden by `SHOW_FOREIGN_HOTELS`).
      New hotels are written `published` from now on.
- [x] C: hotel leads warmińsko-mazurskie (2026-11-07, `find-hotels`): 24 leads, 3 do sprawdzenia (Port 110,
      Joseph Conrad: JS/TLS, read in Chrome; Mikołajki Resort Jora Wielka: own site not found); skipped
      Lake Hill Mazury, Marina Club (nothing for 0-3).
- [x] C: warmińsko-mazurskie hotels, batch 1 (2026-11-07): Robert's Port (Stare Sady, 11 facts; brodzik
      only 3+), Natura Mazur (Warchały, 11), Ognisty Ptak (Ogonki, 10), Pałac Mortęgi (7: under 8). Car
      access only; train for Mazury still to do (rozklad-pkp.pl). 20 leads left.
- [x] C: warmińsko-mazurskie hotels, batch 2 (2026-11-08): Hotel Młyn (Elbląg, 12 facts: cot 15 zł/doba,
      free stroller, brodzik), Siedlisko Morena (Jeziorowskie, 10; regulamin PDF is text-as-graphics, unread),
      Gołębiewski Mikołajki (12: brodzik 35–36°C, kids' club 9–19 with a parent), Anders (Stare Jabłonki, 10;
      Mini Klub from 4, no brodzik). Car access only; train still to do. 16 leads left.
- [ ] U (phone/e-mail, optional): cot fee and free-stay age at Morena, Gołębiewski Mikołajki and Anders
      (none of the three sites states them); Młyn free-stay age.
- [x] C: warmińsko-mazurskie hotels, batch 3 (2026-11-08): Mrągowo Resort (8 facts: cot 60 zł/pobyt, playroom
      from 1 with a parent, brodzik), Mazurski Raj (Piaski, 9: indoor brodzik with mini slides, own beach),
      Kadyny Folwark (10: under 3 free, cot paid, no lift, beach ~1 km), Dr Irena Eris Wzgórza Dylewskie
      (Wysoka Wieś, 9: free stay to 3rd birthday incl. meals, free cot, kids' pool). Skipped Warmia Park
      (robots.txt blocks AI agents incl. Claude). Car access only. 11 leads left.
- [ ] U (phone/e-mail, optional): Kadyny cot fee amount; Mazurski Raj and Mrągowo free-stay age; Mazurski Raj
      Kraina Kłobuka minimum age and whether a parent must stay.
- [x] C: warmińsko-mazurskie hotels, batch 4 (2026-11-08): Zalesie Mazury (16 facts: Baby Club 4 months–3 years
      with carers, free cot/bath/potty/monitor, brodzik 50 cm 29°C), Przystań (Olsztyn, 11 + parking to confirm:
      free cot, heated brodzik with lifeguard), Masuria (Worliny, 6: under 8, cot not stated), Kosewo 78 (6: under
      8, free cot, own beach, no pool). Car access only. 7 leads left (3 need Chrome or have no own site).
- [ ] U (phone/e-mail, optional): Przystań parking (which lot costs 40 vs. 70 zł); Masuria cot and baby items;
      Kosewo 78 high chair, baby items, free-stay age.
- [x] ~~U: decide which pomorskie hotels to publish (all are `draft`);~~ superseded above; those under 8 facts need a phone or e-mail
      round first, or stay off the site.
- [ ] U (phone/e-mail, optional): Kiston cot fee, free-stay age, brodzik; Primavera cot fee, Playland age;
      Villa Baltica free-stay age, playroom hours; Faltom whether under-4s may use Klub Malucha with a parent.
- [ ] U (phone/e-mail, optional): Hotel Jastarnia free-stay age, high chair, baby items; Nadmorski free-stay age,
      Kids Club age; BW Jurata cot fee and parking fee; Łeba Hotel free stay in July-August, cot.
- [ ] U (phone/e-mail, optional): Hotel Ustka free stay under 2 (rule or offer?), cot, baby items; Lubicz fees,
      free-stay age, pool/brodzik; Grand Lubicz free-stay age; Jantar cot fee, high chair.
- [ ] U (phone/e-mail, optional): Forest cot and baby items, free-stay age; Dolina Charlotty whether free stay to 3
      applies to all offers; Notera free-stay age, play zone rules; Skipper high chair, playroom, parking.
- [ ] U (phone/e-mail, optional): La Siesta whether the 15 zł cot fee is per night; Zamek Gniew free-stay age;
      Grano Life free-stay rule outside offers; Platan cot/playpen fee.
- [ ] U (phone/e-mail, optional): Wichrowe Wzgórze and River Style baby items and free-stay age; Miłosz whether
      the 50 zł cot fee is per night; Pod Orłem free-stay age, high chair.
- [x] ~~U: decide which zachodniopomorskie hotels to publish (all are `draft`);~~ all published 2026-11-07; those under 8 facts need a phone or
      e-mail round first, or stay off the site.
- [ ] U (phone/e-mail, optional): Zalewski and Sandra cot, high chair, free-stay age; Baltic Plaza free stay
      outside packages, beach distance.
- [ ] U (phone/e-mail, optional): Trofana free-stay age, playroom, parking; Wave cot fee, Kids Zone minimum age,
      parking fee; Dworek Morski house number, free-stay age, cot fee.
- [ ] U (phone/e-mail, optional): Neptuno free-stay age, cot fee, pool/brodzik; Diva free-stay rule, Kids Club
      minimum age, parking; Aquarius Klub Zabaw age and hours.
- [ ] U (phone/e-mail, optional): Seaside Park free-stay age and cot fee; Wodnik free-stay rule for ages 1-3;
      Cesarskie Ogrody free-stay age and cot fee; Amber Park cot, high chair, playroom hours.
- [ ] U (phone/e-mail, optional): HAVET cot fee; Factory free-stay conditions for under-3s (sentence cut off
      on the site); Hotel Wolin brodzik, playroom age, free-stay rule outside packages.
- [ ] U (phone/e-mail, optional): Unitral and Villa Hoff cot fee amounts; Unitral free-stay age for small
      children; Villa Hoff parking months/fee; whether Lidia/Unitral brodziki are heated.
- [ ] C: project skill `reverify-child-rules` so re-checks of rules are repeatable.
- [ ] C: venues migration (DB) once the venue format is stable.
- [ ] Photos (optional): only with your permission per download (e.g. Unsplash), licence noted.

## Step 5. Before going public (target ~end of November 2026)
- [ ] U: permission e-mails to Rainbow (r.pl) and Itaka (and decide whether to ask about hotel facts).
- [ ] U: repo public → C: Itaka back to 2×/day in `ingest.yml` (Actions minutes).
- [ ] U: domain(s) and analytics; hosting decision (Vercel Hobby vs. Pro/Cloudflare) before any ads.
- [ ] C: SEO basics for B (sitemap, JSON-LD), remove `noindex` only on your go.
- [ ] U: switch Vercel protection off per site when ready (both now `ssoProtection: all`).

## Extension: parents' service (B grows to ages 0–6, three sections)
Decided 2026-11-07: an extension of B (same `family/` site, same Supabase). Product: `docs/family-product.md`;
model: `docs/family-data-model.md`; sources: `docs/family-data-sources.md`.

### E0. Documentation (2026-11-07)
- [x] C: product, data model, data sources, this roadmap section; CLAUDE.md section.
- [ ] U: answer the open questions in the three docs (TODOs) and below.

### E1. MVP: open data + "Gdzie z dzieckiem" for Poznań
- [x] C: source check (2026-11-07, `docs/family-data-sources.md`): NiŚOZ = static JSON on pacjent.gov.pl (821
      points, best source); Poznań playgrounds = city map GeoJSON (2,335 places); nurseries register = app
      without export (`rejestrzlobkow.mrpips.gov.pl`); GIS bathing sites = HTML behind bot protection (no scraper);
      Poznań open data platform has no pools, rinks or culture venues; RSPO API host not resolving.
- [ ] U: decide on the source questions at the end of `docs/family-data-sources.md` (requests to MRiPS / GIS /
      city of Poznań; licences of the NiŚOZ file and the playground GeoJSON).
- [x] U (2026-11-07): NiŚOZ file = public information; Poznań playground GeoJSON used; data requests to
      MRiPS / GIS / the city later.
- [x] C: migration 012 (`venues`, `venue_facts`, `data_sources`, `import_runs`, …) and importers
      `python -m ingest.opendata --source nfz_nisoz|poznan_place_zabaw` (2026-11-07): 551 NiŚOZ points
      nationwide (7 in Poznań), 804 public Poznań playgrounds; re-runs are idempotent, tested.
- [x] C: run both imports into Supabase (2026-11-07). Closed playgrounds ("nieczynne") and game-table-only
      points (ping-pong, chess, table football) are filtered out: 727 playgrounds left.
- [x] C: `python scripts/export_venues.py --city poznan` (DB → committed `family/src/data/map/poznan.json`)
      and the map page `/poznan/` (Leaflet + OSM tiles; playgrounds, NiŚOZ, curated bawialnie; filters;
      source and date under every fact). Re-run the export after each import.
- [x] C: Poznań playground TOMLs on `venues` / `venue_facts` (2026-11-07, migration 013, source `curated`,
      `python -m ingest.curated` upserts them; all 7 published). The map `/poznan/` reads them from the
      export only; `/poznan/bawialnie/` still reads `family.json`. Map equipment chips (tyrolka, linowe,
      pumptrack, naturalny) now OR inside the group (they were AND-ed: 3 chips gave 0 playgrounds).
- [ ] C: nurseries and bathing sites: by hand for Poznań until MRiPS / GIS provide files (no scraper).
- [ ] C: scheduling in Actions within the minutes budget (open data changes slowly: weekly or monthly).
- [ ] C: Poznań section 1 curation: pools/aquaparks, ice rinks, sledding, zoo/farms, rope parks, culture,
      birthday venues (venues' own sites, OSM for discovery).
- [ ] C: site: map + shared filters, category pages, source + verified date on every fact (frontend-design).
- [ ] U: route and home page decision (today `/` is the hotel finder).

### E2. Hotels ("Wyjazdy")
- [ ] Hotels in Poland under "Wyjazdy" (existing curated data; foreign hotels stay hidden). Mostly UI and
      shared fact keys; the curation backlog stays in Step 4.

### E3. Airlines and airports
- [ ] Airline child rules under "Wyjazdy" (existing `/linie/`); airport family facts (play areas, family lanes,
      stroller handover); children's documents, EHIC, car-seat laws abroad.
- [ ] "Niezbędnik rodzica" topics (benefits, deadlines, vaccinations, recalls, car-seat tests): TODO: which
      stage? The brief lists them in the product but not in a stage.

### Backlog (needs your go)
- E-mail agent that asks hotels/venues for missing data and updates facts from replies (`venue_submitted` /
  `hotel_written` sources; GDPR and consent to check).
- Monetization: donations, affiliate links (`PLAN.md` Phase 2; Vercel Hobby terms).
- User accounts, comments, ratings: out of scope (conflicts with "just facts").

## Later (on hold, needs your go)
- Affiliates and ads (Phase 2), family deal alerts (changes A's "no notifications" scope).
- Parent surveys and the B2B badge (Phase 3).
- A "flying with kids" toggle in A (PLAN.md A3–A4).
