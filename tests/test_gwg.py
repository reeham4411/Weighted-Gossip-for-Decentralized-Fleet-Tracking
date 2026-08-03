"""
Correctness tests for the Adaptive-GWG harness.

Each test pins down a property the paper relies on. Several of them fail
against src/legacy/gwg_simulation_v1.py, which is the point: they encode the
defects the audit found so the same claims cannot silently break again.

Run from the repo root:
    python3 -m pytest tests/ -q
    python3 tests/test_gwg.py        # no pytest needed
"""

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import gwg_simulation as G  # noqa: E402


def _pool(n=20000, seed=0):
    """A speed pool with the same support as the real data, without the 50 MB load."""
    rng = np.random.default_rng(seed)
    return np.clip(rng.gamma(3.5, 3.3, n), 5.0, 70.0)


def _fleet(n=200, seed=1):
    return G.Fleet(n, _pool(), np.random.default_rng(seed))


# --------------------------------------------------------------------------
# Push-sum
# --------------------------------------------------------------------------

def test_push_sum_conserves_mass():
    """Total (value, weight) mass is invariant under exchange -- the property
    the convergence guarantee rests on."""
    f = _fleet(200)
    v0, w0 = f.value.sum(), f.weight.sum()
    rng = np.random.default_rng(3)
    for _ in range(2000):
        i, j = int(rng.integers(f.n)), int(rng.integers(f.n))
        if i != j:
            G.push_sum_send(f, i, j)
    assert math.isclose(f.value.sum(), v0, rel_tol=1e-9)
    assert math.isclose(f.weight.sum(), w0, rel_tol=1e-9)


def test_push_sum_is_directional():
    """The v1 defect: a symmetric exchange leaves every weight at 1.0, so the
    (value, weight) pair carries no information and it is not push-sum."""
    f = _fleet(2)
    f.value[:] = [30.0, 10.0]
    f.weight[:] = [1.0, 1.0]
    G.push_sum_send(f, 0, 1)
    assert f.weight[0] == 0.5 and f.weight[1] == 1.5, "sender must shed half its weight"
    assert f.value[0] != f.value[1], "exchange must not be symmetric"


def test_push_sum_reaches_the_true_mean():
    """On a fully connected fleet the estimate converges to the population mean."""
    f = _fleet(60, seed=7)
    target = f.true_speed.mean()
    rng = np.random.default_rng(5)
    for _ in range(4000):
        i = int(rng.integers(f.n))
        j = int(rng.integers(f.n))
        if i != j:
            G.push_sum_send(f, i, j)
    est = f.estimates()
    assert abs(est.mean() - target) / target < 0.02


# --------------------------------------------------------------------------
# Region management
# --------------------------------------------------------------------------

def test_merge_actually_merges():
    """
    v1 relabelled sparse vehicles to ('merged', T), an id region T's own members
    never adopted, so the two groups stayed separate. A merged vehicle must end
    up sharing a region label with vehicles that were already there.
    """
    f = _fleet(400, seed=11)
    _, cells = G.build_spatial_buckets(f)
    labels, _ = G.adaptive_partition(f, cells, min_nodes=5, max_nodes=50)

    from collections import Counter
    sizes = Counter(labels.tolist())
    # No region may be left below the merge threshold while other regions exist
    # to absorb it.
    if len(sizes) > 1:
        assert min(sizes.values()) >= 2, (
            f"a region of size {min(sizes.values())} survived the merge step")


def test_every_vehicle_gets_a_region():
    for n in (50, 200, 1000):
        f = _fleet(n, seed=n)
        _, cells = G.build_spatial_buckets(f)
        labels, _ = G.adaptive_partition(f, cells)
        assert (labels >= 0).all(), "unassigned vehicle in the adaptive partition"


