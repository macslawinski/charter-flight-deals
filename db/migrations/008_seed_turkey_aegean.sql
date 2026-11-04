-- 008_seed_turkey_aegean.sql: r.pl destinations on the Turkish Aegean coast, first seen
-- 2026-11-04 (ADB 114, BJV 717, DLM 324 flights). Without a row they fell back to
-- default_min_stay_days. Same flight time from Poland as Antalya (~3 h), so the same zone as
-- AYT in 003 ('medium').

insert into destinations (iata, name, country, zone) values
    ('ADB', 'Izmir',   'Turcja', 'medium'),
    ('BJV', 'Bodrum',  'Turcja', 'medium'),
    ('DLM', 'Dalaman', 'Turcja', 'medium')
on conflict (iata) do nothing;
