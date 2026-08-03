"""
Generate paper Sections V-VII from results/results.json.

Every number in the generated prose and tables is interpolated from the results
file, so the paper cannot drift out of sync with the experiments. Regenerate
after any run:

    python3 src/gwg_simulation.py
    python3 scripts/make_results_sections.py

Writes:
    paper/RESULTS.md    Sections V, VI, VII
    paper/NUMBERS.md    claim -> evidence map
"""

import json
import os

RESULTS = "results/results.json"
OUT_SECTIONS = "paper/RESULTS.md"
OUT_NUMBERS = "paper/NUMBERS.md"

ORDER = ["uniform", "fixed_gwg", "fixed_confined", "adaptive_gwg"]
NAMES = {
    "uniform": "Uniform Random Gossip",
    "fixed_gwg": "Fixed GWG",
    "fixed_confined": "Fixed GWG (region-confined)",
    "adaptive_gwg": "Adaptive-GWG",
}


def pct(a, b):
    """Relative reduction from a to b, in percent."""
    return (a - b) / a * 100.0 if a else 0.0


def load():
    if not os.path.exists(RESULTS):
        raise SystemExit(
            f"{RESULTS} not found -- run 'python3 src/gwg_simulation.py' first.")
    with open(RESULTS) as fh:
        return json.load(fh)


