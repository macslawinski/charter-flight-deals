-- 005_market_fares.sql: reference prices of regular (scheduled) airlines, shown next to deals.
-- Display-only: nothing here feeds compute_deals(); the deal rule is unchanged.
-- Source: Travelpayouts / Aviasales Data API (cached prices found by Aviasales users, ~2-7 days).

-- Airline classification. Only airlines listed here with is_charter = false are used as the
-- reference; unknown codes are ignored (and logged by the export) until they are classified.
create table airlines (
    iata       text primary key check (length(iata) = 2),
    name       text not null,
    is_charter boolean not null
);

insert into airlines (iata, name, is_charter) values
    ('FR', 'Ryanair', false), ('RK', 'Ryanair UK', false), ('AL', 'Malta Air', false),
    ('RR', 'Buzz', false), ('W6', 'Wizz Air', false), ('W4', 'Wizz Air Malta', false),
    ('W9', 'Wizz Air UK', false), ('LO', 'LOT', false), ('U2', 'easyJet', false),
    ('EC', 'easyJet', false), ('DS', 'easyJet', false), ('VY', 'Vueling', false),
    ('IB', 'Iberia', false), ('UX', 'Air Europa', false), ('TP', 'TAP Air Portugal', false),
    ('S4', 'Azores Airlines', false), ('A3', 'Aegean', false), ('OA', 'Olympic Air', false),
    ('GQ', 'Sky Express', false), ('PC', 'Pegasus', false), ('TK', 'Turkish Airlines', false),
    ('XQ', 'SunExpress', false), ('MS', 'EgyptAir', false), ('TU', 'Tunisair', false),
    ('AT', 'Royal Air Maroc', false), ('LH', 'Lufthansa', false), ('LX', 'Swiss', false),
    ('OS', 'Austrian', false), ('SN', 'Brussels Airlines', false), ('KL', 'KLM', false),
    ('AF', 'Air France', false), ('BT', 'airBaltic', false), ('FB', 'Bulgaria Air', false),
    ('RO', 'Tarom', false), ('JU', 'Air Serbia', false), ('OU', 'Croatia Airlines', false),
    ('DE', 'Condor', false), ('EW', 'Eurowings', false), ('AZ', 'ITA Airways', false),
    ('KM', 'KM Malta Airlines', false), ('CY', 'Cyprus Airways', false), ('EK', 'Emirates', false),
    ('FZ', 'flydubai', false), ('QR', 'Qatar Airways', false), ('LY', 'El Al', false),
    -- charter carriers: excluded from the reference (they are what we compare against)
    ('E4', 'Enter Air', true), ('QS', 'Smartwings', true), ('3Z', 'Smartwings Poland', true),
    ('XC', 'Corendon', true), ('XR', 'Corendon Europe', true), ('SR', 'Sundair', true),
    ('BJ', 'Nouvelair', true), ('SM', 'Air Cairo', true), ('U5', 'SkyUp', true),
    ('X3', 'TUI fly', true), ('TB', 'TUI fly Belgium', true), ('OR', 'TUI fly Netherlands', true),
    ('BY', 'TUI Airways', true), ('6B', 'TUI fly Nordic', true);

-- One row per segment (our origin + destination + departure month) per fetch day, also when the
-- source returned nothing: lets the page say "checked, no direct regular flight found".
create table market_fetches (
    source       text not null,
    origin_iata  char(3) not null,
    dest_iata    char(3) not null,
    dep_month    date not null check (dep_month = date_trunc('month', dep_month)::date),
    fetched_date date not null,          -- Europe/Warsaw calendar day
    fetched_at   timestamptz not null,
    n_fares      integer not null check (n_fares >= 0),
    primary key (source, origin_iata, dest_iata, dep_month, fetched_date)
);

