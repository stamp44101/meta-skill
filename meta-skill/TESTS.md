# Meta SKILL — tests

## Log

### Run 1 — 25 Nov 2026, Malimarea (v0.1)
- Search: keyword "malimarea", all statuses, all countries, FB+IG. 91 ads loaded (library says ~130), 87 own, 4 by others (all under 30 days).
- Kept 10 (30+ days). 52 more had 2+ ads on the creative but ran under 30 days: left out (README, Open for discuss 1).
- Snapshot grids: 8 videos (6 frames each), 2 images. No download, no paid tool.
- Same creative under two IDs (2187111091693389 and 1684969342823966) merged into one row by image hash: 9 rows.
- Types: "new drop or collection" (8), "discount or code" (1).
- Re-ran the same run file: 0 added, 10 updated, logs not duplicated.

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

### Scoring
Must pass: T1, T2, T5. Others: at least 2 of 3.