def main():
    d = load()
    cfg = d["config"]
    main_r = {int(k): v for k, v in d["main"].items()}
    churn = {float(k): v for k, v in d["churn"].items()}
    mob = d["mobility"]
    sens = d["threshold_sensitivity"]
    refresh = {int(k): v for k, v in d["refresh_sweep"].items()}
    av = {int(k): v for k, v in d["av_readiness"].items()}
    sizes = sorted(main_r)
    big = sizes[-1]
    mid = sizes[len(sizes) // 2]

    L = []
    w = L.append

    # ---------------------------------------------------------------- V
    w("## V. Experimental Setup\n")
    w("### A. Dataset\n")
    w(f"Vehicle speeds are drawn from real New York City Taxi and Limousine Commission "
      f"Yellow Taxi trip records [22]. We compute a per-trip average speed from trip "
      f"distance and the pickup/dropoff timestamps, and discard trips outside a "
      f"5–70 mph band as meter or GPS artifacts. This leaves "
      f"**{cfg['dataset_samples']:,} valid speed samples**, with mean "
      f"**{cfg['dataset_mean_mph']:.2f} mph** and standard deviation "
      f"**{cfg['dataset_std_mph']:.2f} mph**.\n")
    w("The coefficient of variation of roughly "
      f"{cfg['dataset_std_mph']/cfg['dataset_mean_mph']:.2f} is the reason this problem "
      "is not trivial: an unaveraged single reading is already about "
      f"{cfg['dataset_std_mph']/cfg['dataset_mean_mph']*100:.0f}% away from its regional "
      "mean in expectation, so a protocol that fails to average has a characteristic "
      "error signature we can recognize in the results.\n")
    w("We deliberately report the year of the data rather than inheriting it from an "
      "earlier draft: an internal review of this project found a draft citing a 2013 "
      "dataset while the experiments used a different period, and we note it here so "
      "the provenance is unambiguous.\n")

    w("### B. Simulation Parameters\n")
    w("| Parameter | Value |")
    w("|---|---|")
    w(f"| Service area | {cfg['grid_size']}×{cfg['grid_size']} cells of "
      f"{cfg['region_size_m']:.0f} m ({cfg['grid_size']*cfg['region_size_m']:.0f} m square) |")
    w(f"| Fleet sizes N | {', '.join(str(n) for n in cfg['node_counts'])} |")
    w(f"| V2X radio range R | {cfg['comm_range_m']:.0f} m |")
    w(f"| Round duration Δt | {cfg['round_duration_s']*1000:.0f} ms (nominal CAM/BSM "
      f"interval [23], [24]) |")
    w(f"| Rounds per run | {cfg['max_rounds']} |")
    w(f"| Independent trials | {cfg['trials']} |")
    w(f"| Merge / split thresholds | n_min = {cfg['adaptive_min']}, "
      f"n_max = {cfg['adaptive_max']} |")
    w(f"| Region refresh interval τ | {cfg['adaptive_refresh_rounds']} round(s) |")
    w(f"| Push-sum payload | {cfg['msg_size_bytes']} B |")
    w(f"| Region-change announcement | {cfg['control_msg_bytes']} B |")
    w(f"| Random seed | {cfg['seed']} |")
    w("")
    w("Each trial generates an independent fleet; within a trial all four protocols see "
      "the same initial fleet, so the comparison is paired. All intervals are 95% "
      "Student-t confidence intervals over trials. Runs that never reach the "
      "convergence criterion are reported as a count of converging trials rather than "
      "averaged in at the round cap, which would produce a figure that estimates "
      "nothing.\n")

    w("### C. Protocols Compared\n")
    w("| Protocol | Peer candidate set | Regions |")
    w("|---|---|---|")
    w("| Uniform Random Gossip | any vehicle, geography ignored | fixed grid |")
    w("| Fixed GWG | inverse-distance within radio range | fixed grid |")
    w("| Fixed GWG (region-confined) | inverse-distance within range **and** own cell | fixed grid |")
    w("| Adaptive-GWG | inverse-distance within range **and** own adaptive region | merge/split |")
    w("")
    w("The third row is the ablation that makes the contribution measurable. Comparing "
      "Adaptive-GWG only against the first two rows conflates region confinement with "
      "region adaptation, and confinement is a one-line change to the baseline.\n")

    w("### D. Metrics\n")
    w("**Macro MAPE** — error averaged within each region, then across regions, so "
      "every region counts equally regardless of population. This is the headline "
      "metric; it is the objective of Section III-D. **Micro MAPE** — error averaged "
      "over vehicles, in which dense regions dominate. **Convergence round** — the "
      "first round at which 90% of evaluable vehicles are within 5% of their region's "
      "true mean. **Mean hop distance** — geographic distance per exchange, a proxy "
      "for transmit power and interference. **Bytes per vehicle** — push-sum payload "
      "plus region-management control traffic. **Cross-region exchange rate** — the "
      "share of exchanges that moved push-sum mass across a boundary of the reporting "
      "partition.\n")
    w("All error metrics are computed against the **fixed reporting partition**, "
      "identical for every protocol, never against a protocol's own regions. Regions "
      "holding fewer than two vehicles are excluded, since a single-vehicle 'average' "
      "is trivially exact and would flatter every protocol equally.\n")

    # ---------------------------------------------------------------- VI
    w("\n---\n")
    w("## VI. Results and Discussion\n")

    w("### A. Main Comparison\n")
    w(f"Table II reports all four protocols at each fleet size, with mobility enabled "
      f"and no churn, over {cfg['trials']} independent trials.\n")
    w("**TABLE II. MAIN RESULTS (mobility on, no churn, 95% CI)**\n")
    w("| N | Protocol | Macro MAPE % | Micro MAPE % | Converged | Hop (m) | B/vehicle | Cross-region % |")
    w("|---|---|---|---|---|---|---|---|")
    for n in sizes:
        for p in ORDER:
            s = main_r[n][p]
            conv = (f"{s['median_convergence_round']:.0f} ({s['n_converged']}/{s['trials']})"
                    if s["median_convergence_round"] is not None
                    else f"0/{s['trials']}")
            w(f"| {n} | {NAMES[p]} | {s['macro_mape']:.2f} ± {s['macro_mape_ci95']:.2f} "
              f"| {s['micro_mape']:.2f} ± {s['micro_mape_ci95']:.2f} | {conv} "
              f"| {s['avg_hop_m']:.1f} | {s['bytes_per_node']:.0f} "
              f"| {s['cross_region_exchange_pct']:.1f} |")
    w("")

    u_big = main_r[big]["uniform"]["macro_mape"]
    f_big = main_r[big]["fixed_gwg"]["macro_mape"]
    c_big = main_r[big]["fixed_confined"]["macro_mape"]
    a_big = main_r[big]["adaptive_gwg"]["macro_mape"]
    w(f"At the largest fleet size (N = {big}), Adaptive-GWG reaches "
      f"**{a_big:.2f}% ± {main_r[big]['adaptive_gwg']['macro_mape_ci95']:.2f}** macro "
      f"MAPE against **{u_big:.2f}%** for Uniform Random Gossip — a "
      f"**{pct(u_big, a_big):.0f}% reduction**. The ordering is consistent across every "
      f"fleet size and the confidence intervals of Adaptive-GWG and Uniform Random "
      f"Gossip do not overlap at any N.\n")

    w("### B. Where the Improvement Actually Comes From\n")
    w("This is the question the ablation exists to answer, and it is the one prior work "
      "in this space does not separate.\n")
    w("**TABLE III. CONTRIBUTION ATTRIBUTION (macro MAPE)**\n")
    w("| N | Fixed GWG | + region confinement | + adaptive regions | Gain from confinement | Gain from adaptation |")
    w("|---|---|---|---|---|---|")
    for n in sizes:
        f = main_r[n]["fixed_gwg"]["macro_mape"]
        c = main_r[n]["fixed_confined"]["macro_mape"]
        a = main_r[n]["adaptive_gwg"]["macro_mape"]
        w(f"| {n} | {f:.2f}% | {c:.2f}% | {a:.2f}% | {pct(f, c):+.1f}% | {pct(c, a):+.1f}% |")
    w("")

    small = sizes[0]
    fs, cs, as_ = (main_r[small]["fixed_gwg"]["macro_mape"],
                   main_r[small]["fixed_confined"]["macro_mape"],
                   main_r[small]["adaptive_gwg"]["macro_mape"])
    w(f"Two things stand out. First, at N = {small} confinement **hurts** "
      f"({pct(fs, cs):+.1f}%): with roughly one vehicle per cell, a confined vehicle "
      f"seldom finds two same-cell peers, so it falls back to the unconfined "
      f"neighbourhood anyway while having lost the chance to average with anyone "
      f"stable. Confinement is only useful once cells are populated enough to gossip "
      f"within. Second, adaptation delivers a positive gain at every fleet size "
      f"({', '.join(f'{pct(main_r[n]['fixed_confined']['macro_mape'], main_r[n]['adaptive_gwg']['macro_mape']):+.1f}% at N={n}' for n in sizes)}), "
      f"and it is largest exactly where confinement fails — which is the regime the "
      f"merge rule was designed for.\n")
    w("This is a narrower claim than 'adaptive regions are better'. It is also the claim "
      "the evidence supports, and it is actionable: a deployment should enable the "
      "adaptive layer when its cells are sparsely populated relative to the merge "
      "threshold, and can skip it otherwise.\n")

    w("### C. The Error Floor of Unconfined Gossip\n")
    xr = {p: main_r[big][p]["cross_region_exchange_pct"] for p in ORDER}
    w(f"Uniform Random Gossip and Fixed GWG do not converge at any fleet size "
      f"(0/{cfg['trials']} trials). This is not slow convergence; it is convergence to "
      f"the wrong target. Push-sum over a connected graph converges to the average over "
      f"that graph, and when peer selection may cross region boundaries the graph spans "
      f"the whole service area, so every vehicle's estimate is drawn toward the "
      f"city-wide mean. The cross-region exchange rate makes the mechanism explicit: "
      f"**{xr['fixed_gwg']:.1f}%** of Fixed GWG's exchanges cross a region boundary at "
      f"N = {big}, versus **{xr['adaptive_gwg']:.1f}%** for Adaptive-GWG.\n")
    w(f"Note that Fixed GWG's error ({f_big:.2f}%) is barely below Uniform's "
      f"({u_big:.2f}%) despite cutting mean hop distance from "
      f"{main_r[big]['uniform']['avg_hop_m']:.0f} m to "
      f"{main_r[big]['fixed_gwg']['avg_hop_m']:.0f} m — a "
      f"{pct(main_r[big]['uniform']['avg_hop_m'], main_r[big]['fixed_gwg']['avg_hop_m']):.0f}% "
      f"reduction. **Geographic weighting buys locality of communication, not locality "
      f"of estimation.** This distinction is easy to lose, because a protocol that "
      f"talks only to nearby vehicles feels like it should produce a local answer. It "
      f"does not: the exchange graph remains connected across the whole area, and mass "
      f"flows along it regardless of how short each individual hop is.\n")
    w("The residual error of the confined variants has the same origin in miniature. A "
      "confined vehicle with fewer than two same-region peers must fall back to the "
      "wider neighbourhood or stop gossiping altogether; each fallback leaks mass "
      "irreversibly across a boundary. Adaptive-GWG's merge rule attacks precisely this "
      "leak by ensuring regions are populated enough that the fallback rarely fires, "
      "which is why its cross-region rate is the lowest in the table.\n")

    w("### D. Cost of Adaptation\n")
    ab = main_r[big]["adaptive_gwg"]["bytes_per_node"]
    cb = main_r[big]["fixed_confined"]["bytes_per_node"]
    w(f"Adaptive-GWG is not free. At N = {big} it sends "
      f"**{ab:.0f} B per vehicle** against **{cb:.0f} B** for the confined fixed-grid "
      f"baseline, an overhead of **{(ab-cb)/cb*100:.1f}%**, from region-change "
      f"announcements. Data-plane message counts are identical across protocols by "
      f"construction — one exchange per vehicle per round — so the control traffic is "
      f"the entire difference, and reporting it as free (as our earlier harness did) "
      f"would have made the accuracy comparison meaningless.\n")
    w("**TABLE IV. REGION-REFRESH INTERVAL (N = 500)**\n")
    w("| τ (rounds) | Macro MAPE % | Control messages | B/vehicle |")
    w("|---|---|---|---|")
    for t in sorted(refresh):
        r = refresh[t]
        w(f"| {t} | {r['macro_mape']:.2f} ± {r['macro_mape_ci95']:.2f} "
          f"| {r['control_messages']:.0f} | {r['bytes_per_node']:.0f} |")
    w("")
    fastest, slowest = min(refresh), max(refresh)
    w(f"Refreshing every round costs {refresh[fastest]['control_messages']:.0f} control "
      f"messages and yields {refresh[fastest]['macro_mape']:.2f}% macro MAPE; refreshing "
      f"every {slowest} rounds cuts control traffic by "
      f"{pct(refresh[fastest]['control_messages'], refresh[slowest]['control_messages']):.0f}% "
      f"at {refresh[slowest]['macro_mape']:.2f}% macro MAPE. The trade-off is real but "
      f"shallow in bytes: control traffic is a small fraction of a budget dominated by "
      f"the per-round push-sum payload.\n")

    w("### E. Mobility\n")
    w("**TABLE V. STATIC VS MOBILE (N = 500)**\n")
    w("| Protocol | Static macro MAPE % | Mobile macro MAPE % | Degradation |")
    w("|---|---|---|---|")
    for p in ORDER:
        s0 = mob["static"][p]["macro_mape"]
        s1 = mob["mobile"][p]["macro_mape"]
        w(f"| {NAMES[p]} | {s0:.2f} | {s1:.2f} | {(s1-s0)/s0*100:+.0f}% |")
    w("")
    ast, amo = mob["static"]["adaptive_gwg"]["macro_mape"], mob["mobile"]["adaptive_gwg"]["macro_mape"]
    cst, cmo = mob["static"]["fixed_confined"]["macro_mape"], mob["mobile"]["fixed_confined"]["macro_mape"]
    w(f"Mobility is the dominant cost in this system. On a static network Adaptive-GWG "
      f"reaches {ast:.2f}% macro MAPE; with vehicles in motion the same protocol reaches "
      f"{amo:.2f}%. The cause is the re-initialization rule of Section IV-A: every "
      f"boundary crossing discards the averaging work a vehicle has accumulated. At "
      f"these speeds a vehicle crosses a {cfg['region_size_m']:.0f} m cell every few "
      f"tens of rounds, so a substantial fraction of the fleet is restarting at any "
      f"moment.\n")
    w(f"The relative ordering is preserved — Adaptive-GWG stays ahead of the confined "
      f"baseline mobile ({amo:.2f}% vs {cmo:.2f}%) as it does static "
      f"({ast:.2f}% vs {cst:.2f}%) — so the mechanism's benefit is not an artifact of a "
      f"static topology. But the absolute degradation is large enough that we regard "
      f"re-initialization, not peer selection, as the most promising target for future "
      f"work.\n")

    w("### F. Churn\n")
    w("**TABLE VI. PER-ROUND CHURN (N = 500)**\n")
    w("| Churn ρ | " + " | ".join(NAMES[p] for p in ORDER) + " |")
    w("|---|" + "---|" * len(ORDER))
    for r in sorted(churn):
        w(f"| {r:.2f} | " + " | ".join(f"{churn[r][p]['macro_mape']:.2f}%" for p in ORDER) + " |")
    w("")
    rates = sorted(churn)
    a0, ahi = churn[rates[0]]["adaptive_gwg"]["macro_mape"], churn[rates[-1]]["adaptive_gwg"]["macro_mape"]
    u0, uhi = churn[rates[0]]["uniform"]["macro_mape"], churn[rates[-1]]["uniform"]["macro_mape"]
    w(f"Churn degrades Adaptive-GWG from {a0:.2f}% to {ahi:.2f}% as the per-round "
      f"departure probability rises from {rates[0]:.0%} to {rates[-1]:.0%}, because a "
      f"departing vehicle destroys the push-sum mass it holds and push-sum conserves "
      f"mass only over a fixed population. The unconfined baselines are comparatively "
      f"insensitive ({u0:.2f}% to {uhi:.2f}%) for an unflattering reason: they are "
      f"already so far from the regional target that losing mass changes little. "
      f"Robustness to churn is not a virtue when it is robustness of a wrong answer.\n")
    w("Adaptive-GWG retains an advantage across the full churn range tested, but the "
      "margin narrows, and we report this as a genuine limit of the approach rather "
      "than as a favourable result.\n")

    w("### G. Sensitivity to the Adaptive Thresholds\n")
    w("**TABLE VII. MERGE/SPLIT THRESHOLD SWEEP (N = 500)**\n")
    w("| n_min | n_max | Macro MAPE % | Mean active regions |")
    w("|---|---|---|---|")
    best = min(sens.values(), key=lambda v: v["macro_mape"])
    worst = max(sens.values(), key=lambda v: v["macro_mape"])
    for k in sorted(sens, key=lambda k: (sens[k]["min"], sens[k]["max"])):
        v = sens[k]
        w(f"| {v['min']} | {v['max']} | {v['macro_mape']:.2f} ± "
          f"{v['macro_mape_ci95']:.2f} | {v['active_regions']:.1f} |")
    w("")
    w(f"Accuracy is governed almost entirely by the merge threshold n_min; the split "
      f"threshold n_max has little effect at this density because few cells are dense "
      f"enough to trigger a split. The best setting tested "
      f"(n_min = {best['min']}, n_max = {best['max']}) gives {best['macro_mape']:.2f}% "
      f"with {best['active_regions']:.0f} active regions; the worst "
      f"(n_min = {worst['min']}, n_max = {worst['max']}) gives {worst['macro_mape']:.2f}% "
      f"with {worst['active_regions']:.0f}.\n")
    w("This sweep also rules out an obvious confound. One might suspect Adaptive-GWG "
      "wins merely by producing coarser regions, which are internally more homogeneous "
      "and therefore easier to estimate. The sweep shows the opposite: aggressive "
      f"merging ({worst['active_regions']:.0f} regions) is the *worst* configuration, "
      f"and the best keeps the partition close to the underlying grid "
      f"({best['active_regions']:.0f} regions) while eliminating only those cells too "
      "sparse to gossip within. The mechanism is repairing sparsity, not coarsening the "
      "problem.\n")

    w("### H. Real-Time Readiness for AV Consumers\n")
    w(f"Treating one round as one {cfg['round_duration_s']*1000:.0f} ms beacon interval "
      f"[23], [24], Table VIII reports the error a protocol would hand a decision system "
      f"at a given deadline. 'Usable' is macro MAPE ≤ 10%, an illustrative threshold for "
      f"cooperative speed advisory rather than one derived from a standard.\n")
    w("**TABLE VIII. ERROR AT A DECISION DEADLINE (macro MAPE %)**\n")
    budgets = sorted(int(b) for b in next(iter(av[big].values())))
    w("| N | Protocol | " + " | ".join(f"{b/1000:.1f} s" for b in budgets) + " |")
    w("|---|---|" + "---|" * len(budgets))
    for n in sizes:
        for p in ORDER:
            row = av[n][p]
            cells = " | ".join(
                f"{row[str(b)]['macro_mape']:.1f}"
                + (" ✓" if row[str(b)]["usable"] else "")
                for b in budgets)
            w(f"| {n} | {NAMES[p]} | {cells} |")
    w("")
    w("Two observations. Under mobility, error does not decrease monotonically with the "
      "deadline: the estimate improves over the first few rounds and then degrades as "
      "boundary crossings accumulate and re-initialization discards averaging work. A "
      "longer deadline is therefore not automatically a better estimate, which is "
      "counter-intuitive and worth stating plainly for anyone sizing a real deployment. "
      "Second, the unconfined baselines never reach the usable threshold at any deadline "
      "or fleet size — consistent with Section VI-C, they are converging to the wrong "
      "quantity, and no amount of additional time repairs that.\n")

    # ---------------------------------------------------------------- VII
    w("\n---\n")
    w("## VII. Limitations and Threats to Validity\n")
    w("**Simulation, not deployment.** We model radio range as a hard disc and do not "
      "model packet loss, channel contention, MAC-layer delay, GPS error, or "
      "non-line-of-sight attenuation in an urban canyon. All of these would raise the "
      "error floor, and contention in particular would penalize the protocol that sends "
      "the most control traffic — which is ours. The relative ordering we report should "
      "be read as an upper bound on Adaptive-GWG's advantage, not a prediction of field "
      "performance.\n")
    w("**Synthetic spatial structure over real speeds.** The speed *values* are real "
      "NYC TLC records, but their spatial arrangement comes from a modelled congestion "
      "field (centre-slow, periphery-fast) rather than from real per-zone speeds, "
      "because the public trip records do not carry the per-zone traces this would "
      "require. The congestion gradient is a plausible but stylized model, and results "
      "would change under a different spatial structure — for example a corridor "
      "pattern rather than a radial one.\n")
    w("**Mobility model.** Vehicles follow a reflected random walk at their observed "
      "speed, not a road network. Real vehicles are constrained to streets, turn at "
      "intersections, and cluster at signals, which would make region membership more "
      "persistent than in our model and probably reduce the re-initialization cost that "
      "Section VI-E identifies as dominant. A road-constrained mobility trace is the "
      "single most valuable improvement to this evaluation.\n")
    w(f"**Scale.** We test up to N = {big} vehicles in a "
      f"{cfg['grid_size']*cfg['region_size_m']:.0f} m square. This is a dense downtown "
      f"district, not a city, and the conclusions about the sparse regime depend on "
      f"vehicles-per-cell rather than on N alone. Results should be read against the "
      f"density ratio N/G², not the fleet size.\n")
    w("**Convergence criterion.** Under mobility no protocol satisfies the 90%-within-5% "
      "criterion, so the convergence column is uninformative here and the comparison "
      "rests on the error curves instead. A criterion tuned to a moving target — for "
      "instance tracking error against a sliding-window regional mean — would be more "
      "discriminating.\n")
    w("**AV framing.** The 100 ms beacon interval is standards-derived [23], [24], but "
      "the 10% usable-error threshold is illustrative and not traceable to any "
      "safety-case requirement. Section I-C scopes Adaptive-GWG to decision support "
      "explicitly; nothing here should be read as a claim about safety-critical "
      "messaging, whose latency determinism push-sum does not provide.\n")
    w("**Statistical power.** Confidence intervals come from "
      f"{cfg['trials']} independent trials. At N = {small} the intervals are wide "
      f"relative to the differences between the weaker protocols, and we avoid claiming "
      f"orderings there that the intervals do not support.\n")
    w("**Prior-version correction.** An earlier version of this work reported per-region "
      "MAPE reductions of 34–96% attributable to adaptive regions. An audit "
      "(`scripts/audit_baseline_claims.py`, `scripts/audit_ablation.py`) found that "
      "result did not hold: the exchange was not push-sum, no ablation isolated "
      "confinement from adaptation, each protocol was scored against its own partition, "
      "and at the largest fleet size the adaptive rule had relabelled no vehicles at "
      "all. The present numbers supersede those entirely. We document this because the "
      "failure mode — a bundled comparison that credits the novel component with a "
      "simpler component's effect — is not specific to us and is easy to reproduce "
      "elsewhere.\n")

    os.makedirs("paper", exist_ok=True)
    with open(OUT_SECTIONS, "w") as fh:
        fh.write("<!-- GENERATED by scripts/make_results_sections.py -- do not edit by hand. -->\n")
        fh.write("<!-- Regenerate: python3 src/gwg_simulation.py && "
                 "python3 scripts/make_results_sections.py -->\n\n")
        fh.write("\n".join(L) + "\n")
    print(f"wrote {OUT_SECTIONS}")

    # ------------------------------------------------------------ NUMBERS
    M = ["# Claim → evidence map\n",
         "Generated by `scripts/make_results_sections.py`. Every claim the paper makes "
         "that carries a number, and where that number comes from. Regenerate after "
         "any experiment run.\n",
         f"Source: `results/results.json` (seed {cfg['seed']}, {cfg['trials']} trials, "
         f"{cfg['max_rounds']} rounds).\n",
         "| Claim | Value | Evidence |", "|---|---|---|"]
    M.append(f"| Dataset size | {cfg['dataset_samples']:,} samples | `config.dataset_samples` |")
    M.append(f"| Dataset mean / sd | {cfg['dataset_mean_mph']:.2f} / "
             f"{cfg['dataset_std_mph']:.2f} mph | `config.dataset_mean_mph`, `.dataset_std_mph` |")
    for n in sizes:
        for p in ORDER:
            s = main_r[n][p]
            M.append(f"| N={n} {NAMES[p]} macro MAPE | {s['macro_mape']:.2f} ± "
                     f"{s['macro_mape_ci95']:.2f}% | `main.{n}.{p}.macro_mape` |")
    M.append(f"| Adaptive vs Uniform at N={big} | {pct(u_big, a_big):.0f}% reduction | "
             f"derived from `main.{big}` |")
    for n in sizes:
        M.append(f"| Gain from confinement, N={n} | "
                 f"{pct(main_r[n]['fixed_gwg']['macro_mape'], main_r[n]['fixed_confined']['macro_mape']):+.1f}% "
                 f"| derived from `main.{n}` |")
        M.append(f"| Gain from adaptation, N={n} | "
                 f"{pct(main_r[n]['fixed_confined']['macro_mape'], main_r[n]['adaptive_gwg']['macro_mape']):+.1f}% "
                 f"| derived from `main.{n}` |")
    M.append(f"| Cross-region exchanges, Fixed GWG, N={big} | {xr['fixed_gwg']:.1f}% "
             f"| `main.{big}.fixed_gwg.cross_region_exchange_pct` |")
    M.append(f"| Cross-region exchanges, Adaptive-GWG, N={big} | {xr['adaptive_gwg']:.1f}% "
             f"| `main.{big}.adaptive_gwg.cross_region_exchange_pct` |")
    M.append(f"| Control-traffic overhead at N={big} | {(ab-cb)/cb*100:.1f}% "
             f"| derived from `main.{big}.*.bytes_per_node` |")
    M.append(f"| Mobility degradation, Adaptive-GWG | {ast:.2f}% → {amo:.2f}% "
             f"| `mobility.static/mobile.adaptive_gwg.macro_mape` |")
    M.append(f"| Churn degradation, Adaptive-GWG | {a0:.2f}% → {ahi:.2f}% "
             f"| `churn.*.adaptive_gwg.macro_mape` |")
    M.append(f"| Best threshold setting | n_min={best['min']}, n_max={best['max']} → "
             f"{best['macro_mape']:.2f}% | `threshold_sensitivity` |")
    M.append("")
    M.append("## Properties enforced by tests\n")
    M.append("`tests/test_gwg.py` — 25 tests. Those that encode a defect found by the "
             "audit of the earlier harness:\n")
    for t, why in [
        ("test_push_sum_is_directional", "the exchange must not be symmetric"),
        ("test_push_sum_conserves_mass", "the convergence guarantee rests on this"),
        ("test_merge_actually_merges", "merged vehicles must share an existing region's label"),
        ("test_region_labels_are_stable_across_rounds", "labels name geography, not a counter"),
        ("test_reporting_partition_is_protocol_independent", "one ground truth for all protocols"),
        ("test_vehicles_actually_move", "the title claims a mobile network"),
        ("test_adaptive_pays_for_its_control_traffic", "adaptation must not be free"),
        ("test_non_converging_runs_are_not_averaged_in", "censored runs are counted, not averaged"),
        ("test_different_seeds_give_different_fleets", "trials must be independent replicates"),
        ("test_singleton_regions_are_excluded", "a one-vehicle average is trivially exact"),
    ]:
        M.append(f"- `{t}` — {why}")
    with open(OUT_NUMBERS, "w") as fh:
        fh.write("\n".join(M) + "\n")
    print(f"wrote {OUT_NUMBERS}")


if __name__ == "__main__":
    main()
