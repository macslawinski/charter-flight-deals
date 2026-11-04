-- Independent recomputation of one deal from raw tables. Replace {{as_of}} and {{flight_key}}.
-- Deliberately does not use transform views/functions.
-- Price used per snapshot: price_last (must match the transform's choice; update both if it changes).

with p as (select * from pipeline_params),
target as (
    select f.*, coalesce(d.min_stay_override, z.min_sensible_stay_days, p.default_min_stay_days) as min_stay
    from flights f
    cross join p
    left join destinations d on d.iata = f.dest_iata
    left join zones z on z.zone = d.zone
    where f.flight_key = '{{flight_key}}'
),
win as (
    select ('{{as_of}}'::date - p.window_days) as w_start, ('{{as_of}}'::date - 1) as w_end from p
),
eligible as (  -- same segment, passes the sensible-stay filter
    select f.flight_key
    from flights f
    cross join p
    join target t on f.operator = t.operator          -- segment is per operator (006)
                 and f.origin_iata = t.origin_iata
                 and f.dest_iata = t.dest_iata
                 and date_trunc('month', f.outbound_date) = date_trunc('month', t.outbound_date)
    left join destinations d on d.iata = f.dest_iata
    left join zones z on z.zone = d.zone
    where (f.return_date is not null or p.include_one_way)
      and (f.stay_days is null
           or f.stay_days >= coalesce(d.min_stay_override, z.min_sensible_stay_days, p.default_min_stay_days))
),
per_flight as (  -- one vote per flight
    select s.flight_key, avg(s.price_last) as flight_avg, count(*) as n_snap, sum(s.n_obs) as n_obs
    from price_snapshots s
    join eligible e using (flight_key)
    cross join win
    where s.snapshot_date between win.w_start and win.w_end
    group by s.flight_key
),
baseline as (
    select avg(flight_avg) as b_avg,
           percentile_cont(0.5) within group (order by flight_avg) as b_median,
           count(*) as n_flights, sum(n_obs) as n_obs
    from per_flight
),
cur as (
    select price_last as current_price
    from price_snapshots
    where flight_key = '{{flight_key}}' and snapshot_date = '{{as_of}}'::date
)
select t.flight_key, t.stay_days, t.min_stay,
       (t.stay_days >= t.min_stay) as stay_ok,
       (t.outbound_date > '{{as_of}}'::date) as departs_after_as_of,
       cur.current_price,
       round(b.b_avg, 2) as baseline_avg,
       round(b.b_median::numeric, 2) as baseline_median,
       round(case when p.baseline_stat = 'median' then b.b_median::numeric else b.b_avg end
             * (1 - p.discount_threshold), 2) as threshold_price,
       round(100 * (1 - cur.current_price
             / nullif(case when p.baseline_stat = 'median' then b.b_median::numeric else b.b_avg end, 0)), 2)
             as discount_pct,
       b.n_flights, b.n_obs, (b.n_flights >= p.min_baseline_flights) as enough_flights,
       win.w_start, win.w_end
from target t, cur, baseline b, p, win;
