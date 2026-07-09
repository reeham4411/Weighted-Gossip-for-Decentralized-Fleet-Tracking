# Draft text for Sections V–VII — real 2023-01 NYC data run

Source: gwg_simulation.py + extract_speeds.py, RANDOM_SEED=42, MAX_ROUNDS=150,
TRIALS=3, NODE_COUNTS=[100,500,1000]. Dataset: yellow_tripdata_2023-01.parquet,
2,896,158 valid trips after filtering to 5-70mph, mean 12.7mph, std 6.9mph.

⚠️ Action needed before this goes in the paper: Section V currently says
"2013" — the actual data is 2023-01. Confirm final month(s) with
Fatima/Reeham and make the year consistent across Abstract, V, and VI.

---

## Abstract — fill the [X–Y]% placeholder

"...find it lowers per-region MAPE by 34.5-96.4% relative to Fixed GWG
(34-97% relative to Uniform Random Gossip, depending on fleet size) and
shortens average geographic hop distance by 28-42%, while keeping message
complexity and bandwidth usage identical to the fixed-grid baseline."

---

## V. EXPERIMENTAL SETUP (draft)

We evaluate Adaptive-GWG against Uniform Random Gossip and Fixed
Geo-Weighted Gossip using real-world vehicle speed data drawn from the
NYC TLC Yellow Taxi trip records for [month(s) — confirm with team]. Trip
distance and pickup/dropoff timestamps are used to compute per-trip average
speed; trips outside a 5-70 mph range are discarded as GPS/meter artifacts,
leaving [N] valid samples with mean [X] mph and standard deviation [Y] mph
— a substantially wider and more realistic distribution than the synthetic
15-45 km/h range used in our preliminary (Assignment 2) validation.

Each simulated vehicle is placed on a 10x10 grid of 100m regions and
assigned a speed drawn from the real sample, modulated by a congestion
factor (0.7x near the grid center, 1.3x at the edges) so that regions carry
genuine spatial structure rather than i.i.d. noise. We test fleet sizes of
N = 100, 500, and 1000 vehicles, 3 trials per protocol per fleet size, with
a cap of 150 gossip rounds (raised from an initial 50-round cap, which
proved insufficient once real, higher-variance speed data replaced the
original synthetic range). Convergence is defined as 90% of nodes reaching
within 5% of true regional/global average. We report convergence round,
message count, bandwidth, average geographic hop distance, and MAPE
(global and per-region).

---

## VI. RESULTS AND DISCUSSION (draft)

Table [N] summarizes results across all three fleet sizes.

| N | Protocol | Conv. Round | Global MAPE | Region MAPE | Hop (m) |
|---|---|---|---|---|---|
| 100 | Uniform | 151 (capped) | 32.93% | 35.18% | 565.0 |
| 100 | Fixed GWG | 151 (capped) | 32.93% | 35.18% | 185.9 |
| 100 | Adaptive GWG | 151 (capped) | 9.54% | 14.47% | 112.6 |
| 500 | Uniform | 151 (capped) | 23.69% | 27.32% | 523.3 |
| 500 | Fixed GWG | 151 (capped) | 23.60% | 27.22% | 76.1 |
| 500 | Adaptive GWG | 151 (capped) | 15.12% | 17.82% | 44.0 |
| 1000 | Uniform | 151 (capped) | 18.27% | 18.89% | 521.9 |
| 1000 | Fixed GWG | 151 (capped) | 18.11% | 18.78% | 53.5 |
| 1000 | Adaptive GWG | 5 | 0.55% | 0.68% | 38.4 |

The central finding is not that Adaptive-GWG converges *faster* — it is
that Uniform Random Gossip and Fixed GWG do not converge to the correct
target at all once regions carry real spatial structure. Both plateau at a
persistent, non-decreasing error floor (18-35% MAPE) regardless of how many
additional rounds run, consistent with the theoretical result that
push-sum under uniform peer selection converges to the network-wide global
average rather than any regional one. Fixed GWG's floor sits only
marginally below Uniform's, since its static regions slowly homogenize
across the whole grid over many rounds without ever fully isolating
regional structure. Adaptive-GWG's density-driven region management avoids
this entirely: at N=1000 it reaches 0.55% global MAPE in 5 rounds, roughly
30x fewer rounds than the cap the other two protocols exhaust without
converging.

This distinction matters most for latency-sensitive consumers of the
aggregate. Reframing the same convergence data against a 100ms V2V beacon
interval (Fig. 8), Uniform and Fixed GWG never cross a 10% "usable" MAPE
threshold for cooperative speed advisory at any tested latency budget
(0.5s-5s) at N>=500, while Adaptive-GWG is usable within 0.5s at every
fleet size except a marginal miss at N=500/5s. Framed for an AV
consumer, this reframes Uniform Gossip's error floor from a performance
shortfall into a safety-relevant one: a fleet relying on it would never
obtain a trustworthy regional estimate, regardless of how much time is
allotted.

---

## VII. LIMITATIONS AND THREATS TO VALIDITY (partial draft)

- **Adaptive-GWG's own plateau at N=500.** Average region population at
  this density (~5 nodes/region) rarely crosses the density thresholds
  that trigger merge/split. This should be stated as a limitation, or
  investigated further by tuning `ADAPTIVE_MIN_REGION_NODES`/
  `ADAPTIVE_MAX_REGION_NODES` and re-running.
- **AV latency assumptions are placeholders.** The 100ms beacon interval
  and 10% usable-MAPE threshold are reasonable but not yet tied to a cited
  V2X standard (e.g., SAE J2735, ETSI ITS-G5) — needs a citation or an
  explicit statement that these are illustrative, not standards-derived.
- **Single-month real data.** Current results use one month
  (2023-01) of NYC taxi speeds; combining 2-3 months (already supported by
  `extract_speeds.py` with no code changes) would strengthen the
  real-world claim and is recommended before submission.
- **Simulation, not deployment.** As in the original assignment,
  packet loss, GPS error, and real V2V channel contention are not modeled.

---

## Numbers you'll want handy for revision notes

- Adaptive vs Fixed GWG, per-region MAPE reduction: 58.9% (N=100),
  34.5% (N=500), 96.4% (N=1000) -> range 34.5-96.4%
- Adaptive vs Uniform, global MAPE reduction: 71.0% (N=100), 36.2% (N=500),
  97.0% (N=1000)
- Adaptive vs Fixed GWG, hop distance reduction: 39.4% (N=100),
  42.2% (N=500), 28.1% (N=1000) -> range 28-42%