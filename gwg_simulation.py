"""
Geo-Weighted Gossip (GWG) vs Uniform Random Gossip +Adaptive GWG
Parallel and Distributed Computing - Assignment 2 / Assignment 3Extension
Team: Fatima Ali (470708), Asma Imran (481920), Adeena Reeham (480941)

 simulation features:
  1. Uniform Random Gossip baseline
  2. Fixed Geo-Weighted Gossip
  3. Push-sum exchange
  4. MAPE, convergence, bandwidth, hop distance, message complexity
  5. Amdahl and Gustafson analysis
  6. Figures 1–5 

CREATE LEVEL ADDITION:
  7. Adaptive Geo-Weighted Gossip
  8. Adaptive region assignment: sparse regions merge, dense regions split
  9. Per-region MAPE metric
 10.trade-off/overhead graph
 11. Progress printing so N=1000 does not look frozen

WHY THIS VERSION IS FASTER:
  - Uniform peer candidates are precomputed once instead of rebuilding a list every gossip call.
  - Neighbor caches are built once per trial.
  - Adaptive region refresh does not rebuild distance caches unnecessarily.
  - Default settings are lighter but still valid fordemonstration.

HOW TO RUN:
    pip install matplotlib numpy
    python gwg_simulation.py

OUTPUT FILES:
    fig1_convergence_curves.png
    fig2_convergence_rounds.png
    fig3_hop_distance.png
    fig4_bandwidth.png
    fig5_message_complexity.png
    fig6_c6_per_region_mape.png
    fig7_c6_adaptive_overhead.png
"""

import random
import math
import time
import os
from collections import defaultdict

import numpy as np

MATPLOTLIB_IMPORT_ERROR = None
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception as exc:
    matplotlib = None
    plt = None
    MATPLOTLIB_IMPORT_ERROR = exc



# CONFIGURATION

RANDOM_SEED           = 42
GRID_SIZE             = 10
REGION_SIZE           = 100.0

# For full original-style run, set MAX_ROUNDS=100 and TRIALS=5.
# For fasterdemonstration including N=1000, these defaults are practical.
MAX_ROUNDS            = 50
TRIALS                = 3
NODE_COUNTS           = [100, 500, 1000]

CONVERGENCE_THRESHOLD = 0.05
CONVERGENCE_PCT       = 0.90
MSG_SIZE_BYTES        = 42
NEIGHBOR_CACHE_K      = 30
OUT_DIR               = "."

#adaptive-zone settings
ADAPTIVE_MIN_REGION_NODES = 3
ADAPTIVE_MAX_REGION_NODES = 20
ADAPTIVE_REFRESH_ROUNDS   = 10

random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)
NYC_SPEEDS = np.load("nyc_speeds.npy")


# NODE CLASS

