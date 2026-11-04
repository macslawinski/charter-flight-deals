-- 001_schema.sql: core tables. Never edit after it is applied; add a new migration instead.

create table zones (
    zone                   text primary key,
    min_sensible_stay_days integer not null check (min_sensible_stay_days >= 0),
    description            text
);

create table destinations (
    iata              char(3) primary key,
    name              text not null,
    country           text not null,
    zone              text not null references zones (zone),
    min_stay_override integer check (min_stay_override >= 0)
);

create table pipeline_params (
    id                    boolean primary key default true check (id),  -- single row
    window_days           integer not null default 30 check (window_days > 0),
    discount_threshold    numeric(4, 3) not null default 0.150 check (discount_threshold between 0 and 1),
    min_baseline_flights  integer not null default 5 check (min_baseline_flights > 0),
    baseline_stat         text not null default 'avg' check (baseline_stat in ('avg', 'median')),
    default_min_stay_days integer not null default 3 check (default_min_stay_days >= 0),
    include_one_way       boolean not null default false
);
insert into pipeline_params default values;

create table raw_fetches (
    id          bigint generated always as identity primary key,
    operator    text not null,
    fetched_at  timestamptz not null default now(),
    http_status integer not null,
    request     jsonb not null,
    response    jsonb,
    parse_ok    boolean,
    parse_error text
);
create index raw_fetches_fetched_at_idx on raw_fetches (fetched_at);

create table flights (
    flight_key    text primary key,
    operator      text not null,
    origin_iata   char(3) not null,
    dest_iata     char(3) not null,
    outbound_date date not null,
    return_date   date,
    flight_no     text,
    stay_days     integer generated always as (return_date - outbound_date) stored,
    first_seen_at timestamptz not null default now(),
    last_seen_at  timestamptz not null default now(),
    check (return_date is null or return_date >= outbound_date)
);
create index flights_segment_idx on flights (origin_iata, dest_iata, outbound_date);

create table price_snapshots (
    flight_key        text not null references flights (flight_key),
    snapshot_date     date not null,  -- Europe/Warsaw calendar day
    price_last        numeric(10, 2) not null check (price_last > 0),  -- PLN per person
    price_min         numeric(10, 2) not null check (price_min > 0),
    seats_left        integer,
    n_obs             integer not null default 1 check (n_obs > 0),
    first_observed_at timestamptz not null,
    last_observed_at  timestamptz not null,
    primary key (flight_key, snapshot_date)
);
create index price_snapshots_date_idx on price_snapshots (snapshot_date);

create table deals (
    as_of             date not null,
    flight_key        text not null references flights (flight_key),
    current_price     numeric(10, 2) not null,
    baseline_avg      numeric(10, 2) not null,
    baseline_median   numeric(10, 2) not null,
    baseline_used     numeric(10, 2) not null,
    threshold_price   numeric(10, 2) not null,
    discount_pct      numeric(5, 2) not null,
    baseline_flights  integer not null,
    baseline_obs      integer not null,
    window_start      date not null,
    window_end        date not null,
    primary key (as_of, flight_key)
);
