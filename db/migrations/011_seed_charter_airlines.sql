-- 011_seed_charter_airlines.sql: charter carriers that now have child rules in
-- data/curated/child_rules/ (child_rules.carrier_iata references airlines). Marked as charter, so
-- the regular-airline reference (005) keeps ignoring them.

insert into airlines (iata, name, is_charter) values
    ('NO', 'Neos', true),
    ('2W', 'World2Fly', true),
    ('3E', 'Electra Airways', true)
on conflict (iata) do nothing;
