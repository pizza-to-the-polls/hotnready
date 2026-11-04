#!/usr/bin/env python3
"""Regenerate hotnready /midterm-volume/ page (index.html + data/midterm_volume.csv)
from DB pulls, adding the Election-Day every-15-minutes chart (2026 vs 2018 vs 2022).

2018/2022 content must come out identical to the published page (verified);
2026 is refreshed through "now"; the E15 section is new."""
import json, math, os, re, subprocess, datetime as dt
from pathlib import Path

# Paths: script-relative by default (works from a fresh clone of this repo),
# overridable via HRWORK / HRPUB / HROUT / QSCRIPT for the original /tmp layout.
# HRPUB is the FROZEN Oct-28-2026 published page in ./template — the one-time
# patches below (watch-chart removal, TODAY-line suppression) apply against it
# every run, and the byte-stability asserts for 2018/2022 anchor to it.
# Do NOT "update" the template to a later page; gen.py already produces that.
HERE = Path(__file__).resolve().parent
W = Path(os.environ.get("HRWORK") or HERE / "work")
PUB = Path(os.environ.get("HRPUB") or HERE / "template")
OUT = Path(os.environ.get("HROUT") or HERE / "out" / "midterm-volume")
(OUT / "data").mkdir(parents=True, exist_ok=True)
Q = os.environ.get("QSCRIPT") or os.path.expanduser("~/.pi/agent/skills/pizzabase-ops/scripts/q.py")

YEARS = [2018, 2022, 2026]
ED = {2018: dt.date(2018, 11, 6), 2022: dt.date(2022, 11, 8), 2026: dt.date(2026, 11, 3)}
COL = {2018: "#e4572e", 2022: "#1f6fb2", 2026: "#7b3fa0"}
CSV_END = {2018: dt.date(2018, 11, 30), 2022: dt.date(2022, 11, 30), 2026: dt.date(2026, 11, 3)}
ET = dt.timezone(dt.timedelta(hours=-5))  # EST (DST ended Nov 1, 2026)
ASOF_DT = dt.datetime.now(ET)
ASOF_LBL = f"{ASOF_DT.strftime('%-I:%M')}{ASOF_DT.strftime('%p').lower()}"

def q(sql):
    return json.loads(subprocess.run(["python3", Q, "--json", sql], capture_output=True, text=True, check=True).stdout)

# ---- fresh 2026 snapshot ---------------------------------------------------------
B = "(created_at at time zone 'UTC' at time zone 'America/New_York')"
rep26 = {r["d"]: r["n"] for r in q(f"select {B}::date as d, count(*) as n from reports where created_at >= '2026-09-01' and created_at < '2026-11-05' group by 1 order by 1")}
ord26 = {r["d"]: r["n"] for r in q(f"select {B}::date as d, count(*) as n from orders   where created_at >= '2026-09-01' and created_at < '2026-11-05' group by 1 order by 1")}
don26 = {r["d"]: (r["n"], round(r["dol"] or 0)) for r in q(f"select {B}::date as d, count(*) as n, sum(amount) as dol from donations where created_at >= '2026-09-01' and created_at < '2026-11-05' group by 1 order by 1")}
SLOTX = f"4*extract(hour from {B})::int + floor(extract(minute from {B})/15)::int"
e15_26 = {}
for m in ("rep", "ord", "don"):
    tbl = {"rep": "reports", "ord": "orders", "don": "donations"}[m]
    dol = ", sum(amount) as dol" if m == "don" else ""
    rows = q(f"select {SLOTX} as slot, count(*) as n{dol} from {tbl} where created_at >= '2026-11-03 05:00' and created_at < '2026-11-04 05:00' group by 1 order by 1")
    e15_26[m] = ({r["slot"]: r["n"] for r in rows}, {r["slot"]: round(r.get("dol") or 0) for r in rows} if m == "don" else None)

# ---- static pulls ----------------------------------------------------------------
def load_static(y):
    rep = {r["d"]: r["n"] for r in json.load(open(W / f"rep{y}.json"))}
    ordn = {r["d"]: r["n"] for r in json.load(open(W / f"ord{y}.json"))}
    don = {r["d"]: (r["n"], round(r["dol"] or 0)) for r in json.load(open(W / f"don{y}.json"))}
    return rep, ordn, don

def load_e15(y):
    out = {}
    for m in ("rep", "ord", "don"):
        rows = json.load(open(W / f"e15_{m}{y}.json"))
        out[m] = ({r["slot"]: r["n"] for r in rows},
                  {r["slot"]: round(r.get("dol") or 0) for r in rows} if m == "don" else None)
    return out

