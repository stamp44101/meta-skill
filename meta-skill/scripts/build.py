#!/usr/bin/env python3
"""Merge a Meta SKILL run into the living memory and rebuild the page.

    python3 -I build.py <out_dir> [run.json ...]
    python3 -I build.py trim <capture.png> <out_dir>/images/<library_id>.png
    python3 -I build.py check-images <out_dir>      (needs tesseract)
    python3 -I build.py import <export file> <Brand> "<own page names>" <YYYY-MM-DD>  > draft.json
    python3 -I build.py geo-ids <out_dir> <Brand>            prints the line that loads the brand's IDs into the tab
    python3 -I build.py geo <out_dir> <results file> <YYYY-MM-DD>   fills `countries` from per-country checks

<out_dir> is meta-<brand>/ (e.g. meta-sher/). It holds:
    meta-<brand>.tsv   one row per kept ad, keyed by Library ID (the memory)
    types-log.tsv      every new type, merge, split and rename, with the reason
    runs-log.tsv       every brand search: when, how, found, kept
    geo-log.tsv        every per-country check: brand, country, results, cards loaded, kept ads seen
    images/<id>.png    one snapshot grid per ad
    meta-<brand>.html  rebuilt on every call from the files above; opens on its own

run.json (written by the agent during a run):
{
  "date": "2026-11-25",
  "searches": [{"brand": "Bupbes", "how": "page 1234 | phrase \\"bupbes\\"", "found": 830, "kept": 41, "note": ""}],
  "ads": [{"id": "...", "brand": "Bupbes", "advertiser": "Bupbes", "page_id": "...", "owner": "own|other",
           "type": "creator-fronted", "status": "active|ended", "start": "YYYY-MM-DD", "end": "",
           "creatives": 2, "versions": false, "format": "video", "media": 1, "video_sec": 13,
           "eu_reach": "", "countries": "", "body": "...", "cta": "", "image": "images/<id>.png", "note": ""}],
  "types_log": [{"action": "new|merge|split|rename", "from": "a, b", "to": "c", "reason": "..."}],
  "retype": {"<id>": "<type>"}
}
Only the standard library and Pillow are used.
"""
import base64, csv, io, json, math, os, sys
from datetime import date

COLS = ["library_id", "brand", "advertiser", "page_id", "owner", "type", "status", "start", "end",
        "days", "creatives", "versions", "format", "media", "video_sec", "eu_reach", "countries",
        "score", "body", "cta", "image", "creative_hash", "first_seen", "last_seen", "note"]
MIN_DAYS = 30        # decision 2: newer ads are never saved
DAY_CAP = 180        # days count up to this
PER_CREATIVE = 5     # points for every extra ad using the same creative (kept small: copies are cheap)
CREATIVE_CAP = 10    # ...counted up to 10 extra ads
TOP_N = 3            # a group is scored on the best ad of each of its top N brands
SHOW_PER_BRAND = 4   # a group shows each brand's best 4 ads; the rest sit behind "show more"
FLIGHT_MIN = 5       # this many ads from one brand ending within FLIGHT_DAYS of each other = a campaign end, flagged
FLIGHT_DAYS = 3
PER_BRAND = 20       # points for every extra brand running the type
# markets checked one by one with the Ad Library country filter (README: Open for discuss 4)
MARKETS = "TH VN SG MY ID PH HK TW KR JP AU NZ US CA GB IN AE KH FR DE".split()
GL = ["date", "brand", "country", "results", "cards", "complete", "seen"]


def read_tsv(path, cols):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [{c: r.get(c, "") for c in cols} for r in csv.DictReader(f, delimiter="\t")]


def write_tsv(path, rows, cols):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: str(r.get(c, "")).replace("\t", " ").replace("\n", " ") for c in cols})


