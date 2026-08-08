"""
Adaptive Region-Aware Geo-Weighted Push-Sum Gossip (Adaptive-GWG)
=================================================================

Evaluation harness for the paper "What Actually Makes Geo-Weighted Gossip
Regional: An Ablation of Region-Aware Push-Sum for Vehicular Networks".

Team: Fatima Ali (470708), Asma Imran (481920), Adeena Reeham (480941)

WHAT THIS VERSION FIXES RELATIVE TO src/legacy/gwg_simulation_v1.py
-------------------------------------------------------------------
The v1 harness produced numbers that did not support the paper's claims. The
audit that established this is reproducible: `python3 scripts/audit_baseline_claims.py`
and `python3 scripts/audit_ablation.py`. Summary of what changed and why:

 1. REAL PUSH-SUM.  v1's exchange was symmetric (both endpoints ended with the
    same value and weight), so every weight stayed pinned at 1.0 forever and the
    (value, weight) pair carried no information -- it was Boyd-style pairwise
    averaging, not Kempe-Dobra-Gehrke push-sum. Here a node keeps half its mass
    and pushes half, so weights genuinely diverge and the estimate is v/w.

 2. THE MISSING ABLATION.  v1 compared Adaptive-GWG only against gossip that was
    free to cross region boundaries (65.9% of v1's Fixed-GWG exchanges left the
    sender's region). That bundles two independent changes: confining gossip to a
    region, and adapting region boundaries to density. FIXED_CONFINED isolates
    them. It is the honest baseline and it is a strong one.

 3. A COMMON EVALUATION PARTITION.  v1 scored each protocol against its own
    partition of the fleet, i.e. a different ground-truth vector per protocol, so
    "per-region MAPE" was not comparable across the table. Every protocol here is
    scored against the same protocol-independent reporting grid.

 4. THE MERGE RULE NOW MERGES.  v1 relabelled sparse cells to ("merged", T) --
    a label region T's own members never adopted -- so the two groups stayed
    separate. Merging now assigns sparse nodes into an existing region's label.

 5. MOBILITY.  v1 never moved a vehicle. The paper's title claims a highly
    mobile network. Vehicles now move each round at their own speed, change
    cells, and re-sample local congestion as they go.

 6. CHURN.  Vehicles join and leave. Push-sum mass held by a departing vehicle
    is destroyed, which biases the estimate -- a real property of push-sum under
    churn that the paper should report rather than hide.

 7. HONEST STATISTICS.  Independent fleets per trial, 95% confidence intervals,
    and censored (non-converging) runs reported as a count instead of being
    averaged into a meaningless "151".

 8. CONTROL-MESSAGE ACCOUNTING.  v1 gave region management away for free, so
    "bandwidth is comparable" was an identity, not a result. Region-change
    announcements are now counted against Adaptive-GWG's own budget.

INPUT
    data/processed/nyc_speeds.npy   (produced by src/extract_speeds.py)

OUTPUT
    results/figures/*.png           publication figures
    results/results.json            every number the paper cites, machine-readable

HOW TO RUN (from repo root)
    python3 src/extract_speeds.py
    python3 src/gwg_simulation.py
"""

from __future__ import annotations

import json
import math
import os
import random
import time
from collections import defaultdict

import numpy as np

MATPLOTLIB_IMPORT_ERROR = None
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception as exc:  # pragma: no cover - environment dependent
    matplotlib = None
    plt = None
    MATPLOTLIB_IMPORT_ERROR = exc


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

RANDOM_SEED = 42

# Service area: a GRID_SIZE x GRID_SIZE lattice of REGION_SIZE-metre cells.
# 10 x 100 m = a 1 km x 1 km downtown area.
GRID_SIZE = 10
REGION_SIZE = 100.0
AREA_M = GRID_SIZE * REGION_SIZE

# One gossip round is one V2X beacon interval. 100 ms is the nominal CAM/BSM
# generation rate in ETSI EN 302 637-2 and SAE J2735, which is what makes
# "round" convertible to wall-clock time in the AV analysis below.
ROUND_DURATION_S = 0.100

# Radio neighbourhood. A vehicle may only gossip with vehicles inside
# COMM_RANGE_M. 250 m is a conservative urban DSRC/C-V2X figure -- deliberately
# below the ~1 km line-of-sight maximum, because the paper's setting is a dense
# built-up area.
COMM_RANGE_M = 250.0

# The inverse-distance draw scores every reachable neighbour. An earlier version
# sampled 12 candidates first to bound per-round cost; tests/test_gwg.py showed
# that shifted mean hop distance by 15%, so the shortcut was dropped. The 3x3
# cell scan already bounds the candidate set to roughly nine cells' occupancy.

MAX_ROUNDS = 150
TRIALS = 10
NODE_COUNTS = [100, 500, 1000]

# Convergence: 90% of evaluable vehicles within 5% of their cell's true mean.
CONVERGENCE_THRESHOLD = 0.05
CONVERGENCE_PCT = 0.90

# A cell needs at least this many vehicles before its average is a meaningful
# estimation target. Singleton cells are excluded from every error metric.
MIN_EVAL_NODES = 2

MSG_SIZE_BYTES = 42          # (value, weight, position, timestamp) push-sum payload
CONTROL_MSG_BYTES = 12       # region-change announcement

# Mobility. Each vehicle drives at its own current speed along a heading that
# random-walks; it reflects off the service-area boundary.
MOBILITY_ENABLED = True
HEADING_JITTER_RAD = 0.08

# Churn: per-round probability that any given vehicle leaves and is replaced by
# a newly arrived one. 0 for the main experiment; swept separately.
CHURN_RATE = 0.0

# Adaptive region management.
ADAPTIVE_MIN_REGION_NODES = 3
ADAPTIVE_MAX_REGION_NODES = 20
# Refresh every round in the headline comparison. The fixed-grid baselines
# re-derive a vehicle's region from its current cell every round, so anything
# slower would report a staleness penalty as if it were a property of adaptive
# region management. run_refresh_sweep() reports what slower refresh costs and
# saves.
ADAPTIVE_REFRESH_ROUNDS = 1

# Periodic restart of the push-sum accumulator, in rounds (0 disables).
#
# Push-sum assumes a fixed population and a static input. Neither holds here:
# vehicles cross region boundaries and re-initialise, which injects fresh
# weight-1 mass into a region where push-sum has already concentrated mass on a
# few holders. That inflates the region's weight with unaveraged readings, and
# the estimate drifts back toward a raw single reading. Measured over 150 rounds
# the error reaches a minimum near round 9 and then degrades by roughly 5x.
#
# Restarting the accumulator periodically is the standard remedy for running
# push-sum on time-varying data, and the convergence curve sets the period: long
# enough to average, short enough that drift cannot accumulate. It is applied
# identically to every protocol, so it does not favour any of them.
RESTART_INTERVAL = 10

# AV real-time readiness.
AV_LATENCY_BUDGETS_MS = [500, 1000, 2000, 5000]
AV_USABLE_MAPE_PCT = 10.0

OUT_DIR = "results/figures"
RESULTS_DIR = "results"
DATA_PATH = "data/processed/nyc_speeds.npy"
ROAD_NETWORK_PATH = "data/processed/road_network.json"

# Road-constrained mobility robustness check (run_road_mobility_comparison).
# Smaller trial count and a single fleet size than the headline TRIALS=10 /
# NODE_COUNTS: this sweep exists to check whether the confinement finding is
# an artefact of the random-walk mobility model, not to re-establish
# statistical power the main experiment already has. N=1000 is the density
# where the headline result is reported.
ROAD_MOBILITY_NODE_COUNTS = [1000]
ROAD_MOBILITY_TRIALS = 5

MPH_TO_MPS = 0.44704

# Protocol identifiers, in the fixed order used by every table and figure.
PROTOCOLS = ["uniform", "fixed_gwg", "fixed_confined", "adaptive_gwg"]
PROTOCOL_LABELS = {
    "uniform": "Uniform Random Gossip",
    "fixed_gwg": "Fixed GWG",
    "fixed_confined": "Fixed GWG (region-confined)",
    "adaptive_gwg": "Adaptive-GWG",
}
PROTOCOL_SHORT = {
    "uniform": "Uniform",
    "fixed_gwg": "Fixed GWG",
    "fixed_confined": "Fixed-confined",
    "adaptive_gwg": "Adaptive-GWG",
}
# Validated with the dataviz palette validator (light mode, categorical):
# lightness band PASS, chroma floor PASS, CVD separation PASS (worst adjacent
# deutan dE 11.0), normal-vision floor PASS (22.9), contrast PASS (all >= 3:1).
PROTOCOL_COLORS = {
    "uniform": "#3B6FD4",
    "fixed_gwg": "#009E73",
    "fixed_confined": "#D55E00",
    "adaptive_gwg": "#8E44AD",
}
# Secondary encoding so the figures survive greyscale printing.
PROTOCOL_MARKERS = {
    "uniform": "o",
    "fixed_gwg": "s",
    "fixed_confined": "^",
    "adaptive_gwg": "D",
}
PROTOCOL_LINESTYLES = {
    "uniform": (0, (1, 1)),
    "fixed_gwg": (0, (5, 2)),
    "fixed_confined": (0, (3, 1, 1, 1)),
    "adaptive_gwg": "solid",
}


def _load_speeds(path=DATA_PATH):
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Could not find '{path}'. Run 'python3 src/extract_speeds.py' from "
            f"the repo root first (see README.md) -- it reads the parquet files "
            f"in data/raw/ and writes this file."
        )
    return np.load(path)


def _load_road_network(path=ROAD_NETWORK_PATH):
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Could not find '{path}'. Run 'python3 src/extract_roads.py' from "
            f"the repo root first (see README.md) -- it fetches a real NYC "
            f"street network via OSM and writes this file."
        )
    return RoadNetwork(path)


