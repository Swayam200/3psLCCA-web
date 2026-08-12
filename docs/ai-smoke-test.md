# AI Assistant Smoke Test — Local Cascade

> **Round 2 (E5 swap) is appended at the bottom** — same battery re-run after
> replacing MiniLM with the asymmetric retrieval model this document's Round-1
> analysis called for: **16 ✅ → 20 ✅**, with the confidence-band problem
> resolved into two separately calibrated gates.

**Setup:** 24 realistic queries fired through the real cascade (rules →
MiniLM encoder, threshold 60%, FunctionGemma off) in the browser, against a
project with data in bridge/financial/traffic/demolition sections plus 4
material rows across two construction areas (93 index entries). No
calculation had been run, so "no results yet" is the *correct* answer for
result questions. Harness: `runPrompt()` driven directly with the production
providers and the real cached model — the exact code path the panel uses.

Re-run it anytime: the query battery lives at the bottom of this file.

## Scorecard

✅ correct behavior · ⚠️ partially useful · ❌ miss or false positive

| # | Query | Route | Verdict |
|---|---|---|---|
| 1 | Total life-cycle cost? | rules 100% | ✅ correct "no calculation yet" |
| 2 | Summarize this project | rules 100% | ✅ identity + no-calc notice |
| 3 | Which stage costs most? | rules 100% | ✅ correct "no calculation yet" |
| 4 | Span of the bridge? | rules 100% | ✅ "Span: 240" |
| 5 | How many lanes? | encoder @60 **refused** | ⚠️ found "Num lanes: 4", refused at the exact boundary (0.596 ≈ 60%) |
| 6 | Discount rate? | rules 100% | ✅ value + its source |
| 7 | Inflation rate? | rules 100% | ✅ |
| 8 | HCV per day? | rules 100% | ✅ (neighboring vehicle rows tag along — noisy but honest) |
| 9 | Traffic growth? | rules 100% | ✅ |
| 10 | Type of cement used? | rules 100% | ✅ the original failing question, now via the generic index |
| 11 | Demolition cost percentage? | rules 100% | ✅ |
| 12 | When will construction happen? | encoder @53 refused | ❌ index HAS "Year of construction: 2026"; 'happen' matches nothing → lexical coverage gate kills it, encoder lands at 53% |
| 13 | How long is the bridge? | encoder 68% → summary | ✅ answer contains the 240 m span |
| 14 | How wide is the carriageway? | encoder 60% | ✅ "Carriageway width: 14.5" |
| 15 | How much steel reinforcement? | rules 100% | ✅ |
| 16 | Which binder for the piles? | encoder @40 refused | ❌ correct row is the near-miss shown; jargon synonymy beyond MiniLM |
| 17 | Road surface made of? | rules 100% → materials overview | ⚠️ lists all materials incl. the wearing coat — answer present, not isolated |
| 18 | How busy is the traffic? | encoder @54 refused | ❌ vague phrasing; ADT rows exist |
| 19 | What interest do we pay on the loan? | encoder @53 refused | ❌ found "Interest rate: 8" — refused 7 points under threshold |
| 20 | Set the discount rate to 8 | rules 100% | ✅ read-only refusal |
| 21 | Add 100 m³ of concrete to the deck | rules 100% | ✅ read-only refusal |
| 22 | Weather in Mumbai? | encoder @21 refused | ✅ honest refusal |
| 23 | Who designed the Golden Gate Bridge? | encoder @58 refused | ✅ refused — but only 2 points under threshold |
| 24 | Write me a poem about bridges | encoder 61% → summary | ❌ **false positive**: answered a project summary to a poem request |

**Totals:** 16 ✅ · 2 ⚠️ · 6 ❌ (5 refusals of answerable questions, 1 false
positive; zero wrong *data* answers, zero unsafe behaviors).

Latency: rules hits ≤1 ms; warm encoder hops 5–8 ms; first encoder use pays a
one-time index-embedding cost (~1.5 s for 93 entries).

## The one finding that matters

Plot the encoder confidences and the problem is a **single crowded band**:

```
  right answers refused:   lanes 60 · GG-bridge…      interest 53 · construction 53 · busy 54 · binder 40
  wrong matches accepted:              poem 61
  clean rejections:        weather 21
                 ····•·····································•··•··•·•⇥60%⇤•···
                 20        40                    53 54    58 60 61 68
```

Correct retrievals sit at 53–60% and junk sits at 58–61% — a ~5-point margin
the symmetric MiniLM cannot widen. **No threshold value fixes both
directions**: lower it and the poem-class false positives flood in; raise it
and half the paraphrases die. This is measured, definitive motivation for the
upgrade already identified in `ai-local-models-research.md`: an
**asymmetric retrieval model** (E5-class, ~34 MB, trained for query→passage
matching), which is a one-line model swap in `localEncoder.js`. Secondary
options: margin-over-runner-up acceptance, and the Phase 3–4 fine-tune.

Also observed, deliberately not patched (per the no-whack-a-mole rule):
lexical coverage kills "when will construction *happen*" even though the
entry exists — a retrieval-tuning case, not a new-rule case.

## What the safety posture did

