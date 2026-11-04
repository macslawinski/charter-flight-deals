-- 003_seed_destinations.sql: the 38 r.pl charter destinations seen on 2026-11-04.
-- Names/countries as shown by r.pl (Polish, used for display). Zone = median outbound CzasLotu
-- from Poland in the 2026-11-04 crawl (short <= 3 h, medium <= 5.5 h, long <= 8 h, exotic > 8 h).
-- Rows marked "est." had no CzasLotu yet (far-future summer flights): zone from typical flight time.

insert into destinations (iata, name, country, zone) values
    -- short (<= 3 h)
    ('VRN', 'Werona',               'Włochy',     'short'),   -- 2:20
    ('CHQ', 'Kreta - Chania',       'Grecja',     'short'),   -- est. 2:50
    ('HER', 'Kreta - Heraklion',    'Grecja',     'short'),   -- est. 2:50
    ('RHO', 'Rodos',                'Grecja',     'short'),   -- est. 2:50
    ('KGS', 'Kos',                  'Grecja',     'short'),   -- est. 2:45
    ('MAH', 'Minorka',              'Hiszpania',  'short'),   -- est. 2:50
    -- medium (3 - 5.5 h)
    ('AYT', 'Antalya',              'Turcja',     'medium'),  -- 3:07
    ('MIR', 'Monastyr',             'Tunezja',    'medium'),  -- 3:05
    ('NBE', 'Enfidha',              'Tunezja',    'medium'),  -- est. 3:05
    ('DJE', 'Djerba',               'Tunezja',    'medium'),  -- 3:20
    ('LEI', 'Almeria',              'Hiszpania',  'medium'),  -- est. 3:30
    ('AGP', 'Malaga',               'Hiszpania',  'medium'),  -- est. 3:45
    ('OUD', 'Wadżda',               'Maroko',     'medium'),  -- est. 3:50
    ('FAO', 'Faro',                 'Portugalia', 'medium'),  -- est. 4:00
    ('HRG', 'Hurghada',             'Egipt',      'medium'),  -- 4:37
    ('AQJ', 'Aqaba',                'Jordania',   'medium'),  -- 4:45
    ('RMF', 'Marsa Alam',           'Egipt',      'medium'),  -- 5:00
    ('AGA', 'Agadir',               'Maroko',     'medium'),  -- 5:15
    -- long (5.5 - 8 h)
    ('FNC', 'Madera',               'Portugalia', 'long'),    -- 5:45
    ('LPA', 'Gran Canaria',         'Hiszpania',  'long'),    -- 6:10
    ('TFS', 'Teneryfa - Południe',  'Hiszpania',  'long'),    -- 6:15
    ('DWC', 'Dubaj Al Maktoum',     'Zjednoczone Emiraty Arabskie', 'long'),  -- 6:30
    ('SLL', 'Salalah',              'Oman',       'long'),    -- 7:40
    -- exotic (> 8 h)
    ('SID', 'Espargos',             'Wyspy Zielonego Przylądka', 'exotic'),  -- 8:05
    ('BJL', 'Banjul',               'Gambia',     'exotic'),  -- 8:15
    ('MBA', 'Mombasa',              'Kenia',      'exotic'),  -- 10:15
    ('BKK', 'Bangkok',              'Tajlandia',  'exotic'),  -- 10:20
    ('HKT', 'Phuket',               'Tajlandia',  'exotic'),  -- 10:35
    ('PEN', 'Penang',               'Malezja',    'exotic'),  -- 10:40
    ('SGN', 'Ho Chi Minh / Sajgon', 'Wietnam',    'exotic'),  -- 10:55
    ('PQC', 'Phu Quoc',             'Wietnam',    'exotic'),  -- 10:55
    ('ZNZ', 'Zanzibar',             'Tanzania',   'exotic'),  -- 11:10
    ('POP', 'Puerto Plata',         'Dominikana', 'exotic'),  -- 11:25
    ('CMB', 'Colombo',              'Sri Lanka',  'exotic'),  -- 11:55
    ('CUN', 'Cancun',               'Meksyk',     'exotic'),  -- 12:35
    ('LIR', 'Liberia',              'Kostaryka',  'exotic'),  -- 13:35
    ('PVR', 'Puerto Vallarta',      'Meksyk',     'exotic'),  -- 14:15
    ('MRU', 'Port Louis',           'Mauritius',  'exotic');  -- 16:30
