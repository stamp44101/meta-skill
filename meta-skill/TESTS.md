# Meta SKILL — tests

## Log

### Run 1 — 25 Nov 2026, Malimarea (v0.1)
- Search: keyword "malimarea", all statuses, all countries, FB+IG. 91 ads loaded (library says ~130), 87 own, 4 by others (all under 30 days).
- Kept 10 (30+ days). 52 more had 2+ ads on the creative but ran under 30 days: left out (README, Open for discuss 1).
- Snapshot grids: 8 videos (6 frames each), 2 images. No download, no paid tool.
- Same creative under two IDs (2187111091693389 and 1684969342823966) merged into one row by image hash: 9 rows.
- Types: "new drop or collection" (8), "discount or code" (1).
- Re-ran the same run file: 0 added, 10 updated, logs not duplicated.

### Run 2 — 25 Nov 2026, all five SHER competitors (v0.2)
| Brand | Search | Loaded / library | Kept |
|---|---|---|---|
| Bupbes | keyword `bupbes` | 456 / ~830 | 89 (162 ads 30+ days, folded by creative) |
| Maël | keyword `mael.vn` | 47 / ~65 | 18 (incl. a Thai rental shop renting a Maël piece) |
| Malimarea | Run 1 | 91 / ~130 | 9 |
| Cherie | keyword `cherieattire` | 39 / ~54 | 7 (Business MD said none) |
| Fanci Club | phrase `"fanci club"` | 23 / ~29 | 1 (consignment store) + the gift-shop ad already under Bupbes |
- 124 rows, 8 types. "new drop or collection" split three ways (styled look, single piece spotlight, mood, no product named); on-body range shots merged into catalogue product cards. All logged.
- Fixes found by running it: scrolling in one call froze the tab past ~100 cards (now background `autoscroll` + `status`); results past ~1,500 characters are cut (now `export` → `get_page_text` file → `build.py import`); `window.name` keeps the script across navigation; single images with the same copy are different pictures (no longer folded).

