-- 009_family_core.sql: shared data core for Product B (family travel, ages 0-3), see PLAN.md §2.
-- Additive only: Product A's tables gain nullable/generated columns, nothing is dropped or rewritten.
-- Curated rows (places, hotels, child rules) are loaded from data/curated/*.toml by `python -m ingest.curated`.

-- Shared slugs: derived from the Polish display name ('Kreta - Heraklion' -> 'kreta-heraklion').
alter table destinations add column slug text generated always as (
    trim(both '-' from regexp_replace(
        translate(lower(name), 'ąćęłńóśźż', 'acelnoszz'), '[^a-z0-9]+', '-', 'g'))
) stored;
alter table destinations add constraint destinations_slug_key unique (slug);

-- Carriers: `airlines` (005) is the carriers table; family-rule pages link to the carrier's own page.
alter table airlines add column website text,
                     add column family_rules_url text;

-- Polish departure airports (replaces the hardcoded ORIGINS map in scripts/export_deals.py later).
create table airports (
    iata     char(3) primary key,
    name     text not null,
    city     text not null,
    country  text not null default 'Polska'
);
insert into airports (iata, name, city) values
    ('BZG', 'Bydgoszcz', 'Bydgoszcz'), ('GDN', 'Gdańsk', 'Gdańsk'), ('KRK', 'Kraków', 'Kraków'),
    ('KTW', 'Katowice', 'Katowice'), ('LCJ', 'Łódź', 'Łódź'), ('LUZ', 'Lublin', 'Lublin'),
    ('POZ', 'Poznań', 'Poznań'), ('RZE', 'Rzeszów', 'Rzeszów'), ('SZZ', 'Szczecin', 'Szczecin'),
    ('WAW', 'Warszawa-Chopin', 'Warszawa'), ('WMI', 'Warszawa-Modlin', 'Warszawa'),
    ('WRO', 'Wrocław', 'Wrocław'), ('OSZ', 'Koszalin', 'Koszalin'), ('SZY', 'Olsztyn-Mazury', 'Olsztyn');

-- Age bands: airline rules split at 2 years (infant '0-2', child '2+'), hotel facilities at 1 and 3.
create type age_band as enum ('0-1', '0-2', '1-2', '2-3', '0-3', '2+', '3+');

-- Where a fact comes from, best first. review_hint is never shown as a verified fact.
create type fact_source as enum ('hotel_written', 'carrier_official', 'hotel_website', 'own_visit',
                                 'operator_page', 'review_hint');

-- Airline rules for children; one row per carrier x rule x age band. `age_band` null = all children.
create table child_rules (
    id            bigint generated always as identity primary key,
    carrier_iata  text not null references airlines (iata),
    rule_key      text not null check (rule_key ~ '^[a-z_]+$'),
    age_band      age_band,
    value         jsonb not null,
    summary_pl    text not null,
    source_type   fact_source not null,
    source_url    text not null check (source_url ~ '^https://'),
    verified_at   date not null,
    to_confirm    boolean not null default false,
    unique nulls not distinct (carrier_iata, rule_key, age_band)
);

-- B places: abroad (reached by flight, linked to A's destinations) or domestic (car/train, no IATA).
create table places (
    slug       text primary key check (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    name       text not null,
    country    text not null,
    region     text,
    kind       text not null check (kind in ('flight', 'domestic')),
    dest_iata  char(3) references destinations (iata),
    check ((kind = 'flight') = (dest_iata is not null))
);

create table hotels (
    id            bigint generated always as identity primary key,
    slug          text not null unique check (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    place_slug    text not null references places (slug),
    name          text not null,
    official_url  text check (official_url ~ '^https://'),
    address       text,
    lat           numeric(9, 6),
    lon           numeric(9, 6),
    status        text not null default 'draft' check (status in ('draft', 'published', 'retired'))
);

-- One fact about a hotel for small children, e.g. cot / fee / heated paddling pool.
create table hotel_child_features (
    hotel_id     bigint not null references hotels (id) on delete cascade,
    feature_key  text not null check (feature_key ~ '^[a-z_]+$'),
    age_band     age_band,
    value        jsonb not null,
    note_pl      text,
    source_type  fact_source not null,
    source_url   text check (source_url ~ '^https://'),
    verified_at  date not null,
    to_confirm   boolean not null default false,   -- sources disagree or unclear: show as "to confirm"
    unique nulls not distinct (hotel_id, feature_key, age_band)
);

-- How to get there: airport transfer abroad, car/train from Polish cities for domestic places.
create table hotel_access (
    hotel_id     bigint not null references hotels (id) on delete cascade,
    from_kind    text not null check (from_kind in ('airport', 'city')),
    from_code    text not null,                      -- 'RHO' or 'Warszawa'
    mode         text not null check (mode in ('transfer', 'car', 'train', 'bus')),
    minutes      integer not null check (minutes > 0),
    note_pl      text,
    source_url   text check (source_url ~ '^https://'),
    verified_at  date not null,
    primary key (hotel_id, from_kind, from_code, mode)
);

-- Same access model as the rest of the schema: RLS on, no policies; only the ingest/export role reads.
alter table airports             enable row level security;
alter table child_rules          enable row level security;
alter table places               enable row level security;
alter table hotels               enable row level security;
alter table hotel_child_features enable row level security;
alter table hotel_access         enable row level security;
