# Charter Flight Deals (PoC)

Tracks flight-only charter prices from Polish tour operators (PoC: r.pl) and flags flights that are
genuinely cheap, with a verifiable proof of the discount. See `CLAUDE.md` for scope and business rules.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows; on Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # fill in DATABASE_URL

pytest
python -m ingest.run --dry-run --from-file tests/fixtures/r_pl_sample.json
```

## Layout

| Path | Purpose |
|---|---|
| `ingest/` | Python ingestion package (config, HTTP client, source parsers, DB store) |
| `config/sources.toml` | Endpoint definitions per operator (no secrets) |
| `db/migrations/` | Numbered SQL migrations; never edit an applied one |
| `scripts/` | `export_deals.py` (DB → `deals.json`) and helpers |
| `web/` | Static frontend |
| `tests/` | Parser unit tests and SQL tests on synthetic data |