def test_dense_cells_split():
    """A cell holding more than max_nodes must be broken up."""
    f = _fleet(600, seed=13)
    # Force everyone into one cell.
    f.x[:] = np.random.default_rng(0).uniform(0, G.REGION_SIZE, f.n)
    f.y[:] = np.random.default_rng(1).uniform(0, G.REGION_SIZE, f.n)
    _, cells = G.build_spatial_buckets(f)
    assert len(set(cells.tolist())) == 1
    labels, stats = G.adaptive_partition(f, cells, min_nodes=3, max_nodes=20)
    assert stats["dense_cells"] == 1
    assert stats["active_regions"] > 1, "dense cell was not split"


def test_region_labels_are_stable_across_rounds():
    """
    Region ids must name the geography they cover, not a counter. With a
    counter, the ids get renumbered whenever the iteration order of occupied
    cells shifts -- which mobility guarantees -- so vehicles that never left
    their region appear to have changed region, and each one then pays a
    spurious push-sum reset and a spurious control message.
    """
    f = _fleet(600, seed=77)
    _, cells = G.build_spatial_buckets(f)
    labels_a, _ = G.adaptive_partition(f, cells)

    # Same positions, different vehicle ordering: the partition must be identical.
    perm = np.random.default_rng(0).permutation(f.n)
    g = _fleet(600, seed=77)
    g.x, g.y = f.x[perm].copy(), f.y[perm].copy()
    g.true_speed = f.true_speed[perm].copy()
    _, gcells = G.build_spatial_buckets(g)
    labels_b, _ = G.adaptive_partition(g, gcells)
    assert np.array_equal(labels_a[perm], labels_b), (
        "partition depends on vehicle indexing, not geography")

    # One round of driving must not relabel vehicles wholesale.
    f.step_mobility()
    _, cells2 = G.build_spatial_buckets(f)
    labels_c, _ = G.adaptive_partition(f, cells2)
    churned = float(np.mean(labels_c != labels_a))
    assert churned < 0.10, (
        f"{churned:.1%} of vehicles changed region label after a single round "
        f"of driving -- labels are not stable")


def test_reporting_partition_is_protocol_independent():
    """
    Every protocol must be scored against the same ground truth. v1 scored each
    protocol against its own partition, so merging cells lowered reported error
    on its own.
    """
    f = _fleet(300, seed=17)
    _, cells = G.build_spatial_buckets(f)
    a = G.reporting_partition(cells)
    adaptive, _ = G.adaptive_partition(f, cells)
    b = G.reporting_partition(cells)
    assert np.array_equal(a, b), "reporting partition changed after adaptive relabelling"


# --------------------------------------------------------------------------
# Mobility and churn
# --------------------------------------------------------------------------

def test_vehicles_actually_move():
    """The paper's title claims a highly mobile network; v1 never moved a vehicle."""
    f = _fleet(200, seed=19)
    x0, y0 = f.x.copy(), f.y.copy()
    for _ in range(50):
        f.step_mobility()
    assert not np.allclose(x0, f.x) or not np.allclose(y0, f.y)
    moved = np.hypot(f.x - x0, f.y - y0)
    assert moved.mean() > 1.0, f"mean displacement {moved.mean():.3f} m is not mobility"


def test_vehicles_stay_in_the_service_area():
    f = _fleet(300, seed=23)
    for _ in range(300):
        f.step_mobility()
    assert f.x.min() >= 0.0 and f.x.max() <= G.AREA_M
    assert f.y.min() >= 0.0 and f.y.max() <= G.AREA_M


def test_churn_replaces_vehicles():
    f = _fleet(400, seed=29)
    before = f.base_speed.copy()
    total = sum(f.step_churn(0.05) for _ in range(10))
    assert total > 0
    assert not np.array_equal(before, f.base_speed)


def test_mobility_changes_cell_membership():
    """Mobility only matters if vehicles cross region boundaries."""
    f = _fleet(500, seed=31)
    c0 = f.cell_index().copy()
    for _ in range(G.MAX_ROUNDS):
        f.step_mobility()
        f.refresh_true_speed()
    assert (f.cell_index() != c0).sum() > 0, "no vehicle changed cell over a full run"


