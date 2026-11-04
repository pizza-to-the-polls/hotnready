# midterm-volume pipeline

Generator for the `/midterm-volume/` page (index.html + data/midterm_volume.csv)
on hotnready — the 2018/2022/2026 midterm volume comparison with the
Election-Day every-15-minutes chart. Built 2026-11-03 (E-Day); used live that
night on a 15-minute cron (see `refresh.sh`, since disarmed).

## Layout

```
pull.py     static pulls for the completed cycles (2018, 2022) → work/*.json
gen.py      regenerates the whole page: fresh 2026 DB pulls + work/ statics
            + ./template → out/midterm-volume/{index.html, data/*.csv}
smoke.js    DOM-stub runtime test of both inline scripts (node smoke.js [html])
refresh.sh  the E-Day cron runner (self-disarming crontab pattern) — kept as
            an example; its /tmp paths will not exist next time
template/   the FROZEN Oct-28-2026 published page. gen.py's one-time patches
            (duplicate watch-chart removal, TODAY-line suppression at k=0)
            apply against it every run, and its 2018/2022 content is the
            byte-stability anchor. Never "update" this to a newer page.
work/ out/  generated (gitignored)
```

Path overrides: `HRWORK`, `HRPUB`, `HROUT`, `QSCRIPT` env vars (defaults are
script-relative). macOS assumed (`%-I` / `%-d` in strftime).

## Running a refresh

```bash
cd tools/midterm-volume
python3 pull.py     # 2018/2022 statics → work/ (verified against known E-Day totals)
python3 gen.py      # fresh 2026 pulls + build → out/  (asserts byte-stability)
node smoke.js       # runtime-test both chart scripts against out/
cp out/midterm-volume/index.html ../../midterm-volume/index.html
cp out/midterm-volume/data/midterm_volume.csv ../../midterm-volume/data/
```

Publish either by committing + pushing `main` (gh auth as mojowen worked E-Day;
Pizza Pages rebuild ≈ 60–90 s) or via the pizza-eagle gate
`~/Projects/pizza-eagle/scripts/publish-hotnready.sh <src> midterm-volume "msg"`
(needs `./request-auth.json` with `writeAllowed: true` in the case workdir).

DB access: `~/.pi/agent/skills/pizzabase-ops/scripts/q.py` — read-only RDS
Data API, profile `ptp-agent`. (Check that skill first; it's canonical.)

## Gotchas (all of these bit on E-Day)

- **`created_at` is UTC-naive.** ET day in November = UTC+5 (EST): window
  `'{D} 05:00' → '{D+1} 05:00'` UTC for an ET day. A plain `'{D} 00:00'` window
  silently truncates ET days at 19:00.
- **15-min slots:** `4*hour + floor(minute/15)::int`. A bare `::int` cast on
  `minute/15` **rounds** (minute 53 → bucket 4) and spills slot 96.
- **CSV is CRLF** — the published `midterm_volume.csv` uses `\r\n`; keep it or
  every row shows as changed.
- **Dollar sums:** per-slot rounding vs one daily round can drift ±$2 — the
  e15-vs-daily assert uses a tolerance, don't tighten it to `==`.
- **2018/2022 must stay byte-identical.** gen.py asserts the regenerated CSV,
  the var D points and the daily SVGs against the template/published page;
  pull.py's windows intentionally reproduce the published CSV exactly
  (including the harmless Nov 29–30 ET truncation — don't "fix" it).
- **2026 is pulled live** by gen.py (daily + E-day 15-min). Mid-day runs race:
  the daily pull and the e15 pull land seconds apart, so gen.py rewrites the
  Nov 3 daily row from the e15 pull for single-snapshot consistency.
- **Page text is session-specific**: callout, takeaway, and section subtitles
  are written in gen.py for E-Day 2026 — edit per use (the "Generated" date
  and as-of labels are automatic).
- **Charts** are inline SVG in the page; the interactive comp + e15 charts are
  vanilla JS with no dependencies. smoke.js covers their runtime behavior
  without a browser (clicks every chip, exercises hovers).
- **Election-night cron pattern** (refresh.sh): `*/15 * * * *` job that (a) takes a
  lock with a 10-min staleness escape, (b) never pushes on gen failure, (c) past a
  cutoff pushes a final refresh and DISARMS via a stop-flag (later ticks no-op).
  **Do NOT rely on cron editing its own crontab on macOS**: `crontab -` from a
  cron-spawned process fails with `crontab: tmp/tmp.NNN: Operation not permitted`
  (verified empirically 2026-11-04 — `crontab -l` works, install doesn't; not fixed
  by cwd or TMPDIR). On 2026-11-03 the naive self-removal silently no-op'd for 5
  hours, pushing harmless duplicate "final refresh" commits every 15 min. Remove
  the schedule line from an interactive shell once the stop-flag is set.

## Next cycle

For 2028 (presidential, Nov 7 2028): add the year to `YEARS`/`ED`/`COL`,
pull its statics in `pull.py` (E-day is a Tuesday — DST already ended, so
the UTC+5 windows hold), and re-decide the 2026-as-complete vs in-progress
framing in gen.py's text blocks. The E15 chart is per-Election-Day by design;
a primary/general difference in poll-close times (6pm ET first close) is
hardcoded in the e15 script's close markers.
