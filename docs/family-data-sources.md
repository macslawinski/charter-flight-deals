# Data sources: parents' service (Product B extension)

Checked online on **2026-11-07** (web search + direct requests). **Status**: `verified` = the form and licence
below were seen by us in the source itself; `partly verified` = the source exists, but format, licence or
coverage is not fully confirmed; `to check` = not confirmed, do not build on it yet. Product:
`docs/family-product.md`. Model: `docs/family-data-model.md`.

Rules that apply to every source (same as `PLAN.md` §3 and CLAUDE.md's polite-client rules): check
`robots.txt` and terms before any automated access; low frequency; no scraping of Google Maps, Facebook, booking
or review sites; save raw responses; parsing fails loudly. Undocumented endpoints of public-sector web apps are
**not** used without checking terms first (TODO per source).

## Open data (MVP)

| Source | URL | Format | Update frequency | Licence | Status |
|---|---|---|---|---|---|
| Rejestr żłobków i klubów dziecięcych (MRiPS; kept by each gmina in the ministry's system) | https://rejestrzlobkow.mrpips.gov.pl/listaRejestrPiu/ZK (embedded in https://empatia.gov.pl/rejestr-zlobkow-i-klubow-dzieciecych) | Angular app; data from an undocumented JSON endpoint `instytucja/getListaRejestr`; **no export, no documented API** | ongoing ("na bieżąco", gminy edit it directly) | Empatia pages: CC BY-NC-ND 3.0 PL "unless stated otherwise"; register data itself: TODO (public information) | **partly verified** (2026-11-07, see notes) |
| Municipal copies of that register on dane.gov.pl (e.g. Gdynia, GZM gminy: Tychy, Zabrze…) | https://api.dane.gov.pl/1.4/datasets?q=żłobków | CSV (Gdynia), XLSX (GZM, harvested from otwartedane.metropoliagzm.pl) | varies; GZM harvested daily | CC BY 4.0 | **verified** (not for Poznań) |
| Serwis Kąpieliskowy (GIS): bathing sites, water quality | https://sk.gis.gov.pl/kapieliska/lista ; listed on dane.gov.pl as dataset 40391 | server-rendered HTML list (718 sites in 2026: season dates, water quality + sampling date, water body, classification); **behind Incapsula bot protection** (non-browser requests get a challenge page); dane.gov.pl entry has no resources | listed as daily; in season | CC0 1.0 (dane.gov.pl entry) | **partly verified** (2026-11-07): no automated import, see notes |
| NFZ night and holiday care points (NiŚOZ): map data file | https://pacjent.gov.pl/nocna-i-swiateczna-opieka-zdrowotna loads `https://pacjent.gov.pl/sites/pacjent/files/dane/Mapa-Nocna-i-swiateczna-pomoc-05.10.2026.json` | **static JSON array**, 821 points: operator name, point address (`adr_lok_*`), phone, `lat`/`lng`, hours per weekday (`harm_*`, filled for 259), notes (`uwagi`), województwo, powiat; 13 rows mention Poznań | file name carries the data date (05.10.2026); the URL changes with each update | TODO: not stated on the page; robots.txt does not block `/sites/` | **verified** form (2026-11-07); licence TODO |
| NFZ API "Umowy" (agreements, providers, service types) | https://api.nfz.gov.pl/app-umw-api/ (Swagger: `/swagger/v1.2/swagger.json`) | JSON (JSON API standard), XML with `format=xml`; `year` (and `branch` for agreements) required; NiŚOZ = products `01.0000.159–162.*` | daily (`updated-at` per agreement) | "Regulamin" linked, not read; built under the "Otwarte Dane" programme | **verified** (2026-11-07): gives NiŚOZ contract holders with seat address and phone, **not** the point address or hours |
| RSPO (Rejestr Szkół i Placówek Oświatowych): preschools | https://rspo.gov.pl/ (search app); API reported at `api-rspo.mein.gov.pl` (OSM wiki) and `api-rspo.men.gov.pl` | API hosts **do not resolve** (2026-11-07); the search app works | ongoing | TODO | **to check** |
| dane.gov.pl API (catalogue for all of the above) | https://api.dane.gov.pl/1.4/ | JSON | n/a | per dataset | **verified** |
| OpenStreetMap (Overpass) | https://overpass-api.de/ | JSON | monthly query per city (our choice) | ODbL ("© OpenStreetMap contributors") | **verified** (already used for playgrounds and hotels) |

### Notes

- **Nurseries register** (checked in a browser 2026-11-07): the current app is
  `rejestrzlobkow.mrpips.gov.pl` (domain **mrpips**; the `mpips`/`mrips` addresses in older municipal pages no
  longer resolve), embedded as an iframe in empatia.gov.pl. Search filters: województwo, powiat, gmina, type,
  "Aktywny Maluch" funding, fees, meal fees, adapted for disabled children; each row has the register number,
  type, name, location and a map link. ~7,080 rows (708 pages × 10). No export button, no robots.txt (the path
  returns the SPA's login page). The app itself re-requests its text bundle hundreds of times per page view (part
  of them answered 503), so the server is fragile. dane.gov.pl has **no national dataset**, only municipal copies
  (none for Poznań).
  **Proposal**: no automated import of the undocumented endpoint. Ask MRiPS (Departament Informatyki) for a bulk
  export or a dane.gov.pl resource; until then, Poznań nurseries by hand from the app (a few dozen rows, with the
  register number as `external_id`). TODO (U): agree, and send the request?
- **Preschools (przedszkola)** are not in the MRiPS register (it covers ages 0–3). RSPO is the national register,
  but both reported API hosts fail DNS from here (2026-11-07). TODO: find the current API address (rspo.gov.pl
  app network requests) and terms. Poznań enrolment: https://nabor.pcss.pl/poznan/ (service, not data).
- **Bathing sites** (checked 2026-11-07): the list is plain HTML with everything we need, but the site sits behind
  Incapsula bot protection, which signals that automated access is not welcome. **No scraper.** Options:
  (1) ask GIS to attach a file or API to dane.gov.pl dataset 40391 (already declared CC0, daily);
  (2) Poznań has only a handful of bathing sites: curate them by hand from the GIS page (source URL + sampling
  date as the verified date) during the season; (3) the EEA bathing water dataset (yearly classification only:
  TODO verify). Kołobrzeg publishes its own bathing sites (dane.gov.pl 2509, CSV, CC BY 4.0).
- **NiŚOZ** (checked 2026-11-07): the pacjent.gov.pl map reads one static JSON file (821 points with point
  addresses and coordinates); this is the best source, better than the NFZ Umowy API, which only names the
  contract holder and its seat (e.g. a POZ clinic in Poznań holds NiŚOZ products `01.0000.162.14/16`). The
  importer must discover the current file name from the page (it is dated) and keep the date as the source's
  "data as of". Hours are empty for most rows; the statutory hours apply (weekdays 18:00–8:00, weekends and
  holidays 24 h), shown as a rule, not as a per-point fact. NFZ line: 800 190 590.
  TODO: licence of the file (pacjent.gov.pl states none on the page; ask CeZ/NFZ or treat as public information
  with attribution).

## Poznań-specific

| Source | URL | Format | Update frequency | Licence | Status |
|---|---|---|---|---|---|
| **Playgrounds and sports places ("miejsca2021")**, layer "Place zabaw i gier" of the city map "Oświata" | https://www.poznan.pl/mim/public/plan/plan.html?mtype=education ; data: `https://www.poznan.pl/mim/plan/map_service.html?mtype=education&co=miejsca2021` | **GeoJSON** FeatureCollection, 2,335 points: 1,312 "plac gier i zabaw" + 1,023 "plac sportowy"; `plac_zabaw=tak` 1,064, `park_linowy=tak` 51; fields: name (403 named), owner/carer (`opiekun`), access (`dostep`: 1,063 unrestricted, 717 no public access…), paid (`platnosc`), `typ`, equipment flags | TODO: "2021" in the name suggests a 2021 inventory; no update date in the data | city terms (below), scope unclear | **verified** form (2026-11-07); freshness and licence TODO |
| Poznań open data platform | https://www.poznan.pl/opendata ; API docs: https://www.poznan.pl/opendata/rest/api/swagger-ui/index.html | Next.js app; 95 datasets (51 via API): JSON, CSV, GeoJSON, SHP… | per dataset (e.g. "półroczna") | per dataset (e.g. "Miasto Poznań" for Komfortki) | **verified** (2026-11-07): **no** pools, ice rinks, playgrounds, nurseries or culture venues; useful: "Wydarzenia publikowane na stronie poznan.pl" (events incl. culture), "Szlaki turystyczne", "Ścieżki dydaktyczne"; "Komfortki" = accessible toilets for disabled adults (bad CSV→JSON conversion), not baby changing |
| "Znajdź i pobierz dane" (old city API list) | https://www.poznan.pl/mim/smartcity/api-dane-przestrzenne,p,25877,38305.html | pointed to `egov.psnc.pl/node/29`, which now returns **404** | n/a | n/a | **dead** (2026-11-07) |
| City terms of reuse | https://www.poznan.pl/mim/smartcity/zasady-i-warunki-wykorzystania-danych,p,25877,38305,46818.html | text | n/a | free, no permission needed; must name the source and the time the data was created and obtained, and say if processed (Zarządzenie 15/2017/K, written for the BIP API) | **partly verified** (scope beyond BIP unclear) |
| GEOPOZ SIP (city GIS) | https://sip.poznan.pl/ ; API `http://sip.geopoz.pl/sip/api/get_api`; WMS on dane.gov.pl (4984, 9156) | WMS, html, API (undocumented here) | TODO | TODO | **to check** |
| Other city map layers | https://www.poznan.pl/mim/plan/plan.html ("Mapy" menu: Turystyka i rekreacja, Oświata, Obiekty, Środowisko…) | GeoJSON via `map_service.html?mtype=…&co=…` | TODO | city terms | **partly verified**: "Turystyka i rekreacja" has only monuments and trails; "Oświata" lists schools, not preschools or nurseries |
| City service pages: winter (ice rinks, sledding), summer, children | https://www.poznan.pl/zima/ , https://www.poznan.pl/lato/ , https://www.poznan.pl/dziecko/ | HTML (curation by hand) | seasonal | city terms | **partly verified** (pages exist; content not read) |
| POSiR (city sports and recreation: pools, rinks) | TODO: official URL | HTML (curation by hand) | TODO | TODO | **to check** |
| Poznań playgrounds and other venues | each venue's own website (as `data/curated/venues/poznan/`) | HTML (curation by hand) | 6-month re-check | facts in our own words | **verified** (in use) |

Poznań summary (2026-11-07): the only machine-readable city source for section 1 is the **playgrounds GeoJSON**.
Pools, ice rinks, sledding hills, culture venues and birthday venues need hand curation (venues' and POSiR's own
pages; OSM for discovery). The playground layer is a map-service endpoint, not a catalogued dataset.
TODO (U): use it (with the city's attribution rule and a monthly re-download), or ask the city to publish it on
the open data platform first? TODO: how current is "miejsca2021"?

## Trips ("Wyjazdy")

| Source | URL | Format | Update frequency | Licence | Status |
|---|---|---|---|---|---|
| Hotels' own websites | per hotel | HTML (curation, `curate-hotel` skill) | 12 months (fees 6) | facts in our own words | **verified** (in use) |
| Airlines' official pages | per carrier | HTML (curation) | 12 months | facts in our own words | **verified** (in use) |
| Airports' own websites (play areas, family lanes, stroller handover) | per airport | HTML (curation) | TODO | facts in our own words | **to check** |
| Children's documents, EHIC, other parent's consent | gov.pl (passports / ID cards), NFZ EKUZ pages, destination countries' official pages | HTML (curation) | yearly | public information | **to check** (URLs not collected yet) |
| Car-seat laws abroad | TODO: an official EU or per-country source | HTML (curation) | yearly | TODO | **to check** |

## Parent essentials ("Niezbędnik rodzica")

| Source | URL | Format | Update frequency | Licence | Status |
|---|---|---|---|---|---|
| Acts (Kodeks pracy, ustawa o opiece nad dziećmi do lat 3, …) | ISAP / ELI API `https://api.sejm.gov.pl/eli/` | JSON, PDF, HTML | on change | public (official texts) | **to check** |
| Benefits: leave, zasiłek opiekuńczy, 800+, Dobry Start | ZUS and gov.pl pages | HTML (curation) | yearly (indexation dates) | public information | **to check** (URLs not collected yet) |
| Vaccination schedule (Program Szczepień Ochronnych) | GIS yearly communiqué in the Health Minister's official journal | PDF (curation) | yearly | public (official text) | **to check** |
| UOKiK register of dangerous products | `http://publikacje.uokik.gov.pl/hermes3_pub/Rejestr.ashx?Typ=ProduktNiebezpieczny` (from a press article, not opened) | HTML; export or RSS unknown | ongoing | TODO | **to check** |
| EU Safety Gate (non-food dangerous products) | https://ec.europa.eu/safety-gate-alerts/ ; weekly report XML export reported by third parties at `.../api/download/weeklyReport/list/xml/en` | XML (weekly), JSON (unofficial) | weekly | free; source acknowledgement required (per third parties) | **to check** (no official API doc found) |
| Car-seat test results (e.g. ADAC Kindersitztest) | adac.de | HTML | twice a year | **copyrighted** | **to check**: TODO whether we may publish results or only link (ask ADAC / use national partners' publications?) |

## Open questions about sources

Checked 2026-11-07: URLs and formats of the nurseries register, GIS bathing sites, NiŚOZ and Poznań city data
(see the tables and notes above). Still open:

1. Nurseries register: no export; ask MRiPS for a bulk export / dane.gov.pl resource? Licence of the data.
2. GIS bathing sites: ask GIS for a file on dane.gov.pl; until then hand curation for Poznań in season.
3. NiŚOZ JSON on pacjent.gov.pl: licence / permission (the page states none).
4. Poznań playgrounds GeoJSON: use the map-service endpoint or ask the city to catalogue it; data freshness.
5. RSPO API address and terms (preschools).
6. ADAC: publish results or link only?
7. OSM ODbL: `PLAN.md` §3a assumes attribution only. If we publish a downloadable dataset mixing OSM with our
   data, the share-alike clause may apply. TODO: confirm the "produced work" reading for a static site.
