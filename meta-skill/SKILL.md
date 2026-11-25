---
name: meta-skill
description: Collect competitors' working Meta ads (Facebook + Instagram) from the Ad Library into one living swipe file per brand (meta-<brand>), scored by how long they ran and how many ads share the creative, grouped by type. Use for Meta ad research, competitor ads, ad swipe files, or "Meta SKILL".
version: 0.2
---

# Meta SKILL — v0.2

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

Open a Chrome tab with keyword search, **all statuses** (ended ads that ran long are most of what we keep), all countries, FB + IG only:

```
https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=ALL&media_type=all&publisher_platforms[0]=facebook&publisher_platforms[1]=instagram&search_type=keyword_unordered&q=<brand or domain>
```

Search the domain or handle (`bupbes`, `mael.vn`, `cherieattire`, `malimarea`); use `search_type=keyword_exact_phrase&q="<two words>"` for names that are common words (`"fanci club"`). The page-only view (`view_all_page_id`) shows nothing for brands with no live ads.

Install `scripts/adlib.js` once per tab: `window.name = String.raw` + the file in backticks + `; eval(window.name)`. `window.name` survives navigation in the tab, so after every navigation run `eval(window.name)` again.

- `MA.autoscroll()` starts loading in the background and returns at once. Wait (10 s waits in `browser_batch`), then `MA.status()` until `done` is true. Never scroll inside one long call: past ~100 cards the tab freezes and the call times out. Big brands stall before the library's total (Bupbes: 456 of ~830); say so in the run log.
- `MA.export(30, '<today>')` puts every loaded ad that ran 30+ days on the page as text and hides the rest; `get_page_text` then saves it to a file (it is padded past 50 KB on purpose; tool results are cut off past ~1,500 characters). `MA.clearOut()` restores the page.
- `python3 -I scripts/build.py import <saved file> <Brand> "<own page names>" <today> > draft.json` turns it into a draft run: own vs other by advertiser name, and videos or carousels with the same copy and card count folded into one row (the other IDs go in the note). Single images are never folded: same copy often means different pictures.

### 2. Keep the working ads

- **Only ads that ran 30+ days** (end date, or today if still active). Newer ads are not saved at all; a later run catches them. `export` already applies this.
- **Whose ad:** the brand's own page is `own`. Another advertiser naming the brand (rental shop, stockist, consignment, gift shop, creator) is `other` and kept the same way. Delete draft rows that only match the word (keyword search returns baby food for "mael").
- EU reach: for a kept ad with `EU transparency`, `await MA.versions(id)` then `await MA.eu(versionId)`, then `MA.closeDialogs()`. Record countries only when the library shows them.

### 3. Snapshot grid per kept ad

```
await MA.grid('<id>', 6, '<Brand> · <id>')     → {tiles, rows, video_sec}
computer zoom, region [0, 0, W, 0.35·H], save_to_disk   (W × H = the screenshot frame)
python3 -I scripts/build.py trim <saved file> meta-<brand>/images/<id>.png
```

`grid` lays every carousel card, or 6 frames across a video (one frame per card in a video carousel), in one row on a dark layer and reads the video length. Run it on the search page when it holds under ~100 cards. For big searches open the single-ad page `https://www.facebook.com/ads/library/?id=<id>`, `eval(window.name)`, then `grid`; if that page shows another ad of the same group (`ad not on page`), grid it from the search page. Batch about 6 ads (grid + zoom) per `browser_batch` and trim them right after, in order; saved captures can come back out of order, so before building run `python3 -I scripts/build.py check-images meta-<brand>` and swap any file whose caption shows another ad's ID. Check each grid as it comes back: the picture also tells you the type.

### 4. Type every kept ad

Group by the job the ad does, the way GTM SKILL's Create the list step works: merge types that do the same job, split one when its ads start to differ, and log every new type, merge, split or rename with the reason. Run 9's types were the starting point: creator-fronted (@handle at the top), new drop or collection, catalogue product cards, discount or code, back in stock, customer quote, craft or making-of, someone else's ad naming the brand. The SHER file has since split "new drop or collection" into styled look, single piece spotlight and mood, no product named (see `types-log.tsv`). Read the existing types in the TSV first and reuse them.

### 5. Write the run and build

Fill `type` and `image` in the draft, add `searches` (brand, how, found, kept, note) and `types_log`, save it as `meta-<brand>/runs/<date>-<brand>.json` (shape in the `build.py` docstring; `retype` moves ads already in the file to a new type), then:

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
| `group-notes.tsv` | Per type: what it is and what SHER should test |
| `runs/*.json` | Each run's raw input |
| `meta-<brand>.html` | Rebuilt every run; opens on its own |

**Score** = days (up to 180) + 5 per extra ad using the creative (up to 10) + 10 for "multiple versions" + EU reach bonus (10 at 10k, 20 at 100k). An active ad counts days up to the day it was last seen live.
**Group rank** = average of the best ad of each of its top 3 brands + 20 per extra brand running that type. Each brand shows its best 4 ads per group.

After a run that adds or changes types, update `group-notes.tsv` (type, takeaway, sher_test, updated): what the type is in facts from the page, and one thing SHER should test. Keep both to two sentences.

Send the HTML with one line per brand (found → kept), and any types merged or split.

## Iteration

- A re-run updates dates, status and score of ads already in the file; it never adds them twice. An ad that stopped stays in, marked ended.
- Re-run a brand when the user asks, or when new ads have had 30 days to prove themselves.
- Open questions are tracked in `README.md` → Open for discuss. Don't change those rules without the user.