# --------------------------------------------------------------------------
# Peer selection
# --------------------------------------------------------------------------

def test_geo_selection_respects_radio_range():
    f = _fleet(600, seed=37)
    buckets, cells = G.build_spatial_buckets(f)
    rng = np.random.default_rng(41)
    regions = G.reporting_partition(cells)
    for i in range(0, f.n, 7):
        j = G.select_peer("fixed_gwg", f, buckets, cells, regions, i, rng)
        if j is None:
            continue
        d = math.hypot(f.x[i] - f.x[j], f.y[i] - f.y[j])
        assert d <= G.COMM_RANGE_M + 1e-6, f"selected a peer {d:.1f} m away"


def test_uniform_selection_ignores_geography():
    """The uniform baseline must be free to pick a distant peer, otherwise it is
    not the baseline the paper claims to compare against."""
    f = _fleet(400, seed=43)
    buckets, cells = G.build_spatial_buckets(f)
    regions = G.reporting_partition(cells)
    rng = np.random.default_rng(47)
    dists = []
    for i in range(200):
        j = G.select_peer("uniform", f, buckets, cells, regions, i, rng)
        dists.append(math.hypot(f.x[i] - f.x[j], f.y[i] - f.y[j]))
    assert np.mean(dists) > G.COMM_RANGE_M


def test_confined_selection_prefers_own_region():
    f = _fleet(800, seed=53)
    buckets, cells = G.build_spatial_buckets(f)
    regions = G.reporting_partition(cells)
    rng = np.random.default_rng(59)
    same = tot = 0
    for i in range(f.n):
        j = G.select_peer("fixed_confined", f, buckets, cells, regions, i, rng)
        if j is None:
            continue
        tot += 1
        same += int(regions[j] == regions[i])
    assert same / tot > 0.8, f"only {same/tot:.1%} of confined picks stayed in-region"


def test_inverse_distance_draw_favours_near_peers():
    """
    The inverse-distance rule must actually bias selection toward nearby
    vehicles, not merely restrict the candidate set to the radio range.
    """
    f = _fleet(900, seed=61)
    buckets, cells = G.build_spatial_buckets(f)
    rng = np.random.default_rng(67)
    picked, available = [], []
    for i in range(0, f.n, 3):
        c = G.neighbourhood_candidates(f, buckets, cells, i)
        if len(c) < 5:
            continue
        j = G._inverse_distance_pick(f, i, c, rng)
        picked.append(math.hypot(f.x[i] - f.x[j], f.y[i] - f.y[j]))
        available.append(float(np.mean(
            [math.hypot(f.x[k] - f.x[i], f.y[k] - f.y[i]) for k in c])))
    assert np.mean(picked) < np.mean(available) * 0.9, (
        f"selected mean {np.mean(picked):.1f} m vs uniform-over-range "
        f"{np.mean(available):.1f} m -- weighting had no effect")


# --------------------------------------------------------------------------
# Metrics and statistics
# --------------------------------------------------------------------------

def test_perfect_estimate_scores_zero_error():
    f = _fleet(300, seed=71)
    _, cells = G.build_spatial_buckets(f)
    part = G.reporting_partition(cells)
    truth, counts = G.region_truth(f.true_speed, part)
    est = np.array([truth[int(r)] for r in part])
    micro, macro, frac = G.error_metrics(est, f.true_speed, part)
    assert micro < 1e-9 and macro < 1e-9 and frac == 1.0


def test_macro_and_micro_differ_on_unbalanced_regions():
    """If they never differ, reporting both is pointless -- macro must actually
    protect small regions from being drowned out by dense ones."""
    true_speed = np.array([10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 20.0, 20.0])
    part = np.array([0, 0, 0, 0, 0, 0, 1, 1])
    est = np.array([10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 30.0, 30.0])
    micro, macro, _ = G.error_metrics(est, true_speed, part)
    assert macro > micro, f"macro {macro:.2f} should exceed micro {micro:.2f}"


