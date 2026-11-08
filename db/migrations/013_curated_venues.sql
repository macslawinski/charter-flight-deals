-- 013_curated_venues.sql: hand-curated venues (data/curated/venues/<city>/*.toml) move onto venues / venue_facts.
-- `python -m ingest.curated` upserts them under source 'curated' with external_id = slug; status comes from
-- the file (a human publishes). Additive only.

-- A curated "source" has no single URL: every fact carries its own (the venue's page) and the location
-- points to its OpenStreetMap object.
alter table data_sources alter column url drop not null;

insert into data_sources (id, name_pl, url, kind, licence, attribution_pl, auto_publish) values
    ('curated', 'Sprawdzone ręcznie na stronach samych miejsc', null, 'website', null,
     'Fakty ze stron samych miejsc, z linkiem i datą sprawdzenia przy każdym', false)
on conflict (id) do nothing;

-- Indoor playground ("sala_zabaw") facts kept under the keys the curated files already use. `price_child` stays
-- separate from the shared `price` until a second category needs a cross-category price filter.
insert into fact_keys (key, scope, label_pl) values
    ('toddler_zone',    'sala_zabaw', 'Strefa malucha'),
    ('infant_free',     'sala_zabaw', 'Najmłodsi'),
    ('toddler_classes', 'sala_zabaw', 'Zajęcia dla maluchów'),
    ('price_child',     'sala_zabaw', 'Cena za dziecko'),
    ('price_adult',     'sala_zabaw', 'Cena za dorosłego'),
    ('cafe',            'sala_zabaw', 'Kawiarnia'),
    ('socks_required',  'sala_zabaw', 'Skarpetki'),
    ('supervision',     'sala_zabaw', 'Opieka')
on conflict (key) do nothing;
