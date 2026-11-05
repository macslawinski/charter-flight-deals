# ROADMAP: step by step (as of 2026-11-05)

Operational checklist for both products. Background and rationale: `PLAN.md` (Product B), `CLAUDE.md`
(Product A rules). Owner: **U** = user, **C** = Claude. Tick items off here when done.

## Step 1. This week: close open work (2026-11-05 … 11-08)
- [ ] U: review and merge PR #7 (B redesign, Poznań playgrounds).
- [x] U: pick a look for B: **A, illustrated** (2026-11-05); `/proby/` removed.
- [ ] U: merge PR #8 (`min_history_days` = 7). Migration 010 is already applied in Supabase.
- [ ] C: every morning `check-deals`: cron ran (the 00:17 UTC run may start hours late; the Itaka crawl
      runs only on that one, so a dropped run = an Itaka day missing), no parse failures, flights/day stable.

## Step 2. First real deals in A (from ~2026-11-11)
- Snapshots started 2026-11-04, so segments reach 7 days of history on **2026-11-11**.
- [ ] C: on 11-11 run `check-deals` with full verification of 3 deals; also check how many deals are real
      price drops vs. "cheaper than the segment average" (stay length, holiday dates).
- [ ] U: look at the private A site and judge whether the deals make sense to a human.
- [ ] Decide (U): if most deals are still "short stay vs. long stay" effects, consider splitting segments by
      stay length band (business-rule change, needs your go).

## Step 3. A reaches its definition of done (~2026-11-18 … 11-25)
- [ ] 2+ weeks of cron without manual fixes (from 2026-11-04 → earliest **2026-11-18**).
- [ ] C: after 2–3 weeks of data (~**2026-11-25**) tune `discount_threshold` / `window_days` /
      `baseline_stat` with `data:statistical-analysis`; you decide on changes.
- [ ] C: A1 from PLAN.md: a handful of logged manual requests to see whether r.pl / Itaka return
      infant/child prices (decides the family price, A2).
- [ ] C: donation link + ad slot placeholder on A (definition of done), still private.

## Step 4. B content, in parallel with A's waiting time
- [ ] C: Saltic access times by car and train from the 6 cities.
- [ ] C: more carriers' child rules: Corendon, Aegean, Electra, Neos, Nouvelair, World2Fly, Air Cairo.
- [ ] C: remaining Poznań playgrounds (Kinderlandia, Monsterkowo, Bawimy, Smålandia) where a price list exists;
      resolve the two "do potwierdzenia" facts (Fikołki Karta Malucha, Mlecz hours) — U may phone them.
- [ ] C: Rodos + Crete-Heraklion hotels (PLAN.md B5), facts from hotel websites only.
- [ ] C: project skill `reverify-child-rules` so re-checks of rules are repeatable.
- [ ] C: venues migration (DB) once the venue format is stable.
- [ ] Photos (optional): only with your permission per download (e.g. Unsplash), licence noted.

## Step 5. Before going public (target ~end of November 2026)
- [ ] U: permission e-mails to Rainbow (r.pl) and Itaka (and decide whether to ask about hotel facts).
- [ ] U: repo public → C: Itaka back to 2×/day in `ingest.yml` (Actions minutes).
- [ ] U: domain(s) and analytics; hosting decision (Vercel Hobby vs. Pro/Cloudflare) before any ads.
- [ ] C: SEO basics for B (sitemap, JSON-LD), remove `noindex` only on your go.
- [ ] U: switch Vercel protection off per site when ready (both now `ssoProtection: all`).

## Later (on hold, needs your go)
- Affiliates and ads (Phase 2), family deal alerts (changes A's "no notifications" scope).
- Parent surveys and the B2B badge (Phase 3).
- A "flying with kids" toggle in A (PLAN.md A3–A4).
