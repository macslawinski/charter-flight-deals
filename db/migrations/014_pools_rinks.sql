-- 014_pools_rinks.sql: two more "Gdzie z dzieckiem" categories for curated venues: pools/aquaparks and ice rinks.
-- Additive only. Curated TOMLs set `category`; `python -m ingest.curated` links each venue to it.

insert into venue_categories (slug, section, label_pl, stale_after_months) values
    ('basen',     'gdzie', 'Baseny i aquaparki', 6),
    ('lodowisko', 'gdzie', 'Lodowiska',          6)
on conflict (slug) do nothing;

-- The scope check listed the categories by hand; widen it to the new ones.
alter table fact_keys drop constraint if exists fact_keys_scope_check;
alter table fact_keys add constraint fact_keys_scope_check
    check (scope = 'shared' or scope in ('sala_zabaw', 'plac_zabaw', 'nisoz', 'basen', 'lodowisko'));

-- "Children under N only with an adult" applies to pools and rinks as much as to playgrounds.
update fact_keys set scope = 'shared' where key = 'supervision';

insert into fact_keys (key, scope, label_pl) values
    ('pools',         'basen',     'Niecki'),
    ('paddling_pool', 'basen',     'Brodzik'),
    ('swim_nappies',  'basen',     'Pieluchy do pływania'),
    ('baby_classes',  'basen',     'Zajęcia dla niemowląt'),
    ('season',        'lodowisko', 'Sezon'),
    ('skate_rental',  'lodowisko', 'Wypożyczalnia łyżew'),
    ('skating_aid',   'lodowisko', 'Pomoc do nauki jazdy'),
    ('helmet',        'lodowisko', 'Kask')
on conflict (key) do nothing;
