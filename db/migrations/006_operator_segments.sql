-- 006_operator_segments.sql: segment = operator + origin + destination + departure month.
-- With a second operator (Itaka) the same physical flight can be sold by both r.pl and Itaka;
-- a shared baseline would count it twice ("one vote per flight"). Each operator now gets its own
-- baseline. Everything else in compute_deals is unchanged (see 004_transform.sql).

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
    per_flight as (
        select e.operator, e.origin_iata, e.dest_iata, e.dep_month, e.flight_key,
               avg(s.price_last) as avg_price,
               sum(s.n_obs)      as n_obs
        from eligible_flights e
        join price_snapshots s on s.flight_key = e.flight_key
        cross join p
        where s.snapshot_date between p_as_of - p.window_days and p_as_of - 1
        group by e.operator, e.origin_iata, e.dest_iata, e.dep_month, e.flight_key
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
        select c.flight_key, c.price, seg.b_avg, seg.b_median, seg.n_flights, seg.n_obs,
               case when p.baseline_stat = 'median' then seg.b_median else seg.b_avg end as used,
               p.discount_threshold, p.window_days, p.min_baseline_flights
        from cur c
        join seg using (operator, origin_iata, dest_iata, dep_month)
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

-- create or replace keeps existing grants; restate the lockdown so this file stands on its own.
revoke execute on function compute_deals(date) from public;
do $$
begin
    if exists (select 1 from pg_roles where rolname = 'anon') then  -- Supabase only
        revoke execute on function compute_deals(date) from anon, authenticated;
    end if;
end;
$$;