DATA = {y: load_static(y) for y in (2018, 2022)}
DATA[2026] = (rep26, ord26, don26)
E15 = {y: load_e15(y) for y in (2018, 2022)}
E15[2026] = e15_26

def day(y, d):
    d = d.isoformat() if isinstance(d, dt.date) else d
    rep, ordn, don = DATA[y]
    return {"d": d, "k": (dt.date.fromisoformat(d) - ED[y]).days,
            "rep": rep.get(d, 0), "ord": ordn.get(d, 0),
            "don": don.get(d, (0, 0))[0], "dol": don.get(d, (0, 0))[1]}

# ---- E15 arrays -------------------------------------------------------------------
def e15_arr(y):
    out = {}
    for m in ("rep", "ord", "don"):
        vals, dols = E15[y][m]
        out[m] = [vals.get(s, 0) for s in range(96)]
        out["dol_don"] = [dols.get(s, 0) if dols else 0 for s in range(96)]
    return out

E15A = {y: e15_arr(y) for y in YEARS}
NOW_SLOT = max(max(s for s in range(96) if E15A[2026][m][s]) for m in ("rep", "ord", "don"))

def e15_day(y, m, upto=95): return sum(E15A[y][m][: upto + 1])
def e15_dol(y, upto=95): return sum(E15A[y]["dol_don"][: upto + 1])

# Nov 3 must come from ONE snapshot: rewrite the daily-dict entries from the e15 pull
# (the daily pull ran ~15s earlier; only Nov 3 can drift)
d3 = ED[2026].isoformat()
DATA[2026][0][d3] = e15_day(2026, "rep")
DATA[2026][1][d3] = e15_day(2026, "ord")
DATA[2026][2][d3] = (e15_day(2026, "don"), e15_dol(2026))

today = day(2026, ED[2026])
assert (today["rep"], today["ord"], today["don"]) == (e15_day(2026, "rep"), e15_day(2026, "ord"), e15_day(2026, "don"))
for y in (2018, 2022):
    d = day(y, ED[y])
    assert (d["rep"], d["ord"], d["don"]) == (e15_day(y, "rep"), e15_day(y, "ord"), e15_day(y, "don")), y
    assert abs(e15_dol(y) - d["dol"]) <= 2, (y, e15_dol(y), d["dol"])  # slotwise rounding vs single daily round
cum = {y: {m: e15_day(y, m, NOW_SLOT) for m in ("rep", "ord", "don")} for y in YEARS}
cumdol = {y: e15_dol(y, NOW_SLOT) for y in YEARS}
print("NOW_SLOT", NOW_SLOT, "cum:", {y: (cum[y]["rep"], cum[y]["ord"], cum[y]["don"], cumdol[y]) for y in YEARS})

# ---- CSV --------------------------------------------------------------------------
lines_csv = ["election_year,date_us_eastern,days_to_election_day,reports,orders,donations,donation_dollars"]
for y in YEARS:
    d = dt.date(y, 9, 1)
    while d <= CSV_END[y]:
        r = day(y, d)
        lines_csv.append(f"{y},{r['d']},{r['k']},{r['rep']},{r['ord']},{r['don']},{r['dol']}")
        d += dt.timedelta(days=1)
csv_new = "\r\n".join(lines_csv) + "\r\n"
pub_rows = {r.split(",")[1]: r for r in (PUB / "data/midterm_volume.csv").read_text().strip().splitlines()[1:]}
new_rows = {r.split(",")[1]: r for r in lines_csv[1:]}
drift = [d for d, r in pub_rows.items() if new_rows.get(d) != r]
assert all(d >= "2026-10-28" for d in drift), drift  # published 2026 tail rows were partial-day snapshots
print("CSV ok; drifted rows (expected, 2026 growth):", drift)

