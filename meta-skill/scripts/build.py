#!/usr/bin/env python3
"""Merge a Meta SKILL run into the living memory and rebuild the page.

    python3 -I build.py <out_dir> [run.json ...]
    python3 -I build.py trim <capture.png> <out_dir>/images/<library_id>.png

<out_dir> is meta-<brand>/ (e.g. meta-sher/). It holds:
    meta-<brand>.tsv   one row per kept ad, keyed by Library ID (the memory)
    types-log.tsv      every new type, merge, split and rename, with the reason
    runs-log.tsv       every brand search: when, how, found, kept
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
PER_CREATIVE = 15    # points for every extra ad using the same creative
CREATIVE_CAP = 10    # ...counted up to 10 extra ads
TOP_N = 3            # a group is scored on its best N ads
PER_BRAND = 20       # points for every extra brand running the type


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
                f"also shown as {a['library_id']}" in r.get("note", "")
                or hamming(r["creative_hash"], a["creative_hash"]) <= 6)), None)
            alias = bool(hit)
        if hit and alias:
            if f"also shown as {a['library_id']}" not in hit.get("note", ""):
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
    for r in rows:
        r["days"] = days_of(r, today)
        r["score"] = score(r)


def rank(rows):
    groups = {}
    for r in rows:
        groups.setdefault(r.get("type") or "untyped", []).append(r)
    ranked = []
    for t, ads in groups.items():
        ads.sort(key=lambda r: -int(r["score"]))
        top = [int(r["score"]) for r in ads[:TOP_N]]
        brands = sorted({r["brand"] for r in ads})
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
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def life(r):
    d = int(r["days"])
    return f"at least {d} days, still running" if r.get("status") == "active" else f"ran {d} days, ended {r.get('end')}"


def html(out, name, rows, types_log, runs_log, today):
    ranked = rank(rows)
    brands = sorted({r["brand"] for r in rows})
    parts = []
    for gi, (gscore, t, gbrands, ads) in enumerate(ranked, 1):
        cards = []
        for i, r in enumerate(ads, 1):
            src = thumb(os.path.join(out, r["image"])) if r.get("image") else ""
            img = f'<img src="{src}" alt="">' if src else '<div class="noimg">no snapshot</div>'
            meta = [life(r), f'{r["creatives"]} ads use this creative' if int(r.get("creatives") or 1) > 1 else "",
                    "multiple versions" if r.get("versions") == "yes" else "",
                    r.get("format", "") + (f' · {r["video_sec"]}s' if r.get("video_sec") else ""),
                    f'EU reach {int(float(r["eu_reach"])):,}' if r.get("eu_reach") else "",
                    r.get("countries", "")]
            cards.append(
                f'<article data-brand="{esc(r["brand"])}"><div class="snap">{img}</div><div class="info">'
                f'<div class="top"><span class="rank">#{i}</span><b>{esc(r["brand"])}</b>'
                f'<span class="tag {esc(r.get("owner", ""))}">{"own ad" if r.get("owner") == "own" else "by " + esc(r.get("advertiser", ""))}</span>'
                f'<span class="score">{r["score"]}</span></div>'
                f'<div class="meta">{" · ".join(esc(m) for m in meta if m)}</div>'
                f'<p>{esc(r.get("body", ""))}</p>'
                f'<a href="https://www.facebook.com/ads/library/?id={esc(r["library_id"])}" target="_blank" rel="noopener">Library ID {esc(r["library_id"])}</a>'
                f'{" · " + esc(r["note"]) if r.get("note") else ""}</div></article>')
        parts.append(f'<section><h2><span class="rank">{gi}</span>{esc(t)}<small>group score {gscore} · '
                     f'{len(ads)} ads · {len(gbrands)} brand{"s" if len(gbrands) > 1 else ""}: {esc(", ".join(gbrands))}</small></h2>'
                     f'<div class="grid">{"".join(cards)}</div></section>')
    runs = "".join(f'<tr><td>{esc(s.get("date"))}</td><td>{esc(s.get("brand"))}</td><td>{esc(s.get("how"))}</td>'
                   f'<td>{esc(s.get("found"))}</td><td>{esc(s.get("kept"))}</td><td>{esc(s.get("note"))}</td></tr>' for s in runs_log[::-1])
    tlog = "".join(f'<tr><td>{esc(e.get("date"))}</td><td>{esc(e.get("action"))}</td><td>{esc(e.get("from"))}</td>'
                   f'<td>{esc(e.get("to"))}</td><td>{esc(e.get("reason"))}</td></tr>' for e in types_log[::-1])
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
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:14px}}
article{{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}}
.snap{{background:#111;overflow-x:auto}}.snap img{{display:block;height:220px;width:auto;cursor:zoom-in}}.noimg{{color:#888;padding:40px;text-align:center}}
.info{{padding:10px 12px}}.top{{display:flex;gap:8px;align-items:center}}.score{{margin-left:auto;font-weight:700}}
.tag{{font-size:12px;color:var(--mute);border:1px solid var(--line);border-radius:4px;padding:0 6px}}.tag.other{{color:var(--acc);border-color:var(--acc)}}
.meta{{color:var(--mute);font-size:12.5px;margin:4px 0}}article p{{margin:6px 0;font-size:13px;max-height:5.8em;overflow:hidden}}a{{color:var(--acc)}}
details{{margin-top:30px}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{border-bottom:1px solid var(--line);padding:5px 6px;text-align:left;vertical-align:top}}
#lb{{position:fixed;inset:0;background:rgba(0,0,0,.92);display:none;align-items:center;justify-content:center;z-index:9}}#lb img{{max-width:96vw;max-height:94vh}}
</style></head><body>
<header><h1>{esc(name)} — competitor Meta ads that kept running</h1>
<p>Facebook + Instagram only. Kept: live {MIN_DAYS}+ days. Score = days (up to {DAY_CAP}) + {PER_CREATIVE} per extra ad using the creative + 10 for multiple versions + EU reach bonus.
Groups ranked by their best {TOP_N} ads + {PER_BRAND} per extra brand. Running long means the brand kept paying, not proof it sold. Rebuilt {today.isoformat()} · {len(rows)} ads · {len(ranked)} types.</p></header>
<nav><button class="on" data-b="">All brands</button>{chips}</nav>
<main>{"".join(parts) or "<p>No ads kept yet.</p>"}
<details><summary>Searches ({len(runs_log)})</summary><table><tr><th>Date</th><th>Brand</th><th>How</th><th>Found</th><th>Kept</th><th>Note</th></tr>{runs}</table></details>
<details><summary>Type changes ({len(types_log)})</summary><table><tr><th>Date</th><th>Action</th><th>From</th><th>To</th><th>Reason</th></tr>{tlog}</table></details>
</main><div id="lb"><img alt=""></div>
<script>
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{{document.querySelectorAll('nav button').forEach(x=>x.classList.toggle('on',x===b));
document.querySelectorAll('article').forEach(a=>a.style.display=!b.dataset.b||a.dataset.brand===b.dataset.b?'':'none');
document.querySelectorAll('section').forEach(s=>s.style.display=[...s.querySelectorAll('article')].some(a=>a.style.display!=='none')?'':'none')}});
const lb=document.getElementById('lb');document.querySelectorAll('.snap img').forEach(i=>i.onclick=()=>{{lb.querySelector('img').src=i.src;lb.style.display='flex'}});
lb.onclick=()=>lb.style.display='none';document.onkeydown=e=>{{if(e.key==='Escape')lb.style.display='none'}};
</script></body></html>"""
    path = os.path.join(out, f"{name}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    return path


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
    RL = ["date", "brand", "how", "found", "kept", "note"]
    rows, types_log, runs_log = read_tsv(tsv, COLS), read_tsv(tl, TL), read_tsv(rl, RL)
    today = date.today()
    for rp in sys.argv[2:]:
        with open(rp, encoding="utf-8") as f:
            run = json.load(f)
        today, a, u, s = merge(out, run, rows, types_log, runs_log)
        print(f"{rp}: {a} added, {u} updated, {s} skipped (under {MIN_DAYS} days)")
    rescore(rows, today)
    rows.sort(key=lambda r: (r.get("type", ""), -int(r["score"])))
    write_tsv(tsv, rows, COLS)
    write_tsv(tl, types_log, TL)
    write_tsv(rl, runs_log, RL)
    page = html(out, name, rows, types_log, runs_log, today)
    print(f"{len(rows)} ads in {tsv}\n{page} ({os.path.getsize(page) // 1024} KB)")


if __name__ == "__main__":
    main()