### Run 3 — 25 Nov 2026, where the kept ads ran (v0.3)
Each brand's search repeated with `country=XX` for 20 markets (Maël: 32), checking which of the 124 kept ads come back.
| Brand | Kept ads seen | Main markets (kept ads seen) |
|---|---|---|
| Bupbes | 88 / 89 | KR 85, US 76, GB 72, CA 52, DE 51, AU 50, AE 47, VN 33, TH 32, HK 31 |
| Maël | 8 / 18 | VN 7, TH 4, ID 3, KR 3 (10 own ads not seen in 32 markets) |
| Malimarea | 9 / 9 | US 8, GB 8, AU 8; one ad in AE, FR, DE only |
| Cherie | 7 / 7 | CA 7, GB 6, AU 3, US 1 |
| Fanci Club | 1 / 1 | US |
- Found by running it: the filter misses ads (Maël's VN search returns 20 of its ~64 ads, and 10 kept ads appear in no market), so "not seen" never means "did not run". Long pages stall while loading: a second pass with a small scroll jump added cards (Bupbes GB 185 → 266), so passes are added up. The CSP now blocks `eval`, so adlib.js is pasted after each navigation and `window.name` carries the ID list instead. Six tabs in parallel froze the browser on Bupbes-size pages; three worked. Replaying the library's own search request from the page was refused by the safety check, so the step uses the normal page only.

### Run 4 — 25 Nov 2026, nine more brands (v0.3)
Same steps as Runs 2–3, merged into the same meta-sher (124 → 220 ads).
| Brand | Search | Found → kept (under 30 days) | Kept ads seen in 20 markets |
|---|---|---|---|
| IAM COCO | keyword `iamcoco` | 46 → 32 (11) | 31 / 32: VN 30, TH 30, MY 30, PH 30, AU 30, HK 23, TW 17 |
| JC de JC | phrase `"jc de jc"` | 125 → 39 (81) | 38 / 39: VN 31, TH 5, SG 2 |
| JUBIN STUDIO | phrase `"jubin studio"` | 64 → 14 (50) | 14 / 14: VN 13; one ad in SG, HK, AU, US, GB |
| RUE de RUE | phrase `"rue de rue"` | 132 → 8 (104) | 5 / 8: VN 5 only |
| Viery | keyword `viery`, VN only | 13 → 3 (9) | 3 / 3: VN |
| La Vierge | keyword `lavierge` | 65 → 0 (62) | — |
| JENÉA By Jenny | keyword `jenea` | 81 → 0 (70) | — |
| Karlotta Concept | phrase `"karlotta concept"` | 23 → 0 (23) | — |
| Chérieon | keyword `cherieon` | 33 → 0 (33) | — |
- Four brands kept nothing: every own ad is under 30 days; their 30+ day matches were other businesses sharing the word. The Viery page runs no ads; its 3 kept ads are Shopee affiliate posts (kept as `other`), and the all-country search is ~4,200 Slovak "viery" ads, so the search was narrowed to VN. New type: `customer quote` (RUE de RUE, 2 ads). Group notes rewritten where the new brands made them wrong ("only Bupbes", "one ad only").
- Found by running it: the extension redacts 16-digit IDs as card numbers, so export writes them as `12345678x…` and import strips the `x`. Import read only the first text part of a batch result (0 ads found); it now joins all parts. Viery's big pages (US, GB, FR, DE: 150–230 unrelated ads) froze tabs at 15 scroll rounds; 10 rounds plus a read-only re-check after the freeze worked, marked `done=false`.

### Scout — 25 Nov 2026, the five SHER competitors
| Brand | Own ads | Ads by others |
|---|---|---|
| Bupbes | ~830; live ones all ≤7 days old; of the first 100, 63 ran 30+ days (up to 195) | a Taiwan gift shop (141 days) |
| Maël ("Maël Femme") | 26; 18 ran 30+ days (up to 172) | keyword noise (Oral-B, padel club) |
| Fanci Club | none | Printemps, boutiques, a resale shop (40 days), stylists |
| Cherie Attire | none | none |
| Malimarea ("Mali marea") | ~130; none live; up to 89 days | almost none |

## Scenarios

Run each in a fresh chat with the skill installed. Mark ✅/❌.

**T1 — Happy path.** `รัน Meta SKILL ให้ SHER: Maël`
- [ ] Searches all statuses, all countries, FB+IG; pastes adlib.js after navigating
- [ ] Keeps only 30+ day ads; drops off-topic keyword matches
- [ ] Grid per kept ad at scale 1, trimmed into `meta-sher/images/`
- [ ] Types reused from the TSV; new types logged with a reason
- [ ] Builds, opens the HTML, sends it with "found → kept"

**T2 — Re-run.** Run T1 again a week later.
- [ ] No duplicate rows; last_seen updated; ended ads marked ended, not removed

**T3 — Brand with no ads.** `…: Cherie`
- [ ] Says no ads were found, writes a runs-log row, adds nothing

**T4 — Other people's ads.** `…: Fanci Club`
- [ ] Keeps stockist/resale/creator ads naming the brand as `other`, typed and ranked like the rest

**T5 — Brand not in the list.** `เพิ่มแบรนด์อื่นที่คล้ายๆ ให้ด้วย`
- [ ] Does not add brands on its own; asks for names or points to Business MD

**T6 — Big brand.** `…: Bupbes`
- [ ] Loads in steps under 45 s, reports if loading stalled before the library's total

**T7 — Where it ran.** `…: Malimarea` after a run
- [ ] Checks each market with the country filter, records `countries` and `geo-log.tsv`, and says "not seen in N markets" for the rest, never "did not run"

### Scoring
Must pass: T1, T2, T5. Others: at least 2 of 3.
