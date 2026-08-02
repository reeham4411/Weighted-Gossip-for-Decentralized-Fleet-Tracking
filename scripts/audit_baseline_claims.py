"""
Empirical audit of src/gwg_simulation.py as committed.
Each check prints EVIDENCE, not an opinion.
Run from repo root:  python3 scratchpad/audit_current.py
"""
import sys, os, math, random
sys.path.insert(0, "src/legacy")

import numpy as np
import gwg_simulation_v1 as G

print("=" * 78)
print("AUDIT 1: does push_sum_exchange actually implement push-sum?")
print("=" * 78)
a = G.Vehicle(0, 0.0, 0.0, 30.0)
b = G.Vehicle(1, 10.0, 0.0, 10.0)
print(f"  before: a=(v={a.value:.3f}, w={a.weight:.3f})  b=(v={b.value:.3f}, w={b.weight:.3f})")
G.push_sum_exchange(a, b)
print(f"  after : a=(v={a.value:.3f}, w={a.weight:.3f})  b=(v={b.value:.3f}, w={b.weight:.3f})")
print(f"  -> weights equal after exchange? {a.weight == b.weight == 1.0}")
print(f"  -> a.value == b.value (symmetric, not directional)? {abs(a.value-b.value) < 1e-12}")

# run a real fleet and check the weight invariant across a whole experiment
random.seed(42); np.random.seed(42)
nodes = G.create_fleet(200)
G.build_peer_caches(nodes)
G.assign_fixed_regions(nodes)
for n in nodes:
    n.reset()
for r in range(20):
    for n in nodes:
        G.push_sum_exchange(n, G.select_peer_geo_weighted(n, nodes))
weights = np.array([n.weight for n in nodes])
est_eq_val = all(abs(n.estimate - n.value) < 1e-9 for n in nodes)
print(f"  -> after 20 rounds on N=200: weight min={weights.min():.6f} max={weights.max():.6f}")
print(f"  -> estimate == value for every node? {est_eq_val}")
print("  VERDICT: weights are invariant at 1.0, so the (value,weight) pair carries")
print("           no information; this is symmetric pairwise gossip averaging")
print("           (Boyd et al.), NOT Kempe et al. directional push-sum.")

print()
print("=" * 78)
print("AUDIT 2: is mobility modelled at all?")
print("=" * 78)
random.seed(42); np.random.seed(42)
nodes = G.create_fleet(100)
pos_before = [(n.x, n.y) for n in nodes]
G.build_peer_caches(nodes)
G.run_experiment(nodes, G.select_peer_adaptive_geo_weighted, max_rounds=30, adaptive=True)
pos_after = [(n.x, n.y) for n in nodes]
moved = sum(1 for p, q in zip(pos_before, pos_after) if p != q)
print(f"  nodes whose (x,y) changed over a 30-round run: {moved} / {len(nodes)}")
print(f"  'x' assigned anywhere outside create_fleet? "
      f"{'no' if open('src/legacy/gwg_simulation_v1.py').read().count('.x =') == 1 else 'yes'}")
print("  VERDICT: positions are frozen. The paper's title claims 'Highly Mobile")
print("           Vehicular Networks'; the simulated network is static.")

print()
print("=" * 78)
print("AUDIT 3: are message/bandwidth counts a *result* or an identity?")
print("=" * 78)
random.seed(42); np.random.seed(42)
nodes = G.create_fleet(150)
G.build_peer_caches(nodes)
for label, sel, ad in [("uniform", G.select_peer_uniform, False),
                       ("fixed  ", G.select_peer_geo_weighted, False),
                       ("adaptive", G.select_peer_adaptive_geo_weighted, True)]:
    out = G.run_experiment(nodes, sel, max_rounds=25, adaptive=ad)
    print(f"  {label}: total_messages={out[1]}  avg_bw_bytes={out[2]:.1f}  "
          f"(N*rounds = {150*25})")
print("  VERDICT: every protocol performs exactly one exchange per node per round,")
print("           so message count and bandwidth are identical BY CONSTRUCTION.")
print("           Reporting 'comparable bandwidth' as a finding is not evidence.")
print("           Adaptive region management sends no control messages at all —")
print("           its coordination cost is invisible to the bandwidth metric.")

print()
print("=" * 78)
print("AUDIT 4: is per-region MAPE comparable across protocols?")
print("=" * 78)
random.seed(42); np.random.seed(42)
nodes = G.create_fleet(500)
G.build_peer_caches(nodes)
G.assign_fixed_regions(nodes)
fixed_parts = len(set(n.region_id for n in nodes))
_, fixed_counts = G.compute_true_regional_avg(nodes)
G.adaptive_region_assignment(nodes)
adap_parts = len(set(n.region_id for n in nodes))
_, adap_counts = G.compute_true_regional_avg(nodes)
print(f"  fixed grid   : {fixed_parts} regions, sizes min={min(fixed_counts.values())} "
      f"max={max(fixed_counts.values())}")
print(f"  adaptive     : {adap_parts} regions, sizes min={min(adap_counts.values())} "
      f"max={max(adap_counts.values())}")
print("  VERDICT: each protocol's MAPE is measured against ITS OWN partition of the")
print("           fleet, i.e. a different ground-truth vector. Merging sparse cells")
print("           into larger ones lowers within-region variance, which lowers MAPE")
print("           independently of any protocol improvement. The headline")
print("           'per-region MAPE reduced 34-96%' is confounded by this.")

print()
print("=" * 78)
print("AUDIT 5: does Fixed GWG gossip across region boundaries?")
print("=" * 78)
random.seed(42); np.random.seed(42)
nodes = G.create_fleet(500)
G.build_peer_caches(nodes)
G.assign_fixed_regions(nodes)
cross = tot = 0
for n in nodes:
    for _ in range(50):
        p = G.select_peer_geo_weighted(n, nodes)
        tot += 1
        cross += (p.region_id != n.region_id)
print(f"  Fixed GWG: {cross/tot*100:.1f}% of selected peers are OUTSIDE the sender's region")
cross_a = tot_a = 0
G.adaptive_region_assignment(nodes)
for n in nodes:
    for _ in range(50):
        p = G.select_peer_adaptive_geo_weighted(n, nodes)
        tot_a += 1
        cross_a += (p.region_id != n.region_id)
print(f"  Adaptive : {cross_a/tot_a*100:.1f}% of selected peers are OUTSIDE the sender's region")
print("  VERDICT: Fixed GWG leaks mass across regions on most exchanges, so it")
print("           necessarily drifts to the global mean. Adaptive-GWG confines")
print("           gossip to the region. The measured gap therefore conflates TWO")
print("           independent changes: (a) region-confined peer selection and")
print("           (b) density-driven adapt. No experiment separates them, so the")
print("           paper cannot attribute the gain to its stated contribution.")

print()
print("=" * 78)
print("AUDIT 6: how is a non-converging run reported?")
print("=" * 78)
print(f"  MAX_ROUNDS={G.MAX_ROUNDS}; a run that never converges is recorded as "
      f"{G.MAX_ROUNDS + 1}")
print("  and then averaged with converging runs via np.mean.")
print("  VERDICT: '151 (capped)' is a censored observation. Averaging censored and")
print("           uncensored values produces a number that is not a mean of anything.")
print("           np.std() with TRIALS=3 and ddof=0 also understates the spread, and")
print("           the paper's own Section VI asks for confidence intervals.")
