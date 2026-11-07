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
| Rejestr żłobków i klubów dziecięcych (MRiPS; kept by each gmina in the ministry's system) | Ministry system "Empatia" (address TODO, see notes) | web search per gmina; export unknown | ongoing ("na bieżąco", gminy edit it directly) | TODO | **to check** |
| Municipal copies of that register on dane.gov.pl (e.g. Gdynia, GZM gminy: Tychy, Zabrze…) | https://api.dane.gov.pl/1.4/datasets?q=żłobków | CSV (Gdynia), XLSX (GZM, harvested from otwartedane.metropoliagzm.pl) | varies; GZM harvested daily | CC BY 4.0 | **verified** (not for Poznań) |
| Serwis Kąpieliskowy (GIS): bathing sites, water quality | https://sk.gis.gov.pl/ ; listed on dane.gov.pl as dataset 40391 | dane.gov.pl entry has **no resources** (link only); the site is a JS app, no documented export or API | listed as daily; in season | CC0 1.0 (dane.gov.pl entry) | **partly verified** |
| NFZ night and holiday care points (NiŚOZ): map | https://pacjent.gov.pl/nocna-i-swiateczna-opieka-zdrowotna | HTML map; export unknown | TODO | TODO | **partly verified** |
| NFZ API "Umowy" (agreements, providers, service types) | https://api.nfz.gov.pl/app-umw-api/ | JSON (JSON API standard), XML with `format=xml`; Swagger UI | TODO (`/available-years` suggests yearly plans + changes) | "Regulamin" linked, not read; built under the "Otwarte Dane" programme | **partly verified** |
| dane.gov.pl API (catalogue for all of the above) | https://api.dane.gov.pl/1.4/ | JSON | n/a | per dataset | **verified** |
| OpenStreetMap (Overpass) | https://overpass-api.de/ | JSON | monthly query per city (our choice) | ODbL ("© OpenStreetMap contributors") | **verified** (already used for playgrounds and hotels) |

### Notes

- **Nurseries register**: dane.gov.pl has **no national dataset**; only municipal copies (48 hits for "żłobków",
  none from Poznań; UM Poznania's 25 datasets on dane.gov.pl are all administrative). The register is kept by
  gminy in the ministry's system; municipal pages point to `empatia.mpips.gov.pl` / `empatia.gov.pl` and older
  pages to `rejestrzlobkow.mpips.gov.pl`. Our requests to `rejestrzlobkow.mrips.gov.pl` and
  `empatia.mpips.gov.pl` failed (DNS), so the current address is **not confirmed**. Per municipal pages it holds
  contact data, fees, number of places, enrolled children and opening hours.
  TODO: find the current URL; is there a download or API? licence? Ask MRiPS (Departament Informatyki) for a
  bulk export if there is none.
- **Preschools (przedszkola)** are not in the MRiPS register (it covers ages 0–3). Candidate: RSPO (Rejestr Szkół
  i Placówek Oświatowych, MEN), which has a public API (`api-rspo.men.gov.pl`); our request failed (DNS), so
  **to check**. Poznań enrolment: https://nabor.pcss.pl/poznan/ (service, not data).
- **Bathing sites**: no API found. Options, in order: (1) ask GIS whether the dane.gov.pl entry can get a file or
  API resource (it is already declared as open data, CC0, daily); (2) the EEA bathing water dataset (EU
  directive reporting, yearly classification only, not current results: TODO verify); (3) the web app's own
  requests only after checking its terms. Kołobrzeg publishes its own bathing sites (dane.gov.pl 2509, CSV,
  CC BY 4.0), which shows the per-city path exists elsewhere.
- **NiŚOZ**: lists are per NFZ regional branch (for Poznań: Wielkopolski OW NFZ) and on the pacjent.gov.pl map.
  TODO: does `/service-types` in the Umowy API have a NiŚOZ code so `/agreements` can be filtered by it, and do
  agreements include the point's address and hours? NiŚOZ hours are statutory (weekdays 18:00–8:00, weekends and
  holidays 24 h); the NFZ phone line is 800 190 590.

## Poznań-specific

| Source | URL | Format | Update frequency | Licence | Status |
|---|---|---|---|---|---|
| Poznań open data platform | https://www.poznan.pl/opendata | JS app; dataset list not readable without a browser | TODO | see terms below | **to check** |
| "Znajdź i pobierz dane" (city API list) | https://www.poznan.pl/mim/smartcity/api-dane-przestrzenne,p,25877,38305.html | REST/webservices documented at `egov.psnc.pl/node/29` (city objects "obiekty", events "wydarzenia", tourism, school catchment areas…) | varies; some services marked as last updated 2014 | see terms below | **partly verified** |
| City terms of reuse | https://www.poznan.pl/mim/smartcity/zasady-i-warunki-wykorzystania-danych,p,25877,38305,46818.html | text | n/a | free, no permission needed; must name the source and the time the data was created and obtained, and say if processed (Zarządzenie 15/2017/K, written for the BIP API) | **partly verified** (scope beyond BIP unclear) |
| GEOPOZ SIP (city GIS) | https://sip.poznan.pl/ ; API `http://sip.geopoz.pl/sip/api/get_api`; WMS on dane.gov.pl (4984, 9156) | WMS, html, API (undocumented here) | TODO | TODO | **to check** |
| City map layers (e.g. public toilets) | https://www.poznan.pl/mim/plan/plan.html | map viewer (WMS/GeoRSS layers) | TODO | TODO | **to check** |
| City service pages: winter (ice rinks, sledding), summer, children | https://www.poznan.pl/zima/ , https://www.poznan.pl/lato/ , https://www.poznan.pl/dziecko/ | HTML (curation by hand) | seasonal | city terms | **partly verified** (pages exist; content not read) |
| POSiR (city sports and recreation: pools, rinks) | TODO: official URL | HTML (curation by hand) | TODO | TODO | **to check** |
| Poznań playgrounds and other venues | each venue's own website (as `data/curated/venues/poznan/`) | HTML (curation by hand) | 6-month re-check | facts in our own words | **verified** (in use) |

TODO: is the city's "obiekty" webservice usable for pools, ice rinks, playgrounds or culture venues (which
object classes exist)? Needs a look at `egov.psnc.pl/node/29` in a browser.

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

1. Nurseries register: current URL, export/API, licence (see notes).
2. GIS bathing sites: ask GIS for a file/API resource on dane.gov.pl, or use the EEA yearly data only?
3. NiŚOZ: NFZ Umowy API usable (NiŚOZ code, addresses)? If not, per-branch lists by hand.
4. Poznań: which city services list pools, rinks, playgrounds, culture venues? (browser check of the open data
   platform and `egov.psnc.pl/node/29`).
5. ADAC: publish results or link only?
6. OSM ODbL: `PLAN.md` §3a assumes attribution only. If we publish a downloadable dataset mixing OSM with our
   data, the share-alike clause may apply. TODO: confirm the "produced work" reading for a static site.
