# Adaptive Region-Aware Geo-Weighted Push-Sum Gossip

A leaderless gossip protocol that lets a fleet of vehicles compute live,
**per-region** average speed with no central server — evaluated against real NYC
TLC taxi trip data, with vehicles in continuous motion.

**Team:** Asma Imran (481920) · Fatima Ali (470708) · Adeena Reeham (480941)
School of Electrical Engineering and Computer Science, NUST

Four protocols are compared head to head:

| Protocol | Peer candidates | Role |
|---|---|---|
| Uniform Random Gossip | any vehicle, geography ignored | baseline |
| Fixed GWG | inverse-distance within radio range | baseline |
| **Fixed GWG (region-confined)** | within range **and** own grid cell | **ablation** |
| **Adaptive-GWG** | within range **and** own adaptive region | our protocol |

The third row is the one that matters methodologically. Without it, a comparison
credits adaptive region management with an improvement that region confinement —
a one-line change to the baseline — already delivers.

## What we actually found

Two mechanisms are usually bundled together under "adaptive geo-weighted gossip".
Only one of them is doing anything:

- **Region confinement accounts for the entire improvement.** Restricting peer
  selection to the sender's own grid cell — a one-line change to the fixed-grid
  baseline — reduces per-region error by +9.9% at N=100 (~1 vehicle/cell), +57.4%
  at N=500 (~5 vehicles/cell), and +48.1% at N=1000 (~10 vehicles/cell).
- **Adaptive region management adds nothing measurable on top of it**, at any
  fleet size tested (−0.1%, −3.3%, −0.2% respectively — confidence intervals
  overlap throughout), while it alone carries control-message traffic the
  confined baseline does not pay.

So the practical guidance is not a switch by density: in this setting — a fixed
grid already well matched to radio range, with roughly uniform vehicle density —
confine gossip to a region and stop there; the adaptive layer buys nothing here
and costs traffic. Whether adaptation earns its keep in a badly-sized or
wildly uneven-density deployment is outside what this evaluation covers.

Separately, **geographic weighting buys locality of communication, not locality of
estimation.** Fixed GWG cuts mean hop distance by ~84% versus uniform gossip but
barely improves accuracy: 68.9% of its exchanges still cross a region boundary at
N=1000, the gossip graph still spans the service area, and push-sum still
converges toward the city-wide mean. Confinement, not weighting, is what makes an
estimate regional.

Exact figures, confidence intervals and the claim-to-evidence map:
[`paper/RESULTS.md`](paper/RESULTS.md) and [`paper/NUMBERS.md`](paper/NUMBERS.md),
both generated from `results/results.json`.

### A correction to an earlier version of this work

An earlier harness (kept at [`src/legacy/gwg_simulation_v1.py`](src/legacy/gwg_simulation_v1.py))
reported 34–96% per-region MAPE reductions attributable to adaptive regions. That
result did not survive audit and has been withdrawn. The audit is reproducible:

```bash
python3 scripts/audit_baseline_claims.py   # push-sum, mobility, metrics, statistics
python3 scripts/audit_ablation.py          # the confounded comparison
```

It found that the exchange was symmetric rather than directional (so every
push-sum weight stayed at 1.0 and the protocol was plain pairwise averaging);
vehicles never moved, in a paper about mobile networks; each protocol was scored
against its own partition of the fleet, so merging cells lowered reported error on
its own; the merge rule assigned sparse vehicles a label the target region never
adopted, so it never merged anything; message and bandwidth counts were identical
by construction, making "comparable bandwidth" an identity rather than a result;
non-converging runs were averaged in at the round cap; and at N=1000 — where the
largest win was reported — the adaptive rule relabelled zero vehicles.

The current numbers supersede those entirely. `tests/test_gwg.py` pins each of
these properties so they cannot regress silently.

## Repo structure

