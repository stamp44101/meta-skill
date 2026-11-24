---
name: meta-skill
description: Collect competitors' working Meta ads (Facebook + Instagram) from the Ad Library into one living swipe file per brand (meta-<brand>), scored by how long they ran and how many ads share the creative, grouped by type. Use for Meta ad research, competitor ads, ad swipe files, or "Meta SKILL".
version: 0.1
---

# Meta SKILL — v0.1

Collects competitors' ads that kept running on Facebook and Instagram, as references for our Social Ads GTM. Every run adds to one living file and never replaces it.

Facts only. Running long means the brand kept paying, not proof it sold: write it that way. Reply in the user's language (casual Thai by default), technical terms in English.

## Run in Chat

Needs Claude in Chrome, signed in to Facebook (the Ad Library needs no account, but Chrome gives the real page). Python 3 with Pillow for `scripts/build.py`. Nothing is downloaded to the user's computer and no paid tool is used.

## Inputs

- **Our brand** — names the output: `meta-<brand>/` (e.g. `meta-sher/`), saved beside this skill.
- **Brands to search** — from the user in chat, or from the Competitors table in our Business MD. Never add a brand yourself.
- **The output folder** if it already exists — it is the memory; read `meta-<brand>.tsv` and `types-log.tsv` first.

## Workflow

### 1. Search each brand

Open a new Chrome tab per brand with keyword search, **all statuses** (ended ads that ran long are most of what we keep), all countries, FB + IG only:

```
https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=ALL&media_type=all&publisher_platforms[0]=facebook&publisher_platforms[1]=instagram&search_type=keyword_unordered&q=<brand>
```

Use `search_type=keyword_exact_phrase&q="<two words>"` for names that are common words (Fanci Club, Cherie Attire, Mael). The page-only view (`view_all_page_id`) shows nothing for brands with no live ads, so don't use it.

After the page loads, paste all of `scripts/adlib.js` with `javascript_tool` (again after every navigation). Then:

- `await MA.scroll(8)` until `grew` is 0. One call must stay under 45 s; if the tab freezes, take smaller steps.
- `MA.brief()` lists every loaded ad: `[id, advertiser, a|e, start, end, creatives, versions, format]`. Results are cut off past ~1,500 characters, so filter or page in the page (`MA.rows(offset, 10)`) rather than printing everything.

### 2. Keep the working ads

- **Keep only ads that ran 30+ days** (end date, or today if still active). Newer ads are not saved at all; a later run catches them.
- **Whose ad:** the brand's own page is `own`. Another advertiser naming the brand (rental shop, stockist, shipper, gift shop, creator, magazine) is `other` and kept the same way. Drop ads that only match the word and aren't about the brand (keyword search returns toothpaste and padel clubs for "Mael").
- For a kept ad with `eu_flag`, or whose creative group matters, `await MA.versions(id)` lists the versions (each with its own dates), and `await MA.eu(versionId)` reads EU reach and countries from Transparency by location. Then `MA.closeDialogs()`. Record countries only when the library shows them.

### 3. Snapshot grid per kept ad

```
await MA.grid('<id>', 6, '<Brand> · <id>')        → {tiles, rows, video_sec, cut}
computer zoom, region [0, 0, W, H], save_to_disk, scale 1
python3 -I scripts/build.py trim <saved file> meta-<brand>/images/<id>.png
```

`grid` lays every carousel card, or 6 frames across a video (one frame per card in a video carousel), on a dark layer top-left, and reads the video length. W is the screenshot frame width; H is 35% of the frame height for 1 row, 66% for 2 rows, full for more. Always `scale 1`: the saved file has the returned size. Batch grid + zoom pairs in `browser_batch`, about 5 ads per batch. `MA.clearGrid()` at the end.

### 4. Type every kept ad

Group by the job the ad does, the way GTM SKILL's Create the list step works: merge types that do the same job, split one when its ads start to differ, and log every new type, merge, split or rename with the reason. Run 9's types are a starting point only: creator-fronted (@handle at the top), new drop or collection, catalogue product cards, discount or code, back in stock, customer quote, craft or making-of, someone else's ad naming the brand. Read the existing types in the TSV first and reuse them.

### 5. Write the run and build

Write `meta-<brand>/runs/<date>-<brand(s)>.json` (shape in the `build.py` docstring: searches, ads, types_log, retype), then:

```
python3 -I scripts/build.py meta-<brand> meta-<brand>/runs/<file>.json
```

`build.py` upserts by Library ID, merges the same creative shown under another ID (image hash; noted as "also shown as"), recomputes every score, ranks, and rebuilds `meta-<brand>.html` with all images packed inside. Open the HTML (headless Chrome screenshot) and check it before sending.

## Output

`meta-<brand>/` beside this skill:

| File | What |
|---|---|
| `meta-<brand>.tsv` | The memory: one row per kept ad, keyed by Library ID, with first seen, last seen, status (active / ended) and score |
| `images/<id>.png` | Snapshot grid per ad |
| `types-log.tsv` | Every type change, with the reason |
| `runs-log.tsv` | Every brand search: date, how, found, kept, note (brands with no ads get a row too) |
| `runs/*.json` | Each run's raw input |
| `meta-<brand>.html` | Rebuilt every run; opens on its own |

**Score** = days (up to 180) + 15 per extra ad using the creative (up to 10) + 10 for "multiple versions" + EU reach bonus (10 at 10k, 20 at 100k). An active ad counts days up to the day it was last seen live.
**Group rank** = average of its best 3 scores + 20 per extra brand running that type.

Send the HTML with one line per brand (found → kept), and any types merged or split.

## Iteration

- A re-run updates dates, status and score of ads already in the file; it never adds them twice. An ad that stopped stays in, marked ended.
- Re-run a brand when the user asks, or when new ads have had 30 days to prove themselves.
- Open questions are tracked in `README.md` → Open for discuss. Don't change those rules without the user.
