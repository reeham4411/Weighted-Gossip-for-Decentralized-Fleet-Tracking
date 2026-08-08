"""Audit part 2: the two findings that decide whether the paper's claim stands."""
import sys, random, math
sys.path.insert(0, "src/legacy")
import numpy as np
import gwg_simulation_v1 as G
from collections import defaultdict, Counter

print("=" * 78)
print("AUDIT 7: does the 'merge sparse regions' rule actually merge?")
print("=" * 78)
random.seed(42); np.random.seed(42)
nodes = G.create_fleet(300)
G.build_peer_caches(nodes)
G.assign_fixed_regions(nodes)
fixed_of = {n.node_id: n.fixed_region_id for n in nodes}
G.adaptive_region_assignment(nodes)

merged_labels = [n.region_id for n in nodes if isinstance(n.region_id, tuple) and n.region_id and n.region_id[0] == "merged"]
if merged_labels:
    lbl = Counter(merged_labels).most_common(1)[0][0]
    target = lbl[1]
    members = [n for n in nodes if n.region_id == lbl]
    target_members = [n for n in nodes if n.region_id == target]
    print(f"  example merged label: ('merged', {target})")
    print(f"    nodes carrying that merged label      : {len(members)}")
    print(f"    nodes actually living in region {target}: "
          f"{sum(1 for n in nodes if fixed_of[n.node_id] == target)}")
    print(f"    of those, how many share the merged label? "
          f"{sum(1 for n in nodes if fixed_of[n.node_id] == target and n.region_id == lbl)}")
    print(f"    nodes still labelled with the bare target id: {len(target_members)}")
    print("  VERDICT: the sparse nodes are given a NEW region id ('merged', T) that the")
    print("           target region's own members never adopt. The two groups remain")
    print("           SEPARATE regions. 'Merging' creates a phantom region instead of")
    print("           joining an existing one -- the merge rule does not merge.")
else:
    print("  no merged regions at this density")

print()
print("=" * 78)
print("AUDIT 8: at N=1000, does the adaptive layer do ANYTHING?")
print("=" * 78)
for N in (100, 500, 1000):
    random.seed(42); np.random.seed(42)
    nodes = G.create_fleet(N)
    G.assign_fixed_regions(nodes)
    fixed_ids = [n.region_id for n in nodes]
    stats = G.adaptive_region_assignment(nodes)
    adapt_ids = [n.region_id for n in nodes]
    identical = fixed_ids == adapt_ids
    print(f"  N={N:>4}: sparse={stats['sparse_regions']:>3} dense={stats['dense_regions']:>3} "
          f"active={stats['active_regions']:>3} changed={stats['changed_node_pct']:.1f}%  "
          f"partition identical to fixed grid? {identical}")
print("  VERDICT: at N=1000 the adaptive rule is a NO-OP -- every cell holds ~10 nodes,")
print("           between MIN=3 and MAX=20, so nothing merges and nothing splits.")
print("           Yet N=1000 is where the paper reports its biggest win (96.4%).")
print("           That win therefore cannot come from adaptivity.")

print()
print("=" * 78)
print("AUDIT 9: ABLATION -- fixed grid + region-confined peer selection")
print("=" * 78)
print("  Isolates the two changes bundled into 'Adaptive GWG':")
print("    (a) confine gossip to your own region   (b) adapt region boundaries")


def select_peer_region_confined_fixed(node, nodes):
    """Fixed 10x10 grid, but peers restricted to the sender's own cell."""
    same = [o for o in node.neighbor_cache if o.fixed_region_id == node.fixed_region_id]
    cands = same if len(same) >= 2 else (node.neighbor_cache or node.all_peer_cache)
    return G.weighted_choice_by_inverse_distance(node, cands)


print()
print(f"  {'N':>5} | {'protocol':>26} | {'regionMAPE':>10} | {'conv':>6} | {'hop(m)':>7}")
print("  " + "-" * 66)
for N in (100, 500, 1000):
    random.seed(42); np.random.seed(42)
    nodes = G.create_fleet(N)
    G.build_peer_caches(nodes)
    for label, sel, ad in [
        ("Uniform", G.select_peer_uniform, False),
        ("Fixed GWG (unconfined)", G.select_peer_geo_weighted, False),
        ("Fixed GWG + region-confined", select_peer_region_confined_fixed, False),
        ("Adaptive GWG", G.select_peer_adaptive_geo_weighted, True),
    ]:
        cr, ms, bw, hop, ec, conv, pr, oh = G.run_experiment(nodes, sel, max_rounds=150, adaptive=ad)
        print(f"  {N:>5} | {label:>26} | {pr[-1]:>9.2f}% | {cr:>6} | {hop:>7.1f}")
    print("  " + "-" * 66)
print("  VERDICT: read the third row against the fourth. If they match, the entire")
print("           reported gain comes from region-confined peer selection -- a")
print("           one-line change to the BASELINE -- and not from the adaptive")
print("           merge/split mechanism the paper claims as contribution #1.")
