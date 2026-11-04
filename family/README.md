# family/: Product B site (working name "Pieluchy i paszporty")

Static Astro site, private test version (`noindex`). See `PLAN.md` at the repo root.

```
python scripts/export_family.py      # data/curated/*.toml -> family/src/data/family.json (commit it)
cd family; npm install; npm run dev  # http://localhost:4321
npm run build                        # dist/
```

The build needs no database or Python: it reads the committed `src/data/family.json`.
`tests/test_export_family.py` fails if that file is stale. Every rule/feature key needs a Polish label in
`src/lib/data.ts`, otherwise the build fails on purpose. Astro 6 (not 7) because the local Node is 22.14.
