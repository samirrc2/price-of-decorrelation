# inputs/  (optional context snippets)

Drop one JSON per (ticker, date) here to give agents a real, cell-specific
news+fundamentals snippet instead of the neutral placeholder.

Filename: `<TICKER>_<YYYY-MM-DD>.json`  e.g. `AAPL_2026-04-15.json`

```json
{
  "headline": "One-line headline as of the as-of date.",
  "fundamentals": "2-4 sentence fundamentals summary.",
  "asof": "2026-04-14"
}
```

`asof` MUST be strictly before the analysis date in the filename (no lookahead);
the pipeline asserts this and refuses to run otherwise. If a file is absent the
pipeline builds a neutral placeholder and flags snippet_source=constructed_placeholder.
