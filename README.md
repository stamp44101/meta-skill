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
| `meta-skill/scripts/geo.js` | Pasted into the tab for step 2b: which kept ads come back under each country filter |
| `meta-skill/scripts/build.py` | Merges a run into the memory, scores, ranks, fills countries, rebuilds the HTML |
| `meta-sher/` | SHER's living file: 220 ads from 10 brands — Bupbes, JC de JC, IAM COCO, Maël, JUBIN STUDIO, Malimarea, RUE de RUE, Cherie, Viery, Fanci Club; La Vierge, JENÉA, Karlotta Concept and Chérieon had no 30+ day ads (25 Nov 2026) |

## Rules

- An ad live under 30 days is never saved, whatever its creative count. A later run picks it up once it reaches 30 days. The creative count only adds to the score.

## Known limits

What the skill does today and where the data stops. Every number here was checked on 25–26 Nov 2026.

1. **Living memory format.** `creative_hash` catches the same creative under a new Library ID, scores are recomputed on every build (not stored as truth), `types-log.tsv` and `runs-log.tsv` are separate, and the HTML packs ≤360 px thumbnails while full grids stay in `images/`.
2. **Score.** Days + 5 per extra ad on the creative (up to 10) + 10 for multiple versions + EU reach (10 points at 10,000 people reached in the EU, 20 at 100,000). Ads are ranked by score inside each look; looks are listed by size. EU reach was read for the 53 ads seen in FR or DE; the highest is 1,236, so it adds no points yet.
3. **Creative groups.** The card shows one ad's dates, but its group ("4 ads use this creative") can run longer (Malimarea 2187111091693389: card 22 May–19 Aug, a version ran to 26 Aug). The card's dates are scored.
4. **Countries.** The library names countries only for ads that reached the EU, so step 2b repeats each search with the country filter for 20 markets: SHER's region, US / GB / CA / AU / NZ, AE, FR and DE. 204 of 220 kept ads were seen in at least one. The filter misses ads (Maël's VN search returns 20 of its ~64 ads), so the page says "not seen in the N countries checked", never "did not run". Long pages stall while loading, so Bupbes's counts are a floor.
5. **Big brands.** Bupbes has ~830 ads; loading stopped at 456 after ~10 minutes, so older ads may be missing.
6. **Snapshot quality.** Grids are screenshots of frames at about 300 px tall, enough to see the idea, not to reuse.
7. **Same copy, one row.** Videos and carousels with the same copy, format and card count are folded into one row (other IDs in the note). Two Bupbes single images were folded the same way before that rule changed (1365127932258105, 1744620560314514).
8. **Cherie.** Business MD says Cherie runs no Meta ads of its own; its page "Cherie" has ~54, linking to cherieattire.com (checked 25 Nov). Search `cherieattire`. Fanci Club really has none of its own.
9. **Where this lives.** The skill is its own repo; the output for SHER sits here as `meta-sher/`.

## Page

Ads are grouped by look (how they were shot, judged from the pictures), not by caption; the caption's angle is a tag and a filter. Brand × look table first (ads · best score), then a brand × country table (kept ads seen per market), then each look with a one-line stat (format mix, video length, median run, still running) and what the look is, in facts, from `meta-sher/group-notes.tsv` (edit it by hand or ask Claude; rebuild to show), then the ads. Each brand shows its best 4 per look; the rest sit behind "show more". Flags: ads that ended with 5+ others from the same brand within 3 days and ads sharing copy with others (different pictures).

## Research behind it

What we took from existing skills and tools (Nov 2026):

- [goose-skills · ad-angle-miner](https://github.com/gooseworks-ai/goose-skills/blob/main/skills/shared/ad-angle-miner/SKILL.md): "sustained ad" = 30+ days or 3+ variants; write "at least N days, still running"; drop off-category ads.
- [goose-skills · competitor-ad-intelligence](https://github.com/gooseworks-ai/goose-skills/blob/main/skills/shared/competitor-ad-intelligence/SKILL.md): longevity is sustained spend, not proof of results; keep the library link with every ad.
- [Apify · bovi/meta-ads-library-scraper](https://apify.com/bovi/meta-ads-library-scraper): days from `total_active_time`, longevity capped, `collation_count` (the "N ads use this creative" number) as the scale signal.
- [Apify · curious_coder/facebook-ads-library-scraper](https://apify.com/curious_coder/facebook-ads-library-scraper): the paid fallback if Chrome is too slow.
- [dev.to · FB ad spy with SQLite](https://dev.to/olams/build-a-facebook-ad-spy-tool-to-reverse-engineer-winning-campaigns-4421): upsert by ID with first/last seen; its gap (stopped ads never marked) is why we search all statuses.
- [thatrebeccarae · competitor-ads-analyst](https://github.com/thatrebeccarae/claude-marketing/tree/main/skills/competitor-ads-analyst) and [AgriciDaniel · ads-competitor](https://github.com/AgriciDaniel/claude-ads/blob/main/skills/ads-competitor/SKILL.md): date everything, keep observation apart from inference.
- Meta's own Ad Library API (and the FB Ads connector's library search) only holds commercial ads that reached the EU or UK, so it can't be the main source for Asian brands.