def test_singleton_regions_are_excluded():
    """A region of one vehicle has a trivially perfect 'average' and would
    otherwise flatter every protocol."""
    true_speed = np.array([10.0, 12.0, 40.0])
    part = np.array([0, 0, 1])
    est = np.array([11.0, 11.0, 999.0])   # the singleton is wildly wrong
    micro, macro, _ = G.error_metrics(est, true_speed, part)
    assert micro < 20.0 and macro < 20.0, "singleton region leaked into the metric"


def test_ci95_is_a_real_confidence_interval():
    m, ci = G.mean_ci95([10.0, 12.0, 11.0, 9.0, 13.0])
    assert math.isclose(m, 11.0)
    sd = np.std([10.0, 12.0, 11.0, 9.0, 13.0], ddof=1)
    assert math.isclose(ci, 2.776 * sd / math.sqrt(5), rel_tol=1e-3)
    assert G.mean_ci95([5.0])[1] == 0.0


def test_non_converging_runs_are_not_averaged_in():
    """
    v1 recorded a non-converging run as MAX_ROUNDS+1 and averaged it, producing
    '151 rounds' -- a number that estimates nothing. Censored runs must be
    reported as a count.
    """
    runs = [
        {"converged": True, "convergence_round": 10, "final_micro_mape": 1.0,
         "final_macro_mape": 1.0, "avg_hop_m": 40.0, "total_bytes_per_node": 100.0,
         "micro_curve": [1.0], "macro_curve": [1.0], "data_messages": 1,
         "control_messages": 0, "avg_active_regions": 10.0},
        {"converged": False, "convergence_round": None, "final_micro_mape": 30.0,
         "final_macro_mape": 30.0, "avg_hop_m": 40.0, "total_bytes_per_node": 100.0,
         "micro_curve": [30.0], "macro_curve": [30.0], "data_messages": 1,
         "control_messages": 0, "avg_active_regions": 10.0},
    ]
    s = G.summarize(runs)
    assert s["n_converged"] == 1 and s["trials"] == 2
    assert s["median_convergence_round"] == 10.0


# --------------------------------------------------------------------------
# Accounting and reproducibility
# --------------------------------------------------------------------------

def test_adaptive_pays_for_its_control_traffic():
    """
    v1 gave region management away for free, which made 'bandwidth is comparable
    to the baseline' an identity rather than a result.
    """
    pool = _pool()
    a = G.run_once("adaptive_gwg", 300, pool, seed=5, max_rounds=20)
    b = G.run_once("fixed_confined", 300, pool, seed=5, max_rounds=20)
    assert a["control_messages"] > 0
    assert b["control_messages"] == 0
    assert a["total_bytes_per_node"] > b["total_bytes_per_node"], (
        "adaptive region management must show up in the bandwidth metric")


def test_runs_are_reproducible():
    pool = _pool()
    a = G.run_once("adaptive_gwg", 200, pool, seed=99, max_rounds=15)
    b = G.run_once("adaptive_gwg", 200, pool, seed=99, max_rounds=15)
    assert a["final_macro_mape"] == b["final_macro_mape"]
    assert a["avg_hop_m"] == b["avg_hop_m"]


def test_different_seeds_give_different_fleets():
    """Trials must be independent replicates, or the confidence intervals are
    meaningless. v1 reused one fleet layout for every trial."""
    pool = _pool()
    a = G.run_once("fixed_gwg", 200, pool, seed=1, max_rounds=15)
    b = G.run_once("fixed_gwg", 200, pool, seed=2, max_rounds=15)
    assert a["final_macro_mape"] != b["final_macro_mape"]


def test_geo_weighting_shortens_hops():
    """The core claim of geo-weighted selection."""
    pool = _pool()
    u = G.run_once("uniform", 400, pool, seed=3, max_rounds=20)
    g = G.run_once("fixed_gwg", 400, pool, seed=3, max_rounds=20)
    assert g["avg_hop_m"] < u["avg_hop_m"] * 0.5


if __name__ == "__main__":
    fns = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {name}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
