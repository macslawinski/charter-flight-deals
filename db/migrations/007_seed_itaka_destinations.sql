-- 007_seed_itaka_destinations.sql: Itaka charter destinations missing from 003 (seen 2026-11-04).
-- Without a row, a destination falls back to default_min_stay_days (3), so e.g. a 3-day
-- Fuerteventura trip would pass the sensible-stay filter. Zone = median outbound flight duration
-- from Poland in the 2026-11-04 Itaka crawl (short <= 3 h, medium <= 5.5 h, long <= 8 h,
-- exotic > 8 h), same rule as 003. Names in Polish, for display.

insert into destinations (iata, name, country, zone) values
    -- short (<= 3 h)
    ('CUF', 'Cuneo',          'Włochy',      'short'),   -- 1:50 (n=9)
    ('TRN', 'Turyn',          'Włochy',      'short'),   -- 2:10 (n=7)
    ('ASR', 'Kayseri',        'Turcja',      'short'),   -- 3:00 (n=19)
    -- medium (3 - 5.5 h)
    ('PXO', 'Porto Santo',    'Portugalia',  'medium'),  -- 4:50 (n=13)
    -- long (5.5 - 8 h)
    ('SPC', 'La Palma',       'Hiszpania',   'long'),    -- 5:35 (n=47)
    ('FUE', 'Fuerteventura',  'Hiszpania',   'long'),    -- 5:45 (n=273)
    ('ACE', 'Lanzarote',      'Hiszpania',   'long'),    -- 5:50 (n=104)
    -- exotic (> 8 h)
    ('DSS', 'Dakar',          'Senegal',     'exotic'),  -- 8:15 (n=24)
    ('NOS', 'Nosy Be',        'Madagaskar',  'exotic'),  -- 9:30 (n=10)
    ('MLE', 'Male',           'Malediwy',    'exotic'),  -- 9:55 (n=10)
    ('PUJ', 'Punta Cana',     'Dominikana',  'exotic'),  -- 10:25 (n=107)
    ('KBV', 'Krabi',          'Tajlandia',   'exotic'),  -- 10:40 (n=28)
    ('LGK', 'Langkawi',       'Malezja',     'exotic')   -- 10:50 (n=21)
on conflict (iata) do nothing;