```
.
├── README.md
├── src/
│   ├── extract_speeds.py            NYC TLC parquet -> data/processed/nyc_speeds.npy
│   ├── gwg_simulation.py            all protocols, experiments, figures, results.json
│   └── legacy/
│       └── gwg_simulation_v1.py     archived; kept so the audit stays reproducible
├── tests/
│   └── test_gwg.py                  25 protocol-correctness tests
├── scripts/
│   ├── verify_pipeline.sh           one-command end-to-end verification
│   ├── make_results_sections.py     results.json -> paper Sections V-VII
│   ├── build_paper.py               assembles paper/FULL_PAPER.md (+ .docx)
│   ├── audit_baseline_claims.py     evidence for the v1 defects
│   └── audit_ablation.py            evidence that the v1 comparison was confounded
├── data/
│   ├── raw/                         yellow_tripdata_*.parquet (gitignored)
│   └── processed/                   nyc_speeds.npy (gitignored)
├── results/
│   ├── results.json                 every number the paper cites — tracked
│   └── figures/                     fig1-fig10 (gitignored, regenerate anytime)
├── paper/
│   ├── adaptive_gwg_paper.md        hand-written sections (I-IV, VIII)
│   ├── RESULTS.md                   Sections V-VII — GENERATED, do not hand-edit
│   ├── NUMBERS.md                   claim -> evidence map — GENERATED
│   └── FULL_PAPER.md                the two spliced together — GENERATED
└── docs/
    ├── PDC_A2_GWG_FINAL_WithTOC.docx original Assignment 2 system-design report
    ├── project_explained.md
    └── EXPERIMENT_README.md
```

`data/` and `results/figures/` are gitignored because both regenerate in minutes
from the parquet source. `results/results.json` **is** tracked — it is the
evidence the paper's numbers are checked against.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install pandas pyarrow numpy matplotlib
```

## Running the pipeline

1. **Get real NYC TLC data.** Download one or more months from
   <https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page> into `data/raw/`,
   named `yellow_tripdata_YYYY-MM.parquet`. Every matching file is combined
   automatically; no code change is needed to add months.

2. **Extract speeds** — prints per-file counts and the distribution:
   ```bash
   python3 src/extract_speeds.py
   ```

3. **Run everything** — main comparison, churn sweep, mobility sweep, threshold
   sweep, refresh sweep, AV analysis, 9 figures, and `results/results.json`:
   ```bash
   python3 src/gwg_simulation.py
   ```

4. **Regenerate the paper's results sections** from that JSON, then assemble the
   full document:
   ```bash
   python3 scripts/make_results_sections.py
   python3 scripts/build_paper.py       # -> paper/FULL_PAPER.md (+ .docx via pandoc)
   ```

Steps 3–4 are the only way paper numbers should ever change. `paper/RESULTS.md`
and `paper/NUMBERS.md` are generated files — edit the generator, not the output.

## Before you push

```bash
bash scripts/verify_pipeline.sh
```

Checks raw data, extraction sanity, **the protocol test suite**, a clean
simulation run, every field the paper generator reads, all 9 figures, and that
the paper sections regenerate. Exits non-zero naming what failed.

Running the tests is the part that matters. This project has already shipped a
pipeline that ran cleanly end to end while computing the wrong quantity; a green
run is not evidence that the results mean anything.

```bash
python3 tests/test_gwg.py          # or: python3 -m pytest tests/ -q
```

## Pushing changes

```bash
git checkout -b short-description-of-your-change
# make changes
bash scripts/verify_pipeline.sh    # must pass
git add -A
git commit -m "what changed and why"
git push origin short-description-of-your-change
```

Then open a PR into `main`. The parquet files, `nyc_speeds.npy` and
`results/figures/` will not appear in `git status` — they are gitignored by design.

## Extending the evaluation

- **More months of data:** drop more parquet files into `data/raw/`, re-run
  steps 2–3. `nyc_speeds.npy` is stored as float32 to keep the combined file small
  (~11 MB per month).
- **Different densities:** the density regime is set by `N / GRID_SIZE²`, not by
  fleet size alone. To probe the regime boundary, vary `NODE_COUNTS` or
  `GRID_SIZE` in `src/gwg_simulation.py`.
- **A road-constrained mobility trace** would be the single most valuable
  improvement — see the limitations section of the paper.
