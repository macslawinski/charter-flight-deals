-- 010_min_history_days.sql: no deal until the segment has enough days of price history.
-- With one day of history the "baseline" is just today's cross-section of other flights in the
-- segment (e.g. a 7-day trip vs 14-day trips), not a price drop. A segment now needs at least
-- min_history_days distinct snapshot dates inside the window, on top of min_baseline_flights.
-- Everything else in compute_deals is unchanged (see 006_operator_segments.sql).

alter table pipeline_params
    add column min_history_days integer not null default 7 check (min_history_days > 0);

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
        select e.flight_key, e.operator, e.origin_iata, e.dest_iata, e.dep_month,
               s.price_last as price
        from eligible_flights e
        join price_snapshots s on s.flight_key = e.flight_key and s.snapshot_date = p_as_of
        where e.outbound_date > p_as_of
    ),
    in_window as (
        select e.operator, e.origin_iata, e.dest_iata, e.dep_month, e.flight_key,
               s.snapshot_date, s.price_last, s.n_obs
        from eligible_flights e
        join price_snapshots s on s.flight_key = e.flight_key
        cross join p
        where s.snapshot_date between p_as_of - p.window_days and p_as_of - 1
    ),
    per_flight as (
        select operator, origin_iata, dest_iata, dep_month, flight_key,
               avg(price_last) as avg_price,
               sum(n_obs)      as n_obs
        from in_window
        group by operator, origin_iata, dest_iata, dep_month, flight_key
    ),
    seg_days as (
        select operator, origin_iata, dest_iata, dep_month,
               count(distinct snapshot_date)::integer as n_days
        from in_window
        group by operator, origin_iata, dest_iata, dep_month
    ),
    seg as (
        select operator, origin_iata, dest_iata, dep_month,
               avg(avg_price)                                                  as b_avg,
               percentile_cont(0.5) within group (order by avg_price)::numeric as b_median,
               count(*)::integer                                               as n_flights,
               sum(n_obs)::integer                                             as n_obs
        from per_flight
        group by operator, origin_iata, dest_iata, dep_month
    ),
    scored as (
        select c.flight_key, c.price, seg.b_avg, seg.b_median, seg.n_flights, seg.n_obs, sd.n_days,
               case when p.baseline_stat = 'median' then seg.b_median else seg.b_avg end as used,
               p.discount_threshold, p.window_days, p.min_baseline_flights, p.min_history_days
        from cur c
        join seg using (operator, origin_iata, dest_iata, dep_month)
        join seg_days sd using (operator, origin_iata, dest_iata, dep_month)
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
      and n_days >= min_history_days
      and price <= used * (1 - discount_threshold)
$$;

-- create or replace keeps existing grants; restate the lockdown so this file stands on its own.
revoke execute on function compute_deals(date) from public;
do $$
begin
    if exists (select 1 from pg_roles where rolname = 'anon') then  -- Supabase only
        revoke execute on function compute_deals(date) from anon, authenticated;
    end if;
end;
$$;