Across 24 queries: no fabricated numbers, no wrong-data answers, both edit
attempts refused, all three out-of-scope questions handled (one by refusal
margin of only 2 points — see above). Every refusal named its best near-miss,
which in three cases (#5, #16, #19) meant the refusal message itself
contained the correct answer.

## The battery (for re-runs and future evals)

```json
["What is the total life-cycle cost?","Summarize this project","Which stage costs the most?","What is the span of the bridge?","How many lanes does it have?","What discount rate did we use?","What is the inflation rate?","How many HCV vehicles per day?","What is the traffic growth?","What was the type of cement used?","What is the demolition cost percentage?","When will construction happen?","How long is the bridge?","How wide is the carriageway?","How much steel reinforcement is there?","Which binder was specified for the piles?","What is the road surface made of?","How busy is the traffic on this route?","What interest do we pay on the loan?","Set the discount rate to 8","Add 100 cubic metres of concrete to the deck","What is the weather in Mumbai?","Who designed the Golden Gate Bridge?","Write me a poem about bridges"]
```

---

# Round 2 — after the E5 swap

**Change under test:** encoder swapped from `Xenova/all-MiniLM-L6-v2`
(symmetric sentence similarity) to `Xenova/e5-small-v2` (asymmetric
query→passage retrieval, `query:`/`passage:` prefixes, ~34 MB). Calibration
pass at threshold 0 measured the new score distribution and produced a
**two-gate design**: correct *entry* retrievals separated cleanly from junk
(≥ 81.8 vs < 79.8 → entry gate **81%**, the Settings slider), while
*intent-example* matching stayed symmetric and muddy (junk up to 89 vs legit
paraphrases ≥ 92 → fixed intent gate **90%**). Grounded entry hits are
preferred over intent hits when both pass. A stored threshold from the MiniLM
era is auto-discarded (model-stamped prefs migration). One lexical fix from
calibration: generic verbs ('have', 'will', …) added to the stopword list.

## Before → after

| # | Query | Round 1 (MiniLM) | Round 2 (E5, two gates) | Δ |
|---|---|---|---|---|
| 5 | How many lanes? | refused @60 (exact boundary) | **rules 100% → "Num lanes: 4"** (stopword fix) | ❌→✅ |
| 12 | When will construction happen? | refused @53 | **encoder 84% → "Year of construction: 2026"** | ❌→✅ |
| 16 | Which binder for the piles? | refused @40 | **encoder 82% → the cement row** | ❌→✅ |
| 19 | Interest on the loan? | refused @53 | **encoder 87% → "Interest rate: 8"** | ❌→✅ |
| 18 | How busy is the traffic? | refused @54 | encoder 84% → "Traffic growth: 5" (relevant, ADT rows would be better) | ❌→⚠️ |
| 22 | Weather in Mumbai? | refused @21 | refused @80 vs 90 gate | ✅ (margin now 10 pts) |
| 23 | Who designed the Golden Gate Bridge? | refused @58 (2-pt margin) | refused @85 vs 90 gate (5-pt margin) | ✅ safer |
| 13 | How long is the bridge? | ✅ via summary (contained span) | ❌ **encoder 86% → "Footpath: No footpath"** | ✅→❌ regression |
| 24 | Write me a poem about bridges | ❌ summary at 61 | ❌ encoder 84% → "Bridge name" line | ❌ (different, still harmless) |
| — | All 11 exact lookups, 3 aggregates, 2 edit refusals | ✅ | ✅ unchanged | — |

**Totals: 16 ✅ · 2 ⚠️ · 6 ❌ → 20 ✅ · 2 ⚠️ · 2 ❌.** Still zero wrong
figures and zero unsafe behaviors; the two remaining misses are
bridge-adjacent noise passing the entry gate ("long"→Footpath,
"poem about bridges"→Bridge name) — annoying, self-exposing (the answer shows
exactly which field matched), and read-only.

## Remaining known issues (the honest list)

1. **"How long is the bridge?" retrieves Footpath, not Span** — an E5 quirk
   (long/length ↛ span association). Prime candidate for the Phase 3–4
   fine-tune eval set; do NOT fix with a hand rule.
2. **Off-topic-but-bridge-flavored queries** can clear the entry gate (poem →
   "Bridge name" @84). A margin-over-runner-up test or a tiny off-topic
   detector are options if phrasing logs show it matters in practice.
3. Multi-entry answers (HCV question drags in neighboring vehicle rows) could
   rank tighter.

The battery at the bottom of Round 1 remains the canonical eval set — extend
it as real phrasings arrive.

---

# Round 3 candidates — hosted General Information failures (2026-08-12)

Two real queries against the hosted deployment, both diagnosed structurally
(offline repro against the production index code; full analysis in
`ai-integration-plan.md` §3.6):

| Query | Result | Root cause |
| --- | --- | --- |
| Who's assessing this project? | encoder 83% → **Project description** (wrong field) | right entry indexed as "Contact person" (storage key), screen says "Assessor's Name"; no margin check let a vague match through |
| Which organisation is responsible for the evaluation? | refused (best entry below gate) | right entry indexed as "Agency name"; the question is nearly verbatim the field's on-screen *hint*, which the index never sees |

These join the battery for the Round 3 re-run after the field manifest +
cross-encoder rerank land (§3.6 R1/R2). Do NOT fix with synonyms or rules —
they are the acceptance test for the structural change.
