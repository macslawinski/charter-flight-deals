---
name: apply-migration
description: Safely write and apply a Postgres schema/SQL change for this project - new numbered file in db/migrations/, test locally or in a rolled-back transaction, apply to Supabase via the connector, run advisors, and confirm repo and DB are in sync. Use for any change to tables, views, SQL functions, indexes, seeds or RLS, and whenever the user says "dodaj kolumnę", "zmień schemat", "zrób migrację", "wrzuć to do bazy", "zaktualizuj transform", even if they don't say "migration".
---

# Apply a migration

The repo's `db/migrations/` is the source of truth; the Supabase project must always equal
"all files applied in order". Drift makes the transform untestable and future migrations unsafe.

## 1. Look before changing
- Supabase connector: `list_migrations` and `list_tables` (schema `public`). Compare with the files in
  `db/migrations/`. If they disagree, stop and tell the user what differs — don't paper over drift.
- Find the next number: highest `NNN_` prefix + 1.

## 2. Write the file
- `db/migrations/NNN_short_name.sql`. **Never edit a file that is already applied** (it is in
  `list_migrations`): the DB would not re-run it, so repo and DB would silently diverge. Fix forward
  with a new file.
- Every new table in `public`: `alter table ... enable row level security;` with no policies.
  The browser never talks to the DB (frontend reads `deals.json`); RLS-without-policies blocks the
  public `anon` key while the ingest/export role (`postgres` via `DATABASE_URL`) bypasses it.
- Core logic stays parameterized by `as_of` (no `now()` / `current_date` inside transform functions)
  and reads thresholds from `pipeline_params` / reference tables — that is what makes it testable.
- Prefer idempotent-safe DDL where cheap (`create or replace view/function`).

## 3. Test before applying
Pick the first that is available:
1. Local: Supabase CLI (`supabase db reset` applies all migrations to the local stack) or a local
   Postgres (`psql -v ON_ERROR_STOP=1 -f` each file in order on a scratch DB). Then run the SQL tests.
2. No local DB: on the remote project run the migration body wrapped in `begin; ... rollback;` with
   `execute_sql`, plus a couple of checking selects inside the same transaction. Nothing persists.

For transform changes, include the synthetic cases from CLAUDE.md (planted deal found, 3-day long-haul
dropped, too-few-flights segment yields nothing, 10% drop not flagged).

## 4. Apply
- **Ask the user before applying to the remote project** if the migration drops or rewrites data
  (drop table/column, destructive update, type change with cast). Additive changes may go ahead.
- `apply_migration` with `name` = file name without `.sql`, query = exact file content (byte-for-byte,
  so the DB's record matches the repo).

## 5. Verify
- `list_migrations` shows the new entry; `list_tables` shows the expected structure.
- `get_advisors` for `security` and `performance`; fix findings in a follow-up migration or explain why
  they don't apply.
- Quick sanity select with `LIMIT` (never `select *` on `raw_fetches` / `price_snapshots`).

## 6. Report (Polish, short)
File name, what changed, how it was tested, advisor results, anything the user must decide.
Commit the migration file together with any code that depends on it.
