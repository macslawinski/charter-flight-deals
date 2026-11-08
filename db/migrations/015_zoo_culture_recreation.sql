-- 015_zoo_culture_recreation.sql: three more "Gdzie z dzieckiem" categories for curated venues: zoos and gardens,
-- children's theatre, and recreation (slope, summer toboggan). Additive only.

insert into venue_categories (slug, section, label_pl, stale_after_months) values
    ('zoo',       'gdzie', 'Zoo i ogrody',      6),
    ('kultura',   'gdzie', 'Teatr dla dzieci',  6),
    ('rekreacja', 'gdzie', 'Stok i atrakcje',   6)
on conflict (slug) do nothing;

alter table fact_keys drop constraint if exists fact_keys_scope_check;
alter table fact_keys add constraint fact_keys_scope_check
    check (scope = 'shared' or scope in ('sala_zabaw', 'plac_zabaw', 'nisoz', 'basen', 'lodowisko',
                                         'zoo', 'kultura', 'rekreacja'));

-- "Free for the youngest" and "season" apply beyond indoor playgrounds and rinks.
update fact_keys set scope = 'shared' where key in ('infant_free', 'season');

insert into fact_keys (key, scope, label_pl) values
    ('playground',     'zoo',       'Plac zabaw'),
    ('youngest_shows', 'kultura',   'Spektakle dla najmłodszych'),
    ('kids_rides',     'rekreacja', 'Atrakcje dla dzieci')
on conflict (key) do nothing;