# ---- static SVG builder -----------------------------------------------------------
def svg_daily(y, ymax, watch):
    if watch: width, right, kmin, kmax = 1240, 1220, -63, 7
    else:     width, right, kmin, kmax = 980, 960, -45, 7
    slot = (width - 64 - 20) / (kmax - kmin + 1)
    T, ph, bottom, L = 30, 304, 334, 64
    xc = lambda k: L + slot * (k - kmin) + slot / 2
    yv = lambda v: bottom - ph * (v / ymax)
    p = []
    for i in range(1, 6):
        v = ymax * i / 5; yy = yv(v)
        p.append(f'<line x1="{L}" y1="{yy:.1f}" x2="{right}" y2="{yy:.1f}" class="grid"/><text x="56" y="{yy+4:.1f}" class="ylab" text-anchor="end">{v:,.0f}</text>')
    p.append(f'<rect x="{L}" y="{T}" width="{xc(0)-L:.1f}" height="{ph}" class="pre"/>')
    p.append(f'<line x1="{xc(0):.1f}" y1="{T}" x2="{xc(0):.1f}" y2="{bottom}" class="eday"/>')
    if not watch:
        p.append(f'<rect x="{xc(0):.1f}" y1="{T}" width="{right-xc(0):.1f}" height="{ph}" class="future"/>')
    for k in range(kmin, kmax + 1):
        r = day(y, ED[y] + dt.timedelta(days=k))
        active = [(m, r[m]) for m in ("rep", "ord", "don") if r[m] > 0]
        n = len(active); bw = slot * 0.26
        for i, (m, v) in enumerate(active):
            frac = (i + 1) / (n + 1)
            bx = xc(r["k"]) + slot * (frac - 0.5) - bw / 2
            hh = max(v / ymax * ph, 0.4)
            lab = "E-DAY" if r["k"] == 0 else (f"E{r['k']}" if r["k"] < 0 else f"E+{r['k']}")
            name = {"rep": "reports", "ord": "orders", "don": "donations"}[m]
            extra = f" (${r['dol']:,})" if m == "don" else ""
            p.append(f'<rect x="{bx:.1f}" y="{bottom-hh:.1f}" width="{bw:.1f}" height="{hh:.1f}" class="bar {m}"><title>{lab}: {v:,} {name}{extra}</title></rect>')
    p.append(f'<line x1="{L}" y1="{bottom}" x2="{right}" y2="{bottom}" class="axis"/>')
    for k in ([-63, -45, -30, -21, -14, -7, -3, 0, 7] if watch else [-45, -30, -21, -14, -7, -3, 0, 3, 7]):
        xx = xc(k); lab = "E-DAY" if k == 0 else (f"E{k}" if k < 0 else f"E+{k}")
        p.append(f'<line x1="{xx:.1f}" y1="{bottom}" x2="{xx:.1f}" y2="{bottom+5}" class="tick"/><text x="{xx:.1f}" y="{bottom+18}" class="xlab" text-anchor="middle">{lab}</text>')
    return p

# ---- E15 blob ----------------------------------------------------------------------
E15B = {"years": [{"yr": y, "color": COL[y], "rep": E15A[y]["rep"], "ord": E15A[y]["ord"],
                   "don": E15A[y]["don"], "dol": E15A[y]["dol_don"]} for y in YEARS],
        "ymax": {}, "nowSlot": NOW_SLOT, "asof": ASOF_LBL}
for m in ("rep", "ord", "don"):
    mx = max(max(E15A[y][m]) for y in YEARS)
    E15B["ymax"][m] = max(50, int(50 * round(mx * 1.12 / 50)))
print("e15 ymax:", E15B["ymax"])

# ---- text bits ----------------------------------------------------------------------
def daterange(y, k_lo, k_hi):
    t = {"rep": 0, "ord": 0, "don": 0, "dol": 0}
    for k in range(k_lo, k_hi + 1):
        r = day(y, ED[y] + dt.timedelta(days=k))
        for m in t: t[m] += r[m]
    return t

assert (daterange(2018, -45, 30)["rep"], daterange(2022, -45, 30)["rep"]) == (2345, 455)
wk18, wk22, pre18, pre22 = daterange(2018, -7, -1), daterange(2022, -7, -1), daterange(2018, -45, -8), daterange(2022, -45, -8)
wk26, tot26 = daterange(2026, -7, -1), daterange(2026, -45, 0)

through = (f'Election Day, {ASOF_LBL} ET (partial)' if ASOF_DT.date() == ED[2026]
           else f'{ASOF_DT.strftime("%b %-d")}, {ASOF_LBL} ET')
sub_hdr = ('Daily counts from production <code>pizzabase</code> (reports, orders, donations tables), bucketed by US/Eastern day. '
           'X-axes aligned on Election Day (E). <b>New: Election Day intraday — every 15 minutes, 2026 vs 2018 vs 2022</b> (next chart). '
           f'2026 data current through {through}. Generated {ASOF_DT.strftime("%a %b %-d, %Y")}.')
hr = ASOF_DT.hour  # ET hour
on_eday = ASOF_DT.date() == ED[2026]
day_done = (not on_eday) and NOW_SLOT >= 95
lead = (f'E-DAY is here (Tue Nov 3, 2026, {ASOF_LBL} ET)' if on_eday
        else f'E-Day final — pulled Wed Nov 4, {ASOF_LBL} ET' if day_done
        else f'E-Day wrap-up (Wed Nov 4, {ASOF_LBL} ET)')
