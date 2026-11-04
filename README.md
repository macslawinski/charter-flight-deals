# Charter Flight Deals (PoC)

Darmowa aplikacja, która śledzi ceny **samych lotów czarterowych** (bez hoteli i pakietów) polskich
biur podróży i oznacza loty *naprawdę* tanie — z weryfikowalnym dowodem rabatu.
Obecny etap: **proof of concept z jednym operatorem — r.pl (Rainbow Tours)**.
Zakres i reguły biznesowe: `CLAUDE.md`.

## Jak to działa

1. **Pobieranie** (`ingest/`) — co kilka godzin skrypt odpytuje API czarterów r.pl:
   lista kierunków → wyloty dla każdego kierunku → powroty (w paczkach po 200 pakietów).
   Pełny przebieg to ok. 90 zapytań z losową przerwą 3–8 s; przy 403 przebieg się zatrzymuje.
2. **Zapis** (Postgres / Supabase) — surowa odpowiedź trafia do `raw_fetches` (14 dni),
   loty do `flights`, a dzienna cena do `price_snapshots` (cena za osobę w PLN, tam i z powrotem).
3. **Transformacja** (SQL) — średnia krocząca z 30 dni dla segmentu (lotnisko wylotu + cel +
   miesiąc wylotu), filtr sensownej długości pobytu, reguła okazji: cena ≤ 85% średniej.
4. **Strona** (`web/`) — statyczna lista okazji z dowodem, np.
   `1 249 zł ≤ 0,85 × 1 612 zł = 1 370 zł → 22,5% poniżej średniej (14 lotów, 312 obserwacji)`.

Pierwsze okazje pojawią się dopiero po zebraniu historii cen (zimny start jest zamierzony).

## Szybki start

```powershell
python -m venv .venv
.venv\Scripts\activate              # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
copy .env.example .env              # uzupełnij DATABASE_URL

pytest
python -m ingest.run --dry-run --from-file tests/fixtures/r_pl_sample.json
```

### Lokalna baza (Postgres 18)

```powershell
pg_ctl start -D "$env:USERPROFILE\scoop\apps\postgresql\current\data" -w
python scripts/db_local.py          # tworzy od nowa bazę cfd_local i wgrywa migracje
python -m ingest.run --from-file tests/fixtures/r_pl_sample.json `
    --database-url postgresql://postgres@localhost:5432/cfd_local
```

Testy bazy (`tests/test_store.py`) używają `cfd_local` i są pomijane, gdy Postgres nie działa.

## Uruchamianie pobierania

| Polecenie | Co robi |
|---|---|
| `python -m ingest.run --dry-run` | pobiera dane z r.pl, parsuje, niczego nie zapisuje |
| `python -m ingest.run --dry-run --save-raw data/r_pl_raw.json` | j.w. + zapisuje surowy plik |
| `python -m ingest.run` | pobiera i zapisuje do bazy z `DATABASE_URL` |
| `python -m ingest.run --from-file plik.json` | zapisuje do bazy dane z zapisanego pliku |

Kody wyjścia: `0` OK, `1` błąd parsowania (surowe dane zostają w bazie), `2` brak konfiguracji,
`3` osiągnięty limit zapytań (zapisane tylko kompletne kierunki).

## Struktura repo

| Ścieżka | Zawartość |
|---|---|
| `ingest/` | pakiet Pythona: konfiguracja, klient HTTP, parsery źródeł, zapis do bazy |
| `ingest/sources/r_pl.py` | pobieranie i mapowanie API r.pl → `FlightOffer` |
| `config/sources.toml` | definicje endpointów (bez sekretów) |
| `db/migrations/` | numerowane migracje SQL — zastosowanej migracji się nie edytuje |
| `scripts/` | `export_deals.py` (baza → `deals.json`), `db_local.py`, `json_shape.py` |
| `web/` | statyczny frontend (Vercel) |
| `tests/` | testy parsera, zapisu do bazy i transformacji SQL |

## Praca z gitem

Każda zmiana powstaje na osobnej gałęzi (`feat/...`, `fix/...`). Przed scaleniem do `main`
muszą przejść `ruff check .`, `pyright` i `pytest`.

## Uwagi prawne

API r.pl jest nieudokumentowane i używane tylko na potrzeby PoC. Przed publicznym startem
planujemy poprosić Rainbow o zgodę lub oficjalny feed. Skrypt przedstawia się własnym
User-Agentem i nie obchodzi żadnych zabezpieczeń.
