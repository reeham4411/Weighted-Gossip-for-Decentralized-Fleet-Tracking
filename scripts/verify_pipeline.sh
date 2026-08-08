#!/usr/bin/env bash
# End-to-end verification for the Adaptive-GWG pipeline.
# Run from the repo root:  bash scripts/verify_pipeline.sh
#
# Checks, in order:
#   1. raw parquet data is present
#   2. extract_speeds.py runs and produces a sane nyc_speeds.npy
#   3. the cached road network for the road-mobility robustness check is present
#   4. the protocol test suite passes            <- correctness, not just "it ran"
#   5. gwg_simulation.py runs and writes results/results.json
#   6. results.json contains every field the paper's generator reads
#   7. all figures are present and non-empty
#   8. the paper's results sections regenerate from results.json
#
# Exits non-zero listing every failure. Run before any push.

set -u
FAIL=0
PY=${PYTHON:-python3}

echo "== 1. Raw data =="
if ! ls data/raw/yellow_tripdata_*.parquet >/dev/null 2>&1; then
    echo "FAIL: no yellow_tripdata_*.parquet in data/raw/"
    echo "      download at least one month from the NYC TLC site and place it there"
    exit 1
fi
echo "OK: $(ls data/raw/yellow_tripdata_*.parquet | wc -l | tr -d ' ') parquet file(s)"

echo ""
echo "== 2. extract_speeds.py =="
rm -f data/processed/nyc_speeds.npy   # a stale file would mask a failed run
if ! $PY src/extract_speeds.py; then
    echo "FAIL: extract_speeds.py exited non-zero"
    exit 1
fi
$PY - <<'EOF' || FAIL=1
import numpy as np, sys
a = np.load("data/processed/nyc_speeds.npy")
ok = True
if len(a) < 1000:
    print(f"FAIL: only {len(a)} samples"); ok = False
if a.min() < 5 or a.max() > 70:
    print(f"FAIL: range [{a.min():.1f},{a.max():.1f}] outside the 5-70mph filter"); ok = False
if not (5 < a.mean() < 40):
    print(f"FAIL: mean {a.mean():.1f}mph implausible for NYC taxi data"); ok = False
if ok:
    print(f"OK: {len(a):,} samples, mean {a.mean():.2f}mph, sd {a.std():.2f}mph")
sys.exit(0 if ok else 1)
EOF

echo ""
echo "== 3. Road network cache =="
if [ ! -s data/processed/road_network.json ]; then
    echo "FAIL: data/processed/road_network.json missing"
    echo "      run 'python3 src/extract_roads.py' (needs network access, run once)"
    exit 1
fi
$PY - <<'EOF' || FAIL=1
import json, sys
d = json.load(open("data/processed/road_network.json"))
ok = True
if len(d.get("nodes", {})) < 10:
    print(f"FAIL: only {len(d.get('nodes', {}))} road nodes — implausible for a real block"); ok = False
if len(d.get("edges", [])) < 10:
    print(f"FAIL: only {len(d.get('edges', []))} road edges — implausible for a real block"); ok = False
if ok:
    print(f"OK: {len(d['nodes'])} nodes, {len(d['edges'])} edges")
sys.exit(0 if ok else 1)
EOF

echo ""
echo "== 4. Protocol correctness tests =="
# These are the point of the check. A pipeline that runs cleanly while computing
# the wrong thing is exactly the failure this repo already had once.
if $PY tests/test_gwg.py; then
    echo "OK: protocol properties hold"
else
    echo "FAIL: tests/test_gwg.py — do not push, and do not trust any figure produced"
    FAIL=1
fi

echo ""
echo "== 5. gwg_simulation.py (a few minutes) =="
rm -f results/figures/fig*.png results/results.json
if ! $PY src/gwg_simulation.py > /tmp/gwg_run.log 2>&1; then
    echo "FAIL: gwg_simulation.py exited non-zero — see /tmp/gwg_run.log"
    tail -30 /tmp/gwg_run.log
    exit 1
fi
echo "OK: simulation completed"

echo ""
echo "== 6. results.json completeness =="
$PY - <<'EOF' || FAIL=1
import json, sys
d = json.load(open("results/results.json"))
ok = True
for key in ("config", "main", "churn", "mobility", "road_mobility",
            "threshold_sensitivity", "refresh_sweep", "av_readiness"):
    if key not in d:
        print(f"FAIL: results.json missing top-level '{key}'"); ok = False
protos = ["uniform", "fixed_gwg", "fixed_confined", "adaptive_gwg"]
fields = ["macro_mape", "macro_mape_ci95", "micro_mape", "avg_hop_m",
          "bytes_per_node", "cross_region_exchange_pct", "n_converged",
          "control_messages", "macro_curve"]
for n, per in d.get("main", {}).items():
    for p in protos:
        if p not in per:
            print(f"FAIL: main.{n} missing protocol '{p}'"); ok = False; continue
        for f in fields:
            if f not in per[p]:
                print(f"FAIL: main.{n}.{p} missing '{f}'"); ok = False
for n, per in d.get("road_mobility", {}).items():
    for p in protos:
        if p not in per:
            print(f"FAIL: road_mobility.{n} missing protocol '{p}'"); ok = False; continue
        if "macro_mape" not in per[p]:
            print(f"FAIL: road_mobility.{n}.{p} missing 'macro_mape'"); ok = False
if ok:
    print(f"OK: results.json has all fields for {len(d['main'])} fleet sizes "
          f"x {len(protos)} protocols")
sys.exit(0 if ok else 1)
EOF

echo ""
echo "== 7. Figures =="
EXPECTED="fig1_convergence_curves.png fig2_final_mape.png fig3_attribution.png \
fig4_hop_distance.png fig5_communication_cost.png fig6_churn.png \
fig7_threshold_sensitivity.png fig8_av_readiness.png fig9_mobility.png \
fig10_restart_interval.png fig11_road_mobility.png"
MISSING=0
for f in $EXPECTED; do
    if [ ! -s "results/figures/$f" ]; then
        echo "FAIL: results/figures/$f missing or empty"
        MISSING=1; FAIL=1
    fi
done
[ "$MISSING" -eq 0 ] && echo "OK: all 11 figures present and non-empty"

echo ""
echo "== 8. Paper sections regenerate =="
if $PY scripts/make_results_sections.py >/dev/null; then
    if [ -s paper/RESULTS.md ] && [ -s paper/NUMBERS.md ]; then
        echo "OK: paper/RESULTS.md and paper/NUMBERS.md regenerated from results.json"
    else
        echo "FAIL: generator ran but produced empty output"; FAIL=1
    fi
    if $PY scripts/build_paper.py && [ -s paper/FULL_PAPER.md ]; then
        echo "OK: paper/FULL_PAPER.md assembled"
    else
        echo "FAIL: scripts/build_paper.py could not assemble the paper"; FAIL=1
    fi
else
    echo "FAIL: scripts/make_results_sections.py exited non-zero"; FAIL=1
fi

echo ""
if [ "$FAIL" -eq 0 ]; then
    echo "ALL CHECKS PASSED — pipeline is consistent end to end."
    exit 0
else
    echo "ONE OR MORE CHECKS FAILED — see above before pushing."
    exit 1
fi