if on_eday:
    surge = ("The evening surge (6–10pm ET) is still ahead." if hr < 18 else
             "The evening surge (6–10pm ET) is underway." if hr < 22 else
             "The evening surge window (6–10pm ET) has passed.")
else:
    surge = "The evening surge window (6–10pm ET) has passed — these are final E-Day tallies."
callout = (f'<div class="callout"><b>{lead}:</b> '
           f'{("E-Day so far 2026 has" if on_eday else "E-Day 2026 finished with")} '
           f'<b>{today["rep"]:,} reports / {today["ord"]:,} orders / {today["don"]:,} donations (${today["dol"]:,})</b> — versus '
           f'<b>{cum[2018]["rep"]:,} rep / {cum[2018]["ord"]:,} ord / {cum[2018]["don"]:,} don (${cumdol[2018]:,})</b> in 2018 and '
           f'<b>{cum[2022]["rep"]:,} rep / {cum[2022]["ord"]:,} ord / {cum[2022]["don"]:,} don (${cumdol[2022]:,})</b> in 2022 '
           f'<b>{("by the same time of day" if on_eday else "across the full day")}</b>. '
           f'2018 finished E-Day at 2,087 rep · 9,227 don ($312,791); 2022 at 332 rep · 1,496 don ($82,505). '
           f'E−1 (Mon Nov 2) did 83 rep / 483 don — the biggest pre-Election-Day day of 2026’s cycle. {surge}</div>')
e15_section = f'''<h2>Election Day, every 15 minutes — 2026 vs 2018 vs 2022</h2>
<div class="sub">Same-day shape of the surge: volume bucketed every 15 minutes, US/Eastern (00:00–24:00 ET), on each cycle&rsquo;s Election Day.
<span class="sw" style="background:{COL[2018]}"></span>2018 &nbsp;<span class="sw" style="background:{COL[2022]}"></span>2022 &nbsp;<span class="sw" style="background:{COL[2026]}"></span>2026 — {('the purple line ends at the data timestamp (' + ASOF_LBL + ' ET, E-Day in progress)' if on_eday else 'the purple line covers the complete day — final E-Day tallies, pulled ' + ASOF_LBL + ' ET' if day_done else 'the purple line covers Election Day (final), pulled ' + ASOF_LBL + ' ET')}.
Dashed red lines: first polls close 6:00pm ET (KY/IN), the 7:00–8:00pm ET close wave. Hover for exact quarter-hour values; chips switch metric.</div>
<div id="e15ctl"></div>
<div id="e15wrap"><div id="e15"></div><div id="e15tip"></div></div>'''

# ---- page assembly --------------------------------------------------------------------
html = (PUB / "index.html").read_text()
L_ = html.split("\n")
def find_line(pred, desc):
    for i, l in enumerate(L_):
        if pred(l): return i
    raise SystemExit("not found: " + desc)

i_sub = find_line(lambda l: l.startswith('<div class="sub">Daily counts'), "hdr sub")
i_cal = find_line(lambda l: l.startswith('<div class="callout">'), "callout")
L_[i_sub] = f'<div class="sub">{sub_hdr}</div>'
L_[i_cal] = callout
L_.insert(i_cal + 1, e15_section)

def find_after(i0, pred, desc):
    for i in range(i0, len(L_)):
        if pred(L_[i]): return i
    raise SystemExit("not found: " + desc)

# drop the duplicate 2026 watch chart (h2+sub+svg sit right above "Daily detail" — same data as
# the 2026 daily-detail chart below), its live-TODAY <script> block, and the stale legend Today swatch
drop = [
    find_after(i_cal, lambda l: l.strip() == '<h2>2026 watch — the full cycle at a glance</h2>', "watch h2"),
    find_after(i_cal, lambda l: "computed live by your browser" in l, "watch sub"),
    find_after(i_cal, lambda l: 'id="chart2026"' in l, "watch svg"),
]
assert drop == sorted(drop) and drop[2] - drop[0] == 2, drop
L_ = [l for i, l in enumerate(L_) if i not in drop]
i_vp = find_after(i_cal, lambda l: "var P = {" in l, "P var")
i_sc = max(i for i in range(i_vp + 1) if L_[i].strip() == "<script>")
i_esc = find_after(i_vp, lambda l: l.strip() == "</script>", "P script end")
del L_[i_sc:i_esc + 1]
del L_[find_after(i_cal, lambda l: 'width:3px;"></span>Today' in l, "legend today")]

