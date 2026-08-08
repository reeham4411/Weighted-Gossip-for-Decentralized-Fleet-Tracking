> ## ⚠️ Superseded — describes the v1 design and results
>
> This document explains the **original** protocol design and the results produced by
> `src/legacy/gwg_simulation_v1.py`. Those results did not survive audit and have been
> withdrawn; see the "A correction to an earlier version of this work" section of the
> root [`README.md`](../README.md).
>
> Specifically, claims in this document that no longer hold: that the exchange
> implements push-sum (it was symmetric, so every weight stayed at 1.0); that
> Adaptive GWG's per-region MAPE advantage of 34–96% is attributable to adaptive
> region management (it was measured against a confounded baseline and each protocol
> was scored against its own partition); and that vehicles are mobile (v1 never moved
> one). Function and figure names here refer to v1 and no longer exist in `src/`.
>
> It is kept because Sections 1–5 and 9 — the problem framing, the data pipeline, and
> the mathematics of gossip averaging — remain accurate and useful background. For
> current results see [`paper/RESULTS.md`](../paper/RESULTS.md) and
> [`paper/adaptive_gwg_paper.md`](../paper/adaptive_gwg_paper.md).

---

# Geo-Weighted Gossip (GWG) with Adaptive Region Management

### Parallel & Distributed Computing | Assignment 2 + Assignment 3 C-6 Extension

**Team: Fatima Ali (470708) · Asma Imran (481920) · Adeena Reeham (480941)**

---

## Table of Contents

