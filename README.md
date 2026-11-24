# Meta SKILL

Collects competitors' Meta ads (Facebook + Instagram) that kept running, as references for SHER's Social Ads GTM. One living swipe file per brand: each run adds to it and never replaces it.

## Install

Copy `meta-skill/` into your skills folder (or upload it as a skill). It needs Claude in Chrome and Python 3 with Pillow.

## Use

> รัน Meta SKILL ให้ SHER: Bupbes, Mael, Fanci, Cherie, Malimarea

Brands come from chat or from Competitors in Business MD. Output goes to `meta-<brand>/` beside the skill, e.g. [`meta-sher/`](meta-sher/).

## Files

| Path | What |
|---|---|
| `meta-skill/SKILL.md` | The skill |
| `meta-skill/TESTS.md` | Test log and scenarios |
| `meta-skill/scripts/adlib.js` | Pasted into the Ad Library tab: loads, reads and snapshots ads |
| `meta-skill/scripts/build.py` | Merges a run into the memory, scores, ranks, rebuilds the HTML |
| `meta-sher/` | SHER's living file: 124 ads from Bupbes, Maël, Malimarea, Cherie and Fanci Club (25 Nov 2026) |

## Open for discuss

Decided for v0.1 so the skill could run. Change any of them and the SKILL follows.

1. **New ads with 2+ creatives.** Decision 2 (drop anything under 30 days) and decision 3 (keep 30+ days *or* 2+ ads on the creative) clash. v0.1 follows decision 2: under 30 days is never saved, and the creative count only adds to the score. Real cost: Bupbes has 28 live ads with 2+ creatives, none 30 days old yet; Malimarea had 52 such ads, all left out.
2. **Living memory format.** v0.1 uses the proposal plus: `creative_hash` to catch the same creative under a new Library ID, scores recomputed on every build (not stored as truth), separate `types-log.tsv` and `runs-log.tsv`, and the HTML packs ≤360 px thumbnails, full grids stay in `images/`.
3. **Score weights.** Days up to 180, +15 per extra ad on the creative (up to 10), +10 for multiple versions, EU reach +10 at 10k / +20 at 100k. Group = best 3 average + 20 per extra brand. All picked, not measured.
4. **Creative groups.** The card shows one ad's dates, but its group ("4 ads use this creative") can run longer (Malimarea 2187111091693389: card 22 May–19 Aug, a version ran to 26 Aug). v0.1 scores the card's dates. Opening every group would make runs much slower.
5. **Countries.** The library only shows where an ad ran for ads that reached the EU (Transparency by location). Everything else has no country. Per-country searches would find more but multiply the run time.
6. **Big brands.** Bupbes has ~830 ads; loading stopped at 456 after ~10 minutes, so older ads may be missing. Options: split the search by date range or country, or a paid scraper (Apify, about $0.75 per 1,000 ads), which needs approval.
7. **Snapshot quality.** Grids are screenshots of frames at about 300 px tall, enough to see the idea, not to reuse. Full-size frames would need a download.
8. **Same copy, one row.** Videos and carousels with the same copy, format and card count are folded into one row (other IDs in the note). That matched every Bupbes case checked, but two Bupbes single images were folded the same way before the rule changed (1365127932258105, 1744620560314514); worth a look.
9. **Business MD is out of date on Cherie.** It says Cherie runs no Meta ads of its own; its page "Cherie" has ~54 (search `cherieattire`, not "Cherie Attire"). Fanci Club really has none of its own.
10. **Where this lives.** The skill is its own repo; the output for SHER sits here as `meta-sher/`. If it should move next to Business MD instead, say so.

## Research behind it

What we took from existing skills and tools (Nov 2026):

- [goose-skills · ad-angle-miner](https://github.com/gooseworks-ai/goose-skills/blob/main/skills/shared/ad-angle-miner/SKILL.md): "sustained ad" = 30+ days or 3+ variants; write "at least N days, still running"; drop off-category ads.
- [goose-skills · competitor-ad-intelligence](https://github.com/gooseworks-ai/goose-skills/blob/main/skills/shared/competitor-ad-intelligence/SKILL.md): longevity is sustained spend, not proof of results; keep the library link with every ad.
- [Apify · bovi/meta-ads-library-scraper](https://apify.com/bovi/meta-ads-library-scraper): days from `total_active_time`, longevity capped, `collation_count` (the "N ads use this creative" number) as the scale signal.
- [Apify · curious_coder/facebook-ads-library-scraper](https://apify.com/curious_coder/facebook-ads-library-scraper): the paid fallback if Chrome is too slow.
- [dev.to · FB ad spy with SQLite](https://dev.to/olams/build-a-facebook-ad-spy-tool-to-reverse-engineer-winning-campaigns-4421): upsert by ID with first/last seen; its gap (stopped ads never marked) is why we search all statuses.
- [thatrebeccarae · competitor-ads-analyst](https://github.com/thatrebeccarae/claude-marketing/tree/main/skills/competitor-ads-analyst) and [AgriciDaniel · ads-competitor](https://github.com/AgriciDaniel/claude-ads/blob/main/skills/ads-competitor/SKILL.md): date everything, keep observation apart from inference.
- Meta's own Ad Library API (and the FB Ads connector's library search) only holds commercial ads that reached the EU or UK, so it can't be the main source for Asian brands.