# 2018/2022 daily SVGs: drop stale static TODAY line+label (today == E-DAY now)
for y, lab in ((2018, "2018 midterm"), (2022, "2022 midterm")):
    i = find_after(i_cal, lambda l, lab=lab: 'class="chart"' in l and lab in l, lab)
    l = L_[i]
    for frag in ('<line x1="731.8" y1="30" x2="731.8" y2="334" class="today"/>',
                 '<text x="726.8" y="44" class="tlab" text-anchor="end">TODAY · Oct 28, 2026 (E−6)</text>'):
        assert frag in l, frag
        l = l.replace(frag, "")
    L_[i] = l

# 2026 daily detail SVG: regenerate; ymax adaptive so an evening surge can't overflow the plot
i_svg26 = find_after(i_cal, lambda l: 'class="chart"' in l and "2026 midterm" in l, "2026 svg")
peak26 = max(today["rep"], today["ord"], today["don"])
def nice(v):
    for m in (50, 100, 250, 500):
        s = m * math.ceil(v / m)
        if s <= m * 20: return int(s)
    return int(1000 * math.ceil(v / 1000))
ym26d = max(4000, nice(peak26 * 1.15))
p = svg_daily(2026, ym26d, watch=False)
p.append(f'<text x="74" y="32" class="ptitle">2026 midterm (in progress) — Election Day Tue Nov 3 &middot; {("data through Nov 3, " + ASOF_LBL + " ET (E-Day partial)" if on_eday else "E-Day complete &middot; final pull " + ASOF_LBL + " ET")}</text>')
L_[i_svg26] = f'<svg viewBox="0 0 980 380" class="chart">{"".join(p)}</svg>'

# table
i_tbl = find_after(i_cal, lambda l: l.strip() == "<table>", "table")
i_tbl_end = find_after(i_tbl, lambda l: l.strip() == "</tbody></table>", "table end")
pct = lambda y: round(day(y, ED[y])["rep"] / daterange(y, -45, 30)["rep"] * 100)
row = lambda *c: "<tr><th>" + c[0] + "</th>" + "".join(f"<td>{x}</td>" for x in c[1:]) + "</tr>"
table = f'''<table>
<thead><tr><th>Election</th><th>E-Day reports / orders</th><th>E-Day donations</th><th>E−7→E−1 rep / don</th><th>E−45 → E−8 rep / don<br><span class="mut">(2026: E−45 → E-Day)</span></th><th>Reports on E-Day</th></tr></thead>
<tbody>
{row("2018 midterm", "2,087 / 697", "9,227<br><span class='mut'>$312,791</span>", f"{wk18['rep']:,} / {wk18['don']:,}", f"{pre18['rep']:,} / {pre18['don']:,}", f"{pct(2018)}%")}
{row("2022 midterm", "332 / 189", "1,496<br><span class='mut'>$82,505</span>", f"{wk22['rep']:,} / {wk22['don']:,}", f"{pre22['rep']:,} / {pre22['don']:,}", f"{pct(2022)}%")}
{row("2026 midterm<br><span class='mut'>" + ("in progress · E-Day · accounted so far" if on_eday else "E-Day complete · final E-Day tallies") + "</span>",
     f"{today['rep']:,} / {today['ord']:,}<br><span class='mut'>" + ("today so far, as of " if on_eday else "E-Day final, as of ") + ASOF_LBL + " ET</span>",
     f"{today['don']:,}<br><span class='mut'>${today['dol']:,} " + ("so far today" if on_eday else "final") + "</span>",
     f"{wk26['rep']:,} / {wk26['don']:,}<br><span class='mut'>complete (Oct 28–Nov 2)</span>",
     f"{tot26['rep']:,} / {tot26['don']:,}<br><span class='mut'>${tot26['dol']:,} E−45 → E-Day</span>",
     "<span class='mut'>TBD<br>(" + ("day in progress" if on_eday else "post-E-Day tail to come") + ")</span>")}
</tbody></table>'''
L_[i_tbl:i_tbl_end + 1] = table.split("\n")

