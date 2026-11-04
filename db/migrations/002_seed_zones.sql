-- 002_seed_zones.sql: zones by flight time from Poland. Destinations are seeded once r.pl data shows
-- which airports actually appear.

insert into zones (zone, min_sensible_stay_days, description) values
    ('short',  3, 'up to 3 h flight'),
    ('medium', 5, '3 to 5.5 h flight'),
    ('long',   7, '5.5 to 8 h flight'),
    ('exotic', 9, 'over 8 h flight');