class Vehicle:
    def __init__(self, node_id, x, y, true_speed):
        self.node_id = node_id
        self.x = x
        self.y = y

        self.fixed_region_id = (int(x // REGION_SIZE), int(y // REGION_SIZE))
        self.region_id = self.fixed_region_id

        self.initial_speed = true_speed
        self.true_speed = true_speed

        self.value = true_speed
        self.weight = 1.0
        self.estimate = true_speed

        self.messages_sent = 0
        self.bytes_sent = 0

        self.neighbor_cache = []
        self.all_peer_cache = []

    def reset(self):
        self.value = self.true_speed
        self.weight = 1.0
        self.estimate = self.true_speed
        self.messages_sent = 0
        self.bytes_sent = 0

    def reset_region_to_fixed(self):
        self.region_id = self.fixed_region_id

    def distance_to(self, other):
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)



# CREATE FLEET

def create_fleet(n_nodes):
    total_area = GRID_SIZE * REGION_SIZE
    nodes = []

    for i in range(n_nodes):
        x = random.uniform(0, total_area)
        y = random.uniform(0, total_area)

        rx = int(x // REGION_SIZE)
        ry = int(y // REGION_SIZE)

        center_distance = math.sqrt((rx - GRID_SIZE / 2) ** 2 + (ry - GRID_SIZE / 2) ** 2)
        speed = float(random.choice(NYC_SPEEDS))

        nodes.append(Vehicle(i, x, y, speed))

    return nodes



# CACHE BUILDING

def build_peer_caches(nodes, k=NEIGHBOR_CACHE_K):
    """
    Builds both:
      - all_peer_cache: used by Uniform Random Gossip
      - neighbor_cache: used by Fixed GWG and Adaptive GWG

    This avoids rebuilding peer lists inside every gossip exchange.
    """
    for node in nodes:
        others = [other for other in nodes if other.node_id != node.node_id]
        others.sort(key=lambda other: node.distance_to(other))

        node.all_peer_cache = others
        node.neighbor_cache = others[:k]



#ADAPTIVE REGION ASSIGNMENT

def assign_fixed_regions(nodes):
    for node in nodes:
        node.region_id = node.fixed_region_id


def region_center(region_id):
    rx, ry = region_id
    return ((rx + 0.5) * REGION_SIZE, (ry + 0.5) * REGION_SIZE)


def nearest_non_sparse_region(sparse_region, dense_or_normal_regions):
    if not dense_or_normal_regions:
        return sparse_region

    sx, sy = region_center(sparse_region)

    def dist_to_region(region_id):
        cx, cy = region_center(region_id)
        return math.sqrt((sx - cx) ** 2 + (sy - cy) ** 2)

    return min(dense_or_normal_regions, key=dist_to_region)


def adaptive_region_assignment(
    nodes,
    min_region_nodes=ADAPTIVE_MIN_REGION_NODES,
    max_region_nodes=ADAPTIVE_MAX_REGION_NODES,
):
    """
   Create Level improvement.

    Fixed GWG uses a fixed 10x10 grid.
    Adaptive GWG changes the logical aggregation regions:

      Sparse fixed region: count < min_region_nodes
          → merge with nearest non-sparse region

      Dense fixed region: count > max_region_nodes
          → split into 4 subregions

      Normal fixed region:
          → keep unchanged

    This is a system-level improvement because the aggregation structure
    adapts to vehicle density instead of assuming every zone should be equal.
    """
    fixed_groups = defaultdict(list)

    for node in nodes:
        node.reset_region_to_fixed()
        fixed_groups[node.fixed_region_id].append(node)

    sparse_regions = {
        region_id for region_id, group in fixed_groups.items()
        if len(group) < min_region_nodes
    }

    dense_regions = {
        region_id for region_id, group in fixed_groups.items()
        if len(group) > max_region_nodes
    }

    normal_regions = set(fixed_groups.keys()) - sparse_regions - dense_regions
    merge_targets = list(normal_regions | dense_regions)

    changed_nodes = 0

    for fixed_region_id, group in fixed_groups.items():
        count = len(group)

        if count < min_region_nodes:
            target = nearest_non_sparse_region(fixed_region_id, merge_targets)
            new_region_id = ("merged", target)

            for node in group:
                if node.region_id != new_region_id:
                    changed_nodes += 1
                node.region_id = new_region_id

        elif count > max_region_nodes:
            rx, ry = fixed_region_id
            x_mid = (rx + 0.5) * REGION_SIZE
            y_mid = (ry + 0.5) * REGION_SIZE

            for node in group:
                sx = 0 if node.x < x_mid else 1
                sy = 0 if node.y < y_mid else 1
                new_region_id = ("split", fixed_region_id, sx, sy)

                if node.region_id != new_region_id:
                    changed_nodes += 1
                node.region_id = new_region_id

        else:
            for node in group:
                node.region_id = fixed_region_id

    active_regions = len(set(node.region_id for node in nodes))

    return {
        "sparse_regions": len(sparse_regions),
        "dense_regions": len(dense_regions),
        "active_regions": active_regions,
        "changed_nodes": changed_nodes,
        "changed_node_pct": (changed_nodes / len(nodes)) * 100 if nodes else 0.0,
    }



# TRUE AVERAGES AND ERROR METRICS

def compute_true_regional_avg(nodes):
    totals = {}
    counts = {}

    for node in nodes:
        totals[node.region_id] = totals.get(node.region_id, 0.0) + node.true_speed
        counts[node.region_id] = counts.get(node.region_id, 0) + 1

    true_avgs = {
        region_id: totals[region_id] / counts[region_id]
        for region_id in totals
    }

    return true_avgs, counts


def compute_mape(nodes, true_avgs, region_counts):
    errors = []

    for node in nodes:
        if region_counts.get(node.region_id, 1) < 2:
            continue

        true_value = true_avgs.get(node.region_id, node.true_speed)

        if true_value > 0:
            errors.append(abs(node.estimate - true_value) / true_value * 100)

    return float(np.mean(errors)) if errors else 0.0


def compute_per_region_mape(nodes, true_avgs, region_counts):
    """
   metric.

    Instead of allowing dense regions to dominate the average, this calculates
    error per region first and then averages the regional errors.
    """
    region_errors = defaultdict(list)

    for node in nodes:
        if region_counts.get(node.region_id, 1) < 2:
            continue

        true_value = true_avgs.get(node.region_id, node.true_speed)

        if true_value > 0:
            error = abs(node.estimate - true_value) / true_value * 100
            region_errors[node.region_id].append(error)

    per_region_values = [
        float(np.mean(errors))
        for errors in region_errors.values()
        if errors
    ]

    return float(np.mean(per_region_values)) if per_region_values else 0.0


def check_convergence(nodes, true_avgs, region_counts):
    eligible = [
        node for node in nodes
        if region_counts.get(node.region_id, 1) >= 2
    ]

    if not eligible:
        return 1.0

    converged = 0

    for node in eligible:
        true_value = true_avgs.get(node.region_id, node.true_speed)

        if true_value > 0:
            error = abs(node.estimate - true_value) / true_value
            if error <= CONVERGENCE_THRESHOLD:
                converged += 1

    return converged / len(eligible)



# PUSH-SUM EXCHANGE

def push_sum_exchange(sender, receiver):
    sender_half_value = sender.value / 2
    sender_half_weight = sender.weight / 2

    receiver_half_value = receiver.value / 2
    receiver_half_weight = receiver.weight / 2

    sender.value = sender_half_value + receiver_half_value
    sender.weight = sender_half_weight + receiver_half_weight

    receiver.value = receiver_half_value + sender_half_value
    receiver.weight = receiver_half_weight + sender_half_weight

    sender.estimate = sender.value / sender.weight
    receiver.estimate = receiver.value / receiver.weight

    sender.messages_sent += 1
    sender.bytes_sent += MSG_SIZE_BYTES

    return sender.distance_to(receiver)



# PEER SELECTION

def select_peer_uniform(node, nodes):
    """
    Previous baseline, optimized:
    uniform random selection from all other nodes.
    """
    return random.choice(node.all_peer_cache)


def weighted_choice_by_inverse_distance(node, candidates):
    epsilon = 1.0

    weights = [
        1.0 / max(node.distance_to(other), epsilon)
        for other in candidates
    ]

    total = sum(weights)

    if total <= 0:
        return random.choice(candidates)

    r = random.random()
    cumulative = 0.0

    for other, weight in zip(candidates, weights):
        cumulative += weight / total
        if r <= cumulative:
            return other

    return candidates[-1]


def select_peer_geo_weighted(node, nodes):
    candidates = node.neighbor_cache if node.neighbor_cache else node.all_peer_cache
    return weighted_choice_by_inverse_distance(node, candidates)


def select_peer_adaptive_geo_weighted(node, nodes):
    """
    Adaptive GWG:
      1. Prefer peers in the same adaptive region.
      2. If there are not enough same-region peers, use nearest-neighbor cache.
      3. Select using inverse-distance weighting.
    """
    same_region_candidates = [
        other for other in node.neighbor_cache
        if other.region_id == node.region_id
    ]

    if len(same_region_candidates) >= 2:
        candidates = same_region_candidates
    else:
        candidates = node.neighbor_cache if node.neighbor_cache else node.all_peer_cache

    return weighted_choice_by_inverse_distance(node, candidates)



# RUN ONE EXPERIMENT

def run_experiment(nodes, select_peer_fn, max_rounds=MAX_ROUNDS, adaptive=False):
    if adaptive:
        overhead_initial = adaptive_region_assignment(nodes)
    else:
        assign_fixed_regions(nodes)
        overhead_initial = {
            "sparse_regions": 0,
            "dense_regions": 0,
            "active_regions": len(set(node.region_id for node in nodes)),
            "changed_nodes": 0,
            "changed_node_pct": 0.0,
        }

    true_avgs, region_counts = compute_true_regional_avg(nodes)

    for node in nodes:
        node.reset()

    convergence_round = None
    total_hop_distance = 0.0
    total_exchanges = 0

    global_error_per_round = []
    per_region_error_per_round = []

    overhead_records = [overhead_initial]

    for round_no in range(1, max_rounds + 1):
        if adaptive and round_no > 1 and round_no % ADAPTIVE_REFRESH_ROUNDS == 0:
            overhead_records.append(adaptive_region_assignment(nodes))
            true_avgs, region_counts = compute_true_regional_avg(nodes)

        for node in nodes:
            peer = select_peer_fn(node, nodes)
            hop = push_sum_exchange(node, peer)

            total_hop_distance += hop
            total_exchanges += 1

        global_mape = compute_mape(nodes, true_avgs, region_counts)
        per_region_mape = compute_per_region_mape(nodes, true_avgs, region_counts)

        global_error_per_round.append(global_mape)
        per_region_error_per_round.append(per_region_mape)

        if convergence_round is None:
            fraction_converged = check_convergence(nodes, true_avgs, region_counts)

            if fraction_converged >= CONVERGENCE_PCT:
                convergence_round = round_no

    converged = convergence_round is not None
    conv_round_out = convergence_round if converged else max_rounds + 1

    total_messages = total_exchanges
    avg_bandwidth = sum(node.bytes_sent for node in nodes) / len(nodes)
    avg_hop = total_hop_distance / total_exchanges if total_exchanges else 0.0

    overhead_summary = {
        "avg_sparse_regions": float(np.mean([o["sparse_regions"] for o in overhead_records])),
        "avg_dense_regions": float(np.mean([o["dense_regions"] for o in overhead_records])),
        "avg_active_regions": float(np.mean([o["active_regions"] for o in overhead_records])),
        "avg_changed_node_pct": float(np.mean([o["changed_node_pct"] for o in overhead_records])),
    }

    return (
        conv_round_out,
        total_messages,
        avg_bandwidth,
        avg_hop,
        global_error_per_round,
        converged,
        per_region_error_per_round,
        overhead_summary,
    )



# FULL EXPERIMENT SUITE

def run_all_experiments():
    results = {}

    print("=" * 86, flush=True)
    print("GWG Simulation — Uniform vs Fixed GWG vs Adaptive GWG (C-6 CREATE LEVEL)", flush=True)
    print("=" * 86, flush=True)
    print(f"Settings: MAX_ROUNDS={MAX_ROUNDS}, TRIALS={TRIALS}, NODE_COUNTS={NODE_COUNTS}", flush=True)

    for N in NODE_COUNTS:
        print(f"\n>>> N = {N} nodes  ({TRIALS} trials each protocol)", flush=True)

        nodes = create_fleet(N)
        build_peer_caches(nodes)

        original_speeds = [node.true_speed for node in nodes]

        trial_data = {
            "uniform":      {"cr": [], "ms": [], "bw": [], "hp": [], "ec": None, "pr": None, "oh": []},
            "geo_weighted": {"cr": [], "ms": [], "bw": [], "hp": [], "ec": None, "pr": None, "oh": []},
            "adaptive_gwg": {"cr": [], "ms": [], "bw": [], "hp": [], "ec": None, "pr": None, "oh": []},
        }

        protocol_runs = [
            ("uniform", "Uniform", select_peer_uniform, False),
            ("geo_weighted", "Fixed GWG", select_peer_geo_weighted, False),
            ("adaptive_gwg", "Adaptive GWG", select_peer_adaptive_geo_weighted, True),
        ]

        for trial in range(TRIALS):
            print(f"    Trial {trial + 1}/{TRIALS} for N={N}", flush=True)

            for node, speed in zip(nodes, original_speeds):
                node.true_speed = max(5, speed + random.gauss(0, 2))
                node.initial_speed = node.true_speed

            for key, label, selector, adaptive in protocol_runs:
                print(f"      Running {label}...", flush=True)

                r, m, b, h, ec, _converged, pr, oh = run_experiment(
                    nodes,
                    selector,
                    adaptive=adaptive,
                )

                trial_data[key]["cr"].append(r)
                trial_data[key]["ms"].append(m)
                trial_data[key]["bw"].append(b)
                trial_data[key]["hp"].append(h)
                trial_data[key]["oh"].append(oh)

                if trial_data[key]["ec"] is None:
                    trial_data[key]["ec"] = ec
                else:
                    trial_data[key]["ec"] = [
                        old + new for old, new in zip(trial_data[key]["ec"], ec)
                    ]

                if trial_data[key]["pr"] is None:
                    trial_data[key]["pr"] = pr
                else:
                    trial_data[key]["pr"] = [
                        old + new for old, new in zip(trial_data[key]["pr"], pr)
                    ]

        results[N] = {}

        for key, data in trial_data.items():
            overhead_list = data["oh"]

            results[N][key] = {
                "conv_round": float(np.mean(data["cr"])),
                "conv_std": float(np.std(data["cr"])),
                "total_msgs": float(np.mean(data["ms"])),
                "avg_bw_bytes": float(np.mean(data["bw"])),
                "avg_hop_m": float(np.mean(data["hp"])),
                "err_curve": [value / TRIALS for value in data["ec"]],
                "per_region_err_curve": [value / TRIALS for value in data["pr"]],
                "final_mape": (data["ec"][-1] / TRIALS) if data["ec"] else 0.0,
                "final_per_region_mape": (data["pr"][-1] / TRIALS) if data["pr"] else 0.0,
                "overhead": {
                    "avg_sparse_regions": float(np.mean([o["avg_sparse_regions"] for o in overhead_list])),
                    "avg_dense_regions": float(np.mean([o["avg_dense_regions"] for o in overhead_list])),
                    "avg_active_regions": float(np.mean([o["avg_active_regions"] for o in overhead_list])),
                    "avg_changed_node_pct": float(np.mean([o["avg_changed_node_pct"] for o in overhead_list])),
                },
            }

        u = results[N]["uniform"]
        g = results[N]["geo_weighted"]
        a = results[N]["adaptive_gwg"]

        print(
            f"  Uniform      conv={u['conv_round']:.1f}±{u['conv_std']:.1f}  "
            f"msgs={u['total_msgs']:.0f}  bw={u['avg_bw_bytes']/1024:.2f}KB  "
            f"hop={u['avg_hop_m']:.1f}m  regionMAPE={u['final_per_region_mape']:.2f}%",
            flush=True,
        )

        print(
            f"  Fixed GWG    conv={g['conv_round']:.1f}±{g['conv_std']:.1f}  "
            f"msgs={g['total_msgs']:.0f}  bw={g['avg_bw_bytes']/1024:.2f}KB  "
            f"hop={g['avg_hop_m']:.1f}m  regionMAPE={g['final_per_region_mape']:.2f}%",
            flush=True,
        )

        print(
            f"  Adaptive GWG conv={a['conv_round']:.1f}±{a['conv_std']:.1f}  "
            f"msgs={a['total_msgs']:.0f}  bw={a['avg_bw_bytes']/1024:.2f}KB  "
            f"hop={a['avg_hop_m']:.1f}m  regionMAPE={a['final_per_region_mape']:.2f}%",
            flush=True,
        )

        hop_gain = (
            (g["avg_hop_m"] - a["avg_hop_m"]) / g["avg_hop_m"] * 100
            if g["avg_hop_m"] else 0.0
        )

        prmape_gain = (
            (g["final_per_region_mape"] - a["final_per_region_mape"])
            / g["final_per_region_mape"] * 100
            if g["final_per_region_mape"] else 0.0
        )

        print(
            f" vs Fixed GWG: hop {hop_gain:+.1f}%  "
            f"per-region MAPE {prmape_gain:+.1f}%  "
            f"active regions={a['overhead']['avg_active_regions']:.1f}  "
            f"changed nodes={a['overhead']['avg_changed_node_pct']:.1f}%",
            flush=True,
        )

    return results



# AMDAHL / GUSTAFSON

def print_amdahl_analysis():
    print("\nAMDAHL'S LAW  (f = serial fraction = 0.05)")
    f = 0.05

    for p in [1, 2, 4, 8, 16, 32, 64]:
        speedup = 1 / (f + (1 - f) / p)
        print(f"  p={p:>3}  speedup={speedup:.2f}x  efficiency={speedup / p * 100:.1f}%")

    print("\nGUSTAFSON'S LAW  (scaled speedup = p - f*(p-1))")

    for p in [1, 2, 4, 8, 16, 32]:
        scaled_speedup = p - f * (p - 1)
        print(f"  p={p:>3}  scaled speedup={scaled_speedup:.2f}x")



# SUMMARY TABLES

def print_summary_table(results):
    print("\n" + "=" * 115)
    print("RESULTS SUMMARY")
    print("=" * 115)
    print(
        f"{'N':>6} | {'Protocol':>13} | {'Conv.Rnd':>9} | {'Msgs':>8} | "
        f"{'BW(KB)':>7} | {'Hop(m)':>8} | {'Global MAPE':>11} | {'Region MAPE':>11}"
    )
    print("-" * 115)

    labels = [
        ("uniform", "Uniform"),
        ("geo_weighted", "Fixed GWG"),
        ("adaptive_gwg", "Adaptive GWG"),
    ]

    for N in NODE_COUNTS:
        for key, label in labels:
            data = results[N][key]
            print(
                f"{N:>6} | {label:>13} | {data['conv_round']:>9.1f} | "
                f"{data['total_msgs']:>8.0f} | {data['avg_bw_bytes']/1024:>7.2f} | "
                f"{data['avg_hop_m']:>8.1f} | {data['final_mape']:>10.2f}% | "
                f"{data['final_per_region_mape']:>10.2f}%"
            )

        fixed = results[N]["geo_weighted"]
        adaptive = results[N]["adaptive_gwg"]

        hop_gain = (
            (fixed["avg_hop_m"] - adaptive["avg_hop_m"])
            / fixed["avg_hop_m"] * 100
            if fixed["avg_hop_m"] else 0.0
        )

        prmape_gain = (
            (fixed["final_per_region_mape"] - adaptive["final_per_region_mape"])
            / fixed["final_per_region_mape"] * 100
            if fixed["final_per_region_mape"] else 0.0
        )

        print(
            f"{'':>6}  Adaptive vs Fixed GWG: "
            f"hop {hop_gain:+.1f}% | per-region MAPE {prmape_gain:+.1f}% | "
            f"active regions {adaptive['overhead']['avg_active_regions']:.1f} | "
            f"changed nodes {adaptive['overhead']['avg_changed_node_pct']:.1f}%"
        )
        print("-" * 115)


def print_c6_interpretation():
    print("\n" + "=" * 90)
    print("C-6 CREATE LEVEL INTERPRETATION")
    print("=" * 90)

    print(
        "Novel improvement: Adaptive Geo-Weighted Gossip dynamically changes the logical\n"
        "aggregation regions based on vehicle density. Dense regions are split, sparse\n"
        "regions are merged, and normal regions remain unchanged.\n"
    )

    print(
        "Baseline comparison: Adaptive-GWG is compared against Fixed GWG and Uniform\n"
        "Random Gossip using the same seed, fleet sizes, message size, max rounds,\n"
        "and neighbor-cache settings.\n"
    )

    print(
        "Measurable improvement: Use Region MAPE and Hop Distance as the main C-6\n"
        "metrics. Bandwidth and message count should remain unchanged, showing that\n"
        "the improvement comes from smarter system organization rather than sending\n"
        "extra messages.\n"
    )

    print(
        "Trade-off: Adaptive-GWG adds region-management computation and may change\n"
        "node region labels. This overhead is shown by active_regions and changed_nodes.\n"
    )



# PLOTS

def plot_results(results, out_dir=OUT_DIR):
    if plt is None:
        print("\nPlot generation skipped because matplotlib is unavailable.")
        print(f"Reason: {MATPLOTLIB_IMPORT_ERROR}")
        return []

    os.makedirs(out_dir, exist_ok=True)

    rounds = list(range(1, MAX_ROUNDS + 1))
    x = np.arange(len(NODE_COUNTS))
    w = 0.25

    red = "#E74C3C"
    green = "#2ECC71"
    blue = "#3498DB"

    # Fig 1: Global MAPE convergence curves
    fig, axes = plt.subplots(1, len(NODE_COUNTS), figsize=(5.5 * len(NODE_COUNTS), 4))

    if len(NODE_COUNTS) == 1:
        axes = [axes]

    fig.suptitle("Global MAPE Convergence over Gossip Rounds", fontsize=13, fontweight="bold")

    for ax, N in zip(axes, NODE_COUNTS):
        ax.plot(rounds, results[N]["uniform"]["err_curve"], color=red, lw=2, label="Uniform")
        ax.plot(rounds, results[N]["geo_weighted"]["err_curve"], color=green, lw=2, label="Fixed GWG")
        ax.plot(rounds, results[N]["adaptive_gwg"]["err_curve"], color=blue, lw=2, label="Adaptive GWG")
        ax.axhline(5, color="gray", ls="--", alpha=0.7, label="5% threshold")
        ax.set_title(f"N={N}")
        ax.set_xlabel("Round")
        ax.set_ylabel("Global MAPE (%)")
        ax.legend(fontsize=8)
        ax.set_ylim(0, 50)
        ax.grid(alpha=0.3)

    plt.tight_layout()
    p1 = os.path.join(out_dir, "fig1_convergence_curves.png")
    plt.savefig(p1, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"Saved {p1}")

    # Fig 2: Convergence rounds
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x - w, [results[N]["uniform"]["conv_round"] for N in NODE_COUNTS], w, color=red, label="Uniform")
    ax.bar(x, [results[N]["geo_weighted"]["conv_round"] for N in NODE_COUNTS], w, color=green, label="Fixed GWG")
    ax.bar(x + w, [results[N]["adaptive_gwg"]["conv_round"] for N in NODE_COUNTS], w, color=blue, label="Adaptive GWG")
    ax.set_xticks(x)
    ax.set_xticklabels([str(N) for N in NODE_COUNTS])
    ax.set_xlabel("Fleet Size (N)")
    ax.set_ylabel("Rounds to 90% Convergence")
    ax.set_title("Convergence Speed vs Fleet Size", fontweight="bold")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    p2 = os.path.join(out_dir, "fig2_convergence_rounds.png")
    plt.savefig(p2, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"Saved {p2}")

    # Fig 3: Hop distance
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x - w, [results[N]["uniform"]["avg_hop_m"] for N in NODE_COUNTS], w, color=red, label="Uniform")
    ax.bar(x, [results[N]["geo_weighted"]["avg_hop_m"] for N in NODE_COUNTS], w, color=green, label="Fixed GWG")
    ax.bar(x + w, [results[N]["adaptive_gwg"]["avg_hop_m"] for N in NODE_COUNTS], w, color=blue, label="Adaptive GWG")
    ax.set_xticks(x)
    ax.set_xticklabels([str(N) for N in NODE_COUNTS])
    ax.set_xlabel("Fleet Size (N)")
    ax.set_ylabel("Avg Hop Distance (m)")
    ax.set_title("Average Geographic Hop Distance per Message", fontweight="bold")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    p3 = os.path.join(out_dir, "fig3_hop_distance.png")
    plt.savefig(p3, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"Saved {p3}")

    # Fig 4: Bandwidth
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x - w, [results[N]["uniform"]["avg_bw_bytes"] / 1024 for N in NODE_COUNTS], w, color=red, label="Uniform")
    ax.bar(x, [results[N]["geo_weighted"]["avg_bw_bytes"] / 1024 for N in NODE_COUNTS], w, color=green, label="Fixed GWG")
    ax.bar(x + w, [results[N]["adaptive_gwg"]["avg_bw_bytes"] / 1024 for N in NODE_COUNTS], w, color=blue, label="Adaptive GWG")
    ax.set_xticks(x)
    ax.set_xticklabels([str(N) for N in NODE_COUNTS])
    ax.set_xlabel("Fleet Size (N)")
    ax.set_ylabel("Avg Bandwidth per Node (KB)")
    ax.set_title("Per-Node Bandwidth Usage", fontweight="bold")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    p4 = os.path.join(out_dir, "fig4_bandwidth.png")
    plt.savefig(p4, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"Saved {p4}")

    # Fig 5: Message complexity
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(NODE_COUNTS, [results[N]["uniform"]["total_msgs"] for N in NODE_COUNTS], "o-", color=red, lw=2, ms=8, label="Uniform")
    ax.plot(NODE_COUNTS, [results[N]["geo_weighted"]["total_msgs"] for N in NODE_COUNTS], "s-", color=green, lw=2, ms=8, label="Fixed GWG")
    ax.plot(NODE_COUNTS, [results[N]["adaptive_gwg"]["total_msgs"] for N in NODE_COUNTS], "^-", color=blue, lw=2, ms=8, label="Adaptive GWG")
    ax.set_xlabel("Fleet Size (N)")
    ax.set_ylabel("Total Messages")
    ax.set_title("Message Complexity vs Fleet Size", fontweight="bold")
    ax.legend()
    ax.grid(alpha=0.3)

    plt.tight_layout()
    p5 = os.path.join(out_dir, "fig5_message_complexity.png")
    plt.savefig(p5, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"Saved {p5}")

    # Fig 6:Per-region MAPE
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x - w, [results[N]["uniform"]["final_per_region_mape"] for N in NODE_COUNTS], w, color=red, label="Uniform")
    ax.bar(x, [results[N]["geo_weighted"]["final_per_region_mape"] for N in NODE_COUNTS], w, color=green, label="Fixed GWG")
    ax.bar(x + w, [results[N]["adaptive_gwg"]["final_per_region_mape"] for N in NODE_COUNTS], w, color=blue, label="Adaptive GWG")
    ax.set_xticks(x)
    ax.set_xticklabels([str(N) for N in NODE_COUNTS])
    ax.set_xlabel("Fleet Size (N)")
    ax.set_ylabel("Final Per-Region MAPE (%)")
    ax.set_title("C-6 Metric: Per-Region MAPE Comparison", fontweight="bold")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    p6 = os.path.join(out_dir, "fig6_c6_per_region_mape.png")
    plt.savefig(p6, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"Saved {p6}")

    # Fig 7: Adaptive overhead
    fig, ax = plt.subplots(figsize=(9, 5))
    active_regions = [results[N]["adaptive_gwg"]["overhead"]["avg_active_regions"] for N in NODE_COUNTS]
    changed_nodes = [results[N]["adaptive_gwg"]["overhead"]["avg_changed_node_pct"] for N in NODE_COUNTS]

    ax.plot(NODE_COUNTS, active_regions, "o-", lw=2, ms=8, label="Active adaptive regions")
    ax.set_xlabel("Fleet Size (N)")
    ax.set_ylabel("Average Active Regions")
    ax.set_title("C-6 Trade-off: Adaptive Region Management Overhead", fontweight="bold")
    ax.grid(alpha=0.3)

    ax2 = ax.twinx()
    ax2.plot(NODE_COUNTS, changed_nodes, "s--", lw=2, ms=8, label="Changed nodes (%)")
    ax2.set_ylabel("Changed Nodes (%)")

    lines_1, labels_1 = ax.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax.legend(lines_1 + lines_2, labels_1 + labels_2, loc="best")

    plt.tight_layout()
    p7 = os.path.join(out_dir, "fig7_c6_adaptive_overhead.png")
    plt.savefig(p7, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"Saved {p7}")

    return [p1, p2, p3, p4, p5, p6, p7]



# MAIN

if __name__ == "__main__":
    start_time = time.time()

    results = run_all_experiments()
    print_summary_table(results)
    print_c6_interpretation()
    print_amdahl_analysis()
    plot_results(results)

    print(f"\nDone in {time.time() - start_time:.1f}s")