-- Round-trip fares as returned by the source. origin/dest = the codes WE asked for (our airports);
-- origin_airport/dest_airport = the actual airports (e.g. WAW request -> WMI Modlin).
-- Price: per person, PLN, without checked baggage.
create table market_fares (
    source           text not null,
    origin_iata      char(3) not null,
    dest_iata        char(3) not null,
    outbound_date    date not null,      -- local date at the departure airport
    return_date      date not null,
    airline          text not null,
    origin_airport   char(3),
    dest_airport     char(3),
    flight_no        text,
    transfers        integer not null check (transfers >= 0),
    return_transfers integer not null check (return_transfers >= 0),
    price_pln        numeric(10, 2) not null check (price_pln > 0),
    found_date       date,               -- when an Aviasales user found the price, if known
    link             text,               -- path on aviasales.com
    fetched_date     date not null,
    fetched_at       timestamptz not null,
    stay_days        integer generated always as (return_date - outbound_date) stored,
    check (return_date >= outbound_date),
    primary key (source, origin_iata, dest_iata, outbound_date, return_date, airline, fetched_date)
);
create index market_fares_segment_idx
    on market_fares (origin_iata, dest_iata, fetched_date, outbound_date);

alter table pipeline_params
    add column market_stay_tolerance_days integer not null default 2
        check (market_stay_tolerance_days >= 0),
    add column market_max_age_days integer not null default 3 check (market_max_age_days >= 0);

-- Reference price for each deal of p_as_of: the cheapest direct (both ways) round trip of a
-- non-charter airline in the deal's segment (same origin, destination, departure month) whose stay
-- is within market_stay_tolerance_days of the deal's stay. Uses the segment's latest fetch from
-- [p_as_of - market_max_age_days, p_as_of]. One row per deal whose segment was fetched in that
-- window; price is null when the fetch found no matching fare.
create or replace function market_reference(p_as_of date)
returns table (
    flight_key     text,
    source         text,
    checked_at     timestamptz,
    price          numeric,
    airline        text,
    airline_name   text,
    origin_airport text,
    dest_airport   text,
    outbound_date  date,
    return_date    date,
    same_dates     boolean,
    found_date     date,
    link           text
)
language sql
stable
set search_path = public
as $$
    with p as (
        select * from pipeline_params
    ),
    d as (
        select f.flight_key, f.origin_iata, f.dest_iata, f.outbound_date, f.return_date,
               f.stay_days, date_trunc('month', f.outbound_date)::date as dep_month
        from deals dl
        join flights f on f.flight_key = dl.flight_key
        where dl.as_of = p_as_of and f.return_date is not null
    ),
    lf as (
        select distinct on (d.flight_key) d.flight_key, mf.source, mf.fetched_date, mf.fetched_at
        from d
        join market_fetches mf on mf.origin_iata = d.origin_iata and mf.dest_iata = d.dest_iata
                              and mf.dep_month = d.dep_month
        cross join p
        where mf.fetched_date between p_as_of - p.market_max_age_days and p_as_of
        order by d.flight_key, mf.fetched_date desc, mf.fetched_at desc
    ),
    best as (
        select distinct on (d.flight_key)
               d.flight_key, m.price_pln, m.airline, a.name as airline_name,
               m.origin_airport, m.dest_airport, m.outbound_date, m.return_date,
               (m.outbound_date = d.outbound_date and m.return_date = d.return_date) as same_dates,
               m.found_date, m.link
        from d
        join lf on lf.flight_key = d.flight_key
        join market_fares m on m.source = lf.source and m.fetched_date = lf.fetched_date
                           and m.origin_iata = d.origin_iata and m.dest_iata = d.dest_iata
                           and date_trunc('month', m.outbound_date)::date = d.dep_month
        join airlines a on a.iata = m.airline and not a.is_charter
        cross join p
        where m.transfers = 0 and m.return_transfers = 0
          and abs(m.stay_days - d.stay_days) <= p.market_stay_tolerance_days
        order by d.flight_key, m.price_pln,
                 (m.outbound_date = d.outbound_date and m.return_date = d.return_date) desc,
                 abs(m.outbound_date - d.outbound_date)
    )
    select lf.flight_key, lf.source, lf.fetched_at, b.price_pln, b.airline, b.airline_name,
           b.origin_airport, b.dest_airport, b.outbound_date, b.return_date, b.same_dates,
           b.found_date, b.link
    from lf
    left join best b on b.flight_key = lf.flight_key
$$;

alter table airlines       enable row level security;
alter table market_fetches enable row level security;
alter table market_fares   enable row level security;

revoke execute on function market_reference(date) from public;
do $$
begin
    if exists (select 1 from pg_roles where rolname = 'anon') then  -- Supabase only
        revoke execute on function market_reference(date) from anon, authenticated;
    end if;
end;
$$;
