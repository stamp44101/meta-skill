---
name: meta-skill
description: Collect competitors' working Meta ads (Facebook + Instagram) from the Ad Library into one living swipe file per brand (meta-<brand>), scored by how long they ran, how many ads share the creative and their EU reach, grouped by how each ad was shot (its look). Use for Meta ad research, competitor ads, ad swipe files, or "Meta SKILL".
version: 0.5
---

# Meta SKILL — v0.5

Collects competitors' ads that kept running on Facebook and Instagram, as references for our Social Ads GTM. Every run adds to one living file and never replaces it.

Facts only. Reply in the user's language (casual Thai by default), technical terms in English.

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

Paste `scripts/adlib.js` into the tab with `javascript_tool` after every navigation (the Ad Library's CSP blocks `eval`, so it can't be stored and re-run).

- `MA.autoscroll()` starts loading in the background and returns at once. Wait (10 s waits in `browser_batch`), then `MA.status()` until `done` is true. Never scroll inside one long call: past ~100 cards the tab freezes and the call times out. Big brands stall before the library's total (Bupbes: 456 of ~830); say so in the run log.
- `MA.export(30, '<today>')` puts every loaded ad that ran 30+ days on the page as text and hides the rest; `get_page_text` then saves it to a file (it is padded past 50 KB on purpose; tool results are cut off past ~1,500 characters). `MA.clearOut()` restores the page.
- `python3 -I scripts/build.py import <saved file> <Brand> "<own page names>" <today> > draft.json` turns it into a draft run: own vs other by advertiser name, one row per Library ID. Ads are never folded by caption; build.py merges the same picture shown under another Library ID by image hash.

### 2. Keep the working ads

- **Only ads that ran 30+ days** (end date, or today if still active). Newer ads are not saved at all; a later run catches them. `export` already applies this.
- **Whose ad:** the brand's own page is `own`. Another advertiser naming the brand (rental shop, stockist, consignment, gift shop, creator) is `other` and kept the same way. Delete draft rows that only match the word (keyword search returns baby food for "mael").
- EU reach: for a kept ad with `EU transparency`, `await MA.versions(id)` then `await MA.eu(versionId)`, then `MA.closeDialogs()`.

### 2b. Where it ran

The library shows no country on ads outside the EU, but its country filter lists only ads that reached that country. So for each brand, run the same search once per market with `country=XX` and see which kept ads come back. Snippets are in `scripts/geo.js`:

1. `python3 -I scripts/build.py geo-ids meta-<brand> "<Brand>"` prints a SET line: paste it once per tab.
2. Per market: navigate (`&country=XX`, same `q` and `search_type` as step 1), paste SCROLL, wait, paste CHECK, and append the line it returns to a results file. Run SCROLL + CHECK again on long pages until `n` stops growing; passes add up.
3. `python3 -I scripts/build.py geo meta-<brand> <results file> <today>` (keep the file as `runs/<date>-geo.txt`) fills `countries` and logs every check in `geo-log.tsv`.

Markets: start with the list in `build.py` (`MARKETS`, 20: SHER's region, the big English-language markets, the Gulf, FR and DE) plus any the user names. Then per brand, check batches: the 10 biggest Facebook countries not yet checked for that brand plus the unchecked neighbours of countries where its ads were seen. Stop that brand when a batch finds no new country; otherwise run another batch. Several tabs can run in parallel (one `browser_batch` per tab). A kept ad not seen in any market may still have run elsewhere: write "not seen in the N markets checked", never "did not run".

### 3. Snapshot grid per kept ad

```
await MA.grid('<id>', 6, '<Brand> · <id>')     → {tiles, rows}
computer zoom, region [0, 0, W, 0.35·H], save_to_disk   (W × H = the screenshot frame)
python3 -I scripts/build.py trim <saved file> meta-<brand>/images/<id>.png
```

`grid` lays every carousel card, or 6 frames across a video (one frame per card in a video carousel), in one row on a dark layer. Run it on the search page when it holds under ~100 cards. For big searches open the single-ad page `https://www.facebook.com/ads/library/?id=<id>`, `eval(window.name)`, then `grid`; if that page shows another ad of the same group (`ad not on page`), grid it from the search page. Batch about 6 ads (grid + zoom) per `browser_batch` and trim them right after, in order; saved captures can come back out of order, so before building run `python3 -I scripts/build.py check-images meta-<brand>` and swap any file whose caption shows another ad's ID. Check each grid as it comes back: the picture is what decides the look.

### 4. Label every kept ad by its look

`type` is the **look**: how the ad was produced, judged by looking at its snapshot grid, never from the caption. Format (carousel or video) and the place itself (café, beach, bedroom) don't decide it; how produced it is does. The SHER file uses five, from most controlled to most raw:

- **studio, minimal**: plain backdrop, white cut-out or a bare room, controlled light; the garment is the subject (packshots on white count here)
- **editorial**: a styled, magazine-like shoot with a concept, set, props, theatrical light or a dramatic place; the same production stays editorial whatever room or field it moves to
- **polished lookbook**: a photographer, natural light, real place, natural poses, no concept
- **casual, phone-shot**: looks self-made: mirror selfies, try-ons presented to camera, handheld unboxing or flat-lays on a bed, snapshots
- **graphic layout**: a designed card or collage led by text or annotations, not a shoot

Tie-breaks, so the same picture gets the same look every run:
- judge one brand's shoot as a whole: if its outdoor and indoor sets share the same styling and lighting, they share one look
- a bare room with a chair, curtain or wallpaper and plain posing → studio
- a try-on presented to camera or a mirror selfie → casual, however nice the room

A carousel or video that mixes looks goes where most of its frames sit. To label many ads, stack the grids into numbered contact sheets and look at them in batches. Reuse these looks; if a new one is needed, merge or split, log it in `types_log` with the reason (build.py leaves any `type` that is not an existing look empty and warns).


### 5. Write the run and build

Fill `type` (the look) and `image` in the draft, add `searches` (brand, how, found, kept, note) and `types_log`, save it as `meta-<brand>/runs/<date>-<brand>.json` (shape in the `build.py` docstring; `retype` moves ads already in the file to another look), then:

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
| `types-log.tsv` | Every group change (new look, merge, split, regroup), with the reason |
| `runs-log.tsv` | Every brand search: date, how, found, kept, note (brands with no ads get a row too) |
| `geo-log.tsv` | Every per-country check: brand, country, results, cards loaded, kept ads seen |
| `geo-ids.json` | The ID order the last SET line used (CHECK returns indexes into it) |
| `group-notes.tsv` | Per look: what it is, in facts from the page |
| `runs/*.json` | Each run's raw input |
| `meta-<brand>.html` | Rebuilt every run; opens on its own |

**Score** = days + 5 per extra ad using the creative (up to 10) + 10 for "multiple versions" + EU reach bonus (10 at 10k, 20 at 100k). An active ad counts days up to the day it was last seen live.
Ads are ranked by score inside each look; looks are listed by size. Each look shows its first 12 ads; the rest are one tap away.

After a run that adds ads or changes looks, update `group-notes.tsv` (type, takeaway, updated): what the look is, in facts from the page, in two sentences. No advice or verdicts.

Send the HTML with one line per brand (found → kept), and any looks merged or split.

## Iteration

- A re-run updates dates, status and score of ads already in the file; it never adds them twice. An ad that stopped stays in, marked ended.
- Re-run a brand when the user asks.
- Known limits are listed in `README.md` → Known limits. Don't change the brief's rules without the user.
