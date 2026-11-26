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
4. **Countries.** Every brand is searched with all countries. Where each ad ran is read by repeating the search with the country filter, one country per page load; the filter offers about 240. Each brand got the same 20 countries first (SHER's region, US / GB / CA / AU / NZ, AE, FR, DE), then batches: the 10 biggest Facebook countries not yet checked plus the neighbours of countries where its ads were seen. A brand stops when a batch finds no new country. On 26 Nov only IAM COCO found new ones (LA, CN), so it got a second batch, which found none. Now 30–55 countries per brand, 66 in all; 204 of 220 kept ads were seen in at least one, and each card says how many countries were checked. Countries outside these batches were not checked. The filter also misses ads (Maël's VN search returns 20 of its ~64 ads), so "not seen" never means "did not run".
5. **Big brands.** Bupbes has ~830 ads; loading stopped at 456 after ~10 minutes, so older ads may be missing.
6. **Snapshot quality.** Grids are screenshots of frames at about 300 px tall, enough to see the idea, not to reuse.
7. **Rows folded before 26 Nov.** Earlier runs folded videos and carousels with the same copy, format and card count into one row (other IDs in the note): 54 rows hold 90 more IDs. On 26 Nov three folded IDs were opened next to their row's grid (Bupbes 1515527936510892, 1643115670746420, 1079318697981481) and showed the same picture, i.e. one creative under several IDs. Imports now keep one row per Library ID and merge only by image hash.
8. **Cherie.** Business MD says Cherie runs no Meta ads of its own; its page "Cherie" has ~54, linking to cherieattire.com (checked 25 Nov). Search `cherieattire`. Fanci Club really has none of its own.
9. **Where this lives.** The skill is its own repo; the output for SHER sits here as `meta-sher/`.

## Page

Ads are grouped by look (how they were shot, judged from the pictures), not by caption. Each look with one line on what puts an ad in it (`meta-sher/group-notes.tsv`) and its ads ranked by score; the first 12 show, the rest are behind "show all". The version with a caption "angle" filter is kept on branch `legacy-v0.4-looks-angle`.

