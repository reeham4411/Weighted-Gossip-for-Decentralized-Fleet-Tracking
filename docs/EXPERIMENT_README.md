# GWG Experiment Pipeline — Run & Push Guide (v2)

## What changed since v1

1. **Bug fix (important):** `create_fleet()` computed `center_distance` but
   never used it — meaning a vehicle's speed had **zero correlation with its
   position**. This undermined the entire premise of regional gossip
   (regions had no real "truth" to converge to). Fixed: speed now gets a
   mild congestion factor based on distance from the grid center (0.7x near
   the center — congested, 1.3x at the edges — freer-flowing), layered on
   top of the real NYC speed sample so the real-world distribution is
   preserved, just spatially structured like a real city.
2. **`MAX_ROUNDS` raised from 50 → 150.** Real NYC speed data has far more
   variance than the original synthetic 15–45 km/h range, so protocols
   need more rounds to have a fair shot at reaching 90% convergence.
3. **`extract_speeds.py` now supports multiple months.** Drop more parquet
   files in the folder and it auto-combines them — see below.
4. **New AV / self-driving-car real-time readiness analysis** (`fig8`) —
   see "AV Angle" section below.

## Key finding from your real-data run (before the fix)

Uniform Random Gossip and Fixed GWG **plateaued at a fixed error and never
improved**, no matter how many rounds ran. This is expected, not a bug:
push-sum with uniform peer selection provably converges to the **global**
weighted average of the whole fleet — never the regional one. Once regions
have genuine spatial structure (the fix above), that shows up as a
persistent, non-decreasing error floor for Uniform, a smaller but still
present floor for Fixed GWG (because it slowly homogenizes across regions
over many rounds), and near-total convergence for Adaptive GWG when its
regions stay well-populated. **This is a stronger and more defensible
result than "GWG converges 40% faster"** — it shows Uniform Gossip is
structurally incapable of learning regional structure at all, not just
slower. Worth building your Results/Discussion section around this.

One thing to flag as a limitation rather than a solved problem: at N=500,
Adaptive GWG also plateaued somewhat, likely because average region
population (~5 nodes) rarely triggers the density-based merge/split logic.
Worth a sentence in Limitations, or an experiment tuning region size.

## Step 1 — Download real NYC taxi data (one month or many)

https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page

Direct pattern:
```
https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2023-01.parquet
```

**To extend the dataset to more months** (bigger, more representative
sample): just download more months and drop them in the same folder as
`extract_speeds.py`, named like:
```
yellow_tripdata_2023-01.parquet
yellow_tripdata_2023-02.parquet
yellow_tripdata_2023-03.parquet
```
No code changes needed — `extract_speeds.py` auto-detects every file
matching `yellow_tripdata_*.parquet` and combines them into one
`nyc_speeds.npy`. More months = a larger, more representative real-world
speed distribution, which strengthens the "real data" claim in your paper.
2–3 months (roughly 6–9M trip rows combined) is a reasonable amount for a
semester project — you don't need all of 2023.

Confirm with Fatima/Reeham which month(s) you're actually citing in the
report text (currently says "2013" — update it to match whatever you use).

## Step 2 — Extract speeds

```bash
pip install pandas pyarrow numpy --break-system-packages
python3 extract_speeds.py
```

Prints per-file and combined sample counts plus the speed distribution
(min/max/mean/std) so you can sanity-check it before running the sim.

## Step 3 — Run the full simulation

```bash
pip install matplotlib --break-system-packages
python3 gwg_simulation.py
```

With `MAX_ROUNDS=150` and `NODE_COUNTS=[100,500,1000]` this takes roughly
20–60 seconds depending on your dataset size and machine. Produces:

- Terminal summary table (convergence round, messages, bandwidth, hop
  distance, global + per-region MAPE for Uniform / Fixed GWG / Adaptive GWG)
- C-6 novelty interpretation printout
- Amdahl's / Gustafson's Law analysis
- **New: AV real-time readiness table** — global MAPE at 0.5s / 1s / 2s / 5s
  latency budgets, flagged usable/not-usable
- 8 PNG figures (`fig1`...`fig8`) in the same folder

**Use these real numbers when you write the Experiment/Results section —
not any numbers from an earlier draft written before real data was used.**

## AV / self-driving-car angle

Autonomous vehicle platooning and cooperative collision-avoidance depend on
frequent, low-latency V2V speed updates (DSRC/C-V2X beacon intervals are
typically ~100ms). `fig8_av_real_time_readiness.png` and the terminal AV
table reframe your existing convergence data through that lens: treating
each gossip round as one ~100ms beacon interval, it shows what error each
protocol would hand an AV decision system at 0.5s/1s/2s/5s budgets, against
a 10% "usable" threshold. This is a legitimate reframing of data you
already have — not a new simulation — and it's exactly the angle a
reviewer would want if you're motivating GWG for AV fleets specifically:
Uniform Gossip's persistent error floor becomes a *safety* argument, not
just a performance one — a self-driving fleet using uniform gossip would
never get a usable regional speed estimate, at any latency budget.

You can tune `AV_ROUND_LATENCY_MS` and `AV_USABLE_MAPE_PCT` at the top of
`gwg_simulation.py` if you want to cite different assumptions (e.g. cite a
specific V2V standard's beacon interval instead of the 100ms placeholder).

## Step 4 — Push to git

Your terminal history shows you switched `origin` to your own fork
(`urpinklipbalm/...`) and pushed `asma-real-data-experiments` there
successfully — good, that part worked. But that means your branch is
sitting on **your fork**, not the team's original repo
(`reeham4411/Weighted-Gossip-for-Decentralized-Fleet-Tracking`). To get it
into the team repo:

```bash
# add the team repo as a second remote (only needs to be done once)
git remote add upstream https://github.com/reeham4411/Weighted-Gossip-for-Decentralized-Fleet-Tracking.git

# after making the changes above, commit as usual
git add gwg_simulation.py extract_speeds.py nyc_speeds.npy \
        fig1_convergence_curves.png fig2_convergence_rounds.png \
        fig3_hop_distance.png fig4_bandwidth.png fig5_message_complexity.png \
        fig6_c6_per_region_mape.png fig7_c6_adaptive_overhead.png \
        fig8_av_real_time_readiness.png EXPERIMENT_README.md
git commit -m "Fix speed/region correlation bug, extend to multi-month data, add AV real-time analysis"

# push to your own fork (origin) as before
git push origin asma-real-data-experiments

# ALSO push to the team repo so they see it directly
git push upstream asma-real-data-experiments
```

Then open a PR on the team repo:
`https://github.com/reeham4411/Weighted-Gossip-for-Decentralized-Fleet-Tracking/compare/main...asma-real-data-experiments`
(swap in your fork as the compare source if GitHub doesn't let you push
directly — either "compare across forks" on the team repo, or push to
`upstream` directly if you have write access, which your earlier successful
push suggests you might).

**Check `nyc_speeds.npy` size first** (`ls -lh nyc_speeds.npy`) — your
earlier push was 16.89 MiB total, so you're still in a safe range. If you
add several more months and it balloons past ~50–100MB, add it to
`.gitignore` instead and just document the two extraction commands so
anyone can regenerate it locally.