# ---------------------------------------------------------------------------
# FLEET
# ---------------------------------------------------------------------------

def congestion_factor(cell_x, cell_y):
    """
    Speed multiplier for a grid cell: 0.7x at the congested centre rising to
    1.3x on the free-flowing outer corridors.

    Real cities show this gradient, and without it a "regional average" is just
    i.i.d. noise with no spatial structure for a regional protocol to recover --
    the v1 harness computed this quantity and then discarded it, which is why
    its regional ground truth was meaningless.
    """
    max_d = math.sqrt(2) * (GRID_SIZE / 2.0)
    d = math.sqrt((cell_x - GRID_SIZE / 2.0) ** 2 + (cell_y - GRID_SIZE / 2.0) ** 2)
    return 0.7 + 0.6 * min(d / max_d, 1.0)


class RoadNetwork:
    """
    Lightweight loader for the cached OSM extract (src/extract_roads.py writes
    it; this class never imports osmnx). Node ids from the JSON are remapped
    to dense integer indices for array-friendly lookups; adjacency is a
    per-node list of (neighbour_index, edge_length_m) so a vehicle reaching a
    node can pick its next edge in O(degree) rather than scanning every edge.
    """

    def __init__(self, path):
        with open(path) as f:
            raw = json.load(f)

        ids = list(raw["nodes"].keys())
        self.index_of = {node_id: i for i, node_id in enumerate(ids)}
        self.positions = np.array(
            [raw["nodes"][node_id] for node_id in ids], dtype=np.float64
        )
        self.n_nodes = len(ids)

        self.adjacency = [[] for _ in range(self.n_nodes)]
        self.edges = []  # flat (u, v, length) for uniform initial edge sampling
        for u_id, v_id, length in raw["edges"]:
            u, v = self.index_of[u_id], self.index_of[v_id]
            self.adjacency[u].append((v, length))
            self.adjacency[v].append((u, length))
            self.edges.append((u, v, length))

    def random_edge_positions(self, n, rng):
        """A uniformly random edge and a uniformly random point along it, for
        initial vehicle placement (and respawning churned-out vehicles)."""
        choices = rng.integers(0, len(self.edges), n)
        from_idx = np.empty(n, dtype=np.int64)
        to_idx = np.empty(n, dtype=np.int64)
        lengths = np.empty(n, dtype=np.float64)
        flip = rng.random(n) < 0.5
        for i, c in enumerate(choices):
            u, v, length = self.edges[c]
            if flip[i]:
                u, v = v, u
            from_idx[i] = u
            to_idx[i] = v
            lengths[i] = length
        progress = rng.uniform(0.0, lengths)
        return from_idx, to_idx, lengths, progress

    def xy(self, from_idx, to_idx, lengths, progress):
        frac = np.divide(progress, lengths, out=np.zeros_like(progress),
                         where=lengths > 0)
        p0 = self.positions[from_idx]
        p1 = self.positions[to_idx]
        return (p0[:, 0] + frac * (p1[:, 0] - p0[:, 0]),
                p0[:, 1] + frac * (p1[:, 1] - p0[:, 1]))

    def next_edge(self, arriving_at, came_from, rng):
        """Which node to head toward after reaching `arriving_at`, having just
        come from `came_from`. Excludes an immediate U-turn unless the node is
        a dead end (its only edge is the one just traversed)."""
        neighbours = self.adjacency[arriving_at]
        options = [(v, length) for v, length in neighbours if v != came_from]
        if not options:
            options = neighbours
        v, length = options[rng.integers(0, len(options))]
        return v, length


