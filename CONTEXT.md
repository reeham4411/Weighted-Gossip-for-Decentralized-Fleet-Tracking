# PDC GWG Project — Context Handoff

Paste this whole file at the start of a new chat (along with the current
`gwg_simulation.py`, `extract_speeds.py`, and your latest `fig*.png` files)
to pick up exactly where this session left off.

## Project

Geo-Weighted Gossip (GWG) for Decentralized Fleet Tracking — PDC semester
project. Team: Asma Imran (481920), Fatima Ali (470708), Adeena Reeham
(480941). Repo (team, original): `reeham4411/Weighted-Gossip-for-Decentralized-Fleet-Tracking`.
Asma's fork: `urpinklipbalm/Weighted-Gossip-for-Decentralized-Fleet-Tracking`.

Division of labor per team chat: Asma owns the experiment/dataset/code
side; Fatima + Reeham own the literature review and are drafting an IEEE-
format paper for Asma to fill in the experiment/results section of.

## What's been done, in order

1. Original assignment doc (`PDC_A2_GWG_FINAL_WithTOC.docx`) describes the
   full system design: geo-weighted gossip protocol, push-sum aggregation,
   adaptive zone sizing (the C-6/novel contribution), Amdahl/Gustafson
   analysis, etc. — all based on **synthetic** speed data at that stage.
2. `extract_speeds.py` was written to pull real speeds from NYC TLC Yellow
   Taxi parquet trip data (filters trips to realistic 5–70mph, computes
   speed = distance/duration).
3. `gwg_simulation.py` already had real-data loading wired in
   (`np.load("nyc_speeds.npy")` feeding `create_fleet()`) before this
   session started — that integration was already someone else's/earlier
   work, not something built in this session.
4. **This session, first pass:** validated both scripts end-to-end with a
   synthetic stand-in dataset (no real data downloaded, since the sandbox
   here can't reach nyc.gov/cloudfront — only PyPI/npm/GitHub). No bugs
   found in that pass. Delivered files + a v1 README with git push steps.
5. Asma ran it for real on her machine with actual NYC data, got 7 result
   figures, and pushed a branch (`asma-real-data-experiments`) to her own
   fork (`urpinklipbalm/...`) — note: NOT yet pushed to the team's original
   repo (`reeham4411/...`), that's still pending.
6. **This session, second pass (current):** analyzed the 7 real-data
   figures Asma uploaded. Found a real, substantive issue:
   - `create_fleet()` computed `center_distance` (distance of a vehicle's
     region from the grid center) but **never used it** — speed was
     assigned with zero correlation to position. This meant "regional
     ground truth" had no real spatial meaning, and results were
     confounded.
   - **Fixed**: speed now gets a congestion factor (0.7x near center,
     1.3x at edges) layered onto the real NYC speed sample, giving
     regions genuine spatial structure.
   - **Key finding surfaced from this**: Uniform Random Gossip provably
     converges only to the *global* average, not regional — so once
     regions have real structure, Uniform's error plateaus permanently
     and never improves with more rounds. Fixed GWG does better but still
     slowly homogenizes over many rounds. Adaptive GWG converges near-
     completely (when its regions stay well-populated). This reframes the
     paper's core argument: GWG's advantage isn't just *speed* of
     convergence, it's *whether convergence to the right target happens at
     all*.
   - Also found: `MAX_ROUNDS` was 50, too low for real (higher-variance)
     data to have a fair shot at converging — raised to 150.
   - Added: multi-month support in `extract_speeds.py` (glob-matches
     `yellow_tripdata_*.parquet`, auto-combines any number of files —
     no code changes needed to add more months).
   - Added: AV/self-driving-car real-time readiness analysis
     (`compute_av_readiness`, `print_av_readiness`, `plot_av_readiness` →
     `fig8_av_real_time_readiness.png`) — reframes existing convergence
     curves as "would this protocol give an autonomous vehicle a usable
     speed estimate within a realistic V2V decision budget (0.5s–5s)?"
     Assumes 1 gossip round ≈ 100ms V2V beacon interval,
     "usable" = global MAPE ≤ 10%. This is a data reframing, not a new
     simulation — same underlying `err_curve` data, different lens.
   - Validated all of the above end-to-end with synthetic test data before
     handing off (found the same plateau pattern in test data too, which
     is what led to investigating and finding the `center_distance` bug).
   - Delivered: updated `gwg_simulation.py`, updated `extract_speeds.py`,
     updated `EXPERIMENT_README.md` (v2), and this context file.

## What's still outstanding / next steps

1. **Asma needs to re-run the pipeline with real data** using the updated
   `gwg_simulation.py` (with the bug fix + MAX_ROUNDS=150) — the 7 figures
   she already has are from the *pre-fix* version and should be regenerated.
2. Decide with Fatima/Reeham which month(s) of NYC data to actually cite
   (report text says "2013", script/download links used "2023-01" — pick
   one, ideally 2–3 months combined for a bigger sample per multi-month
   support added).
3. Push the updated code + regenerated figures to git — needs to go to
   the **team repo** (`reeham4411/...`), not just Asma's fork. See
   `EXPERIMENT_README.md` Step 4 for the `git remote add upstream` flow.
4. Write the actual Experiment/Results section of the IEEE draft using the
   regenerated real numbers — key narrative should center on the Uniform-
   Gossip-converges-to-global-not-regional finding, since it's a stronger,
   more defensible result than a generic "40% faster" claim.
5. Decide whether to address the N=500 Adaptive GWG plateau (region
   population too sparse to trigger adaptive merge/split) — either explain
   it as a limitation or tune region-size thresholds and re-test.
6. Investigate/confirm the AV latency assumptions (100ms round, 10%
   usable-MAPE threshold) against an actual V2V standard citation if this
   angle is going in the paper, rather than leaving them as placeholders.
7. Sync with Fatima/Reeham's literature review draft to make sure the
   Results section terminology and claims are consistent with what they've
   written.

## Known constraints for whoever continues this

- No access to nyc.gov/cloudfront to download real TLC data directly in
  a sandboxed session — real data extraction has to run on Asma's own
  machine.
- `nyc_speeds.npy` was ~16.89 MiB when first pushed (single month) — fine
  for git; keep an eye on size if combining several months.
- Team's `main` branch currently has 1 commit with the original 4 files
  (docx report, `gwg_simulation.py`, `extract_speeds.py`, this project's
  `project_explained.md`). Confirm with Reeham whether the team pushes
  directly to `main` or goes through PRs before merging.