def dhash(path):
    """64-bit difference hash of an image, as hex. Empty if the image is missing."""
    try:
        from PIL import Image
        im = Image.open(path).convert("L")
        im = im.crop((0, im.height // 10, im.width, im.height))  # skip the caption line
        im = im.resize((9, 8))
        px = list(im.tobytes())
        bits = "".join("1" if px[r * 9 + c] > px[r * 9 + c + 1] else "0" for r in range(8) for c in range(8))
        return "%016x" % int(bits, 2)
    except Exception:
        return ""


def first_tile_hash(path):
    """dHash of the first card or frame of a grid, so one picture shown as a single image and as
    the first card of a carousel still matches."""
    try:
        from PIL import Image
        im = Image.open(path).convert("L")
        h = im.height
        top = int(h * 0.1)
        t = im.crop((6, top, 6 + int((h - top) * 0.78), h - 4)).resize((9, 8))
        px = list(t.tobytes())
        bits = "".join("1" if px[r * 9 + c] > px[r * 9 + c + 1] else "0" for r in range(8) for c in range(8))
        return "%016x" % int(bits, 2)
    except Exception:
        return ""


def hamming(a, b):
    return bin(int(a, 16) ^ int(b, 16)).count("1") if a and b else 99


def days_of(r, today):
    try:
        s = date.fromisoformat(r["start"])
        # an ad still running counts up to the day it was last seen live, not the build day
        e = date.fromisoformat(r["end"] or r.get("last_seen") or today.isoformat()) if (r.get("end") or r.get("last_seen")) else today
        return max(0, (e - s).days)
    except Exception:
        return 0


def eu_points(reach):
    try:
        n = int(float(reach))
    except Exception:
        return 0
    return 20 if n >= 100_000 else 10 if n >= 10_000 else 0


def score(r):
    extra = min(max(int(r.get("creatives") or 1) - 1, 0), CREATIVE_CAP)
    return (min(int(r["days"]), DAY_CAP) + PER_CREATIVE * extra
            + (10 if str(r.get("versions")).lower() in ("true", "1", "yes") else 0) + eu_points(r.get("eu_reach")))


def merge(out, run, rows, types_log, runs_log):
    today = date.fromisoformat(run.get("date") or date.today().isoformat())
    by_id = {r["library_id"]: r for r in rows}
    added = updated = skipped = 0
    for a in run.get("ads", []):
        a = dict(a)
        a["library_id"] = str(a.pop("id", a.get("library_id", "")))
        img = a.get("image") or ""
        a["creative_hash"] = dhash(os.path.join(out, img)) if img else ""
        a["days"] = days_of(a, today)
        a["versions"] = "yes" if a.get("versions") in (True, "true", "yes", 1, "1") else "no"
        if a["days"] < MIN_DAYS:
            skipped += 1
            continue
        hit = by_id.get(a["library_id"])
        alias = False
        if not hit:  # the same creative shown under another Library ID (Meta groups change between runs)
            hit = next((r for r in rows if r["brand"] == a.get("brand") and (
                a["library_id"] in r.get("note", "")
                or hamming(r["creative_hash"], a["creative_hash"]) <= 6)), None)
            alias = bool(hit)
        if hit and alias:
            if a["library_id"] not in hit.get("note", ""):
                hit["note"] = (hit.get("note", "") + f" also shown as {a['library_id']}").strip()
            # one creative, one row: widest dates, the larger creative count, active if either is
            hit["start"] = min(hit["start"], a["start"]) if hit.get("start") and a.get("start") else hit.get("start") or a.get("start")
            if "active" in (hit.get("status"), a.get("status")):
                hit["status"], hit["end"] = "active", ""
            else:
                hit["end"] = max(hit.get("end") or "", a.get("end") or "")
            hit["creatives"] = max(int(hit.get("creatives") or 1), int(a.get("creatives") or 1))
            for k in ("eu_reach", "countries", "video_sec"):
                hit[k] = hit.get(k) or a.get(k, "")
            hit["last_seen"] = today.isoformat()
            updated += 1
        elif hit:
            keep_type = hit.get("type")
            for k, v in a.items():
                if k in ("library_id", "first_seen", "note", "type") or v in ("", None):
                    continue
                hit[k] = v
            hit["type"] = a.get("type") or keep_type
            hit["last_seen"] = today.isoformat()
            updated += 1
        else:
            a["first_seen"] = a["last_seen"] = today.isoformat()
            rows.append(a)
            by_id[a["library_id"]] = a
            added += 1
    for lid, t in (run.get("retype") or {}).items():
        if lid in by_id:
            by_id[lid]["type"] = t
    for e in run.get("types_log", []):
        e = {"date": today.isoformat(), **{k: str(v) for k, v in e.items()}}
        if e in types_log:  # the same run merged twice
            continue
        types_log.append(e)
        if e.get("action") in ("merge", "rename") and e.get("to"):
            olds = [s.strip() for s in str(e.get("from", "")).split(",") if s.strip()]
            for r in rows:
                if r.get("type") in olds:
                    r["type"] = e["to"]
    for s in run.get("searches", []):
        s = {"date": today.isoformat(), **{k: str(v) for k, v in s.items()}}
        if s not in runs_log:
            runs_log.append(s)
    return today, added, updated, skipped


def rescore(rows, today):
    from collections import Counter
    from datetime import date as _d
    ended = [r for r in rows if r.get("status") == "ended" and r.get("end")]
    copies = Counter((r["brand"], norm(r.get("body", ""))) for r in rows)
    for r in rows:
        r["days"] = days_of(r, today)
        r["score"] = score(r)
        r["_flight"] = ""
        if r.get("status") == "ended" and r.get("end"):
            e = _d.fromisoformat(r["end"])
            near = [x for x in ended if x["brand"] == r["brand"] and abs((_d.fromisoformat(x["end"]) - e).days) <= FLIGHT_DAYS]
            if len(near) >= FLIGHT_MIN:
                lo = min(x["end"] for x in near); hi = max(x["end"] for x in near)
                r["_flight"] = (f"ended with {len(near) - 1} other {r['brand']} ads between {lo} and {hi} "
                                "(a campaign end, not a verdict on this ad)")
        same = [x for x in rows if x is not r and x["brand"] == r["brand"] and norm(x.get("body", "")) == norm(r.get("body", "")) and norm(r.get("body", ""))]
        if same:
            twin = sum(1 for x in same if hamming(x.get("_ft", ""), r.get("_ft", "")) <= 3)
            other = len(same) - twin
            bits = []
            if other:
                bits.append(f"same copy as {other} other ad{'s' if other > 1 else ''} here with a different picture")
            if twin:
                bits.append(f"same copy and picture as {twin} other ad{'s' if twin > 1 else ''} here in another format")
            r["_copies"] = "; ".join(bits)
        else:
            r["_copies"] = ""


def rank(rows):
    groups = {}
    for r in rows:
        groups.setdefault(r.get("type") or "untyped", []).append(r)
    ranked = []
    for t, ads in groups.items():
        ads.sort(key=lambda r: -int(r["score"]))
        best = {}
        for r in ads:  # each brand's best ad, so one big brand can't carry a type alone
            best.setdefault(r["brand"], int(r["score"]))
        top = sorted(best.values(), reverse=True)[:TOP_N]
        brands = sorted(best)
        gscore = round(sum(top) / len(top) + PER_BRAND * (len(brands) - 1))
        ranked.append((gscore, t, brands, ads))
    ranked.sort(key=lambda g: -g[0])
    return ranked


def thumb(path, h=360):
    try:
        from PIL import Image
        im = Image.open(path).convert("RGB")
        if im.height > h:
            im = im.resize((round(im.width * h / im.height), h))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=72)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def esc(s):
    return (str(s).replace("\ufffd", " ").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def life(r):
    d = int(r["days"])
    return f"at least {d} days, still running" if r.get("status") == "active" else f"ran {d} days, ended {r.get('end')}"


def median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else ""


def group_stats(ads):
    from collections import Counter
    n = len(ads)
    fm = Counter(("video" if "video" in r["format"] else r["format"]) for r in ads)
    vids = [int(float(r["video_sec"])) for r in ads if str(r.get("video_sec", "")).strip() not in ("", "0")]
    parts = [", ".join(f"{k} {round(100 * v / n)}%" for k, v in fm.most_common())]
    if vids:
        parts.append(f"videos ~{median(vids)}s")
    parts.append(f"median run {median([int(r['days']) for r in ads])} days")
    live = sum(r.get("status") == "active" for r in ads)
    if live:
        parts.append(f"{live} still running")
    return " · ".join(parts)


def geo_ids(out, brand):
    """Print the JS line that stores the brand's kept IDs (and their alias IDs) in the tab; save the order."""
    import re
    name = os.path.basename(os.path.abspath(out))
    rows = [r for r in read_tsv(os.path.join(out, f"{name}.tsv"), COLS) if r["brand"] == brand]
    if not rows:
        sys.exit(f"no rows for {brand}")
    pairs = []
    for r in rows:
        for i in [r["library_id"]] + re.findall(r"\d{14,17}", r.get("note", "")):
            pairs.append([i, r["library_id"]])
    path = os.path.join(out, "geo-ids.json")
    allids = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    allids[brand] = pairs
    with open(path, "w", encoding="utf-8") as f:
        json.dump(allids, f, ensure_ascii=False)
    ids = " ".join(i for i, _ in pairs)
    print(f"window.name=JSON.stringify({{b:{json.dumps(brand)},W:'{ids}'.split(' ')}});'set'")


def geo(out, results, day):
    """Read `#Brand|CC t=.. n=.. done=.. hit=i.j.k` lines (indexes into geo-ids.json), fill `countries`, log every check.
    Several checks of one country add up: a long page often loads more cards on a second pass."""
    import re
    name = os.path.basename(os.path.abspath(out))
    ids = json.load(open(os.path.join(out, "geo-ids.json"), encoding="utf-8"))
    tsv = os.path.join(out, f"{name}.tsv")
    rows = read_tsv(tsv, COLS)
    checks = {}
    for line in open(results, encoding="utf-8"):
        m = re.match(r"#(.+?)\|(\w+) t=(\S*) n=(\d+) done=(\w+) hit=(\S*)", line.strip())
        if not m or m.group(2) == "ALL" or m.group(1) not in ids:
            continue
        b, cc, t, n, done, h = m.groups()
        c = checks.setdefault((b, cc), {"hits": set(), "t": t, "n": 0, "done": False})
        c["hits"] |= {int(x) for x in h.split(".") if x}
        c["n"], c["t"] = max(c["n"], int(n)), t or c["t"]
        c["done"] = c["done"] or done == "true"
    seen = {}
    for (b, cc), c in checks.items():
        for i in c["hits"]:
            seen.setdefault(ids[b][i][1], set()).add(cc)
    order = {c: k for k, c in enumerate(MARKETS)}
    checked_brands = {b for b, _ in checks}
    for r in rows:
        if r["brand"] in checked_brands:
            have = {x.strip() for x in r.get("countries", "").split(",") if x.strip()} | seen.get(r["library_id"], set())
            r["countries"] = ", ".join(sorted(have, key=lambda c: (order.get(c, 99), c)))
    write_tsv(tsv, rows, COLS)
    gl = os.path.join(out, "geo-log.tsv")
    log = read_tsv(gl, GL)
    for (b, cc), c in sorted(checks.items(), key=lambda x: (x[0][0], order.get(x[0][1], 99))):
        kept_here = len({ids[b][i][1] for i in c["hits"]})
        log.append({"date": day, "brand": b, "country": cc, "results": c["t"], "cards": c["n"],
                    "complete": "yes" if c["done"] else "no", "seen": kept_here})
    write_tsv(gl, log, GL)
    for b in sorted(checked_brands):
        mine = [r for r in rows if r["brand"] == b]
        print(f"{b}: {sum(1 for r in mine if r['countries'])}/{len(mine)} kept ads seen in at least one of "
              f"{len({cc for bb, cc in checks if bb == b})} countries")


def markets_table(out, rows, brands):
    """Brand x country: kept ads seen there. Only countries where something was seen get a column."""
    log = read_tsv(os.path.join(out, "geo-log.tsv"), GL)
    if not log:
        return ""
    checked = {}
    for e in log:
        checked.setdefault(e["brand"], set()).add(e["country"])
    order = {c: k for k, c in enumerate(MARKETS)}
    seen_any = {c for r in rows for c in (x.strip() for x in r.get("countries", "").split(",")) if c}
    all_checked = set().union(*checked.values())
    # every core market that was checked shows, zeros included (a 0 is a market nobody here is buying);
    # extra markets show only where something was seen, the rest are named under the table
    cols = sorted({c for c in all_checked if c in order} | seen_any, key=lambda c: (order.get(c, 99), c))
    extra_zero = {b: sorted(c for c in cs if c not in cols) for b, cs in checked.items()}
    body = []
    for b in brands:
        mine = [r for r in rows if r["brand"] == b]
        if b not in checked:
            body.append(f'<tr><th>{esc(b)}</th><td colspan="{len(cols) + 1}" class="nil">not checked</td></tr>')
            continue
        cells = []
        for c in cols:
            n = sum(1 for r in mine if c in {x.strip() for x in r.get("countries", "").split(",")})
            cells.append(f'<td>{n}</td>' if n else ('<td class="nil">0</td>' if c in checked[b] else '<td class="nil">·</td>'))
        unseen = sum(1 for r in mine if not r.get("countries"))
        body.append(f'<tr><th>{esc(b)} <small>({len(mine)})</small></th>{"".join(cells)}<td>{unseen}</td><td>{len(checked[b])}</td></tr>')
    return (f'<h2>Where the kept ads ran <small>kept ads seen in each country with the Ad Library country filter</small></h2>'
            f'<div class="scroll"><table class="mx"><tr><th>brand (kept)</th>{"".join(f"<th>{c}</th>" for c in cols)}<th>not seen</th><th>countries checked</th></tr>{"".join(body)}</table></div>'
            f'<p class="stats">One ad can run in several countries, so a row adds up to more than its kept ads. '
            f'{"".join(f"{esc(b)} also checked {', '.join(cs)}: none seen. " for b, cs in sorted(extra_zero.items()) if cs)}'
            f'"Not seen" means the country filter did not show it in any country checked: it may have run elsewhere, '
            f'or long pages stopped loading before reaching it. 0 = checked, none seen; · = not checked. Every check is in geo-log.tsv.</p>')


def html(out, name, rows, types_log, runs_log, today, notes=None):
    notes = notes or {}
    ranked = rank(rows)
    brands = sorted({r["brand"] for r in rows})
    # brand x type matrix: count / best score
    mrows = []
    for gscore, t, gbrands, ads in ranked:
        cells = []
        for b in brands:
            mine = [int(r["score"]) for r in ads if r["brand"] == b]
            cells.append(f'<td>{len(mine)} <small>· {max(mine)}</small></td>' if mine else '<td class="nil">–</td>')
        mrows.append(f'<tr><th>{esc(t)}</th>{"".join(cells)}</tr>')
    totals = "".join(f'<td><b>{sum(r["brand"] == b for r in rows)}</b></td>' for b in brands)
    matrix = (f'<div class="scroll"><table class="mx"><tr><th>type \\ brand: ads · best score</th>{"".join(f"<th>{esc(b)}</th>" for b in brands)}</tr>'
              f'{"".join(mrows)}<tr><th>all</th>{totals}</tr></table></div>')
    parts = []
    for gi, (gscore, t, gbrands, ads) in enumerate(ranked, 1):
        cards = []
        seen = {}
        for i, r in enumerate(ads, 1):
            seen[r["brand"]] = seen.get(r["brand"], 0) + 1
            extra = seen[r["brand"]] > SHOW_PER_BRAND
            src = thumb(os.path.join(out, r["image"])) if r.get("image") else ""
            img = f'<img src="{src}" alt="">' if src else '<div class="noimg">no snapshot</div>'
            meta = [life(r), f'{r["creatives"]} ads use this creative' if int(r.get("creatives") or 1) > 1 else "",
                    "multiple versions" if r.get("versions") == "yes" else "",
                    r.get("format", "") + (f' · {r["video_sec"]}s' if r.get("video_sec") else ""),
                    f'EU reach {int(float(r["eu_reach"])):,}' if r.get("eu_reach") else "",
                    ("seen in " + r["countries"]) if r.get("countries") else ""]
            flags = [f for f in (r.get("_flight"), r.get("_copies")) if f]
            cards.append(
                f'<article data-brand="{esc(r["brand"])}"{" class=more" if extra else ""}><div class="snap">{img}</div><div class="info">'
                f'<div class="top"><span class="rank">#{i}</span><b>{esc(r["brand"])}</b>'
                f'<span class="tag {esc(r.get("owner", ""))}">{"own ad" if r.get("owner") == "own" else "by " + esc(r.get("advertiser", ""))}</span>'
                f'<span class="score">{r["score"]}</span></div>'
                f'<div class="meta">{" · ".join(esc(m) for m in meta if m)}</div>'
                f'{"".join(f"<div class=flag>{esc(x)}</div>" for x in flags)}'
                f'<p>{esc(r.get("body", ""))}</p>'
                f'<a href="https://www.facebook.com/ads/library/?id={esc(r["library_id"])}" target="_blank" rel="noopener">Library ID {esc(r["library_id"])}</a>'
                f'{" · " + esc(r["note"]) if r.get("note") else ""}</div></article>')
        hidden = sum(1 for c in cards if " class=more" in c)
        nt = notes.get(t, {})
        note = (f'<div class="note"><p><b>What it is:</b> {esc(nt.get("takeaway", ""))}</p>'
                f'<p><b>SHER test:</b> {esc(nt.get("sher_test", ""))}</p></div>') if nt else ""
        more = f'<button class="showmore">show {hidden} more (each brand capped at {SHOW_PER_BRAND})</button>' if hidden else ""
        parts.append(f'<section><h2><span class="rank">{gi}</span>{esc(t)}<small>group score {gscore} · '
                     f'{len(ads)} ads · {len(gbrands)} brand{"s" if len(gbrands) > 1 else ""}: {esc(", ".join(gbrands))}</small></h2>'
                     f'<div class="stats">{esc(group_stats(ads))}</div>{note}'
                     f'<div class="grid">{"".join(cards)}</div>{more}</section>')
    runs = "".join(f'<tr><td>{esc(s.get("date"))}</td><td>{esc(s.get("brand"))}</td><td>{esc(s.get("how"))}</td>'
                   f'<td>{esc(s.get("found"))}</td><td>{esc(s.get("kept"))}</td><td>{esc(s.get("under_30", ""))}</td><td>{esc(s.get("note"))}</td></tr>' for s in runs_log[::-1])
    tlog = "".join(f'<tr><td>{esc(e.get("date"))}</td><td>{esc(e.get("action"))}</td><td>{esc(e.get("from"))}</td>'
                   f'<td>{esc(e.get("to"))}</td><td>{esc(e.get("reason"))}</td></tr>' for e in types_log[::-1])
    cut = [(x.get("brand"), x.get("under_30")) for x in runs_log if x.get("under_30")]
    cut_line = (" (left out: " + ", ".join(f"{b} {n}" for b, n in cut) + ")") if cut else ""
    eu_n = sum(1 for r in rows if r.get("eu_reach"))
    chips = "".join(f'<button data-b="{esc(b)}">{esc(b)}</button>' for b in brands)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(name)} — competitor Meta ads</title><style>
:root{{--bg:#faf9f7;--fg:#1d1b19;--mute:#77716b;--line:#e6e1da;--card:#fff;--acc:#8a2b3a}}
@media(prefers-color-scheme:dark){{:root{{--bg:#151413;--fg:#eee9e3;--mute:#9c958e;--line:#2c2926;--card:#1e1c1a;--acc:#e48a99}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}}
header{{padding:28px 24px 8px;max-width:1400px;margin:auto}}h1{{margin:0 0 4px;font-size:24px}}header p{{margin:0;color:var(--mute)}}
nav{{position:sticky;top:0;background:var(--bg);padding:10px 24px;border-bottom:1px solid var(--line);z-index:2;display:flex;gap:6px;flex-wrap:wrap}}
nav button{{border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:99px;padding:4px 12px;cursor:pointer}}nav button.on{{background:var(--fg);color:var(--bg)}}
main{{max-width:1400px;margin:auto;padding:0 24px 40px}}h2{{font-size:18px;margin:28px 0 10px;display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}}
h2 small{{font-weight:400;color:var(--mute);font-size:13px}}.rank{{color:var(--acc);font-weight:700}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(420px,100%),1fr));gap:14px}}.scroll{{overflow-x:auto;-webkit-overflow-scrolling:touch}}*{{min-width:0}}body{{overflow-x:clip}}
article{{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}}
.snap{{background:#111;overflow-x:auto}}.snap img{{display:block;height:220px;width:auto;cursor:zoom-in}}.noimg{{color:#888;padding:40px;text-align:center}}
.info{{padding:10px 12px}}.top{{display:flex;gap:8px;align-items:center}}.score{{margin-left:auto;font-weight:700}}
.tag{{font-size:12px;color:var(--mute);border:1px solid var(--line);border-radius:4px;padding:0 6px}}.tag.other{{color:var(--acc);border-color:var(--acc)}}
.meta{{color:var(--mute);font-size:12.5px;margin:4px 0}}article p{{margin:6px 0;font-size:13px;max-height:5.8em;overflow:hidden}}a{{color:var(--acc)}}
details{{margin-top:30px}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{border-bottom:1px solid var(--line);padding:5px 6px;text-align:left;vertical-align:top}}
.stats{{color:var(--mute);font-size:13px;margin:-4px 0 8px}}.note{{background:var(--card);border-left:3px solid var(--acc);padding:6px 12px;margin:0 0 12px;border-radius:4px}}.note p{{margin:4px 0}}
.flag{{font-size:12px;color:var(--acc);margin:2px 0}}article.more{{display:none}}section.open article.more{{display:block}}
.showmore{{margin:10px 0;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:6px;padding:5px 12px;cursor:pointer}}
.mx{{width:auto;margin:14px 0 4px}}.mx td,.mx th{{padding:4px 10px}}.mx td{{text-align:center}}.mx td small{{color:var(--mute)}}.mx .nil{{color:var(--line)}}
:root[data-theme=dark]{{--bg:#151413;--fg:#eee9e3;--mute:#9c958e;--line:#2c2926;--card:#1e1c1a;--acc:#e48a99}}:root[data-theme=light]{{--bg:#faf9f7;--fg:#1d1b19;--mute:#77716b;--line:#e6e1da;--card:#fff;--acc:#8a2b3a}}
@media(max-width:600px){{header{{padding:18px 14px 6px}}header p{{font-size:13px}}main{{padding:0 14px 32px}}nav{{padding:8px 14px;flex-wrap:nowrap;overflow-x:auto}}nav button{{flex:none;min-height:36px}}.snap img{{height:170px}}.mx{{font-size:12.5px}}.mx td,.mx th{{padding:4px 6px;white-space:nowrap}}h2{{font-size:16px}}.showmore{{min-height:44px;width:100%}}}}
#lb{{position:fixed;inset:0;background:rgba(0,0,0,.92);display:none;align-items:center;justify-content:center;z-index:9}}#lb img{{max-width:96vw;max-height:94vh}}
</style></head><body>
<header><h1>{esc(name)} — competitor Meta ads that kept running</h1>
<p>Facebook + Instagram only. Kept: live {MIN_DAYS}+ days. Score = days (up to {DAY_CAP}) + {PER_CREATIVE} per extra ad using the creative (counted up to {CREATIVE_CAP} ads, so at most {PER_CREATIVE * CREATIVE_CAP} points) + 10 for multiple versions + EU reach bonus ({eu_n} of {len(rows)} ads have EU reach data{', so it moves no score yet' if not eu_n else ''}).
Groups ranked by the best ad of each of their top {TOP_N} brands + {PER_BRAND} per extra brand, so one big brand can't carry a type. Each brand shows its best {SHOW_PER_BRAND} per group. Running long means the brand kept paying, not proof it sold. Short promo ads rarely reach {MIN_DAYS} days, so offers are under-represented here{cut_line}. Rebuilt {today.isoformat()} · {len(rows)} ads · {len(ranked)} types.</p></header>
<nav><button class="on" data-b="">All brands</button>{chips}</nav>
<main>{matrix}{markets_table(out, rows, brands)}{"".join(parts) or "<p>No ads kept yet.</p>"}
<details><summary>Searches ({len(runs_log)})</summary><div class="scroll"><table><tr><th>Date</th><th>Brand</th><th>How</th><th>Loaded</th><th>Kept</th><th>Left out, under {MIN_DAYS} days</th><th>Note</th></tr>{runs}</table></div></details>
<details><summary>Type changes ({len(types_log)})</summary><div class="scroll"><table><tr><th>Date</th><th>Action</th><th>From</th><th>To</th><th>Reason</th></tr>{tlog}</table></div></details>
</main><div id="lb"><img alt=""></div>
<script>
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{{document.querySelectorAll('nav button').forEach(x=>x.classList.toggle('on',x===b));
document.querySelectorAll('article').forEach(a=>a.style.display=!b.dataset.b||a.dataset.brand===b.dataset.b?(b.dataset.b?'block':''):'none');
document.querySelectorAll('section').forEach(s=>s.style.display=[...s.querySelectorAll('article')].some(a=>a.style.display!=='none')?'':'none')}});
document.querySelectorAll('.showmore').forEach(b=>b.onclick=()=>{{b.closest('section').classList.add('open');b.remove()}});
const lb=document.getElementById('lb');document.querySelectorAll('.snap img').forEach(i=>i.onclick=()=>{{lb.querySelector('img').src=i.src;lb.style.display='flex'}});
lb.onclick=()=>lb.style.display='none';document.onkeydown=e=>{{if(e.key==='Escape')lb.style.display='none'}};
</script></body></html>"""
    path = os.path.join(out, f"{name}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    return path


def norm(t):
    return " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in t).split())[:160]


def import_export(path, brand, own_names, today):
    """Turn an adlib.js export (page text saved by get_page_text) into a draft run.

    One ad per creative: ads from the same advertiser with the same copy, format and card
    count are one creative shown under several Library IDs. The draft keeps the longest-running
    ID, the widest dates and the largest creative count, and lists the other IDs in the note.
    The agent fills in type (and owner where the guess is wrong) and the image paths.
    """
    text = open(path, encoding="utf-8").read()
    if path.endswith(".json"):
        text = json.loads(text)[0]["text"]
    text = text[text.find("MA-EXPORT-START"):text.find("MA-EXPORT-END")]
    own = [o.strip().lower() for o in own_names.split(",") if o.strip()]
    groups = {}
    for line in text.split("\n")[1:]:
        f = [x.strip() for x in line.split("¦")]
        if len(f) < 14:
            continue
        lid, adv, pid, status, start, end, days, n, ver, fmt, media, vsec, eu, body = f[:14]
        # single images with the same copy are often different pictures (multiple versions), so
        # only videos and carousels are folded together here; build.py still merges exact image matches
        key = (adv.lower(), norm(body), fmt, media) if fmt != "image" else (lid,)
        ad = {"id": lid, "brand": brand, "advertiser": adv, "page_id": pid,
              "owner": "own" if adv.lower() in own else "other", "type": "", "status": status,
              "start": start, "end": end, "days": int(days), "creatives": int(n or 1), "versions": ver == "1",
              "format": fmt, "media": int(media or 1), "video_sec": vsec, "eu_flag": eu == "1", "body": body, "image": ""}
        g = groups.get(key)
        if not g:
            groups[key] = dict(ad, also=[])
            continue
        lead, other = (ad, g) if ad["days"] > g["days"] else (g, ad)
        merged = dict(lead, also=g["also"] + [other["id"]])
        merged["start"] = min(g["start"], ad["start"])
        merged["status"] = "active" if "active" in (g["status"], ad["status"]) else "ended"
        merged["end"] = "" if merged["status"] == "active" else max(g["end"], ad["end"])
        merged["creatives"] = max(g["creatives"], ad["creatives"])
        merged["versions"] = g["versions"] or ad["versions"]
        merged["eu_flag"] = g["eu_flag"] or ad["eu_flag"]
        groups[key] = merged
    ads = []
    for g in sorted(groups.values(), key=lambda x: -x["days"]):
        also = g.pop("also")
        g.pop("days")
        g["note"] = ("also shown as " + ", ".join(also)) if also else ""
        ads.append(g)
    return {"date": today, "searches": [], "types_log": [], "ads": ads}


def check_images(out):
    """Read the ID printed in each grid's caption (tesseract) and list files whose name disagrees.
    Captures saved in a batch can come back out of order, so run this before every build."""
    import glob, re, subprocess
    from PIL import Image
    bad = []
    for f in sorted(glob.glob(os.path.join(out, "images", "*.png"))):
        fid = os.path.basename(f)[:-4]
        im = Image.open(f).convert("L")
        h, w = max(18, int(im.height * 0.085)), min(im.width, 900)
        im.crop((0, 0, w, h)).resize((w * 3, h * 3)).point(lambda v: 255 - v).save("/tmp/_cap.png")
        t = subprocess.run(["tesseract", "/tmp/_cap.png", "-", "--psm", "7"], capture_output=True, text=True).stdout
        m = re.search(r"(\d[\d ]{13,20}\d)", t)
        got = m.group(1).replace(" ", "") if m else ""
        if got != fid:
            bad.append((fid, got, t.strip()[:50]))
    for b in bad:
        print(f"{b[0]}  caption reads {b[1] or '?'}  ({b[2]})")
    print(f"{len(bad)} to look at (OCR misreads of 1-2 digits are fine; a different whole ID means the files are swapped)")


def trim(src, dst):
    """Cut the dark empty area off a full-frame grid capture and save it as PNG."""
    from PIL import Image, ImageChops
    im = Image.open(src).convert("RGB")
    im = im.crop((0, 0, im.width - max(16, im.width // 60), im.height))  # drop the page scrollbar
    bg = Image.new("RGB", im.size, im.getpixel((im.width - 1, im.height - 1)))
    diff = ImageChops.difference(im, bg).convert("L").point(lambda v: 255 if v > 18 else 0)
    box = diff.getbbox()
    if box:
        im = im.crop((0, 0, min(im.width, box[2] + 8), min(im.height, box[3] + 8)))
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    im.save(dst)
    print(f"{dst} {im.width}x{im.height}")


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "check-images":
        return check_images(sys.argv[2].rstrip("/"))
    if len(sys.argv) >= 2 and sys.argv[1] == "import":
        if len(sys.argv) != 6:
            sys.exit("usage: build.py import <export file> <Brand> <own advertiser names, comma-separated> <YYYY-MM-DD>")
        print(json.dumps(import_export(*sys.argv[2:6]), ensure_ascii=False, indent=1))
        return
    if len(sys.argv) == 4 and sys.argv[1] == "geo-ids":
        return geo_ids(sys.argv[2].rstrip("/"), sys.argv[3])
    if len(sys.argv) >= 2 and sys.argv[1] == "geo":
        if len(sys.argv) != 5:
            sys.exit("usage: build.py geo <out_dir> <results file> <YYYY-MM-DD>")
        return geo(sys.argv[2].rstrip("/"), sys.argv[3], sys.argv[4])
    if len(sys.argv) >= 2 and sys.argv[1] == "trim":
        if len(sys.argv) != 4:
            sys.exit("usage: build.py trim <capture.png> <out_dir>/images/<library_id>.png")
        return trim(sys.argv[2], sys.argv[3])
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    out = sys.argv[1].rstrip("/")
    name = os.path.basename(os.path.abspath(out))
    os.makedirs(os.path.join(out, "images"), exist_ok=True)
    tsv, tl, rl = (os.path.join(out, f) for f in (f"{name}.tsv", "types-log.tsv", "runs-log.tsv"))
    TL = ["date", "action", "from", "to", "reason"]
    RL = ["date", "brand", "how", "found", "kept", "under_30", "note"]
    rows, types_log, runs_log = read_tsv(tsv, COLS), read_tsv(tl, TL), read_tsv(rl, RL)
    today = date.today()
    for rp in sys.argv[2:]:
        with open(rp, encoding="utf-8") as f:
            run = json.load(f)
        today, a, u, s = merge(out, run, rows, types_log, runs_log)
        print(f"{rp}: {a} added, {u} updated, {s} skipped (under {MIN_DAYS} days)")
    for r in rows:
        r["_ft"] = first_tile_hash(os.path.join(out, r["image"])) if r.get("image") else ""
    rescore(rows, today)
    rows.sort(key=lambda r: (r.get("type", ""), -int(r["score"])))
    write_tsv(tsv, rows, COLS)
    write_tsv(tl, types_log, TL)
    write_tsv(rl, runs_log, RL)
    notes = {r["type"]: r for r in read_tsv(os.path.join(out, "group-notes.tsv"), ["type", "takeaway", "sher_test", "updated"])}
    page = html(out, name, rows, types_log, runs_log, today, notes)
    print(f"{len(rows)} ads in {tsv}\n{page} ({os.path.getsize(page) // 1024} KB)")


if __name__ == "__main__":
    main()