class Fleet:
    """
    Array-backed fleet state. Held as parallel numpy arrays rather than objects
    so that mobility, churn and per-round metrics stay cheap enough to run 10
    independent trials of every protocol.
    """

    def __init__(self, n, speed_pool, rng, road_network=None):
        self.n = n
        self.rng = rng
        self.speed_pool = speed_pool
        self.road_network = road_network

        if road_network is not None:
            (self.road_from, self.road_to,
             self.road_edge_len, self.road_progress) = \
                road_network.random_edge_positions(n, rng)
            self.x, self.y = road_network.xy(
                self.road_from, self.road_to, self.road_edge_len, self.road_progress)
        else:
            self.x = rng.uniform(0.0, AREA_M, n)
            self.y = rng.uniform(0.0, AREA_M, n)
        self.heading = rng.uniform(0.0, 2 * math.pi, n)

        # Each vehicle carries a base draw from the real NYC speed distribution;
        # its observed speed is that draw modulated by wherever it currently is.
        self.base_speed = rng.choice(speed_pool, n).astype(np.float64)
        self.true_speed = np.empty(n, dtype=np.float64)

        self.value = np.empty(n, dtype=np.float64)
        self.weight = np.ones(n, dtype=np.float64)

        self.messages_sent = 0
        self.control_messages = 0
        self.bytes_sent = 0.0
        self.total_hop_distance = 0.0
        self.exchanges = 0

        self.refresh_true_speed()
        self.reset_estimates()

    # -- geometry ----------------------------------------------------------

    def cell_index(self):
        cx = np.clip((self.x // REGION_SIZE).astype(np.int64), 0, GRID_SIZE - 1)
        cy = np.clip((self.y // REGION_SIZE).astype(np.int64), 0, GRID_SIZE - 1)
        return cx * GRID_SIZE + cy

    def refresh_true_speed(self):
        """Re-evaluate each vehicle's observed speed for its current cell."""
        cells = self.cell_index()
        cx = cells // GRID_SIZE
        cy = cells % GRID_SIZE
        factors = np.array([congestion_factor(a, b) for a, b in zip(cx, cy)])
        self.true_speed = np.clip(self.base_speed * factors, 5.0, 70.0)

    def reset_estimates(self, idx=None):
        if idx is None:
            self.value = self.true_speed.copy()
            self.weight = np.ones(self.n, dtype=np.float64)
        else:
            self.value[idx] = self.true_speed[idx]
            self.weight[idx] = 1.0

    def estimates(self):
        return self.value / np.maximum(self.weight, 1e-12)

    # -- dynamics ----------------------------------------------------------

    def step_mobility(self):
        """Advance one round of driving."""
        if not MOBILITY_ENABLED:
            return
        if self.road_network is not None:
            self._step_mobility_road()
        else:
            self._step_mobility_random_walk()

    def _step_mobility_random_walk(self):
        self.heading += self.rng.normal(0.0, HEADING_JITTER_RAD, self.n)
        dist = self.true_speed * MPH_TO_MPS * ROUND_DURATION_S
        self.x += dist * np.cos(self.heading)
        self.y += dist * np.sin(self.heading)

        # Reflect off the service-area boundary.
        for arr in (self.x, self.y):
            np.clip(arr, 0.0, AREA_M, out=arr)
        off = (self.x <= 0.0) | (self.x >= AREA_M) | (self.y <= 0.0) | (self.y >= AREA_M)
        if off.any():
            self.heading[off] += math.pi

    def _step_mobility_road(self):
        """
        Advance each vehicle along its current street edge; on reaching a
        node, turn onto a new edge (never straight back the way it came,
        unless that node is a dead end) and continue with the leftover
        distance. Vectorized for the common case (still mid-edge); only the
        vehicles that actually cross a node this round need the per-vehicle
        graph lookup, and one round's travel (a few metres at most, even at
        70 mph) is almost always far short of a city block, so this loop
        resolves in one or two passes.
        """
        remaining = self.true_speed * MPH_TO_MPS * ROUND_DURATION_S
        for _ in range(8):
            self.road_progress += remaining
            remaining = np.zeros(self.n, dtype=np.float64)
            overflow = self.road_progress - self.road_edge_len
            crossing = np.where(overflow > 0)[0]
            if crossing.size == 0:
                break
            for i in crossing:
                leftover = float(overflow[i])
                arrived_at = int(self.road_to[i])
                came_from = int(self.road_from[i])
                next_to, next_len = self.road_network.next_edge(
                    arrived_at, came_from, self.rng)
                self.road_from[i] = arrived_at
                self.road_to[i] = next_to
                self.road_edge_len[i] = next_len
                self.road_progress[i] = 0.0
                remaining[i] = leftover
        np.clip(self.road_progress, 0.0, self.road_edge_len, out=self.road_progress)
        self.x, self.y = self.road_network.xy(
            self.road_from, self.road_to, self.road_edge_len, self.road_progress)

    def step_churn(self, churn_rate):
        """
        Replace a random subset of vehicles with newly arrived ones.

        The departing vehicle's push-sum mass leaves with it. That is not an
        artefact -- push-sum conserves mass only over a fixed population, so
        churn is exactly where its accuracy guarantee is stressed.
        """
        if churn_rate <= 0.0:
            return 0
        leaving = np.where(self.rng.random(self.n) < churn_rate)[0]
        if leaving.size == 0:
            return 0
        if self.road_network is not None:
            f, t, l, p = self.road_network.random_edge_positions(leaving.size, self.rng)
            self.road_from[leaving] = f
            self.road_to[leaving] = t
            self.road_edge_len[leaving] = l
            self.road_progress[leaving] = p
            self.x[leaving], self.y[leaving] = self.road_network.xy(f, t, l, p)
        else:
            self.x[leaving] = self.rng.uniform(0.0, AREA_M, leaving.size)
            self.y[leaving] = self.rng.uniform(0.0, AREA_M, leaving.size)
            self.heading[leaving] = self.rng.uniform(0.0, 2 * math.pi, leaving.size)
        self.base_speed[leaving] = self.rng.choice(self.speed_pool, leaving.size)
        self.refresh_true_speed()
        self.reset_estimates(leaving)
        return int(leaving.size)


# ---------------------------------------------------------------------------
# SPATIAL INDEX
# ---------------------------------------------------------------------------

def build_spatial_buckets(fleet):
    """
    Bucket vehicles by grid cell. Peer lookup then scans only the 3x3 cell
    neighbourhood, which covers the COMM_RANGE_M radio range for the 100 m cell
    size used here, giving O(N) rebuild per round instead of v1's O(N^2 log N)
    sort -- this is what makes per-round mobility affordable.
    """
    buckets = defaultdict(list)
    cells = fleet.cell_index()
    for i, c in enumerate(cells):
        buckets[int(c)].append(i)
    return buckets, cells


def neighbourhood_candidates(fleet, buckets, cells, i):
    """Vehicle indices within COMM_RANGE_M of vehicle i (excluding i)."""
    c = int(cells[i])
    cx, cy = c // GRID_SIZE, c % GRID_SIZE
    out = []
    xi, yi = fleet.x[i], fleet.y[i]
    r2 = COMM_RANGE_M * COMM_RANGE_M
    for dx in (-1, 0, 1):
        ax = cx + dx
        if ax < 0 or ax >= GRID_SIZE:
            continue
        for dy in (-1, 0, 1):
            ay = cy + dy
            if ay < 0 or ay >= GRID_SIZE:
                continue
            for j in buckets.get(ax * GRID_SIZE + ay, ()):
                if j == i:
                    continue
                if (fleet.x[j] - xi) ** 2 + (fleet.y[j] - yi) ** 2 <= r2:
                    out.append(j)
    return out


# ---------------------------------------------------------------------------
# REGION ASSIGNMENT
# ---------------------------------------------------------------------------

def reporting_partition(cells):
    """
    The protocol-independent evaluation partition: the fixed 10x10 grid, derived
    from each vehicle's current position.

    Every protocol is scored against THIS partition. v1 scored each protocol
    against its own partition, so a protocol could lower its reported error
    simply by merging cells into larger, internally more homogeneous ones.
    """
    return cells.copy()


def adaptive_partition(fleet, cells,
                       min_nodes=None, max_nodes=None):
    """
    Density-driven region management.

      dense cell  (count > max_nodes)  -> split into 4 quadrant sub-regions
      sparse cell (count < min_nodes)  -> its vehicles JOIN the nearest region
      otherwise                        -> unchanged

    Returns (labels, stats). `labels` is an int array of region ids.

    The merge in v1 relabelled sparse vehicles to ("merged", T) -- an id that
    region T's own members never adopted -- so the sparse group became a new
    isolated region rather than joining T. Here sparse vehicles adopt an
    existing region's label, which is what "merge" has to mean for the region
    to actually pool its readings.
    """
    min_nodes = ADAPTIVE_MIN_REGION_NODES if min_nodes is None else min_nodes
    max_nodes = ADAPTIVE_MAX_REGION_NODES if max_nodes is None else max_nodes

    groups = defaultdict(list)
    for i, c in enumerate(cells):
        groups[int(c)].append(i)

    labels = np.full(fleet.n, -1, dtype=np.int64)
    region_members = {}      # label -> list of indices
    region_centroid = {}     # label -> (x, y)
    sparse_units = []        # (members, anchor_cell) groups too small to stand alone
    n_sparse = n_dense = 0

    n_cells = GRID_SIZE * GRID_SIZE

    def label_for_cell(cell):
        """Canonical id of an intact cell."""
        return int(cell)

    def label_for_quadrant(cell, qx, qy):
        """Canonical id of a quadrant of a split cell."""
        return int(n_cells + cell * 4 + qx * 2 + qy)

    def register(members, lab):
        # Region ids are derived from the geography they cover, never from a
        # counter. A counter renumbers regions whenever the iteration order of
        # occupied cells shifts -- which mobility guarantees -- and every
        # renumbered vehicle then looks like it changed region, triggering a
        # spurious push-sum reset and a spurious control message.
        region_members[lab] = list(members)
        region_centroid[lab] = (
            float(np.mean(fleet.x[members])),
            float(np.mean(fleet.y[members])),
        )
        for m in members:
            labels[m] = lab
        return lab

    # Iterate cells in sorted order so the partition is a pure function of
    # positions, independent of vehicle indexing.
    for cell in sorted(groups):
        members = groups[cell]
        count = len(members)
        if count > max_nodes:
            n_dense += 1
            cx, cy = cell // GRID_SIZE, cell % GRID_SIZE
            x_mid = (cx + 0.5) * REGION_SIZE
            y_mid = (cy + 0.5) * REGION_SIZE
            quads = defaultdict(list)
            for m in members:
                q = (0 if fleet.x[m] < x_mid else 1, 0 if fleet.y[m] < y_mid else 1)
                quads[q].append(m)
            for (qx, qy), q_members in sorted(quads.items()):
                if len(q_members) >= min_nodes:
                    register(q_members, label_for_quadrant(cell, qx, qy))
                else:
                    sparse_units.append((q_members, cell))
        elif count < min_nodes:
            n_sparse += 1
            sparse_units.append((members, cell))
        else:
            register(members, label_for_cell(cell))

    # Merge each sparse unit into the nearest established region.
    if region_members:
        for unit, _anchor in sparse_units:
            ux = float(np.mean(fleet.x[unit]))
            uy = float(np.mean(fleet.y[unit]))
            best = min(
                sorted(region_centroid),
                key=lambda lab: (region_centroid[lab][0] - ux) ** 2
                + (region_centroid[lab][1] - uy) ** 2,
            )
            for m in unit:
                labels[m] = best
            region_members[best].extend(unit)
    elif sparse_units:
        # Every cell is sparse (very low density). Agglomerate sparse units with
        # their nearest neighbour until each pooled region can stand alone. The
        # surviving unit's lowest anchor cell names the region, so the label
        # stays put across rounds as long as the grouping does.
        units = [(list(u), a) for u, a in sparse_units]
        while True:
            small = [k for k, (u, _) in enumerate(units) if len(u) < min_nodes]
            if not small or len(units) == 1:
                break
            k = min(small, key=lambda t: (len(units[t][0]), units[t][1]))
            ux = float(np.mean(fleet.x[units[k][0]]))
            uy = float(np.mean(fleet.y[units[k][0]]))
            others = [t for t in range(len(units)) if t != k]
            j = min(
                others,
                key=lambda t: ((float(np.mean(fleet.x[units[t][0]])) - ux) ** 2
                               + (float(np.mean(fleet.y[units[t][0]])) - uy) ** 2,
                               units[t][1]),
            )
            units[j] = (units[j][0] + units[k][0], min(units[j][1], units[k][1]))
            units.pop(k)
        for u, anchor in units:
            register(u, label_for_cell(anchor))

    stats = {
        "sparse_cells": n_sparse,
        "dense_cells": n_dense,
        "active_regions": int(len(set(labels.tolist()))),
    }
    return labels, stats


# ---------------------------------------------------------------------------
# PUSH-SUM
# ---------------------------------------------------------------------------

def push_sum_send(fleet, i, j):
    """
    One directional push-sum step (Kempe, Dobra & Gehrke, FOCS 2003): vehicle i
    keeps half of its (value, weight) mass and pushes the other half to j.

    Mass is conserved exactly, and weights genuinely diverge across the fleet --
    unlike v1's symmetric exchange, under which every weight stayed at 1.0 and
    the estimate degenerated to a plain running mean.
    """
    hv = fleet.value[i] * 0.5
    hw = fleet.weight[i] * 0.5
    fleet.value[i] -= hv
    fleet.weight[i] -= hw
    fleet.value[j] += hv
    fleet.weight[j] += hw

    fleet.messages_sent += 1
    fleet.bytes_sent += MSG_SIZE_BYTES
    d = math.hypot(fleet.x[i] - fleet.x[j], fleet.y[i] - fleet.y[j])
    fleet.total_hop_distance += d
    fleet.exchanges += 1
    return d


# ---------------------------------------------------------------------------
# PEER SELECTION
# ---------------------------------------------------------------------------

def _inverse_distance_pick(fleet, i, candidates, rng):
    """Draw one candidate with probability proportional to 1/distance."""
    if not candidates:
        return None
    xi, yi = fleet.x[i], fleet.y[i]
    weights = []
    for j in candidates:
        d = math.hypot(fleet.x[j] - xi, fleet.y[j] - yi)
        weights.append(1.0 / max(d, 1.0))
    total = sum(weights)
    if total <= 0:
        return int(rng.choice(candidates))
    r = rng.random() * total
    acc = 0.0
    for j, w in zip(candidates, weights):
        acc += w
        if r <= acc:
            return int(j)
    return int(candidates[-1])


def select_peer(protocol, fleet, buckets, cells, regions, i, rng):
    """
    Peer selection for each protocol.

    uniform         any vehicle in the fleet, ignoring geography entirely.
    fixed_gwg       inverse-distance draw over the radio neighbourhood, free to
                    cross region boundaries (this is Dimakis-style geographic
                    weighting applied to a fixed grid).
    fixed_confined  as fixed_gwg, but restricted to the sender's own fixed cell.
                    ABLATION: isolates "confine gossip to a region" from
                    "adapt region boundaries".
    adaptive_gwg    as fixed_confined, but over the adaptive region.

    The confined variants fall back to the full radio neighbourhood when the
    sender's region holds fewer than two reachable peers, otherwise a lone
    vehicle could never gossip at all.
    """
    if protocol == "uniform":
        j = int(rng.integers(fleet.n))
        while j == i:
            j = int(rng.integers(fleet.n))
        return j

    cands = neighbourhood_candidates(fleet, buckets, cells, i)
    if not cands:
        return None

    if protocol == "fixed_gwg":
        return _inverse_distance_pick(fleet, i, cands, rng)

    same = [j for j in cands if regions[j] == regions[i]]
    if len(same) >= 2:
        return _inverse_distance_pick(fleet, i, same, rng)
    return _inverse_distance_pick(fleet, i, cands, rng)


# ---------------------------------------------------------------------------
# METRICS
# ---------------------------------------------------------------------------

def region_truth(true_speed, partition):
    """Per-region mean of the observed speeds, and per-region population."""
    totals = defaultdict(float)
    counts = defaultdict(int)
    for i, r in enumerate(partition):
        totals[int(r)] += true_speed[i]
        counts[int(r)] += 1
    truth = {r: totals[r] / counts[r] for r in totals}
    return truth, counts


def error_metrics(estimates, true_speed, partition):
    """
    Two MAPEs against the reporting partition:

      micro  mean absolute percentage error over VEHICLES. Dense cells dominate.
      macro  error averaged within each region first, then across regions, so
             every region counts equally regardless of population.

    v1 called these "global" and "region" MAPE. Neither was global -- both were
    measured against regional targets -- and the naming caused the paper to
    describe a micro-average as a network-wide average.
    """
    truth, counts = region_truth(true_speed, partition)
    per_region = defaultdict(list)
    all_err = []
    for i, r in enumerate(partition):
        r = int(r)
        if counts[r] < MIN_EVAL_NODES:
            continue
        t = truth[r]
        if t <= 0:
            continue
        e = abs(estimates[i] - t) / t * 100.0
        all_err.append(e)
        per_region[r].append(e)
    micro = float(np.mean(all_err)) if all_err else 0.0
    macro = (
        float(np.mean([float(np.mean(v)) for v in per_region.values()]))
        if per_region else 0.0
    )
    converged_frac = (
        float(np.mean([e <= CONVERGENCE_THRESHOLD * 100.0 for e in all_err]))
        if all_err else 1.0
    )
    return micro, macro, converged_frac


# ---------------------------------------------------------------------------
# ONE RUN
# ---------------------------------------------------------------------------

def run_once(protocol, n, speed_pool, seed,
             max_rounds=MAX_ROUNDS, churn_rate=CHURN_RATE,
             mobility=None, min_nodes=None, max_nodes=None,
             refresh_rounds=None, restart_interval=None, road_network=None):
    """
    Run one protocol on one independently generated fleet.

    `refresh_rounds` controls how often the adaptive layer recomputes its
    regions. It is a parameter rather than a constant because the fixed-grid
    baselines re-derive their region from the vehicle's current cell every
    round; holding the adaptive layer to a slower refresh would penalise it for
    staleness rather than for its region policy. The sweep over this parameter
    is reported alongside the main result.
    """
    refresh_rounds = ADAPTIVE_REFRESH_ROUNDS if refresh_rounds is None else refresh_rounds
    restart_interval = RESTART_INTERVAL if restart_interval is None else restart_interval
    global MOBILITY_ENABLED
    prev_mobility = MOBILITY_ENABLED
    if mobility is not None:
        MOBILITY_ENABLED = mobility

    try:
        rng = np.random.default_rng(seed)
        fleet = Fleet(n, speed_pool, rng, road_network=road_network)

        buckets, cells = build_spatial_buckets(fleet)
        if protocol == "adaptive_gwg":
            regions, rstats = adaptive_partition(fleet, cells, min_nodes, max_nodes)
        else:
            regions = reporting_partition(cells)
            rstats = {
                "sparse_cells": 0,
                "dense_cells": 0,
                "active_regions": int(len(set(regions.tolist()))),
            }

        micro_curve = []
        macro_curve = []
        active_regions_seen = [rstats["active_regions"]]
        convergence_round = None
        order = np.arange(n)
        cross_region_exchanges = 0

        for rnd in range(1, max_rounds + 1):
            # Periodic restart, applied identically to every protocol.
            if restart_interval and rnd > 1 and rnd % restart_interval == 1:
                fleet.reset_estimates()
            fleet.step_mobility()
            fleet.step_churn(churn_rate)
            fleet.refresh_true_speed()

            buckets, cells = build_spatial_buckets(fleet)

            # Region maintenance.
            if protocol == "adaptive_gwg":
                if rnd % refresh_rounds == 0:
                    new_regions, rstats = adaptive_partition(fleet, cells, min_nodes, max_nodes)
                    changed = int(np.sum(new_regions != regions))
                    # Every relabelled vehicle announces its new region.
                    fleet.control_messages += changed
                    fleet.bytes_sent += changed * CONTROL_MSG_BYTES
                    # A vehicle that changed region must restart its push-sum
                    # accumulator: the mass it holds belongs to the old region.
                    if changed:
                        fleet.reset_estimates(np.where(new_regions != regions)[0])
                    regions = new_regions
                    active_regions_seen.append(rstats["active_regions"])
            else:
                new_regions = reporting_partition(cells)
                changed = np.where(new_regions != regions)[0]
                if changed.size:
                    fleet.reset_estimates(changed)
                regions = new_regions

            rng.shuffle(order)
            for i in order:
                i = int(i)
                j = select_peer(protocol, fleet, buckets, cells, regions, i, rng)
                if j is not None:
                    push_sum_send(fleet, i, j)
                    # A confined protocol still has to let an isolated vehicle
                    # gossip, so it falls back to the full radio neighbourhood.
                    # Every such exchange moves push-sum mass across a boundary
                    # of the REPORTING partition and is an irreversible leak
                    # toward the global mean. Counting them is what lets
                    # Section VI attribute the residual error floor to a
                    # mechanism instead of guessing.
                    #
                    # Measured on the reporting partition, never on the
                    # protocol's own regions: scored against its own labels a
                    # confined protocol is trivially at 0% by construction, which
                    # would say nothing about whether mass left the region the
                    # metric actually cares about.
                    if cells[j] != cells[i]:
                        cross_region_exchanges += 1

            est = fleet.estimates()
            report = reporting_partition(cells)
            micro, macro, frac = error_metrics(est, fleet.true_speed, report)
            micro_curve.append(micro)
            macro_curve.append(macro)

            if convergence_round is None and frac >= CONVERGENCE_PCT:
                convergence_round = rnd

        return {
            "protocol": protocol,
            "n": n,
            "converged": convergence_round is not None,
            "convergence_round": convergence_round,
            "final_micro_mape": micro_curve[-1],
            "final_macro_mape": macro_curve[-1],
            # Headline metric: error averaged over the second half of the run.
            # A single final-round reading is phase-sensitive once the
            # accumulator restarts periodically -- restart intervals of 10 and
            # 20 rounds happen to share their last restart before round 150 and
            # so report identical final-round error while behaving differently
            # throughout. Averaging over the steady-state half removes that
            # artefact and is what a deployment actually experiences.
            "steady_macro_mape": float(np.mean(macro_curve[len(macro_curve) // 2:])),
            "steady_micro_mape": float(np.mean(micro_curve[len(micro_curve) // 2:])),
            "best_macro_mape": float(np.min(macro_curve)),
            "best_macro_round": int(np.argmin(macro_curve) + 1),
            "micro_curve": micro_curve,
            "macro_curve": macro_curve,
            "avg_hop_m": fleet.total_hop_distance / max(fleet.exchanges, 1),
            "data_messages": fleet.messages_sent,
            "control_messages": fleet.control_messages,
            "total_bytes_per_node": fleet.bytes_sent / n,
            "avg_active_regions": float(np.mean(active_regions_seen)),
            "cross_region_exchange_pct":
                cross_region_exchanges / max(fleet.exchanges, 1) * 100.0,
        }
    finally:
        MOBILITY_ENABLED = prev_mobility


# ---------------------------------------------------------------------------
# STATISTICS
# ---------------------------------------------------------------------------

# Two-sided 95% t critical values, indexed by degrees of freedom. Avoids a scipy
# dependency for the one thing we need it for.
_T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
        8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160,
        14: 2.145, 15: 2.131, 19: 2.093, 24: 2.064, 29: 2.045}


def mean_ci95(values):
    """Mean and 95% confidence half-width (Student t, unbiased sd)."""
    v = np.asarray(values, dtype=float)
    n = v.size
    if n == 0:
        return 0.0, 0.0
    m = float(v.mean())
    if n == 1:
        return m, 0.0
    sd = float(v.std(ddof=1))
    df = n - 1
    t = _T95.get(df, 1.96 if df > 29 else 2.776)
    return m, t * sd / math.sqrt(n)


def paired_diff_ci95(a_values, b_values):
    """
    Mean and 95% CI of the paired difference a - b (Student t on the per-trial
    differences), plus whether that interval excludes zero.

    Every experiment here pairs trials by construction (run_main_experiment
    uses the same seed, and therefore the same fleet, for every protocol
    within a trial index -- see its docstring). Comparing two protocols by
    checking whether their independent per-protocol confidence intervals
    overlap throws that pairing away and is a strictly more conservative,
    lower-power test than analysing the paired differences directly: a paired
    design cancels the trial-to-trial fleet variance common to both protocols,
    which is exactly the variance an unpaired overlap check cannot remove.
    Reporting only the overlap check would understate how confidently a null
    result can be claimed here.
    """
    a = np.asarray(a_values, dtype=float)
    b = np.asarray(b_values, dtype=float)
    if a.size != b.size:
        raise ValueError("paired comparison requires equal-length, index-aligned samples")
    diff_m, diff_ci = mean_ci95(a - b)
    return {
        "mean_diff": diff_m,
        "ci95": diff_ci,
        "significant": bool(abs(diff_m) > diff_ci),
    }


def summarize(runs):
    """Aggregate the per-trial runs for one (protocol, N) cell of the table."""
    conv = [r["convergence_round"] for r in runs if r["converged"]]
    micro = [r["steady_micro_mape"] for r in runs]
    macro = [r["steady_macro_mape"] for r in runs]
    final_macro = [r["final_macro_mape"] for r in runs]
    best_macro = [r["best_macro_mape"] for r in runs]
    hop = [r["avg_hop_m"] for r in runs]
    byte = [r["total_bytes_per_node"] for r in runs]

    micro_m, micro_ci = mean_ci95(micro)
    macro_m, macro_ci = mean_ci95(macro)
    hop_m, hop_ci = mean_ci95(hop)
    byte_m, byte_ci = mean_ci95(byte)

    curve_len = len(runs[0]["micro_curve"])
    micro_curve = np.mean([r["micro_curve"] for r in runs], axis=0).tolist()
    macro_curve = np.mean([r["macro_curve"] for r in runs], axis=0).tolist()

    return {
        "trials": len(runs),
        "n_converged": len(conv),
        # Censored: reported as a count plus the median over CONVERGING runs
        # only. Averaging "did not converge" into a mean produces a number that
        # is not an estimate of anything, which is what v1 reported as "151".
        "median_convergence_round": float(np.median(conv)) if conv else None,
        "micro_mape": micro_m, "micro_mape_ci95": micro_ci,
        "macro_mape": macro_m, "macro_mape_ci95": macro_ci,
        "final_macro_mape": float(np.mean(final_macro)),
        "best_macro_mape": float(np.mean(best_macro)),
        "best_macro_round": float(np.mean([r["best_macro_round"] for r in runs])),
        "avg_hop_m": hop_m, "avg_hop_m_ci95": hop_ci,
        "bytes_per_node": byte_m, "bytes_per_node_ci95": byte_ci,
        "data_messages": float(np.mean([r["data_messages"] for r in runs])),
        "control_messages": float(np.mean([r["control_messages"] for r in runs])),
        "avg_active_regions": float(np.mean([r["avg_active_regions"] for r in runs])),
        "cross_region_exchange_pct":
            float(np.mean([r["cross_region_exchange_pct"] for r in runs])),
        "micro_curve": micro_curve,
        "macro_curve": macro_curve,
        "curve_len": curve_len,
        # Raw per-trial values, index-aligned with every other protocol at the
        # same N (same seed per trial index -- see run_main_experiment). Kept
        # so a paired test (paired_diff_ci95) can be computed downstream
        # instead of only comparing independent per-protocol intervals.
        "per_trial_macro_mape": [float(x) for x in macro],
        "per_trial_micro_mape": [float(x) for x in micro],
    }


# ---------------------------------------------------------------------------
# EXPERIMENTS
# ---------------------------------------------------------------------------

def run_main_experiment(speed_pool, trials=TRIALS, node_counts=None,
                        churn_rate=CHURN_RATE, mobility=True, tag="main",
                        restart_interval=None, road_network=None):
    node_counts = node_counts or NODE_COUNTS
    out = {}
    for n in node_counts:
        out[n] = {}
        for proto in PROTOCOLS:
            runs = []
            for t in range(trials):
                # Same fleet seed across protocols within a trial (paired
                # comparison), different across trials (independent replicates).
                runs.append(run_once(proto, n, speed_pool,
                                     seed=RANDOM_SEED + 1000 * t,
                                     churn_rate=churn_rate, mobility=mobility,
                                     restart_interval=restart_interval,
                                     road_network=road_network))
            out[n][proto] = summarize(runs)
            s = out[n][proto]
            conv = (f"{s['median_convergence_round']:.0f}"
                    if s["median_convergence_round"] is not None else "--")
            print(f"  [{tag}] N={n:>4} {PROTOCOL_SHORT[proto]:>15}  "
                  f"macroMAPE={s['macro_mape']:6.2f}%±{s['macro_mape_ci95']:.2f}  "
                  f"conv={conv:>4} ({s['n_converged']}/{s['trials']})  "
                  f"hop={s['avg_hop_m']:6.1f}m  "
                  f"bytes/node={s['bytes_per_node']:8.0f}", flush=True)
    return out


def run_churn_sweep(speed_pool, n=500, rates=(0.0, 0.01, 0.02, 0.05, 0.10), trials=5):
    print("\n>>> Churn sensitivity (N=%d)" % n, flush=True)
    out = {}
    for rate in rates:
        out[rate] = {}
        for proto in PROTOCOLS:
            runs = [run_once(proto, n, speed_pool, seed=RANDOM_SEED + 1000 * t,
                             churn_rate=rate, mobility=True)
                    for t in range(trials)]
            out[rate][proto] = summarize(runs)
        print(f"  churn={rate:.2f}  " + "  ".join(
            f"{PROTOCOL_SHORT[p]}={out[rate][p]['macro_mape']:.2f}%" for p in PROTOCOLS
        ), flush=True)
    return out


def run_mobility_sweep(speed_pool, n=500, trials=5):
    print("\n>>> Mobility on/off (N=%d)" % n, flush=True)
    out = {}
    for label, mob in (("static", False), ("mobile", True)):
        out[label] = {}
        for proto in PROTOCOLS:
            runs = [run_once(proto, n, speed_pool, seed=RANDOM_SEED + 1000 * t,
                             churn_rate=0.0, mobility=mob)
                    for t in range(trials)]
            out[label][proto] = summarize(runs)
        print(f"  {label:>7}  " + "  ".join(
            f"{PROTOCOL_SHORT[p]}={out[label][p]['macro_mape']:.2f}%" for p in PROTOCOLS
        ), flush=True)
    return out


def run_threshold_sensitivity(speed_pool, n=500, trials=5):
    """
    Sweep the adaptive layer's two thresholds. The paper claims regions adapt to
    density; if the result were an artefact of one lucky (min, max) pair, that
    claim would not hold up, so the sweep is reported rather than a single point.
    """
    print("\n>>> Adaptive threshold sensitivity (N=%d)" % n, flush=True)
    out = {}
    for lo in (2, 3, 5, 8):
        for hi in (12, 20, 30):
            runs = [run_once("adaptive_gwg", n, speed_pool,
                             seed=RANDOM_SEED + 1000 * t, churn_rate=0.0,
                             mobility=True, min_nodes=lo, max_nodes=hi)
                    for t in range(trials)]
            s = summarize(runs)
            out[f"{lo}_{hi}"] = {"min": lo, "max": hi,
                                 "macro_mape": s["macro_mape"],
                                 "macro_mape_ci95": s["macro_mape_ci95"],
                                 "active_regions": s["avg_active_regions"]}
            print(f"  min={lo:>2} max={hi:>2}  macroMAPE={s['macro_mape']:6.2f}%"
                  f"±{s['macro_mape_ci95']:.2f}  regions={s['avg_active_regions']:.1f}",
                  flush=True)
    return out


def run_refresh_sweep(speed_pool, n=500, rates=(1, 2, 5, 10, 25), trials=5):
    """
    How often does the adaptive layer have to recompute its regions?

    Refreshing every round tracks mobility exactly but pays a control message
    for every vehicle that changes region; refreshing rarely is cheap but lets a
    vehicle hold mass belonging to a region it has already driven out of. This
    sweep is what lets the paper defend its choice instead of asserting it.
    """
    print("\n>>> Adaptive refresh-interval sweep (N=%d)" % n, flush=True)
    out = {}
    for r in rates:
        runs = [run_once("adaptive_gwg", n, speed_pool, seed=RANDOM_SEED + 1000 * t,
                         churn_rate=0.0, mobility=True, refresh_rounds=r)
                for t in range(trials)]
        s = summarize(runs)
        out[str(r)] = {"refresh_rounds": r,
                       "macro_mape": s["macro_mape"],
                       "macro_mape_ci95": s["macro_mape_ci95"],
                       "control_messages": s["control_messages"],
                       "bytes_per_node": s["bytes_per_node"]}
        print(f"  refresh every {r:>2} rounds  macroMAPE={s['macro_mape']:6.2f}%"
              f"±{s['macro_mape_ci95']:.2f}  control msgs={s['control_messages']:.0f}"
              f"  bytes/node={s['bytes_per_node']:.0f}", flush=True)
    return out


def run_restart_sweep(speed_pool, n=500, intervals=(0, 5, 10, 20, 50), trials=5):
    """
    Sweep the push-sum restart period, including 0 (never restart).

    Applied identically to every protocol. Without restart the estimate reaches
    a minimum after a few rounds and then degrades, because re-initialisation at
    region boundaries keeps injecting unaveraged weight-1 mass into regions where
    push-sum has already concentrated mass. Reporting only the final round would
    describe that degraded state; reporting only the minimum would flatter every
    protocol with a number it cannot hold. The sweep shows what a deployment can
    actually sustain.
    """
    print("\n>>> Push-sum restart-interval sweep (N=%d)" % n, flush=True)
    out = {}
    for iv in intervals:
        out[str(iv)] = {}
        for proto in PROTOCOLS:
            runs = [run_once(proto, n, speed_pool, seed=RANDOM_SEED + 1000 * t,
                             churn_rate=0.0, mobility=True, restart_interval=iv)
                    for t in range(trials)]
            s = summarize(runs)
            curve = np.array(s["macro_curve"])
            out[str(iv)][proto] = {
                "macro_mape": s["macro_mape"],
                "macro_mape_ci95": s["macro_mape_ci95"],
                "best_macro_mape": float(curve.min()),
                "best_round": int(curve.argmin() + 1),
            }
        label = "never" if not iv else f"every {iv}"
        print(f"  restart {label:>9}  " + "  ".join(
            f"{PROTOCOL_SHORT[p]}={out[str(iv)][p]['macro_mape']:.2f}%" for p in PROTOCOLS
        ), flush=True)
    return out


def run_road_mobility_comparison(speed_pool, road_network,
                                 node_counts=None, trials=None):
    """
    Robustness check, not a replacement for the main experiment: rerun the
    same four-protocol comparison with vehicles constrained to a real NYC
    street network (src/extract_roads.py) instead of the random-walk mobility
    model used everywhere else, and report whether region confinement still
    explains the improvement. Region assignment, radio range and the
    congestion field are unchanged -- only how vehicles move through the same
    service area changes.
    """
    node_counts = node_counts or ROAD_MOBILITY_NODE_COUNTS
    trials = trials or ROAD_MOBILITY_TRIALS
    print("\n>>> Road-constrained mobility robustness check", flush=True)
    return run_main_experiment(speed_pool, trials=trials, node_counts=node_counts,
                               churn_rate=0.0, mobility=True, tag="road",
                               road_network=road_network)


def compute_ablation_significance(main):
    """
    Paired significance test for the two ablation questions Section VI-B and
    VI-J answer, at every N present in `main`:

      confinement: does confining Fixed GWG to the sender's cell change error?
                   (fixed_gwg per-trial macro MAPE) - (fixed_confined ...)
      adaptation:  does adding density-driven regions on top of confinement
                   change error?
                   (fixed_confined per-trial macro MAPE) - (adaptive_gwg ...)

    Both are paired differences (positive = the second protocol is more
    accurate), using paired_diff_ci95 rather than comparing the two
    protocols' independent confidence intervals -- see that function's
    docstring for why the paired version is the correct, higher-power test
    here. Works for any main-shaped dict (the headline random-walk `main`
    table or the road-constrained `road_mobility` table), since both are
    produced by run_main_experiment with the same seed-per-trial pairing.
    """
    out = {}
    for n, protos in main.items():
        fg = protos["fixed_gwg"]["per_trial_macro_mape"]
        fc = protos["fixed_confined"]["per_trial_macro_mape"]
        ag = protos["adaptive_gwg"]["per_trial_macro_mape"]
        out[n] = {
            "confinement": paired_diff_ci95(fg, fc),
            "adaptation": paired_diff_ci95(fc, ag),
        }
    return out


def compute_av_readiness(main):
    """
    Reframe the convergence curves against a V2X latency budget: at 100 ms per
    beacon interval, a 1 s decision deadline is 10 rounds. Reports the error a
    protocol would hand an AV decision system at that deadline.
    """
    table = {}
    for n, per_proto in main.items():
        table[n] = {}
        for proto, s in per_proto.items():
            row = {}
            for budget in AV_LATENCY_BUDGETS_MS:
                idx = max(1, int(budget / (ROUND_DURATION_S * 1000)))
                idx = min(idx, len(s["macro_curve"]))
                mape = s["macro_curve"][idx - 1]
                row[budget] = {"round": idx, "macro_mape": mape,
                               "usable": bool(mape <= AV_USABLE_MAPE_PCT)}
            table[n][proto] = row
    return table


# ---------------------------------------------------------------------------
# REPORTING
# ---------------------------------------------------------------------------

def print_main_table(main):
    print("\n" + "=" * 122)
    print("MAIN RESULTS  (mobility on, no churn, restart every %d rounds, 95%% CI)" % RESTART_INTERVAL)
    print("=" * 122)
    print("macro/micro MAPE = mean over the steady-state half of the run.")
    print("x-region % = share of exchanges that moved mass across a region boundary.")
    print(f"{'N':>5} | {'Protocol':>27} | {'macro MAPE %':>16} | {'micro MAPE %':>16} | "
          f"{'conv (med)':>11} | {'hop m':>7} | {'B/node':>8} | {'x-region %':>10}")
    print("-" * 122)
    for n in sorted(main):
        for proto in PROTOCOLS:
            s = main[n][proto]
            conv = (f"{s['median_convergence_round']:.0f} ({s['n_converged']}/{s['trials']})"
                    if s["median_convergence_round"] is not None
                    else f"-- (0/{s['trials']})")
            print(f"{n:>5} | {PROTOCOL_LABELS[proto]:>27} | "
                  f"{s['macro_mape']:>9.2f} ±{s['macro_mape_ci95']:<5.2f} | "
                  f"{s['micro_mape']:>9.2f} ±{s['micro_mape_ci95']:<5.2f} | "
                  f"{conv:>11} | {s['avg_hop_m']:>7.1f} | {s['bytes_per_node']:>8.0f} | "
                  f"{s['cross_region_exchange_pct']:>10.1f}")
        print("-" * 122)


def print_attribution(main):
    """
    The question the paper has to answer: how much of Adaptive-GWG's advantage
    comes from confining gossip to a region (which the fixed grid can also do),
    and how much from adapting the regions to density?
    """
    print("\n" + "=" * 92)
    print("CONTRIBUTION ATTRIBUTION  (macro MAPE, lower is better)")
    print("=" * 92)
    print(f"{'N':>5} | {'Fixed GWG':>10} | {'+confined':>10} | {'+adaptive':>10} | "
          f"{'gain: confine':>14} | {'gain: adapt':>12}")
    print("-" * 92)
    for n in sorted(main):
        f = main[n]["fixed_gwg"]["macro_mape"]
        c = main[n]["fixed_confined"]["macro_mape"]
        a = main[n]["adaptive_gwg"]["macro_mape"]
        g1 = (f - c) / f * 100 if f else 0.0
        g2 = (c - a) / c * 100 if c else 0.0
        print(f"{n:>5} | {f:>9.2f}% | {c:>9.2f}% | {a:>9.2f}% | "
              f"{g1:>13.1f}% | {g2:>11.1f}%")
    print("-" * 92)
    print("'gain: confine' is what a one-line change to the fixed-grid baseline buys.")
    print("'gain: adapt'  is what the adaptive region layer adds on top of that.")
    print("Only the second column is evidence for the paper's contribution (1).")


def print_road_mobility_comparison(main, road_mobility):
    """
    Does the confinement finding hold up off the random-walk mobility model?
    Same attribution question as print_attribution, computed on the
    road-constrained run and set beside the random-walk numbers at matched N.
    """
    print("\n" + "=" * 92)
    print("ROAD-CONSTRAINED MOBILITY ROBUSTNESS CHECK  (macro MAPE, lower is better)")
    print("=" * 92)
    print(f"{'N':>5} | {'mobility':>9} | {'Fixed GWG':>10} | {'+confined':>10} | "
          f"{'+adaptive':>10} | {'gain: confine':>14} | {'gain: adapt':>12}")
    print("-" * 92)
    for n in sorted(road_mobility):
        for label, results in (("random-walk", main), ("road net", road_mobility)):
            f = results[n]["fixed_gwg"]["macro_mape"]
            c = results[n]["fixed_confined"]["macro_mape"]
            a = results[n]["adaptive_gwg"]["macro_mape"]
            g1 = (f - c) / f * 100 if f else 0.0
            g2 = (c - a) / c * 100 if c else 0.0
            print(f"{n:>5} | {label:>9} | {f:>9.2f}% | {c:>9.2f}% | {a:>9.2f}% | "
                  f"{g1:>13.1f}% | {g2:>11.1f}%")
    print("-" * 92)
    print("If 'gain: confine' stays large and positive under a real street network,")
    print("the headline finding is not an artefact of the random-walk mobility model.")


def print_av_readiness(av):
    print("\n" + "=" * 92)
    print("AV REAL-TIME READINESS")
    print("=" * 92)
    print(f"One round = {ROUND_DURATION_S*1000:.0f} ms V2X beacon interval "
          f"(ETSI EN 302 637-2 / SAE J2735 nominal CAM/BSM rate).")
    print(f"'OK' = macro MAPE <= {AV_USABLE_MAPE_PCT}%.\n")
    for n in sorted(av):
        print(f"--- N={n} ---")
        print("Protocol".ljust(29) + "".join(f"{b/1000:>10.1f}s" for b in AV_LATENCY_BUDGETS_MS))
        for proto in PROTOCOLS:
            row = av[n][proto]
            cells = "".join(
                f"{row[b]['macro_mape']:>7.1f}%{'OK' if row[b]['usable'] else '  '}"
                for b in AV_LATENCY_BUDGETS_MS)
            print(PROTOCOL_LABELS[proto].ljust(29) + cells)
        print()


def print_amdahl_analysis():
    """
    Speedup bounds for the region-management stage. f is the fraction of a round
    that is inherently serial; the estimate below is illustrative, not measured,
    and the paper says so.
    """
    print("=" * 92)
    print("AMDAHL / GUSTAFSON (illustrative, f = 0.05 serial fraction)")
    print("=" * 92)
    f = 0.05
    print("  p   Amdahl speedup   efficiency   Gustafson scaled speedup")
    for p in (1, 2, 4, 8, 16, 32, 64):
        amdahl = 1 / (f + (1 - f) / p)
        gust = p - f * (p - 1)
        print(f"{p:>3}   {amdahl:>13.2f}x   {amdahl/p*100:>9.1f}%   {gust:>22.2f}x")


# ---------------------------------------------------------------------------
# FIGURES
# ---------------------------------------------------------------------------

def _style(ax):
    ax.grid(alpha=0.25, linewidth=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def _bars(ax, node_counts, values, errs=None):
    """Grouped bars, one group per fleet size, with a 2 px gap between bars."""
    x = np.arange(len(node_counts))
    w = 0.2
    for k, proto in enumerate(PROTOCOLS):
        off = (k - 1.5) * (w + 0.02)
        ax.bar(x + off, values[proto], w,
               yerr=(errs[proto] if errs else None), capsize=3,
               color=PROTOCOL_COLORS[proto], label=PROTOCOL_LABELS[proto],
               edgecolor="white", linewidth=1.2)
    ax.set_xticks(x)
    ax.set_xticklabels([str(n) for n in node_counts])
    _style(ax)


def make_figures(main, churn, mobility, sensitivity, av, restart,
                 road_mobility=None, ablation_significance=None,
                 road_ablation_significance=None, out_dir=OUT_DIR):
    if plt is None:
        print(f"\nFigures skipped, matplotlib unavailable: {MATPLOTLIB_IMPORT_ERROR}")
        return []
    os.makedirs(out_dir, exist_ok=True)
    plt.rcParams.update({"font.size": 9, "axes.titlesize": 10,
                         "figure.facecolor": "white", "savefig.facecolor": "white"})
    node_counts = sorted(main)
    saved = []

    def save(fig, name):
        p = os.path.join(out_dir, name)
        fig.savefig(p, dpi=200, bbox_inches="tight")
        plt.close(fig)
        print(f"  saved {p}")
        saved.append(p)

    # Fig 1 -- convergence curves, one panel per fleet size.
    fig, axes = plt.subplots(1, len(node_counts), figsize=(4.0 * len(node_counts), 3.2),
                             sharey=True)
    axes = np.atleast_1d(axes)
    for ax, n in zip(axes, node_counts):
        rounds = np.arange(1, main[n][PROTOCOLS[0]]["curve_len"] + 1)
        for proto in PROTOCOLS:
            ax.plot(rounds, main[n][proto]["macro_curve"], lw=2,
                    color=PROTOCOL_COLORS[proto], linestyle=PROTOCOL_LINESTYLES[proto],
                    label=PROTOCOL_LABELS[proto])
        ax.axhline(5, color="#888", lw=1, ls=":")
        ax.set_title(f"N = {n}")
        ax.set_xlabel("Gossip round")
        ax.set_yscale("log")
        _style(ax)
    axes[0].set_ylabel("Per-region (macro) MAPE  %")
    axes[-1].legend(frameon=False, fontsize=7.5, loc="upper right")
    fig.suptitle("Convergence of the per-region speed estimate", fontweight="bold", y=1.02)
    save(fig, "fig1_convergence_curves.png")

    # Fig 2 -- final accuracy with CIs.
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    _bars(ax,
          node_counts,
          {p: [main[n][p]["macro_mape"] for n in node_counts] for p in PROTOCOLS},
          {p: [main[n][p]["macro_mape_ci95"] for n in node_counts] for p in PROTOCOLS})
    ax.set_xlabel("Fleet size N")
    ax.set_ylabel("Final per-region MAPE  %")
    ax.set_title("Estimation accuracy after 150 rounds (95% CI)", fontweight="bold")
    ax.legend(frameon=False, fontsize=8)
    save(fig, "fig2_final_mape.png")

    # Fig 3 -- attribution: what each mechanism actually buys.
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    x = np.arange(len(node_counts))
    confine = [(main[n]["fixed_gwg"]["macro_mape"] - main[n]["fixed_confined"]["macro_mape"])
               / max(main[n]["fixed_gwg"]["macro_mape"], 1e-9) * 100 for n in node_counts]
    adapt = [(main[n]["fixed_confined"]["macro_mape"] - main[n]["adaptive_gwg"]["macro_mape"])
             / max(main[n]["fixed_confined"]["macro_mape"], 1e-9) * 100 for n in node_counts]
    ax.bar(x - 0.16, confine, 0.3, color=PROTOCOL_COLORS["fixed_confined"],
           edgecolor="white", linewidth=1.2, label="Region-confined peer selection")
    ax.bar(x + 0.16, adapt, 0.3, color=PROTOCOL_COLORS["adaptive_gwg"],
           edgecolor="white", linewidth=1.2, label="Adaptive region management")
    ax.axhline(0, color="#444", lw=1)
    ax.set_xticks(x)
    ax.set_xticklabels([str(n) for n in node_counts])
    ax.set_xlabel("Fleet size N")
    ax.set_ylabel("MAPE reduction attributable  %")
    ax.set_title("Where the improvement comes from", fontweight="bold")
    ax.legend(frameon=False, fontsize=8)
    _style(ax)
    save(fig, "fig3_attribution.png")

    # Fig 4 -- hop distance.
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    _bars(ax, node_counts,
          {p: [main[n][p]["avg_hop_m"] for n in node_counts] for p in PROTOCOLS},
          {p: [main[n][p]["avg_hop_m_ci95"] for n in node_counts] for p in PROTOCOLS})
    ax.set_xlabel("Fleet size N")
    ax.set_ylabel("Mean hop distance  m")
    ax.set_title("Geographic distance per gossip exchange (95% CI)", fontweight="bold")
    ax.legend(frameon=False, fontsize=8)
    save(fig, "fig4_hop_distance.png")

    # Fig 5 -- communication cost, data vs control bytes.
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    _bars(ax, node_counts,
          {p: [main[n][p]["bytes_per_node"] / 1024 for n in node_counts] for p in PROTOCOLS})
    ax.set_xlabel("Fleet size N")
    ax.set_ylabel("Bytes per vehicle  KB")
    ax.set_title("Communication cost, including region-management control traffic",
                 fontweight="bold")
    ax.legend(frameon=False, fontsize=8)
    save(fig, "fig5_communication_cost.png")

    # Fig 6 -- churn.
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    rates = sorted(churn)
    for proto in PROTOCOLS:
        ax.plot([r * 100 for r in rates], [churn[r][proto]["macro_mape"] for r in rates],
                marker=PROTOCOL_MARKERS[proto], ms=6, lw=2,
                color=PROTOCOL_COLORS[proto], linestyle=PROTOCOL_LINESTYLES[proto],
                label=PROTOCOL_LABELS[proto])
    ax.set_xlabel("Per-round churn rate  % of fleet")
    ax.set_ylabel("Final per-region MAPE  %")
    ax.set_title("Robustness to vehicles joining and leaving (N = 500)", fontweight="bold")
    ax.legend(frameon=False, fontsize=8)
    _style(ax)
    save(fig, "fig6_churn.png")

    # Fig 7 -- threshold sensitivity. Single axis, one line per max threshold.
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    mins = sorted({v["min"] for v in sensitivity.values()})
    maxs = sorted({v["max"] for v in sensitivity.values()})
    ramp = ["#B8D4F0", "#5B9BD5", "#1F4E79"]
    for k, hi in enumerate(maxs):
        ys = [sensitivity[f"{lo}_{hi}"]["macro_mape"] for lo in mins]
        es = [sensitivity[f"{lo}_{hi}"]["macro_mape_ci95"] for lo in mins]
        ax.errorbar(mins, ys, yerr=es, marker="o", ms=6, lw=2, capsize=3,
                    color=ramp[k % len(ramp)], label=f"split above {hi}")
    ax.set_xlabel("Merge threshold: minimum vehicles per region")
    ax.set_ylabel("Final per-region MAPE  %")
    ax.set_title("Sensitivity to the adaptive thresholds (N = 500, 95% CI)",
                 fontweight="bold")
    ax.legend(frameon=False, fontsize=8, title="Split threshold", title_fontsize=8)
    _style(ax)
    save(fig, "fig7_threshold_sensitivity.png")

    # Fig 8 -- AV readiness.
    fig, axes = plt.subplots(1, len(node_counts), figsize=(4.0 * len(node_counts), 3.2),
                             sharey=True)
    axes = np.atleast_1d(axes)
    budgets = [b / 1000 for b in AV_LATENCY_BUDGETS_MS]
    for ax, n in zip(axes, node_counts):
        for proto in PROTOCOLS:
            ys = [av[n][proto][b]["macro_mape"] for b in AV_LATENCY_BUDGETS_MS]
            ax.plot(budgets, ys, marker=PROTOCOL_MARKERS[proto], ms=6, lw=2,
                    color=PROTOCOL_COLORS[proto], linestyle=PROTOCOL_LINESTYLES[proto],
                    label=PROTOCOL_LABELS[proto])
        ax.axhline(AV_USABLE_MAPE_PCT, color="#888", lw=1, ls=":")
        ax.set_title(f"N = {n}")
        ax.set_xlabel("Decision deadline  s")
        ax.set_yscale("log")
        _style(ax)
    axes[0].set_ylabel("Per-region MAPE  %")
    axes[-1].legend(frameon=False, fontsize=7.5)
    fig.suptitle("Error available within a V2X decision deadline", fontweight="bold", y=1.02)
    save(fig, "fig8_av_readiness.png")

    # Fig 10 -- restart interval.
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ivs = sorted(restart, key=lambda k: (int(k) == 0, int(k)))
    xs = list(range(len(ivs)))
    for proto in PROTOCOLS:
        ax.plot(xs, [restart[i][proto]["macro_mape"] for i in ivs],
                marker=PROTOCOL_MARKERS[proto], ms=6, lw=2,
                color=PROTOCOL_COLORS[proto], linestyle=PROTOCOL_LINESTYLES[proto],
                label=PROTOCOL_LABELS[proto])
    ax.set_xticks(xs)
    ax.set_xticklabels(["never" if int(i) == 0 else i for i in ivs])
    ax.set_xlabel("Push-sum restart interval (rounds)")
    ax.set_ylabel("Steady-state per-region MAPE  %")
    ax.set_title("Periodic restart bounds the drift caused by mobility (N = 500)",
                 fontweight="bold")
    ax.legend(frameon=False, fontsize=8)
    _style(ax)
    save(fig, "fig10_restart_interval.png")

    # Fig 9 -- mobility on/off.
    fig, ax = plt.subplots(figsize=(6.0, 3.6))
    x = np.arange(2)
    w = 0.2
    for k, proto in enumerate(PROTOCOLS):
        vals = [mobility["static"][proto]["macro_mape"], mobility["mobile"][proto]["macro_mape"]]
        errs = [mobility["static"][proto]["macro_mape_ci95"],
                mobility["mobile"][proto]["macro_mape_ci95"]]
        ax.bar(x + (k - 1.5) * (w + 0.02), vals, w, yerr=errs, capsize=3,
               color=PROTOCOL_COLORS[proto], label=PROTOCOL_LABELS[proto],
               edgecolor="white", linewidth=1.2)
    ax.set_xticks(x)
    ax.set_xticklabels(["Static network", "Mobile vehicles"])
    ax.set_ylabel("Final per-region MAPE  %")
    ax.set_title("Cost of mobility (N = 500, 95% CI)", fontweight="bold")
    ax.legend(frameon=False, fontsize=8)
    _style(ax)
    save(fig, "fig9_mobility.png")

    # Fig 11 -- random-walk vs. road-constrained mobility, at matched N.
    if road_mobility:
        fig, ax = plt.subplots(figsize=(6.0, 3.6))
        rn = sorted(road_mobility)
        x = np.arange(len(rn))
        w = 0.2
        for k, proto in enumerate(PROTOCOLS):
            vals = [main[n][proto]["macro_mape"] for n in rn]
            errs = [main[n][proto]["macro_mape_ci95"] for n in rn]
            ax.bar(x + (k - 1.5) * (w + 0.02) - 0.42, vals, w, yerr=errs, capsize=3,
                   color=PROTOCOL_COLORS[proto], alpha=0.45,
                   edgecolor="white", linewidth=1.2)
        for k, proto in enumerate(PROTOCOLS):
            vals = [road_mobility[n][proto]["macro_mape"] for n in rn]
            errs = [road_mobility[n][proto]["macro_mape_ci95"] for n in rn]
            ax.bar(x + (k - 1.5) * (w + 0.02) + 0.42, vals, w, yerr=errs, capsize=3,
                   color=PROTOCOL_COLORS[proto], label=PROTOCOL_LABELS[proto],
                   edgecolor="white", linewidth=1.2)
        ax.set_xticks(x)
        ax.set_xticklabels([f"N={n}" for n in rn])
        ax.set_ylabel("Final per-region MAPE  %")
        ax.set_title("Random-walk (left, faded) vs. real-street mobility (right), 95% CI",
                     fontweight="bold")
        ax.legend(frameon=False, fontsize=8)
        _style(ax)
        save(fig, "fig11_road_mobility.png")

    # Fig 12 -- paired significance ("forest plot") for the adaptation question:
    # does adaptive region management change macro MAPE relative to a
    # region-confined fixed grid, tested on the paired per-trial difference
    # rather than by eyeballing whether independent CIs overlap.
    if ablation_significance:
        rows = []  # (label, mean_diff, ci95) -- diff sign flipped so
                   # positive = adaptive-GWG worse (higher error) than confined.
        for n in node_counts:
            a = ablation_significance[n]["adaptation"]
            rows.append((f"N={n}\n(random walk)", -a["mean_diff"], a["ci95"]))
        if road_ablation_significance:
            for n in sorted(road_ablation_significance):
                a = road_ablation_significance[n]["adaptation"]
                rows.append((f"N={n}\n(road-constrained)", -a["mean_diff"], a["ci95"]))

        fig, ax = plt.subplots(figsize=(6.0, 0.9 * len(rows) + 1.2))
        y = np.arange(len(rows))
        diffs = [r[1] for r in rows]
        errs = [r[2] for r in rows]
        colors = ["#D55E00" if abs(d) > e else "#5B5B5B" for d, e in zip(diffs, errs)]
        ax.axvline(0, color="#888", lw=1.2, ls="-")
        ax.errorbar(diffs, y, xerr=errs, fmt="o", ms=7, lw=2, capsize=4,
                    ecolor="#5B5B5B", mec="black", mfc="white", zorder=3)
        for yi, d, c in zip(y, diffs, colors):
            ax.plot(d, yi, "o", ms=9, color=c, zorder=2)
        ax.set_yticks(y)
        ax.set_yticklabels([r[0] for r in rows])
        ax.set_xlabel("Paired difference, adaptive-GWG − fixed-confined (macro MAPE points)\n"
                      "positive = adaptation makes it worse; error bars are 95% paired CI")
        ax.set_title("Does adaptive region management change accuracy?\n"
                     "(paired test on same-trial difference, not independent-CI overlap)",
                     fontweight="bold")
        from matplotlib.lines import Line2D
        legend_handles = [
            Line2D([0], [0], marker="o", color="none", mfc="#5B5B5B", mec="black",
                  ms=9, label="95% CI includes zero (not significant)"),
            Line2D([0], [0], marker="o", color="none", mfc="#D55E00", mec="black",
                  ms=9, label="95% CI excludes zero (significant)"),
        ]
        ax.legend(handles=legend_handles, frameon=False, fontsize=8, loc="upper left",
                 bbox_to_anchor=(0.0, -0.28))
        ax.invert_yaxis()
        _style(ax)
        save(fig, "fig12_paired_significance.png")

    return saved


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    t0 = time.time()
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)

    speeds = _load_speeds()
    print("=" * 92)
    print("Adaptive-GWG evaluation")
    print("=" * 92)
    print(f"Dataset      : {DATA_PATH} -- {len(speeds):,} real NYC TLC trip speeds, "
          f"mean {speeds.mean():.2f} mph, sd {speeds.std():.2f} mph")
    print(f"Service area : {GRID_SIZE}x{GRID_SIZE} cells of {REGION_SIZE:.0f} m "
          f"({AREA_M:.0f} m x {AREA_M:.0f} m)")
    print(f"Radio range  : {COMM_RANGE_M:.0f} m   Round: {ROUND_DURATION_S*1000:.0f} ms")
    print(f"Rounds       : {MAX_ROUNDS}   Trials: {TRIALS}   Fleet sizes: {NODE_COUNTS}")
    print(f"Mobility     : {'on' if MOBILITY_ENABLED else 'off'}   "
          f"Churn: {CHURN_RATE}   Seed: {RANDOM_SEED}\n")

    # Sub-sample the speed pool once; 12.8M draws are unnecessary and slow.
    pool = np.random.default_rng(RANDOM_SEED).choice(speeds, 200_000, replace=False)

    print(">>> Main experiment", flush=True)
    main_results = run_main_experiment(pool)
    churn_results = run_churn_sweep(pool)
    mobility_results = run_mobility_sweep(pool)
    sensitivity_results = run_threshold_sensitivity(pool)
    refresh_results = run_refresh_sweep(pool)
    restart_results = run_restart_sweep(pool)
    av = compute_av_readiness(main_results)
    road_network = _load_road_network()
    road_mobility_results = run_road_mobility_comparison(pool, road_network)
    ablation_significance = compute_ablation_significance(main_results)
    road_ablation_significance = compute_ablation_significance(road_mobility_results)

    print_main_table(main_results)
    print_attribution(main_results)
    print_road_mobility_comparison(main_results, road_mobility_results)
    print_av_readiness(av)
    print_amdahl_analysis()

    print("\n>>> Figures", flush=True)
    make_figures(main_results, churn_results, mobility_results, sensitivity_results,
                 av, restart_results, road_mobility=road_mobility_results,
                 ablation_significance=ablation_significance,
                 road_ablation_significance=road_ablation_significance)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    payload = {
        "config": {
            "seed": RANDOM_SEED, "grid_size": GRID_SIZE, "region_size_m": REGION_SIZE,
            "comm_range_m": COMM_RANGE_M, "round_duration_s": ROUND_DURATION_S,
            "max_rounds": MAX_ROUNDS, "trials": TRIALS, "node_counts": NODE_COUNTS,
            "adaptive_min": ADAPTIVE_MIN_REGION_NODES,
            "adaptive_max": ADAPTIVE_MAX_REGION_NODES,
            "adaptive_refresh_rounds": ADAPTIVE_REFRESH_ROUNDS,
            "restart_interval": RESTART_INTERVAL,
            "msg_size_bytes": MSG_SIZE_BYTES, "control_msg_bytes": CONTROL_MSG_BYTES,
            "dataset_samples": int(len(speeds)),
            "dataset_mean_mph": float(speeds.mean()),
            "dataset_std_mph": float(speeds.std()),
            "road_mobility_node_counts": ROAD_MOBILITY_NODE_COUNTS,
            "road_mobility_trials": ROAD_MOBILITY_TRIALS,
            "road_network_nodes": road_network.n_nodes,
            "road_network_edges": len(road_network.edges),
        },
        "main": {str(k): v for k, v in main_results.items()},
        "churn": {str(k): v for k, v in churn_results.items()},
        "mobility": mobility_results,
        "threshold_sensitivity": sensitivity_results,
        "refresh_sweep": refresh_results,
        "restart_sweep": restart_results,
        "road_mobility": {str(k): v for k, v in road_mobility_results.items()},
        "av_readiness": {str(k): {p: {str(b): d for b, d in row.items()}
                                  for p, row in v.items()} for k, v in av.items()},
        # Paired (same-trial) significance tests backing Section VI-B/VI-J's
        # "no measurable difference" / "measurable liability" claims -- see
        # compute_ablation_significance and paired_diff_ci95.
        "ablation_significance": {str(k): v for k, v in ablation_significance.items()},
        "road_ablation_significance": {str(k): v for k, v in road_ablation_significance.items()},
    }
    path = os.path.join(RESULTS_DIR, "results.json")
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=2)
    print(f"\nWrote {path} -- every number cited in the paper is in this file.")
    print(f"Done in {time.time() - t0:.1f}s")
    return payload


if __name__ == "__main__":
    main()
