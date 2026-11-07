-- 012_venues_core.sql: places for the parents' service (Product B extension), see docs/family-data-model.md.
-- Additive only. A place ("venue") is a thin identity row; everything about it is a fact with its own source
-- and verified date. Open-data importers (`python -m ingest.opendata`) upsert on (source_id, external_id).

-- New fact origins. Not used inside this migration (a new enum value can't be used in the same transaction).
alter type fact_source add value if not exists 'venue_website';
alter type fact_source add value if not exists 'venue_submitted';
alter type fact_source add value if not exists 'open_data';
alter type fact_source add value if not exists 'osm';

-- Categories and the section they belong to; staleness lives here, not in code.
create table venue_categories (
    slug                text primary key check (slug ~ '^[a-z_]+$'),
    section             text not null check (section in ('gdzie', 'wyjazdy', 'niezbednik')),
    label_pl            text not null,
    stale_after_months  integer not null check (stale_after_months > 0)
);
insert into venue_categories (slug, section, label_pl, stale_after_months) values
    ('sala_zabaw', 'gdzie',      'Sale zabaw',                          6),
    ('plac_zabaw', 'gdzie',      'Place zabaw',                         12),
    ('nisoz',      'niezbednik', 'Nocna i świąteczna opieka zdrowotna', 6);

-- Where records come from. attribution_pl is shown on every page that uses the source.
-- auto_publish: official sources publish on import; others (e.g. OSM discovery) wait for a human.
create table data_sources (
    id              text primary key check (id ~ '^[a-z0-9_]+$'),
    name_pl         text not null,
    url             text not null check (url ~ '^https://'),
    kind            text not null check (kind in ('open_data', 'osm', 'website', 'venue_submitted')),
    licence         text,
    attribution_pl  text,
    auto_publish    boolean not null default false
);
insert into data_sources (id, name_pl, url, kind, licence, attribution_pl, auto_publish) values
    ('nfz_nisoz',
     'Mapa punktów nocnej i świątecznej opieki zdrowotnej (pacjent.gov.pl)',
     'https://pacjent.gov.pl/nocna-i-swiateczna-opieka-zdrowotna', 'open_data',
     'informacja publiczna',
     'Źródło: pacjent.gov.pl (Narodowy Fundusz Zdrowia, Ministerstwo Zdrowia)', true),
    ('poznan_place_zabaw',
     'Place gier i zabaw, Plan Poznania (warstwa Oświata)',
     'https://www.poznan.pl/mim/public/plan/plan.html?mtype=education', 'open_data',
     'Miasto Poznań: ponowne wykorzystanie z podaniem źródła i daty (Zarządzenie 15/2017/K)',
     'Źródło: Miasto Poznań, poznan.pl; dane przetworzone (wybrane place ogólnodostępne)', true);

-- One row per import run, for monitoring and for the "data as of" date shown to users.
create table import_runs (
    id            bigint generated always as identity primary key,
    source_id     text not null references data_sources (id),
    started_at    timestamptz not null,
    finished_at   timestamptz,
    status        text not null check (status in ('ok', 'failed')),
    data_url      text,
    data_as_of    date,                       -- the source's own date, when it gives one
    raw_fetch_id  bigint,                     -- raw_fetches.id (no FK: raw rows are pruned after 14 days)
    n_seen        integer, n_inserted integer, n_updated integer, n_retired integer,
    error         text
);
create index import_runs_source_idx on import_runs (source_id, started_at desc);

-- A place on the map. Imported rows are keyed by (source_id, external_id); curated ones get a slug.
create table venues (
    id                    bigint generated always as identity primary key,
    source_id             text not null references data_sources (id),
    external_id           text not null,
    slug                  text unique check (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    name                  text not null,
    locality              text not null,       -- 'Poznań'
    voivodeship           text,
    address               text,
    lat                   numeric(9, 6),
    lon                   numeric(9, 6),
    official_url          text check (official_url ~ '^https?://'),
    location_source_url   text not null check (location_source_url ~ '^https://'),
    location_verified_at  date not null,
    first_seen_at         date not null,
    last_seen_at          date not null,
    status                text not null default 'draft' check (status in ('draft', 'published', 'retired')),
    unique (source_id, external_id),
    check ((lat is null) = (lon is null))
);
create index venues_locality_idx on venues (locality);

create table venue_category_links (
    venue_id  bigint not null references venues (id) on delete cascade,
    category  text not null references venue_categories (slug),
    primary key (venue_id, category)
);
create index venue_category_links_category_idx on venue_category_links (category);

-- Vocabulary of facts: 'shared' keys are filterable across categories; others extend one category.
create table fact_keys (
    key       text primary key check (key ~ '^[a-z_]+$'),
    scope     text not null check (scope = 'shared' or scope in ('sala_zabaw', 'plac_zabaw', 'nisoz')),
    label_pl  text not null
);
insert into fact_keys (key, scope, label_pl) values
    ('age_range',       'shared',     'Wiek dziecka'),
    ('stroller_access', 'shared',     'Z wózkiem'),
    ('changing_table',  'shared',     'Przewijak'),
    ('parking',         'shared',     'Parking'),
    ('toilet',          'shared',     'Toaleta'),
    ('price',           'shared',     'Cena'),
    ('opening_hours',   'shared',     'Godziny otwarcia'),
    ('phone',           'shared',     'Telefon'),
    ('notes',           'shared',     'Uwagi'),
    ('service_mode',    'nisoz',      'Rodzaj świadczenia'),
    ('access',          'plac_zabaw', 'Dostęp'),
    ('managed_by',      'plac_zabaw', 'Zarządca'),
    ('equipment',       'plac_zabaw', 'Wyposażenie');

-- One fact about a venue: same columns as hotel_child_features, plus a numeric age range in months.
create table venue_facts (
    venue_id        bigint not null references venues (id) on delete cascade,
    fact_key        text not null references fact_keys (key),
    age_min_months  integer check (age_min_months >= 0),
    age_max_months  integer,
    value           jsonb not null,
    short_pl        text not null check (char_length(short_pl) between 1 and 80),
    note_pl         text,
    source_type     fact_source not null,
    source_url      text check (source_url ~ '^https://'),
    verified_at     date not null,
    to_confirm      boolean not null default false,
    -- only a venue's own submission may lack a URL (compared as text: the value is new in this file)
    check (source_url is not null or source_type::text = 'venue_submitted'),
    check (age_max_months is null or age_min_months is null or age_min_months <= age_max_months),
    unique nulls not distinct (venue_id, fact_key, age_min_months, age_max_months)
);

-- Same access model as the rest of the schema: RLS on, no policies; only the ingest/export role reads.
alter table venue_categories     enable row level security;
alter table data_sources         enable row level security;
alter table import_runs          enable row level security;
alter table venues               enable row level security;
alter table venue_category_links enable row level security;
alter table fact_keys            enable row level security;
alter table venue_facts          enable row level security;
