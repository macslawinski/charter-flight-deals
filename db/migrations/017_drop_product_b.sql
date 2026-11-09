-- 017_drop_product_b.sql: Product B ("Pieluchy i paszporty") moved to its own repo and Supabase
-- project on 2026-11-09 (docs/repo-split-plan.md). Drop B's tables and types (009, 012-016) and the
-- columns 009 added to A's tables for B; A uses none of them. Backup taken before applying:
-- pg_dump of the 13 tables, kept outside the repo. Charter carriers seeded in 011 stay in `airlines`.

drop table if exists venue_facts, venue_category_links, venues, import_runs, data_sources, fact_keys,
    venue_categories, hotel_access, hotel_child_features, hotels, places, child_rules, airports;

drop type if exists fact_source;
drop type if exists age_band;

alter table airlines drop column if exists website, drop column if exists family_rules_url;
alter table destinations drop column if exists slug;  -- also drops destinations_slug_key

-- Raw responses of B's open-data importers.
delete from raw_fetches where operator in ('nfz_nisoz', 'poznan_place_zabaw');