# var D
i_varD = find_after(i_cal, lambda l: l.strip().startswith("var D = {"), "var D")
varD_pub = L_[i_varD].strip()
i1 = varD_pub.index('{"yr": 2018'); i2 = varD_pub.index('{"yr": 2022')
i3 = varD_pub.index('{"yr": 2026'); i4 = varD_pub.index('], "kmin')
y18 = varD_pub[i1:i2].rstrip().rstrip(',').strip()
y22 = varD_pub[i2:i3].rstrip().rstrip(',').strip()
y26old = varD_pub[i3:i4].strip()
assert y18.startswith('{"yr": 2018') and y18.endswith('}') and '"yr": 2022' not in y18
assert y22.startswith('{"yr": 2022') and y22.endswith('}') and '"yr": 2026' not in y22
assert y26old.startswith('{"yr": 2026') and y26old.endswith('}')
PT = re.compile(r'\{"k": (-?\d+), "date": "([\d-]+)", "rep": (\d+), "ord": (\d+), "don": (\d+), "dol": (\d+)\}')
def pts_from(blob):
    pts = re.search(r'"points": \[(.*)\]', blob).group(1)
    return [{"k": int(g[0]), "date": g[1], "rep": int(g[2]), "ord": int(g[3]), "don": int(g[4]), "dol": int(g[5])} for g in PT.findall(pts)]
for y, blob in ((2018, y18), (2022, y22), (2026, y26old)):
    pts = pts_from(blob)
    assert pts[0]["k"] == -45 and pts[-1]["k"] == (7 if y != 2026 else -6)
    for pt in pts:
        d = day(y, ED[y] + dt.timedelta(days=pt["k"]))
        if y != 2026 or pt["k"] < -6:
            assert (d["rep"], d["ord"], d["don"], d["dol"]) == (pt["rep"], pt["ord"], pt["don"], pt["dol"]), (y, pt)
        else:
            assert (d["rep"], d["ord"], d["don"]) >= (pt["rep"], pt["ord"], pt["don"]), (pt,)
print("published var D points verified vs DB")
pts26 = [{"k": k, "date": (ED[2026] + dt.timedelta(days=k)).isoformat(), **{m2: day(2026, ED[2026] + dt.timedelta(days=k))[m2] for m2 in ("rep", "ord", "don", "dol")}} for k in range(-45, 1)]
jpts = "[" + ", ".join(json.dumps(p2) for p2 in pts26) + "]"
todayLabel = "TODAY · Nov 3, 2026 (E-DAY)"
L_[i_varD] = ('  var D = {"years": [' + y18 + ", " + y22 + ', {"yr": 2026, "color": "#7b3fa0", "edate": "2026-11-03", "points": ' + jpts + '}], '
              f'"kmin": -45, "kmax": 7, "todayK": 0, "todayLabel": "{todayLabel}", "surgeLabel": ""}};')

# takeaway
i_take = find_after(i_cal, lambda l: l.startswith('<div class="sub" style="margin-top:14px">Takeaway:'), "takeaway")
take_2026 = (f'2026 is living it right now: {today["rep"]:,} reports and {today["don"]:,} donations (${today["dol"]:,}) by {ASOF_LBL} ET, '
             'with the evening close-of-polls surge (6–10pm ET) — the tall spikes in the 15-minute chart above — still ahead.' if on_eday else
             f'2026 lived it: {today["rep"]:,} reports and {today["don"]:,} donations (${today["dol"]:,}) on E-Day, '
             'with the evening close-of-polls surge (6–10pm ET) showing as the tall spikes in the 15-minute chart above.')
L_[i_take] = ('<div class="sub" style="margin-top:14px">Takeaway: midterm demand is overwhelmingly an Election-Day phenomenon — reports ramp only in the final ~4 days, '
              'then spike 10–20×. Donations ramp earlier (~E−10) and hit 4–5× report volume on E-Day ($313K in 2018, $83K in 2022). '
              f'{take_2026}</div>')

html_new = "\n".join(L_)

# comp-script patches: surge label; suppress today line when todayK==0 (overlaps E-DAY)
assert 'fl.textContent = "2026 surge happens here \\u2192";' in html_new
html_new = html_new.replace('fl.textContent = "2026 surge happens here \\u2192";', 'fl.textContent = D.surgeLabel || "";')
tb_old = '''    el("line", {x1: tx, y1: T, x2: tx, y2: T + PH, "class": "today"}, svg);
    var tl = el("text", {x: tx + 6, y: T + 16, "class": "tlab"}, svg);
    tl.textContent = D.todayLabel;'''
tb_new = '''    if (D.todayK !== 0) {
      el("line", {x1: tx, y1: T, x2: tx, y2: T + PH, "class": "today"}, svg);
      var tl = el("text", {x: tx + 6, y: T + 16, "class": "tlab"}, svg);
      tl.textContent = D.todayLabel;
    }'''
assert tb_old in html_new
html_new = html_new.replace(tb_old, tb_new)

