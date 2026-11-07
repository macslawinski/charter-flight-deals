# Hotel feature keys (closed list: `FEATURE_KEYS` in `ingest/curated.py`)

The site groups them as in `family/src/lib/data.ts` (`FEATURE_GROUPS`). `value` is free-form JSON but
reuse the field names below so pages and future filters read them the same way. Shapes come from the
hotels already curated (Saltic, Mitsis, Lyttos). `short` ≤ 60 chars (one line on a phone card);
`note` = full Polish sentence(s) with the conditions, in our words.

| key | what counts | value examples |
|---|---|---|
| `cot` | baby cot in the room; fee and "on request" matter. `age_band = "0-3"` if the site gives the age | `{ available = true, on_request = true, fee_pln_per_night = 60, fee_pln_per_stay = 180 }` · `{ available = true, on_request = true, free = true }` |
| `child_free_stay` | the youngest stay free / discounted. Set `age_band` to the age the site states (`0-3`, `0-2`...) | `{ free = true, sleeping_with_parents = true, max_children = 1 }` · `{ free = false, discount_pct = 50 }` |
| `baby_monitor` | elektroniczna niania lendable | `{ available = true, on_request = true }` |
| `high_chair` | krzesełka do karmienia | `{ available = true, where = "all_restaurants" }` |
| `kids_menu` | menu / buffet for children | `{ available = true, kids_buffet = true }` |
| `toddler_food` | food for babies/toddlers (słoiczki, kaszki, blended meals, "kącik malucha" in the restaurant) | `{ available = true, baby_corner = true }` |
| `bottle_warmer` | podgrzewacz / sterylizator; also a microwave or kitchen corner offered for warming children's food (say which in the note) | `{ available = true, on_request = true }` · `{ available = true, on_request = true, microwave = true }` |
| `baby_bath` | wanienka | `{ available = true, on_request = true }` |
| `changing_table` | przewijak; where | `{ available = true, where = "public_toilets" }` |
| `potty` | nocnik, nakładka, podest | `{ available = true, on_request = true, toilet_seat_adapter = true, step_stool = true }` |
| `playroom` | indoor playroom / kids club. **Min age and supervision are what a 0–3 parent needs**: record `min_age_years`, `supervised`, `with_parent_under_years` (children under N only with an adult) only if stated. Older files use `under_4_with_parent = true`; leave them, use the generic field in new ones | `{ available = true, open = "08:00", close = "20:00", break = "13:00-13:30" }` · `{ available = true, min_age_years = 4, max_age_years = 12, open = "10:00", close = "18:00", with_parent_under_years = 4 }` · `{ available = true, open = "09:00", close = "21:00", free = true, with_parent_under_years = 5 }` |
| `playground` | outdoor playground | `{ available = true, outdoor = true }` |
| `kids_animation` | animator programme. `age_band = "3+"` when it starts at 3–4 years | `{ available = true, supervised = true }` |
| `paddling_pool` | brodzik (shallow pool for toddlers) | `{ indoor = true, outdoor = true, heated = true, outdoor_seasonal = true }` |
| `kids_pool` | a pool or water play the site **describes as for children** (dziecięcy basen, splash park, kids' aquapark; not a brodzik). A general pool with a slide or a lazy river is not `kids_pool`: mention it in the header ("Also on the site, no feature key for it") | `{ available = true, count = 2, fresh_water = true, splash_park = true }` |
| `shade` | shaded play/pool areas | `{ available = true, where = "playground" }` |
| `lift` | lift (winda) to rooms | `{ available = true, where = "main_building" }` |
| `step_free_access` | no stairs / ramps with a stroller | `{ available = true }` |
| `stroller_rental` | wózek do wypożyczenia | `{ available = true, subject_to_availability = true }` |
| `beach_walk_minutes` | walking time or distance to the beach (sea, lake) | `{ minutes = 3 }` · `{ distance_m = 100 }` · `{ on_beach = true }` |
| `parking` | parking, fee, guarded or not | `{ paid = true, fee_pln_per_day = 90 }` · `{ free = true }` · two kinds: `{ paid = true, fee_pln_per_day = 50, underground_fee_pln_per_day = 70, reservable = false }` · seasonal: `{ paid = true, fee_pln_per_day_low = 35, fee_pln_per_day_high = 55, high_season = "06-01..09-30", guarded = false }` |
| `transfer` | hotel-run transfer from a station / airport | `{ from_station = true, from_airport = true, paid = true, station = "Kołobrzeg", station_km = 6, station_minutes = 15 }` |

Notes
- `free = true` for an item means the site says it is free. If no fee is mentioned, leave the fee out
  and say "Opłaty strona nie podaje" in the note; don't write `free = true`.
- `age_band` takes only `0-1`, `0-2`, `1-2`, `2-3`, `0-3`, `2+`, `3+`. For any other age the site
  states (free stay to 4, playroom from 2.5 years), leave `age_band` out and put the age in the value:
  `{ free = true, max_age_years = 4 }`, `{ available = true, min_age_years = 2.5 }`.
- One fact per `(key, age_band)`. Two different rules for the same key (e.g. free stay 0–2, half price
  2–3): two facts with different `age_band`.
- `beach_walk_minutes` is about the sea or a lake. A mountain hotel simply has none; don't put ski-lift
  distances there.
- Things a 0–3 parent would want but with no key (babysitting, ski kindergarten for 3+, a kids' pool
  only in summer outside the hotel, family rooms with a separate bedroom): list them in the header
  comment ("Also on the site, no feature key for it: ..."). Adding a key means changing
  `FEATURE_KEYS`, `FEATURE_GROUPS` and the labels in `family/src/lib/data.ts`: ask the user first.
