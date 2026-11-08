-- 016_museums_birthdays.sql: museums with a family offer as a "Gdzie z dzieckiem" category, and two fact keys:
-- birthday parties (any curated venue) and family programmes (museums). Additive only.

insert into venue_categories (slug, section, label_pl, stale_after_months) values
    ('muzeum', 'gdzie', 'Muzea dla rodzin', 6)
on conflict (slug) do nothing;

alter table fact_keys drop constraint if exists fact_keys_scope_check;
alter table fact_keys add constraint fact_keys_scope_check
    check (scope = 'shared' or scope in ('sala_zabaw', 'plac_zabaw', 'nisoz', 'basen', 'lodowisko',
                                         'zoo', 'kultura', 'rekreacja', 'muzeum'));

insert into fact_keys (key, scope, label_pl) values
    ('birthday_parties', 'shared', 'Urodziny'),
    ('family_programme', 'muzeum', 'Zajęcia dla rodzin')
on conflict (key) do nothing;
