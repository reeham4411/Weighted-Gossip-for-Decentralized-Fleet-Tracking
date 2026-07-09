#!/usr/bin/env bash
# End-to-end smoke test for the GWG pipeline.
# Run from the repo root: bash scripts/verify_pipeline.sh
#
# Checks, in order:
#   1. data/raw/ has at least one parquet file
#   2. extract_speeds.py runs and produces a sane nyc_speeds.npy
#   3. gwg_simulation.py runs and produces all 8 figures
#   4. figures are non-empty files (not silently broken plots)
# Exits non-zero on the first failure, printing what went wrong.

set -u
FAIL=0

echo "== 1. Checking for raw data =="
if ! ls data/raw/yellow_tripdata_*.parquet >/dev/null 2>&1; then
    echo "FAIL: no yellow_tripdata_*.parquet files found in data/raw/"
    echo "      download at least one month from the TLC site and place it there"
    exit 1
fi
echo "OK: found $(ls data/raw/yellow_tripdata_*.parquet | wc -l | tr -d ' ') parquet file(s)"

echo ""
echo "== 2. Running extract_speeds.py =="
rm -f data/processed/nyc_speeds.npy   # avoid a stale file masking a failed run
python3 src/extract_speeds.py
EXTRACT_STATUS=$?
if [ $EXTRACT_STATUS -ne 0 ]; then
    echo "FAIL: extract_speeds.py exited with status $EXTRACT_STATUS"
    exit 1
fi
if [ ! -f data/processed/nyc_speeds.npy ]; then
    echo "FAIL: data/processed/nyc_speeds.npy was not created"
    exit 1
fi
python3 - <<'EOF'
import numpy as np, sys
arr = np.load("data/processed/nyc_speeds.npy")
ok = True
if len(arr) < 1000:
    print(f"FAIL: only {len(arr)} samples — expected a lot more"); ok = False
if arr.min() < 5 or arr.max() > 70:
    print(f"FAIL: speed range [{arr.min():.1f}, {arr.max():.1f}] outside expected 5-70mph filter"); ok = False
if not (5 < arr.mean() < 40):
    print(f"FAIL: mean speed {arr.mean():.1f}mph looks implausible for NYC taxi data"); ok = False
if ok:
    print(f"OK: {len(arr)} samples, mean {arr.mean():.1f}mph, std {arr.std():.1f}mph — looks sane")
sys.exit(0 if ok else 1)
EOF
if [ $? -ne 0 ]; then FAIL=1; fi

echo ""
echo "== 3. Running gwg_simulation.py (takes ~20-60s depending on data size) =="
rm -f results/figures/fig*.png   # avoid stale figures masking a failed run
python3 src/gwg_simulation.py > /tmp/gwg_run.log 2>&1
if [ $? -ne 0 ]; then
    echo "FAIL: gwg_simulation.py exited with an error — see /tmp/gwg_run.log"
    tail -30 /tmp/gwg_run.log
    exit 1
fi
echo "OK: simulation completed without errors"

echo ""
echo "== 4. Checking output figures =="
EXPECTED_FIGS="fig1_convergence_curves.png fig2_convergence_rounds.png fig3_hop_distance.png fig4_bandwidth.png fig5_message_complexity.png fig6_c6_per_region_mape.png fig7_c6_adaptive_overhead.png fig8_av_real_time_readiness.png"
for f in $EXPECTED_FIGS; do
    path="results/figures/$f"
    if [ ! -s "$path" ]; then
        echo "FAIL: $path missing or empty"
        FAIL=1
    fi
done
if [ "$FAIL" -eq 0 ]; then
    echo "OK: all 8 figures present and non-empty"
fi

echo ""
echo "== 5. Sanity-checking the printed results table =="
if grep -q "Adaptive GWG" /tmp/gwg_run.log && grep -q "RESULTS SUMMARY" /tmp/gwg_run.log; then
    echo "OK: results summary table printed"
else
    echo "FAIL: results summary table not found in output"
    FAIL=1
fi

echo ""
if [ "$FAIL" -eq 0 ]; then
    echo "✅ ALL CHECKS PASSED — pipeline behaves as expected end-to-end."
    exit 0
else
    echo "❌ ONE OR MORE CHECKS FAILED — see messages above before pushing."
    exit 1
fi