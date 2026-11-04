#!/usr/bin/env python3
"""Pull the static (completed-cycle) data the midterm-volume generator needs.

Writes 12 JSON files into HRWORK (default: ./work next to this script):
  rep{y}.json / ord{y}.json / don{y}.json            — daily, US/Eastern day
  e15_{rep,ord,don}{y}.json                          — Election-Day 15-min buckets
for y in {2018, 2022}. 2026 is pulled LIVE by gen.py itself (it changes run to run).

Windows are intentionally IDENTICAL to the original 2026-11-03 E-Day session so
the regenerated CSV is bit-stable with what's published in this repo:
  - daily:   created_at >= '{y}-09-01' and created_at < '{y}-12-01'   (UTC-naive created_at)
             (yes, this truncates Nov 29–30 ET at 19:00 — inherited from the original
             pull; harmless zero tail, and changing it would drift the published CSV)
  - E-day:   '{D} 05:00' → '{D+1} 05:00' UTC   (November = EST, ET day starts 05:00 UTC)
  - 15-min slot: 4*hour + floor(minute/15)   — floor, NOT a plain ::int cast
             (Postgres ::int on the /15 division ROUNDS: minute 53 → slot boundary spill)

DB access: ~/.pi/agent/skills/pizzabase-ops/scripts/q.py (RDS Data API, profile
ptp-agent, read-only role ptp_ro). macOS assumed (%-I in strftime inside gen.py).
"""
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
W = Path(os.environ.get("HRWORK") or HERE / "work")
W.mkdir(parents=True, exist_ok=True)
Q = os.environ.get("QSCRIPT") or os.path.expanduser(
    "~/.pi/agent/skills/pizzabase-ops/scripts/q.py")

ED = {2018: dt.date(2018, 11, 6), 2022: dt.date(2022, 11, 8)}
B = "(created_at at time zone 'UTC' at time zone 'America/New_York')"


def q(sql):
    r = subprocess.run(["python3", Q, "--json", sql], capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr.strip())
    return json.loads(r.stdout)


def pull(y):
    lo, hi = f"{y}-09-01", f"{y}-12-01"
    for name, tbl, dol in (("rep", "reports", False), ("ord", "orders", False),
                           ("don", "donations", True)):
        dcol = ", sum(amount) as dol" if dol else ""
        rows = q(f"select {B}::date as d, count(*) as n{dcol} from {tbl} "
                 f"where created_at >= '{lo}' and created_at < '{hi}' group by 1 order by 1")
        (W / f"{name}{y}.json").write_text(json.dumps(rows))
    d, nd = ED[y].isoformat(), (ED[y] + dt.timedelta(days=1)).isoformat()
    win = f"created_at >= '{d} 05:00' and created_at < '{nd} 05:00'"
    slot = f"4*extract(hour from {B})::int + floor(extract(minute from {B})/15)::int"
    for name, tbl, dol in (("rep", "reports", False), ("ord", "orders", False),
                           ("don", "donations", True)):
        dcol = ", sum(amount) as dol" if dol else ""
        rows = q(f"select {slot} as slot, count(*) as n{dcol} from {tbl} "
                 f"where {win} group by 1 order by 1")
        (W / f"e15_{name}{y}.json").write_text(json.dumps(rows))
    print(f"{y}: pulled daily + e15 into {W}")


def verify(y):
    d = ED[y].isoformat()
    rep = {r["d"]: r["n"] for r in json.load(open(W / f"rep{y}.json"))}
    ordn = {r["d"]: r["n"] for r in json.load(open(W / f"ord{y}.json"))}
    don = {r["d"]: (r["n"], round(r["dol"] or 0)) for r in json.load(open(W / f"don{y}.json"))}
    sums = {}
    for name in ("rep", "ord", "don"):
        rows = json.load(open(W / f"e15_{name}{y}.json"))
        assert all(0 <= r["slot"] <= 95 for r in rows), (y, name, "slot out of range")
        sums[name] = sum(r["n"] for r in rows)
    daily = (rep.get(d, 0), ordn.get(d, 0), don.get(d, (0, 0))[0])
    assert sums == dict(zip(("rep", "ord", "don"), daily)), (y, sums, daily)
    print(f"{y}: E-Day {d} = {daily[0]} rep / {daily[1]} ord / {daily[2]} don "
          f"(${don.get(d, (0, 0))[1]:,}) — e15 sums match daily ✓")


if __name__ == "__main__":
    # known-good E-Day anchors from the 2026-11-03 session
    EXPECT = {2018: (2087, 697, 9227), 2022: (332, 189, 1496)}
    for y in (2018, 2022):
        pull(y)
        verify(y)
        d = ED[y].isoformat()
        got = tuple(json.load(open(W / f"e15_{n}{y}.json")) and
                    sum(r["n"] for r in json.load(open(W / f"e15_{n}{y}.json")))
                    for n in ("rep", "ord", "don"))
        assert got == EXPECT[y], (y, got, EXPECT[y])
    print("all pulls verified against known-good E-Day totals")