# CSS additions
css_add = ''' #e15wrap { position:relative; max-width:1240px; background:#fff; border:1px solid #e5e0d8; border-radius:8px; margin: 6px 0 18px; }
 #e15tip { position:absolute; display:none; pointer-events:none; background:#fffefb; border:1px solid #d8d2c8; border-radius:6px; box-shadow:0 2px 8px rgba(0,0,0,.12); padding:8px 10px; font-size:12px; z-index:5; max-width:360px; }
 #e15tip .th { font-weight:700; margin-bottom:5px; color:#444; }
 #e15tip .tr { white-space:nowrap; padding:1.5px 0; }
 #e15tip .tr.dim { color:#aaa; }
 #e15tip .dot { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:6px; }
 #e15tip .dol { color:#b8860b; }
 .close { stroke:#b3261e; stroke-width:1.2; stroke-dasharray:3 4; opacity:.55; }
 .closelab { font-size:10.5px; fill:#b3261e; font-weight:700; }
 .chip.metric.active { background:#7b3fa0; color:#fff; border-color:#7b3fa0; }
</style>'''
html_new = html_new.replace("</style>", css_add, 1)

# E15 script (inserted before </body>)
E15_JSON = json.dumps(E15B, separators=(",", ":"))
e15_js = f'''<script>
(function () {{
  var E15 = {E15_JSON};
  var MET = [{{key: "rep", label: "Reports"}}, {{key: "ord", label: "Orders"}}, {{key: "don", label: "Donations"}}];
  var W = 1240, H = 460, L = 78, R = 26, T = 52, B = 64, PW = W - L - R, PH = H - T - B, SLOT = PW / 96;
  var state = {{metric: "rep"}};
  var NS = "http://www.w3.org/2000/svg";
  var cont = document.getElementById("e15");
  var tip = document.getElementById("e15tip");
  function el(tag, attrs, parent) {{
    var e = document.createElementNS(NS, tag);
    for (var a in attrs) e.setAttribute(a, attrs[a]);
    if (parent) parent.appendChild(e);
    return e;
  }}
  function x(s) {{ return L + SLOT * (s + 0.5); }}
  function xh(h) {{ return L + PW * h / 24; }}
  function fmt(n) {{ return n.toLocaleString("en-US"); }}
  function money(n) {{ return "$" + Math.round(n).toLocaleString("en-US"); }}
  function tclk(s) {{
    var h = Math.floor(s / 4), m = 15 * (s % 4), hh = h % 12 === 0 ? 12 : h % 12;
    return hh + ":" + (m < 10 ? "0" : "") + m + (h < 12 ? "am" : "pm");
  }}
  function ym() {{ return E15.ymax[state.metric]; }}
  function y(v) {{ return v <= 0 ? T + PH : T + PH - PH * v / ym(); }}
  function render() {{
    while (cont.firstChild) cont.removeChild(cont.firstChild);
    var svg = el("svg", {{viewBox: "0 0 " + W + " " + H, "class": "ichart"}}, cont);
    for (var i = 1; i <= 5; i++) {{
      var v = ym() * i / 5, yy = y(v);
      el("line", {{x1: L, y1: yy, x2: W - R, y2: yy, "class": "grid"}}, svg);
      var t = el("text", {{x: L - 8, y: yy + 4, "class": "ylab", "text-anchor": "end"}}, svg);
      t.textContent = fmt(v);
    }}
    var yl2 = el("text", {{x: 16, y: T + 16, "class": "ylab2"}}, svg);
    yl2.textContent = state.metric + " / 15 min";
    var HL = ["12a", "3a", "6a", "9a", "noon", "3p", "6p", "9p", "12a"];
    for (var h = 0; h <= 24; h += 3) {{
      var xx = xh(h);
      el("line", {{x1: xx, y1: T + PH, x2: xx, y2: T + PH + 5, "class": "tick"}}, svg);
      var t2 = el("text", {{x: xx, y: T + PH + 20, "class": "xlab", "text-anchor": "middle"}}, svg);
      t2.textContent = HL[h / 3];
    }}
    el("line", {{x1: L, y1: T + PH, x2: W - R, y2: T + PH, "class": "axis"}}, svg);
    [[18, "first polls close"], [20, "most polls closed"]].forEach(function (c) {{
      var xx = xh(c[0]);
      el("line", {{x1: xx, y1: T + 18, x2: xx, y2: T + PH, "class": "close"}}, svg);
      var t3 = el("text", {{x: c[0] === 18 ? xx - 5 : xx + 5, y: T + 12, "class": "closelab", "text-anchor": c[0] === 18 ? "end" : "start"}}, svg);
      t3.textContent = c[1] + " " + (c[0] % 12 === 0 ? 12 : c[0] % 12) + (c[0] < 12 ? "am" : "pm") + " ET";
    }});
    E15.years.forEach(function (Y) {{
      var last = Y.yr === 2026 ? E15.nowSlot : 95;
      var d = "";
      for (var s = 0; s <= last; s++) d += (s === 0 ? "M" : "L") + x(s).toFixed(1) + "," + y(Y[state.metric][s]).toFixed(1);
      el("path", {{d: d, "class": "cline l" + Y.yr}}, svg);
      for (var s2 = 0; s2 <= last; s2++)
        if (Y[state.metric][s2] > 0) el("circle", {{r: 2.4, cx: x(s2).toFixed(1), cy: y(Y[state.metric][s2]).toFixed(1), "class": "mk l" + Y.yr}}, svg);
    }});
    var Y26 = E15.years[2], nv = Y26[state.metric][E15.nowSlot];
    var nx = x(E15.nowSlot), ny = y(nv);
    el("circle", {{r: 4.5, cx: nx.toFixed(1), cy: ny.toFixed(1), "class": "hmk l2026"}}, svg);
    var nt = el("text", {{x: nx > 900 ? nx - 8 : nx + 8, y: Math.max(ny - 10, T + 14), "class": "tlab", "text-anchor": nx > 900 ? "end" : "start"}}, svg);
    nt.textContent = "now \\u00b7 " + E15.asof + " ET";
    var cross = el("g", {{style: "display:none"}}, svg);
    var vline = el("line", {{y1: T, y2: T + PH, "class": "cross"}}, cross);
    var cap = el("rect", {{x: L, y: T, width: PW, height: PH, fill: "transparent"}}, svg);
    cap.addEventListener("mousemove", function (ev) {{
      var r = svg.getBoundingClientRect();
      var mx = (ev.clientX - r.left) * (W / r.width);
      var s = Math.max(0, Math.min(95, Math.round((mx - L) / SLOT - 0.5)));
      cross.style.display = "";
      vline.setAttribute("x1", x(s)); vline.setAttribute("x2", x(s));
      var rows = "";
      E15.years.forEach(function (Y) {{
        if (Y.yr === 2026 && s > E15.nowSlot) {{
          rows += '<div class="tr dim"><span class="dot" style="background:' + Y.color + '"></span><b>2026</b> \\u2014 no data yet (E-Day in progress)</div>';
          return;
        }}
        var cum = 0; for (var i2 = 0; i2 <= s; i2++) cum += Y[state.metric][i2];
        rows += '<div class="tr"><span class="dot" style="background:' + Y.color + '"></span><b>' + Y.yr + '</b> &nbsp;' +
          fmt(Y.rep[s]) + ' rep \\u00b7 ' + fmt(Y.ord[s]) + ' ord \\u00b7 ' + fmt(Y.don[s]) + ' don <span class="dol">(' + money(Y.dol[s]) + ')</span>' +
          ' &nbsp;\\u00b7&nbsp; day so far: <b>' + fmt(cum) + '</b> ' + state.metric + '</div>';
      }});
      tip.innerHTML = '<div class="th">' + tclk(s) + " \\u2013 " + tclk((s + 1) % 96) + " ET \\u00b7 quarter-hour " + (s + 1) + "/96</div>" + rows;
      tip.style.display = "block";
      var cr = cont.getBoundingClientRect();
      var px = ev.clientX - cr.left + 16, py = ev.clientY - cr.top + 14;
      if (px + tip.offsetWidth > cr.width - 8) px = ev.clientX - cr.left - tip.offsetWidth - 16;
      if (py + tip.offsetHeight > cr.height - 8) py = ev.clientY - cr.top - tip.offsetHeight - 14;
      tip.style.left = px + "px"; tip.style.top = py + "px";
    }});
    cap.addEventListener("mouseleave", function () {{ cross.style.display = "none"; tip.style.display = "none"; }});
  }}
  var ctl = document.getElementById("e15ctl");
  MET.forEach(function (M) {{
    var b = document.createElement("button");
    b.className = "chip metric" + (M.key === state.metric ? " active" : "");
    b.textContent = M.label;
    b.onclick = function () {{
      state.metric = M.key;
      ctl.querySelectorAll(".metric").forEach(function (b2) {{ b2.classList.remove("active"); }});
      b.classList.add("active");
      render();
    }};
    ctl.appendChild(b);
  }});
  render();
}})();
</script>

</body>'''
html_new = html_new.replace("\n</body>", "\n" + e15_js, 1)

(OUT / "index.html").write_text(html_new)
(OUT / "data/midterm_volume.csv").write_text(csv_new)
print("wrote", OUT / "index.html", len(html_new), "bytes; csv", len(csv_new), "bytes")