1. [The Problem — In Plain English](#1-the-problem--in-plain-english)
2. [Why This Is a Distributed Systems Problem](#2-why-this-is-a-distributed-systems-problem)
3. [What Existing Research Says and Where It Falls Short](#3-what-existing-research-says-and-where-it-falls-short)
4. [Our Solution — Geo-Weighted Gossip](#4-our-solution--geo-weighted-gossip)
5. [How the Data Works](#5-how-the-data-works)
6. [How the Code Works — Every Part Explained](#6-how-the-code-works--every-part-explained)
7. [What the Outputs Mean](#7-what-the-outputs-mean)
8. [What the Visualizations Show](#8-what-the-visualizations-show)
9. [The Math — Explained Simply](#9-the-math--explained-simply)
10. [Bugs Found and Fixed](#10-bugs-found-and-fixed)
11. [The Document (Assignment 2 Report) — What Each Section Does](#11-the-document-assignment-2-report--what-each-section-does)
12. [What Comes Next — Assignment 3](#12-what-comes-next--assignment-3)
13. [Glossary — Every Term Defined](#13-glossary--every-term-defined)

---

## 1. The Problem — In Plain English

Imagine you are Uber, Careem, or any logistics company. You have **thousands of vehicles** spread across a city. You need to know, right now, what the average speed of vehicles is in each neighbourhood — so you can warn drivers about congestion, reroute dynamically, or dispatch vehicles efficiently.

The obvious solution: every car sends its location and speed to a central server every few seconds. The server computes the averages. Done.

**But this breaks in four serious ways:**

| Problem                     | What it means in practice                                                                                                                        |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Single Point of Failure** | If the server crashes, every car in your fleet is blind. No situational awareness at all.                                                        |
| **Bandwidth Bottleneck**    | 5,000 cars all pinging the same server simultaneously = massive congestion at the server's network connection. Packets get lost, latency spikes. |
| **Scalability Ceiling**     | Going from 500 to 5,000 vehicles makes the server 10× busier. The architecture doesn't scale linearly.                                           |
| **Privacy / Jurisdiction**  | Centralising every vehicle's GPS trace in one database creates regulatory headaches across different countries or cities.                        |

**The question this project answers:**

> How can 5,000 vehicles figure out the average speed in each city zone — talking only to each other, with no central server, using as few messages as possible, and still getting an accurate answer?

---

## 2. Why This Is a Distributed Systems Problem

This isn't just a software problem. It has specific properties that make it a **distributed computing** challenge:

### 2.1 No Shared Memory

Each vehicle only knows its own speed and GPS coordinates. There is no global database everyone reads from. Every car is an isolated process.

### 2.2 No Global Clock

In a normal program, you can synchronise steps. Here, thousands of cars are all doing things at slightly different times. There is no "everyone stop and sync" moment. This is called **asynchronous concurrency**.

### 2.3 No Central Coordinator

No one is in charge. No master node. No server. Every vehicle runs the exact same code and makes its own decisions.

### 2.4 Failures Are Normal, Not Exceptional

Cars go through tunnels (network dropout). Cars park (node leaves). Cars re-enter coverage areas (node rejoins). The system must keep working through all of this without any explicit "failure handling" mechanism.

### 2.5 The Core Distributed Challenge

Each node needs to compute a **global aggregate** (regional average speed) using only **local communication** (talking to nearby peers), while tolerating **churn** (nodes leaving and rejoining), **message loss**, and **mobility** (vehicles crossing zone boundaries).

This is precisely the kind of problem that distributed computing was built to solve.

---

## 3. What Existing Research Says and Where It Falls Short

We reviewed 10 peer-reviewed papers. Here's what the landscape looks like and why nothing existing perfectly fits our problem:

### Gossip protocols (Demers 1987, Jelasity 2005)

**What they do:** Nodes randomly pick partners and exchange information. Very robust, self-healing, no central node needed.
**Why they fall short:** The peer selection is completely random. A vehicle in Zone 1 is just as likely to gossip with a vehicle in Zone 100 as with its immediate neighbour. This is wasteful for _regional_ aggregation because cross-zone data is irrelevant to your zone's average.

### Structured overlays (Tapestry/Chord)

**What they do:** Build a carefully maintained network topology so that data routing is deterministic and efficient (O(log N) hops).
**Why they fall short:** Maintaining the overlay requires constant "stabilisation" messages whenever a node joins or leaves. In a fleet of 5,000 moving vehicles (high churn), this maintenance traffic swamps the useful gossip traffic.

### Geographic systems (GHT — Geographic Hash Tables)

**What they do:** Store data at geographic coordinates, enabling spatial queries.
**Why they fall short:** Assume static nodes. The whole design breaks when nodes are constantly moving between zones.

### Hierarchical systems (Astrolabe)

**What they do:** Organise nodes into a hierarchy of zones. Aggregate within each zone, then aggregate between zones.
**Why they fall short:** Requires a predefined hierarchy that must be rebuilt when nodes move between zones. The reconfiguration cost is too high for mobile fleets.

### The Gap

**No existing system combines all four of these simultaneously:**

1. Mobility resilience (works when nodes constantly move)
2. Regional aggregation (computes per-zone averages, not just global averages)
3. Bandwidth efficiency (doesn't waste messages on cross-zone gossip)
4. Self-organisation (no predefined structure, no maintenance overhead)

This gap is what our project fills.

---

## 4. Our Solution — Geo-Weighted Gossip

### The Core Idea

Change one thing about standard gossip: **how a vehicle picks its gossip partner.**

Standard gossip: pick any vehicle in the fleet with equal probability `1/N`.

Our protocol: pick vehicle `j` with probability proportional to `1/distance(i, j)`.

That's it. One formula change. Everything else stays the same.

### Why This Works

Think about what you're trying to compute: the average speed **in your zone**. The vehicles most relevant to that computation are the ones **in the same zone as you**, which are physically nearby. By preferring nearby partners, you concentrate gossip communication where it's actually useful.

The selection is a **soft bias**, not a hard wall. You still occasionally talk to vehicles far away (with low probability). This is intentional — it lets global information propagate across zones over time, so you don't end up with isolated clusters that never exchange data.

### The Formal Rule

```
P(vehicle i selects vehicle j) = (1/dist(i,j)) / SUM over all k of (1/dist(i,k))
```

Where:

- `dist(i,j)` = Euclidean distance between the two vehicles in metres
- The sum in the denominator normalises probabilities so they add up to 1
- A tiny `epsilon = 1.0 metre` is added inside the division to prevent division-by-zero if two vehicles are at exactly the same GPS coordinates

### The Novel Contribution

Three things combined that have never been combined before in vehicular fleet tracking:

1. **Inverse-distance weighted peer selection** — embedded directly into the gossip layer, no separate topology needed
2. **Push-sum aggregation** — guarantees mathematical correctness (not just an approximation)
3. **Adaptive zone sizing** — zones automatically split when too dense, merge when too sparse (no central coordinator needed)

---

## 4.1 C-6 CREATE Level Extension — Adaptive Geo-Weighted Gossip

The original Geo-Weighted Gossip protocol improved regional aggregation by preferring nearby vehicles during peer selection. However, the original design still assumed that every city region should remain a fixed size regardless of vehicle density.

In real urban traffic systems, vehicle density changes continuously:

- Downtown regions may become extremely dense during rush hour.
- Peripheral regions may become sparse late at night.
- Some regions may temporarily contain very few vehicles.

Using the same fixed region size everywhere creates two problems:

1. Dense regions generate excessive local contention.
2. Sparse regions produce unstable regional averages because too few vehicles participate.

To address this limitation, the final C-6 extension introduces Adaptive Geo-Weighted Gossip (Adaptive-GWG).

Adaptive-GWG dynamically changes the logical aggregation regions during runtime:

- Dense regions are automatically split into smaller subregions.
- Sparse regions are automatically merged with nearby regions.
- Normal-density regions remain unchanged.

This creates a self-organizing aggregation structure that adapts automatically to the current fleet distribution without requiring any central coordinator.

The adaptive mechanism improves:

- regional estimation accuracy,
- local communication efficiency,
- geographic locality of gossip exchanges,

while maintaining:

- the same message format,
- the same push-sum aggregation rule,
- the same message complexity class.

The trade-off is additional region-management overhead caused by periodic region reassignment and adaptive region tracking.

## 5. How the Data Works

### What Data We're Using

**Currently in the simulation:** Synthetic data — generated by the code to model realistic urban traffic patterns.

### How the Synthetic Data Is Generated

```
For each vehicle i:
  1. Place it at a random (x, y) position on a 1000m × 1000m grid
  2. Calculate which grid zone it's in (10×10 grid = 100 zones)
  3. Calculate distance from grid centre
  4. Assign base speed: central zones → 15 km/h (congested)
                        peripheral zones → 45 km/h (fast roads)
  5. Add Gaussian noise: speed += random.gauss(mean=0, std=5)
  6. Clamp to realistic range: 5–70 km/h
```

This produces a speed distribution that looks like real urban traffic: slow in the centre, faster at the edges, with natural variation.

### The Ground Truth

Once vehicles are placed, we compute the **true regional average** for each zone:

```
true_avg[zone] = sum(speeds of all vehicles in zone) / count(vehicles in zone)
```

This is what every vehicle is trying to estimate through gossip. It's the answer we're working toward.

### Real-World Dataset Integration

To improve realism, the final implementation incorporated mobility-inspired traffic distributions based on the NYC Yellow Taxi Trip Records dataset.

The dataset contains:

- pickup coordinates,
- trip distances,
- trip durations,
- timestamps,
- taxi movement behaviour across urban regions.

The final system uses a hybrid approach:

- vehicle positions remain synthetically generated to preserve controlled scalability experiments,
- speed distributions are derived from realistic urban traffic behaviour inspired by NYC taxi movement patterns.

This approach preserves experimental reproducibility while improving the realism of the simulated fleet workload.

The hybrid model better reflects:

- congestion variation,
- dense urban traffic,
- sparse peripheral movement,
- realistic vehicle speed fluctuations.

This improves the credibility of the experimental evaluation compared to purely synthetic random-speed generation.

---

## 6. How the Code Works — Every Part Explained

### File: `gwg_simulation.py`

There is one file. Everything is in it.

---

#### CONFIGURATION block

```python
RANDOM_SEED           = 42      # makes results identical every run
GRID_SIZE             = 10      # 10×10 = 100 zones
REGION_SIZE           = 100.0   # each zone is 100m × 100m
MAX_ROUNDS            = 100     # maximum gossip rounds per experiment
CONVERGENCE_THRESHOLD = 0.05    # a node is "converged" if error < 5%
CONVERGENCE_PCT       = 0.90    # need 90% of nodes converged to declare success
MSG_SIZE_BYTES        = 42      # bytes per gossip message (matches Section 2.3)
TRIALS                = 5       # run each experiment 5 times for reliability
NODE_COUNTS           = [100, 500, 1000]  # test these fleet sizes
NEIGHBOR_CACHE_K      = 30      # consider only 30 nearest peers (performance fix)
```

Why `RANDOM_SEED = 42`? So that every time you run the script you get the exact same random numbers and therefore the exact same results. This is called **reproducibility** — a requirement of the assignment.

---

#### `Vehicle` class

Each vehicle object stores:

- `x, y` — GPS position in metres
- `region_id` — which grid zone it's in, computed as `(int(x/100), int(y/100))`
- `true_speed` — the vehicle's own measured speed (its local data)
- `value` — the push-sum numerator (starts = own speed)
- `weight` — the push-sum denominator (starts = 1.0)
- `estimate` — current best guess of regional average = `value / weight`
- `messages_sent`, `bytes_sent` — for measuring communication cost
- `neighbor_cache` — list of K nearest vehicles (built once, used every round)

---

#### `create_fleet(n_nodes)`

Creates N vehicles. Places them randomly. Assigns realistic speeds. Returns a list of Vehicle objects.

---

#### `build_neighbor_caches(nodes, k=30)`

For every vehicle, sorts all other vehicles by distance and keeps the 30 closest. This is a **performance fix** — instead of computing weights over all N vehicles every single gossip call (which was making N=1000 experiments time out), we precompute the K nearest once and reuse it. This is also realistic: real vehicles only know nearby peers via beacon broadcasts.

---

#### `compute_true_regional_avg(nodes)`

Computes the ground truth average speed per zone. This is what we measure accuracy against. Also returns `region_counts` (how many vehicles are in each zone) — needed to skip single-vehicle zones in MAPE calculations.

---

#### `push_sum_exchange(sender, receiver)`

This is the heart of the protocol. When two vehicles gossip:

```
Step 1: Each vehicle halves its (value, weight)
Step 2: Each vehicle adds the other's half to its own
Step 3: Each vehicle updates its estimate = value / weight
```

In code:

```python
sv = sender.value / 2;    sw = sender.weight / 2
rv = receiver.value / 2;  rw = receiver.weight / 2

sender.value   = sv + rv;  sender.weight   = sw + rw
receiver.value = rv + sv;  receiver.weight = rw + sw

sender.estimate   = sender.value   / sender.weight
receiver.estimate = receiver.value / receiver.weight
```

The key mathematical property: `sum(all values)` across the whole network is **perfectly conserved** through every exchange. It never increases or decreases. As weights redistribute evenly, `value/weight` at every node converges to the true network mean.

---

#### `select_peer_uniform(node, nodes)`

```python
others = [n for n in nodes if n.node_id != node.node_id]
return random.choice(others)
```

Every other vehicle has equal probability `1/(N-1)` of being selected. Simple. This is the baseline.

---

#### `select_peer_geo_weighted(node, nodes)`

```python
candidates = node.neighbor_cache  # K=30 nearest vehicles
weights    = [1.0 / max(node.distance_to(o), 1.0) for o in candidates]
total      = sum(weights)
probs      = [w / total for w in weights]
# weighted random draw
r, cumulative = random.random(), 0
for o, p in zip(candidates, probs):
    cumulative += p
    if r <= cumulative:
        return o
return candidates[-1]
```

Nearby vehicles get high weight. Distant vehicles get low weight. The draw is still random — it's just a biased random, not a deterministic choice.

---

#### `compute_mape(nodes, true_avgs, region_counts)`

MAPE = Mean Absolute Percentage Error.

```
MAPE = average of |estimate - true_avg| / true_avg × 100%
```

This tells us how wrong the fleet's estimates are on average. 0% = perfect. We target < 5%.

**Important fix applied:** Single-vehicle zones are skipped. If a zone has only one vehicle, its estimate is trivially correct (it IS the zone's entire data). Counting it as "converged" inflates the numbers.

---

#### `check_convergence(nodes, true_avgs, region_counts)`

Returns the fraction of nodes (in multi-vehicle zones) whose estimate is within 5% of the true zone average. When this fraction reaches 0.90 (90%), the experiment is considered converged.

---

#### `run_experiment(nodes, select_peer_fn, max_rounds)`

The main loop. Takes any peer selection function as a parameter. Runs up to `max_rounds` rounds. In each round:

1. Every vehicle picks a partner using `select_peer_fn`
2. They do `push_sum_exchange`
3. After all vehicles gossip, measure MAPE and convergence fraction
4. If 90% converged, record the round number and stop early

Returns: convergence round, total messages, average bandwidth, average hop distance, MAPE per round.

---

#### `run_all_experiments()`

Outer loop: for each fleet size in `[100, 500, 1000]`, run `TRIALS=5` repetitions of both protocols. Average the results. Print a comparison table.

**Important fix applied:** Original speeds are saved before trials begin. Each trial restores original speeds and adds fresh noise. Without this fix, noise accumulated across trials and speeds drifted far from realistic values.

---

#### `plot_results(results)`

Generates and saves 5 PNG figures. Each figure compares Uniform (red) vs Geo-Weighted (green).

---

#### `print_amdahl_analysis()`

Prints Amdahl's Law and Gustafson's Law tables. Uses `f = 0.05` as the **serial fraction** (5% of work must be sequential: reading results, coordination). This matches Section 5.1 of the report.

---

### File: `gwg_visualize.py`

Separate script for generating visual explanations of what is happening at the node level. Run independently with the same dependencies.

---

## 7. What the Outputs Mean

### Terminal Output

When you run `python gwg_simulation_fixed.py` you see something like:

```
>>> N = 100 nodes  (5 trials each protocol)
  Uniform   conv=72.0±4.1  msgs=14400  bw=0.59KB  hop=540.2m
  GeoWeigh  conv=43.0±3.2  msgs=8600   bw=0.36KB  hop=360.8m
  Improvement: convergence +40.3%  hop -33.2%  msgs -40.3%
```

Reading this line by line:

| Field                             | What it means                                                                                                                                |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `conv=72.0±4.1`                   | On average, took 72 rounds to reach 90% convergence. The ±4.1 is the standard deviation across 5 trials — shows how consistent the result is |
| `msgs=14400`                      | Total gossip messages sent across the whole fleet until convergence                                                                          |
| `bw=0.59KB`                       | Average data sent per vehicle (total bytes / N vehicles / 1024)                                                                              |
| `hop=540.2m`                      | Average physical distance between gossip partners in metres                                                                                  |
| `Improvement: convergence +40.3%` | GWG converges 40% faster than Uniform                                                                                                        |
| `hop -33.2%`                      | GWG partners are 33% closer to each other on average                                                                                         |
| `msgs -40.3%`                     | GWG sends 40% fewer total messages (because it converges faster)                                                                             |

---

### Figure 1 — MAPE Convergence Curves

**What you're looking at:** Three side-by-side plots (one per fleet size). X-axis = gossip round number (1 to 100). Y-axis = average estimation error across the fleet (%). Red line = Uniform, Green line = GWG. Dashed grey line = 5% target.

**What it proves:** GWG's green line crosses the 5% threshold earlier than the red line in every subplot. The gap between the two lines in the first 20 rounds shows how much faster GWG reduces error early on, when local gossip dominates.

---

### Figure 2 — Convergence Rounds Bar Chart

**What you're looking at:** Grouped bar chart. For each fleet size, two bars — Uniform (red) and GWG (green). Height = number of rounds until 90% convergence. Error bars = standard deviation across trials. Percentage annotation above = improvement.

**What it proves:** GWG is consistently faster across all fleet sizes. The improvement being stable (~40%) across N=100, 500, 1000 suggests this is a fundamental protocol advantage, not a fluke.

---

### Figure 3 — Geographic Hop Distance

**What you're looking at:** Grouped bar chart. For each fleet size, Uniform vs GWG average hop distance in metres.

**What it proves:** This is the **direct measurement of the core mechanism**. GWG's bars are shorter because the geo-weighting is actually doing its job — vehicles are preferring nearby partners. If this figure showed no difference, the whole protocol would be a failure.

---

### Figure 4 — Per-Node Bandwidth

**What you're looking at:** Same structure as Figure 3 but measuring total kilobytes sent per vehicle.

**What it proves:** GWG uses less bandwidth per vehicle. Since both protocols send the same 42-byte message per gossip exchange, the bandwidth difference comes entirely from GWG converging in fewer rounds (fewer rounds = fewer total exchanges per node).

---

### Figure 5 — Message Complexity

**What you're looking at:** Line chart. X-axis = fleet size. Y-axis = total messages across the whole fleet until convergence.

**What it proves:** Both lines grow with N (more vehicles = more total messages, obviously). But GWG's line grows more slowly. The gap between lines widens as N increases, suggesting GWG's advantage scales well.

---

## 8. What the Visualizations Show

### File: `gwg_visualize.py` — Run separately

```
python gwg_visualize.py
```

Generates 4 images using a small fleet of 80 vehicles so the plots are readable.

---

### viz1_node_map.png — The Fleet Map

Every vehicle plotted as a dot. Each colour = one geographic zone. The star (★) marks the focal vehicle (Vehicle 0 by default). The grey grid lines show zone boundaries.

**What to notice:** Vehicles cluster unevenly — some zones are dense, others sparse. This is realistic and intentional.

---

### viz2_selection_prob.png — Who Does Vehicle 0 Talk To?

Two side-by-side maps. Both show all vehicles. But the dot size represents the probability that Vehicle 0 picks that vehicle as a gossip partner.

**Left (Uniform):** All dots are the same size — every vehicle has equal probability `1/79`.

**Right (Geo-Weighted):** Vehicles close to the star have large dots. Vehicles far away have tiny dots. The distance rings at 100m, 300m, 600m show how the probability falls off with distance.

**What to notice:** In the Geo-Weighted map, the vehicles right next to Vehicle 0 (same zone) are dramatically more likely to be chosen. Vehicles across the city are visible but tiny. This is the geo-weighting in action.

---

### viz3_round_snapshots.png — How Accuracy Spreads

An 8-panel grid: 4 rounds (0, 5, 10, 20) × 2 protocols. Each panel shows the fleet with vehicles coloured by their estimation error — **green = accurate, red = inaccurate**.

**Round 0:** Everything is red. Every vehicle only knows its own speed.

**Round 5:** Some green appears, especially in GWG (right column). GWG vehicles near each other are already sharing accurate local data.

**Round 10:** GWG shows large patches of green. Uniform is still more mixed.

**Round 20:** Both are mostly green, but GWG is cleaner.

**What to notice:** In GWG, green tends to appear in local clusters first, then spread. In Uniform, green appears more uniformly but more slowly. This is the local-first convergence behaviour that makes GWG faster.

---

### viz4_accuracy_vs_distance.png — Accuracy vs Distance from Vehicle 0

Scatter plot. X-axis = distance from Vehicle 0 in metres. Y-axis = estimation error at round 15.

**Red dots** = Uniform Gossip vehicles. **Green dots** = GWG vehicles.

The dashed lines are trend lines fitted to each set of dots.

**What to notice:** GWG's green trend line should be lower on the left side of the plot (nearby vehicles) than Uniform's red line. This means nearby vehicles under GWG have already converged to accurate estimates by round 15, while under Uniform they haven't — because GWG concentrated local gossip early.

---

## 9. The Math — Explained Simply

### Push-Sum Convergence

Think of 10 friends who each hold a bag of money. Friend 1 holds £30 (representing a vehicle going 30 km/h). Friend 2 holds £45. And so on. They also each hold a "weight" which starts at 1.

Goal: figure out the average without one person collecting all the bags.

**The exchange rule:** When two friends meet, each splits their bag and weight in half and gives one half to the other.

**The magic:** No matter how many exchanges happen, the total money across all 10 friends never changes. It stays at £30 + £45 + ... (the sum of all speeds). And the total weight across all friends stays at 10 (N). So eventually, every friend's bag-total ÷ their weight equals the true mean. It's mathematically guaranteed.

**Formally:** After t rounds, error ≤ C × λ^t where λ is the second-largest eigenvalue of the communication matrix. For GWG (regional gossip, region size R), λ ≈ 1 − 1/R which is smaller than Uniform's λ ≈ 1 − 1/N since R << N. Smaller λ means faster exponential decay of error.

---

### Amdahl's Law

**The question it answers:** If I parallelise this protocol across p processors/vehicles, how much faster does it get?

**The formula:** `S(p) = 1 / (f + (1−f)/p)`

Where:

- `f` = fraction of work that MUST be sequential (cannot be parallelised)
- `p` = number of parallel processors
- `S(p)` = speedup factor

For GWG, f = 0.05 (5% sequential: reading results, round coordination). So 95% of the work (the gossip rounds themselves) is parallelisable.

**What the table shows:** With 8 processors, you get 6.4× speedup (not 8× because 5% is still serial). With 64 processors, you get ~20× (not 64× — the 5% serial work becomes the bottleneck). This plateauing effect is called **Amdahl's ceiling**.

---

### Gustafson's Law

**The question it answers:** As the fleet grows, does the protocol scale?

**The formula:** `Scaled Speedup = p − f × (p − 1)`

Gustafson says: as you add more vehicles, you also have more work to do (more zones to track). So the workload grows with the system. For GWG, with 1000 vehicles and f=0.05: Scaled Speedup = 1000 − 0.05 × 999 ≈ 950×. Meaning: 1000 vehicles can process roughly 950 zones' worth of data simultaneously. This near-linear scaling is why GWG is suitable for large fleets.

---

### MAPE (Mean Absolute Percentage Error)

```
MAPE = (1/n) × Σ |estimate_i − true_avg| / true_avg × 100
```

It's just the average percentage error across all vehicles. If every vehicle's estimate is exactly correct, MAPE = 0%. If every vehicle's estimate is off by 5%, MAPE = 5%. We declare success when MAPE drops below 5%.

---

## 10. Bugs Found and Fixed

These are real bugs in the original simulation code, all corrected in `gwg_simulation_fixed.py`.

---

### Bug 1 — Trial Speed Drift ✗ → ✓

**What the original did:** Added random noise to `node.true_speed` each trial without resetting it first.

**Effect:** By trial 5, each vehicle's speed had drifted away from its initial value by up to ±10 km/h. Trial 1 and Trial 5 were measuring fundamentally different fleets. Results were not comparable across trials.

**Fix:** Save original speeds before trials begin. At the start of each trial, restore original speed then add fresh noise.

---

### Bug 2 — Double-Counted Messages ✗ → ✓

**What the original did:** `push_sum_exchange()` incremented `messages_sent` on BOTH the sender and the receiver. Then `run_experiment()` summed ALL nodes' message counts.

**Effect:** Every single exchange was counted twice. A 14,400-message result was actually 7,200 real exchanges. All bandwidth and message complexity numbers were 2× too high.

**Fix:** Only the sender increments its counter. The experiment tracks total exchanges directly.

---

### Bug 3 — Convergence Never-Detected Masked ✗ → ✓

**What the original did:** Set `convergence_round = MAX_ROUNDS` as a default, then checked `if convergence_round == MAX_ROUNDS` to detect non-convergence. But if the protocol actually needed exactly MAX_ROUNDS to converge, this flag would fire incorrectly.

**Fix:** Use `convergence_round = None` as the default. Check `if convergence_round is not None` separately from whether the experiment hit the round limit.

---

### Bug 4 — Single-Vehicle Zones Inflating Accuracy ✗ → ✓

**What the original did:** Included single-vehicle zones in MAPE and convergence calculations.

**Effect:** A zone with one vehicle has a trivially "correct" estimate — the vehicle IS the zone's average. Its error is always 0%. Including these inflates the convergence fraction and deflates MAPE artificially. With N=100 and 100 zones, many zones have exactly one vehicle, so this effect was significant.

**Fix:** Skip nodes in single-vehicle zones from both MAPE and convergence checks.

---

### Bug 5 — Wrong Message Size ✗ → ✓

**What the original did:** Used `MSG_SIZE_BYTES = 64`.

**Effect:** The report's own Section 2.3 specifies 42 bytes. Bandwidth numbers in the document were inconsistent with the code.

**Fix:** Changed to 42 bytes to match the documented message format.

---

### Bug 6 — Amdahl f Convention Contradiction ✗ → ✓

**What the original did:** Code used `f = 0.85` as the _parallel_ fraction. Report used `f = 0.05` as the _serial_ fraction. Both are used in the Amdahl formula `S = 1/((1−f) + f/p)` — but with opposite conventions.

**Effect:** The code's Amdahl table and the report's Amdahl table produce completely different numbers, and a professor cross-checking them would notice immediately.

**Fix:** Code now uses `f = serial fraction = 0.05` to match the report's convention and formula.

---

### Bug 7 — O(N) Selection Cost (Performance) ✗ → ✓

**What the original did:** `select_peer_geo_weighted()` scanned all N vehicles to build weights on every single gossip call.

**Effect:** For N=1000, 100 rounds, 5 trials = 1,000,000 full-fleet distance scans. This is why the simulation timed out. It's also unrealistic — real vehicles can't "see" the whole fleet.

**Fix:** Pre-build a `neighbor_cache` of the K=30 nearest vehicles per node at experiment start. Selection is now O(30) instead of O(N). Also more realistic — vehicles only know nearby peers via beacon broadcasts.

---

## 11. The Document (Assignment 2 Report) — What Each Section Does

### Cover Page

Names, roll numbers, date. No marks but sets professionalism.

### Table of Contents

Auto-generated. Right-click in Word → Update Field to get correct page numbers.

### Division of Work

- Asma: Architecture, Communication, Consistency, Performance Modeling, Code
- Fatima: Failure Model, Scalability, Risk Analysis, Literature Linkage
- Adeena: Implementation Plan, Novel Contribution, Experimental Framework, Formatting
  All three reviewed everything. Equal 33% each.

---

### Section 1 — System Architecture

**What it covers:** How the system is structured. Three layers (Physical: vehicles with GPS; Protocol: the gossip engine; Application: routing/dispatch using the results). The geographic 10×10 grid. The node state machine (IDLE → SELECT PEER → PUSH VALUE → WAIT → RECEIVE → UPDATE ESTIMATE → back to IDLE).

**Why this section exists:** The assignment requires a system architecture diagram. This shows the examiner you understand how all pieces fit together, not just the algorithm in isolation.

---

### Section 2 — Communication Model

**What it covers:** The gossip protocol type (push-pull), the geo-weighted peer selection formula, the exact 42-byte message format, the push-sum update rule, and how vehicles discover each other via beacon broadcasts.

**Why this section exists:** The assignment requires a communication model. This proves you know how data moves between nodes — not just that it does.

---

### Section 3 — Consistency Model

**What it covers:** We use Eventual Consistency (AP system in CAP theorem terms). Not strong consistency. Nodes don't all agree instantly — they converge to within ±5% over time. This is justified because: (a) network partitions are frequent in vehicular networks, (b) approximate agreement is sufficient for routing decisions.

**Why this section exists:** The assignment requires a consistency model. This shows you understand the CAP theorem and why a real-world distributed system has to make trade-offs.

---

### Section 4 — Failure Model

**What it covers:** Five failure types: crash failure, node churn, region migration, stale data, message loss. How GWG handles each without any explicit recovery mechanism.

**Why this section exists:** The assignment requires a failure model. In distributed systems, failure handling is not optional. A system that only works when everything is perfect is not a distributed system.

---

### Section 5 — Performance Modeling

**What it covers:** Amdahl's Law (what speedup is possible with more processors), Gustafson's Law (how throughput scales with more vehicles), message complexity table (GWG vs Uniform), spectral gap convergence formula (why GWG converges faster, mathematically). Plus the simulation result tables and all 6 charts.

**Why this section exists:** C-5 analytical depth requirement. You must demonstrate you can model system performance mathematically, not just run experiments.

---

### Section 6 — Scalability Assumptions

**What it covers:** Five explicit assumptions (S1–S5) about network connectivity, zone density, churn rate, message delivery rate, clock drift. A table of scalability limits and bottlenecks. The adaptive zone sizing novel feature.

**Why this section exists:** The assignment requires scalability assumptions. Honest acknowledgment of what your system assumes is a sign of rigour. Hiding assumptions is a red flag for examiners.

---

### Section 7 — Implementation Plan

**What it covers:** The single file `gwg_simulation_fixed.py`, how it's structured internally (14 labelled sections), the real peer selection code, the real push-sum exchange code, the real experiment runner, expected terminal output.

**Why this section exists:** The assignment requires an implementation plan. This section was corrected to reference only the real code — no fake multi-file structure.

---

### Section 8 — Risk Analysis

**What it covers:** Five technical risks (staleness, zone oscillation, Python overhead, data gaps, weight drift) and three research risks (improvement less than claimed, sparse zone isolation, overhead cancels savings). Each with likelihood, impact, and mitigation.

**Why this section exists:** C-5 level requires you to anticipate what can go wrong, not just describe what should work.

---

### Section 9 — Novel Contribution and C-6 Justification

**What it covers:** The three-part novelty claim. The comparison table showing GWG is the only system in the literature that satisfies all four properties (geo-aware, no central node, mathematical correctness, adaptive zones).

**Why this section exists:** C-6 is the highest grade band — "Create Level." You must justify that your work is genuinely new, not just an implementation of existing ideas.

---

### Section 10 — Conclusion

Summary of what was achieved. One paragraph. Points to Assignment 3 for experimental validation.

### References

All 10 papers from Assignment 1 literature review.

---

## 12. What Comes Next — Assignment 3

Assignment 3 is the Final Presentation and Demonstration. You need:

### What you need to do

**1. Actually run the simulation to completion**
`gwg_simulation_fixed.py` is ready. Run it on a machine with enough time (it can take 10–20 minutes for all configurations). The figures will be generated automatically.

**2. Load the real NYC Taxi dataset**
Download from nyc.gov/tlc (2013 yellow taxi data). Parse it:

```python
import pandas as pd
df = pd.read_csv('yellow_tripdata_2013-01.csv')
df['speed'] = df['trip_distance'] / (df['trip_time_in_secs'] / 3600)  # km/h
df = df[(df['speed'] > 2) & (df['speed'] < 100)]  # remove outliers
# use pickup_longitude, pickup_latitude as x, y
```

**3. Run failure scenarios**
At round 20, mark 10%, 20%, 30% of vehicles as offline. Measure how many extra rounds the survivors need to reconverge. GWG should recover faster than Uniform because local clusters still function independently.

**4. Sensitivity analysis**
Vary: message drop rate (0%, 5%, 10%, 20%), grid granularity (5×5 vs 10×10 vs 20×20), gossip round frequency.

**5. Prepare the presentation**
10–12 minutes. Show the figures live. Be able to explain every number.

---

## 13. Glossary — Every Term Defined

| Term                     | What it means                                                                                                                                    |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Gossip Protocol**      | A communication pattern where nodes repeatedly share information with randomly selected peers, like gossip spreading through a social group      |
| **Push-Sum**             | A specific gossip algorithm that mathematically guarantees convergence to the true average by conserving the total sum across all exchanges      |
| **Peer**                 | Another vehicle/node that a given vehicle chooses to gossip with                                                                                 |
| **Round**                | One iteration where every node in the fleet performs one gossip exchange                                                                         |
| **Convergence**          | The point where estimates are close enough to the true value (within 5%) — the gossip has "worked"                                               |
| **MAPE**                 | Mean Absolute Percentage Error — average % gap between estimated and true regional speed                                                         |
| **Regional Average**     | The mean speed of all vehicles in one geographic grid zone                                                                                       |
| **Geo-Weighted**         | Selecting gossip partners with probability inversely proportional to distance                                                                    |
| **Push-Sum State**       | The (value, weight) pair each node maintains. Estimate = value/weight                                                                            |
| **Eventual Consistency** | A guarantee that all nodes will eventually agree, but not necessarily right now                                                                  |
| **CAP Theorem**          | Theorem that says a distributed system can only guarantee 2 of: Consistency, Availability, Partition Tolerance. GWG chooses A and P              |
| **Churn**                | Nodes constantly joining and leaving the network (vehicles parking, tunnels, etc.)                                                               |
| **Amdahl's Law**         | Formula giving the maximum speedup from parallelisation given a fixed serial fraction                                                            |
| **Gustafson's Law**      | Formula giving scaled speedup when workload grows with system size                                                                               |
| **Spectral Gap**         | A mathematical property of the gossip communication matrix that determines how fast gossip converges. Larger gap = faster convergence            |
| **Neighbor Cache**       | Pre-computed list of K nearest vehicles per node, used to speed up geo-weighted selection from O(N) to O(K)                                      |
| **Hop Distance**         | Physical distance in metres between two vehicles in a gossip exchange                                                                            |
| **Message Complexity**   | Total number of messages sent across the whole fleet until convergence                                                                           |
| **Bandwidth**            | Total data (bytes/KB) sent per vehicle during the aggregation process                                                                            |
| **Fault Tolerance**      | The ability of the system to keep working correctly when some components fail                                                                    |
| **Distributed System**   | A system where multiple autonomous computers coordinate to achieve a shared goal, without shared memory or a central controller                  |
| **Asynchronous**         | Events happen independently, without waiting for each other or a global clock                                                                    |
| **Region Migration**     | A vehicle crossing from one grid zone to another while driving                                                                                   |
| **Adaptive Zone Sizing** | Zones automatically split when too dense or merge when too sparse, without any central coordinator                                               |
| **C-6 Level**            | The highest level in Bloom's taxonomy — "Create." Requires a genuinely novel system-level contribution, not just implementation of existing work |
| **Reproducibility**      | The ability to run the experiment again and get the same results. Achieved here via `RANDOM_SEED = 42`                                           |
| **Baseline**             | The comparison point — Uniform Random Gossip. GWG is measured against this to prove improvement                                                  |

# 12. Final Experimental Results and C-6 Evaluation

The final implementation compared three protocols:

1. Uniform Random Gossip
2. Fixed Geo-Weighted Gossip (GWG)
3. Adaptive Geo-Weighted Gossip (Adaptive-GWG)

Experiments were performed using fleet sizes:

- N = 100
- N = 500
- N = 1000

The following metrics were evaluated:

- convergence rounds,
- global MAPE,
- per-region MAPE,
- geographic hop distance,
- bandwidth usage,
- message complexity,
- adaptive-region overhead.

## Key Findings

### 1. Adaptive-GWG significantly reduced geographic hop distance

Compared to Fixed GWG, Adaptive-GWG consistently reduced average hop distance by approximately 30–43%.

This indicates that adaptive regions successfully concentrated communication within geographically relevant neighborhoods.

### 2. Adaptive-GWG improved regional estimation accuracy

Per-region MAPE improved substantially:

- approximately 48% improvement for N=500,
- approximately 63% improvement for N=100,
- and near-perfect convergence in dense N=1000 scenarios.

This demonstrates that adaptive region management improves local aggregation quality.

### 3. Communication overhead remained stable

Despite the adaptive behavior:

- message size remained constant,
- total message count remained unchanged,
- bandwidth per node remained approximately equal across protocols.

This shows that the improvement comes from smarter organization of communication rather than increased communication volume.

### 4. Trade-off Analysis

Adaptive-GWG introduces additional region-management overhead:

- regions may split or merge dynamically,
- node region labels may change periodically,
- adaptive-region bookkeeping adds computational complexity.

However, the communication benefits outweighed the management overhead in all evaluated fleet sizes.

## Overall Conclusion

The final results demonstrate that Adaptive Geo-Weighted Gossip satisfies the C-6 CREATE-level requirements by:

- proposing a novel system-level improvement,
- implementing the improvement,
- comparing against baselines,
- demonstrating measurable improvement,
- and analyzing the resulting trade-offs.

---

_This document covers the complete GWG project from problem to solution to code to output to critique. All bugs listed in Section 10 are corrected in `gwg_simulation_fixed.py`. The visualization script `gwg_visualize.py` runs independently and requires no modification._

_Last updated: April 2026_
