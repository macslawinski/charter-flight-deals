# ROADMAP: step by step (as of 2026-11-09)

Operational checklist for Product A (charter flight deals). Rules: `CLAUDE.md`. Owner: **U** = user,
**C** = Claude. Tick items off here when done. Product B ("Pieluchy i paszporty") moved to its own repo
`macslawinski/pieluchy-i-paszporty` on 2026-11-09 (`docs/repo-split-plan.md`).

## Step 1. This week: close open work (2026-11-05 … 11-08)
- [x] U: review and merge PR #7 (B redesign, Poznań playgrounds).
- [x] U: pick a look for B: **A, illustrated** (2026-11-05); `/proby/` removed.
- [x] U: merge PR #8 (`min_history_days` = 7). Migration 010 is already applied in Supabase.
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
- [ ] C: A1 from PLAN.md (B repo): a handful of logged manual requests to see whether r.pl / Itaka return
      infant/child prices (decides the family price, A2).
- [ ] C: donation link + ad slot placeholder on A (definition of done), still private.

## Step 4. Before going public (target ~end of November 2026)
- [x] C+U (2026-11-09): split Product B into its own repo and Supabase project (`docs/repo-split-plan.md`);
      B tables dropped from A's DB in migration 017 (backup kept outside the repo).
- [ ] U: permission e-mails to Rainbow (r.pl) and Itaka (and decide whether to ask about hotel facts).
- [ ] U: repo public → C: Itaka back to 2×/day in `ingest.yml` (Actions minutes).
- [ ] U: domain(s) and analytics; hosting decision (Vercel Hobby vs. Pro/Cloudflare) before any ads.
- [ ] U: switch Vercel protection off for A when ready (now `ssoProtection: all`).

## Later (on hold, needs your go)
- Family deal alerts (changes A's "no notifications" scope).
- A "flying with kids" toggle in A (PLAN.md A3–A4, B repo).
