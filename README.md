# Geo-Weighted Gossip (GWG) for Decentralized Fleet Tracking

Parallel and Distributed Computing semester project — a leaderless gossip
protocol for fleets of vehicles to compute live, per-region average speed
without a central server, evaluated against real NYC TLC taxi trip data.

**Team:** Asma Imran (481920) · Fatima Ali (470708) · Adeena Reeham (480941)
School of Electrical Engineering and Computer Science, NUST

This repo contains three protocols compared head-to-head — Uniform Random
Gossip, Fixed Geo-Weighted Gossip, and our own contribution, Adaptive
Geo-Weighted Gossip (regions merge/split themselves based on vehicle
density) — plus the research paper draft built on top of the results.

## Key finding

Uniform Random Gossip and Fixed GWG don't just converge *slower* than
Adaptive GWG — on real, spatially-structured speed data they don't converge
to the right answer **at all**. Push-sum under uniform peer selection
provably converges to the network-wide global average, not the regional
one, so both baselines plateau at a permanent 18–35% MAPE no matter how
many rounds run. Adaptive GWG, by letting regions adapt to density, reaches
under 1% MAPE in a handful of rounds at larger fleet sizes. Full numbers
are in [`paper/PAPER_RESULTS_SECTIONS_DRAFT.md`](paper/PAPER_RESULTS_SECTIONS_DRAFT.md).

## Repo structure

```
.
├── README.md                  # you are here
├── .gitignore
├── src/
│   ├── extract_speeds.py      # NYC TLC parquet -> data/processed/nyc_speeds.npy
│   └── gwg_simulation.py      # runs all 3 protocols, produces results/figures/*
├── scripts/
│   └── verify_pipeline.sh     # one-command end-to-end smoke test
├── data/
│   ├── raw/                   # put downloaded yellow_tripdata_*.parquet files here (gitignored)
│   └── processed/             # nyc_speeds.npy lands here (gitignored, regenerate anytime)
├── results/
│   └── figures/                # fig1-fig8 .png output (gitignored, regenerate anytime)
├── docs/
│   ├── PDC_A2_GWG_FINAL_WithTOC.docx   # original Assignment 2 system-design report
│   ├── project_explained.md
│   └── EXPERIMENT_README.md            # detailed pipeline run/push guide (v2)
└── paper/
    └── PAPER_RESULTS_SECTIONS_DRAFT.md # IEEE paper Sections V-VII, drafted from real results
```

`data/` and `results/` are gitignored on purpose — both are fully
reproducible from the parquet source + scripts in a couple of minutes, and
keeping them out of git keeps the repo small regardless of how many months
of taxi data you add.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install pandas pyarrow numpy matplotlib --break-system-packages
```

## Running the pipeline

1. **Get real NYC TLC Yellow Taxi data.** Download one or more months from
   https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page and drop
   them into `data/raw/`, named like `yellow_tripdata_2026-01.parquet`.
   You can use as many months as you want — everything below auto-detects
   and combines all of them, no code changes needed.

2. **Extract speeds:**
   ```bash
   python3 src/extract_speeds.py
   ```
   Prints per-file and combined sample counts, the speed distribution, and
   the resulting file size. Output: `data/processed/nyc_speeds.npy`.

3. **Run the simulation:**
   ```bash
   python3 src/gwg_simulation.py
   ```
   Takes roughly 20–90 seconds depending on how much data you combined.
   Produces a terminal results table, C-6 novelty interpretation, Amdahl's/
   Gustafson's Law analysis, an AV real-time-readiness table, and 8 PNGs in
   `results/figures/`.

## Testing / verifying everything still behaves correctly

Before pushing any change to `src/extract_speeds.py` or
`src/gwg_simulation.py`, run the smoke test from the repo root:

```bash
bash scripts/verify_pipeline.sh
```

It re-runs both scripts and checks: raw data is present, the extracted
speed sample count and range are sane (5–70mph, plausible mean), the
simulation exits cleanly, all 8 figures are written and non-empty, and the
results table actually printed. It exits non-zero and prints exactly what
failed if anything's off — safe to run before every push.

## Extending to more months

Just add more `yellow_tripdata_*.parquet` files to `data/raw/` and re-run
steps 2–3 above. More months = a larger, more representative real-world
speed distribution, which strengthens the "real data" claim in the paper.
`nyc_speeds.npy` is saved as float32 to keep the combined file reasonably
small even across several months (~11MB per month of NYC yellow taxi data,
roughly — check the printed size after running `extract_speeds.py`).

## Pushing changes

```bash
git checkout -b <short-description-of-your-change>
# make your changes
bash scripts/verify_pipeline.sh   # must pass before you push
git add -A
git commit -m "clear description of what changed and why"
git push origin <branch-name>
```
Then open a PR into `main` on GitHub. `data/`, `results/figures/`, and the
raw parquet files won't show up in `git status` — that's expected, they're
gitignored.

## Paper draft

See `docs/PDC_A2_GWG_FINAL_WithTOC.docx` for the original Assignment 2
system-design report (protocol design, Amdahl/Gustafson analysis) and
`paper/PAPER_RESULTS_SECTIONS_DRAFT.md` for drafted IEEE paper text
(Sections V–VII) built directly from the real-data results above — pull
the numbers/prose from there into the actual paper draft as Section
III/IV get written up.