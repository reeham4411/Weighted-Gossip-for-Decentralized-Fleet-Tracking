# PR: Rebuild the evaluation on evidence — the headline result does not survive ablation

Open at:
https://github.com/reeham4411/Weighted-Gossip-for-Decentralized-Fleet-Tracking/compare/main...evidence-based-evaluation-rewrite

---

## Summary

An audit of our evaluation harness found that the result this project has been
reporting — a 34–96% per-region MAPE reduction attributable to adaptive region
management — does not hold. This branch rebuilds the harness, re-runs
everything, and rewrites the paper around what the evidence supports.

**The audit is reproducible**, not an assertion. Both scripts pin themselves to
the archived v1 so the finding stays checkable:

```bash
python3 scripts/audit_baseline_claims.py
python3 scripts/audit_ablation.py
```

## What was wrong with v1

| Defect | Evidence |
|---|---|
| The exchange was symmetric, not push-sum | every weight stayed at 1.0 all run, so the `(value, weight)` pair carried no information |
| Vehicles never moved | 0/100 nodes changed position over 30 rounds, in a paper titled "Highly Mobile Vehicular Networks" |
| The comparison was confounded | 65.9% of Fixed-GWG exchanges crossed a region boundary vs 2.6% of Adaptive-GWG's; nothing separated confinement from adaptation |
| The adaptive rule was a no-op where the win was largest | at N=1000 it relabelled 0% of vehicles, yet that is where v1 reported +96.4% |
| The merge rule never merged | sparse vehicles got label `('merged', T)`, which region T's own members never adopted |
| Each protocol was scored against its own partition | merging cells lowers reported error on its own |
| "Comparable bandwidth" was an identity | one exchange per vehicle per round for every protocol; region management sent no control traffic |
| Non-converging runs were averaged in at the cap | producing "151 rounds", which estimates nothing |

## What the corrected ablation shows

| N | Gain from region confinement | Gain from adaptive regions |
|---|---|---|
| 100 | +9.9% | −0.1% |
| 500 | +57.4% | −3.3% |
| 1000 | +48.1% | −0.2% |

**Region confinement accounts for the entire improvement.** Adaptive region
management adds nothing measurable on top of it at any fleet size, with
overlapping confidence intervals throughout, while carrying control traffic the
baseline does not. The threshold sweep supplies the mechanism rather than
restating the result: the best adaptive configuration is the one that changes
the partition least.

Two further findings:

- **Geographic weighting buys locality of communication, not of estimation.**
  Fixed GWG cuts mean hop distance 84% versus uniform gossip and barely improves
  accuracy — 68.9% of its exchanges still cross a region boundary.
- **A drift failure mode for push-sum on a mobile fleet.** Re-initialisation at
  boundaries refills regions with unaveraged readings; error bottoms out around
  round 9 then degrades ~4×. Periodic restart bounds it, and — diagnostically —
  does nothing for the unconfined baselines, confirming their floor is a
  wrong-target problem, not a convergence-rate one.

The scope of the negative result is stated explicitly in Section VI-B: it holds
for a grid already well matched to radio range with roughly uniform density,
which is the setting this protocol was designed and previously evaluated for.

## What changed

- `src/gwg_simulation.py` — rewritten: directional push-sum, per-round mobility
  and churn, the region-confined ablation, a protocol-independent reporting
  partition, control-message accounting, periodic restart, independent fleets
  per trial with 95% CIs, censored reporting of non-converging runs
- `src/legacy/gwg_simulation_v1.py` — v1 archived so the audit stays reproducible
- `tests/test_gwg.py` — 25 tests pinning each property above; several fail
  against v1 by design
- `scripts/make_results_sections.py` — paper Sections V–VII generated from
  `results/results.json`, so no number is hand-transcribed
- `scripts/build_paper.py` — assembles `paper/FULL_PAPER.md` (+ `.docx`), and
  warns while the title still names a contribution the results retract
- `results/results.json` — tracked; every cited number lives here, and a fresh
  run reproduces it byte-for-byte
- Superseded v1 docs banner-marked rather than deleted; their problem framing
  and mathematics remain useful

## Title decision

The paper previously ran under a title naming the adaptive layer as the
contribution, which the evidence no longer supports. The team has settled on
*What Actually Makes Geo-Weighted Gossip Regional: An Ablation of Region-Aware
Push-Sum for Vehicular Networks*, which matches Section VI-B's finding instead
of the claim it retracts.

## Verification

`bash scripts/verify_pipeline.sh` passes end to end: raw data, extraction
sanity, 25/25 tests, clean simulation, every field the generator reads, all 10
figures, and the paper assembling.
