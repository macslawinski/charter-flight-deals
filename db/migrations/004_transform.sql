-- 004_transform.sql: sensible-stay filter, rolling baseline and the deal rule (see CLAUDE.md).
-- Everything is parameterized by as_of and pipeline_params; no now()/current_date inside.

-- Flights that pass the sensible-stay filter. Min stay: destination override -> zone -> default.
-- Destinations missing from `destinations` fall back to default_min_stay_days.
-- security_invoker: the view runs with the caller's rights, so RLS on flights still applies
-- (otherwise the anon API role could read flights through it).
create or replace view eligible_flights with (security_invoker = true) as
select f.flight_key,
       f.operator,
       f.origin_iata,
       f.dest_iata,
       f.outbound_date,
       f.return_date,
       f.stay_days,
       date_trunc('month', f.outbound_date)::date as dep_month,
       coalesce(d.min_stay_override, z.min_sensible_stay_days, p.default_min_stay_days) as min_stay_days
from flights f
cross join pipeline_params p
left join destinations d on d.iata = f.dest_iata
left join zones z on z.zone = d.zone
where case
          when f.return_date is null then p.include_one_way
          else f.stay_days >= coalesce(d.min_stay_override, z.min_sensible_stay_days,
                                       p.default_min_stay_days)
      end;

-- Deals as of a date. Segment = origin + destination + departure month.
-- Baseline: snapshots of eligible flights in the segment from [as_of - window_days, as_of - 1];
-- each flight is averaged first (one vote per flight), then aggregated across flights.
create or replace function compute_deals(p_as_of date)
returns table (
    as_of            date,
    flight_key       text,
    current_price    numeric,
    baseline_avg     numeric,
    baseline_median  numeric,
    baseline_used    numeric,
    threshold_price  numeric,
    discount_pct     numeric,
    baseline_flights integer,
    baseline_obs     integer,
    window_start     date,
    window_end       date
)
language sql
stable
set search_path = public
as $$
    with p as (
        select * from pipeline_params
    ),
    cur as (
        select e.flight_key, e.origin_iata, e.dest_iata, e.dep_month, s.price_last as price
        from eligible_flights e
        join price_snapshots s on s.flight_key = e.flight_key and s.snapshot_date = p_as_of
        where e.outbound_date > p_as_of
    ),
    per_flight as (
        select e.origin_iata, e.dest_iata, e.dep_month, e.flight_key,
               avg(s.price_last) as avg_price,
               sum(s.n_obs)      as n_obs
        from eligible_flights e
        join price_snapshots s on s.flight_key = e.flight_key
        cross join p
        where s.snapshot_date between p_as_of - p.window_days and p_as_of - 1
        group by e.origin_iata, e.dest_iata, e.dep_month, e.flight_key
    ),
    seg as (
        select origin_iata, dest_iata, dep_month,
               avg(avg_price)                                                  as b_avg,
               percentile_cont(0.5) within group (order by avg_price)::numeric as b_median,
               count(*)::integer                                               as n_flights,
               sum(n_obs)::integer                                             as n_obs
        from per_flight
        group by origin_iata, dest_iata, dep_month
    ),
    scored as (
        select c.flight_key, c.price, seg.b_avg, seg.b_median, seg.n_flights, seg.n_obs,
               case when p.baseline_stat = 'median' then seg.b_median else seg.b_avg end as used,
               p.discount_threshold, p.window_days, p.min_baseline_flights
        from cur c
        join seg using (origin_iata, dest_iata, dep_month)
        cross join p
    )
    select p_as_of,
           flight_key,
           price,
           round(b_avg, 2),
           round(b_median, 2),
           round(used, 2),
           round(used * (1 - discount_threshold), 2),
           round(100 * (1 - price / used), 2),
           n_flights,
           n_obs,
           p_as_of - window_days,
           p_as_of - 1
    from scored
    where n_flights >= min_baseline_flights
      and price <= used * (1 - discount_threshold)
$$;

-- Materialize deals for one as_of date (idempotent). Returns the number of deals.
create or replace function refresh_deals(p_as_of date)
returns integer
language plpgsql
set search_path = public
as $$
declare
    n integer;
begin
    delete from deals where deals.as_of = p_as_of;
    insert into deals (as_of, flight_key, current_price, baseline_avg, baseline_median,
                       baseline_used, threshold_price, discount_pct, baseline_flights,
                       baseline_obs, window_start, window_end)
    select * from compute_deals(p_as_of);
    get diagnostics n = row_count;
    return n;
end;
$$;

-- Only the ingest/export role (postgres) runs the transform; not callable through the public API.
revoke execute on function compute_deals(date), refresh_deals(date) from public;
do $$
begin
    if exists (select 1 from pg_roles where rolname = 'anon') then  -- Supabase only
        revoke execute on function compute_deals(date), refresh_deals(date) from anon, authenticated;
        revoke all on eligible_flights from anon, authenticated;
    end if;
end;
$$;

-- Covering indexes for FKs flagged by the Supabase performance advisor.
create index if not exists deals_flight_key_idx on deals (flight_key);
create index if not exists destinations_zone_idx on destinations (zone);
