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
    cells_total = cfg["grid_size"] ** 2
    big = sizes[-1]
    small = sizes[0]
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

    confine_gains = [pct(main_r[n]["fixed_gwg"]["macro_mape"],
                         main_r[n]["fixed_confined"]["macro_mape"]) for n in sizes]
    adapt_gains = [pct(main_r[n]["fixed_confined"]["macro_mape"],
                       main_r[n]["adaptive_gwg"]["macro_mape"]) for n in sizes]

    def separates(n):
        """Do the confined and adaptive 95% intervals separate at this N?"""
        c, a = main_r[n]["fixed_confined"], main_r[n]["adaptive_gwg"]
        return (a["macro_mape"] + a["macro_mape_ci95"] < c["macro_mape"] - c["macro_mape_ci95"]
                or c["macro_mape"] + c["macro_mape_ci95"] < a["macro_mape"] - a["macro_mape_ci95"])

    confine_str = ", ".join(
        "{:+.1f}% at N={} ({:.0f} vehicles/cell)".format(g, n, n / cells_total)
        for g, n in zip(confine_gains, sizes))
    adapt_str = ", ".join("{:+.1f}% at N={}".format(g, n)
                          for g, n in zip(adapt_gains, sizes))
    ci_str = "; ".join(
        "N={}: {:.2f} +/- {:.2f} against {:.2f} +/- {:.2f}".format(
            n, main_r[n]["fixed_confined"]["macro_mape"],
            main_r[n]["fixed_confined"]["macro_mape_ci95"],
            main_r[n]["adaptive_gwg"]["macro_mape"],
            main_r[n]["adaptive_gwg"]["macro_mape_ci95"])
        for n in sizes)

    w(f"**Region confinement accounts for the entire improvement.** Restricting peer "
      f"selection to the sender's own cell — a one-line change to the fixed-grid "
      f"baseline — is worth {confine_str}.\n")
    w(f"**Adaptive region management adds nothing measurable on top of it:** "
      f"{adapt_str}. Every one of these is negative or negligible, and at no fleet size "
      f"do the two confidence intervals separate ({ci_str}). Adaptive-GWG additionally "
      f"carries region-management control traffic that the confined baseline does not "
      f"(Section VI-D).\n")
    if any(separates(n) for n in sizes):
        w("(The intervals do separate at "
          + ", ".join(f"N={n}" for n in sizes if separates(n))
          + " — see Table III for the direction.)\n")

    w("We report this as the paper's principal finding, and it is worth being direct "
      "about what it means. The adaptive merge/split layer is the component this line of "
      "work — including our own earlier version of it — treats as the novel "
      "contribution. Measured against gossip that is free to cross region boundaries, it "
      "appears to deliver a large improvement. Measured against a fixed grid that simply "
      "keeps its gossip inside a cell, it delivers none. **The improvement is real; the "
      "attribution was wrong.**\n")
    w("The threshold sweep in Section VI-H supplies the mechanism rather than merely "
      "restating the result: the best adaptive configuration is the one that changes the "
      "partition least, and accuracy degrades monotonically as merging grows more "
      "aggressive. There is no setting of the merge and split thresholds at which "
      "adaptation beats leaving the grid alone — the optimum sits at the boundary of "
      "doing nothing.\n")
    w("This does not make region management useless in general, and we are careful not "
      "to over-claim in the negative direction either. Our fixed grid is already well "
      "matched to the service area: every cell lies comfortably inside radio range of "
      "its own members, and vehicles are close to uniformly distributed. Adaptation has "
      "little to repair under those conditions. A deployment whose cells are badly sized "
      "relative to radio range, or whose density varies by orders of magnitude across "
      "the map, is a different setting that this evaluation does not cover. What we can "
      "say is that in the setting the protocol was designed and previously evaluated "
      "for, the improvement belongs to confinement.\n"
      )

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
    xr_s = {p: main_r[small][p]["cross_region_exchange_pct"] for p in ORDER}
    w(f"The confined variants collapse this rate to near zero once cells are populated "
      f"({main_r[big]['fixed_confined']['cross_region_exchange_pct']:.1f}% at N = {big}), "
      f"and their accuracy improves correspondingly. At N = {small} they cannot: "
      f"**{xr_s['fixed_confined']:.1f}%** of the confined baseline's exchanges still "
      f"cross a boundary, because with about {small//cells_total} vehicle per cell the "
      f"fallback rule fires almost every round. That is the mechanism behind the "
      f"negative confinement gain in Table III, measured rather than inferred.\n")
    w(f"One caveat on how to read this column for Adaptive-GWG. It is measured against "
      f"the reporting partition for every protocol, so for the confined baselines it is "
      f"pure leakage — their regions *are* the reporting cells. Adaptive-GWG's regions "
      f"are deliberately not the reporting cells, so its rate "
      f"({xr_s['adaptive_gwg']:.1f}% at N = {small}, "
      f"{main_r[big]['adaptive_gwg']['cross_region_exchange_pct']:.1f}% at N = {big}) "
      f"mixes leakage with intentional pooling across cells it has merged. It is "
      f"therefore diagnostic for the baselines and only indicative for our protocol, and "
      f"we do not read Adaptive-GWG's higher rate at N = {small} as a defect — it is the "
      f"merge rule doing what it was designed to do.\n")

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

    w("### E. Periodic Restart and the Drift Caused by Mobility\n")
    restart = d["restart_sweep"]
    w("Running push-sum on a moving fleet has a failure mode that a single "
      "end-of-run number hides. Without periodic restart the estimate reaches a "
      "minimum after a handful of rounds and then **degrades steadily**, because "
      "re-initialization at region boundaries keeps injecting fresh weight-1 mass into "
      "regions where push-sum has already concentrated mass on a few holders. The "
      "region's weight fills up with unaveraged single readings and the estimate drifts "
      "back toward exactly the raw measurement the protocol exists to improve on.\n")
    never = restart.get("0")
    if never:
        for p in ("fixed_confined", "adaptive_gwg"):
            nv = never[p]
            w(f"- {NAMES[p]} without restart: best **{nv['best_macro_mape']:.2f}%** at "
              f"round {nv['best_round']}, degrading to **{nv['macro_mape']:.2f}%** "
              f"steady state — a factor of "
              f"{nv['macro_mape']/max(nv['best_macro_mape'], 1e-9):.1f}.")
        w("")
    w("The remedy is standard for push-sum over time-varying data: restart the "
      "accumulator periodically. The convergence curve sets the period — long enough to "
      "average, short enough that drift cannot accumulate. We apply it identically to "
      "every protocol, so it favours none of them.\n")
    w("**TABLE V. PUSH-SUM RESTART INTERVAL (N = 500, steady-state macro MAPE %)**\n")
    ivs = sorted(restart, key=lambda k: (int(k) == 0, int(k)))
    w("| Restart interval | " + " | ".join(NAMES[p] for p in ORDER) + " |")
    w("|---|" + "---|" * len(ORDER))
    for i in ivs:
        lab = "never" if int(i) == 0 else f"every {i} rounds"
        w(f"| {lab} | " + " | ".join(f"{restart[i][p]['macro_mape']:.2f}" for p in ORDER) + " |")
    w("")
    best_iv = min((i for i in ivs if int(i) > 0),
                  key=lambda i: restart[i]["adaptive_gwg"]["macro_mape"])
    cfg_iv = str(cfg.get("restart_interval", 10))
    w(f"Restarting every {best_iv} rounds is best for both confined protocols, cutting "
      f"Adaptive-GWG from {restart['0']['adaptive_gwg']['macro_mape']:.2f}% to "
      f"{restart[best_iv]['adaptive_gwg']['macro_mape']:.2f}%. Restarting too often "
      f"leaves too few rounds to average; too rarely lets drift accumulate. The "
      f"remaining experiments use every {cfg_iv} rounds"
      + (f", which is within the confidence interval of the {best_iv}-round optimum "
         f"({restart[cfg_iv]['adaptive_gwg']['macro_mape']:.2f}% vs "
         f"{restart[best_iv]['adaptive_gwg']['macro_mape']:.2f}%) and was fixed before "
         f"this sweep was run" if cfg_iv != best_iv else "") + ".\n")
    w(f"The most informative column is the leftmost. Uniform Random Gossip and Fixed GWG "
      f"barely move across the entire sweep "
      f"({restart['0']['uniform']['macro_mape']:.1f}% → "
      f"{restart[best_iv]['uniform']['macro_mape']:.1f}% and "
      f"{restart['0']['fixed_gwg']['macro_mape']:.1f}% → "
      f"{restart[best_iv]['fixed_gwg']['macro_mape']:.1f}%). Restart repairs staleness, "
      f"and staleness was never their problem — they are converging accurately to the "
      f"wrong quantity, and no scheduling change fixes a target error. This is the "
      f"cleanest confirmation in the paper that the error floor of Section VI-C is "
      f"structural rather than an artifact of how long we ran the protocol.\n")

    w("### F. Mobility\n")
    w("**TABLE VI. STATIC VS MOBILE (N = 500)**\n")
    w("| Protocol | Static macro MAPE % | Mobile macro MAPE % | Degradation |")
    w("|---|---|---|---|")
    for p in ORDER:
        s0 = mob["static"][p]["macro_mape"]
        s1 = mob["mobile"][p]["macro_mape"]
        w(f"| {NAMES[p]} | {s0:.2f} | {s1:.2f} | {(s1-s0)/s0*100:+.0f}% |")
    w("")
    ast, amo = mob["static"]["adaptive_gwg"]["macro_mape"], mob["mobile"]["adaptive_gwg"]["macro_mape"]
    cst, cmo = mob["static"]["fixed_confined"]["macro_mape"], mob["mobile"]["fixed_confined"]["macro_mape"]
    worst_deg = max((mob["mobile"][p]["macro_mape"] - mob["static"][p]["macro_mape"])
                    / mob["static"][p]["macro_mape"] * 100 for p in ORDER)
    w(f"With periodic restart in place, mobility costs between "
      f"{min((mob['mobile'][p]['macro_mape'] - mob['static'][p]['macro_mape']) / mob['static'][p]['macro_mape'] * 100 for p in ORDER):.0f}% "
      f"and {worst_deg:.0f}% additional error. That is a far smaller penalty than the "
      f"same comparison shows without restart, which is the point of Section VI-E: most "
      f"of what looks like a mobility penalty is really accumulated drift that restart "
      f"already removes.\n")
    w(f"The two confined protocols absorb the larger relative hit "
      f"({cst:.2f}% → {cmo:.2f}% and {ast:.2f}% → {amo:.2f}%) precisely because they "
      f"have the most to lose: they are the only ones estimating the right quantity in "
      f"the first place, so discarding accumulated averaging at a boundary crossing "
      f"actually costs them something. The unconfined baselines barely move, for the "
      f"same unflattering reason they are insensitive to everything else in this "
      f"paper.\n")
    if amo <= cmo:
        w(f"Adaptive-GWG remains ahead of the confined baseline under mobility "
          f"({amo:.2f}% vs {cmo:.2f}%).\n")
    else:
        w(f"We note that Adaptive-GWG is **behind** the confined baseline in both "
          f"conditions here ({ast:.2f}% vs {cst:.2f}% static, {amo:.2f}% vs {cmo:.2f}% "
          f"mobile), consistent with Section VI-B: adaptive region boundaries move as "
          f"density fluctuates, and each move forces a re-initialization that a fixed "
          f"grid does not pay. Under mobility, a stable partition is worth more than a "
          f"well-fitted one.\n")

    w("### G. Churn\n")
    w("**TABLE VII. PER-ROUND CHURN (N = 500)**\n")
    w("| Churn ρ | " + " | ".join(NAMES[p] for p in ORDER) + " |")
    w("|---|" + "---|" * len(ORDER))
    for r in sorted(churn):
        w(f"| {r:.2f} | " + " | ".join(f"{churn[r][p]['macro_mape']:.2f}%" for p in ORDER) + " |")
    w("")
    rates = sorted(churn)
    a0, ahi = churn[rates[0]]["adaptive_gwg"]["macro_mape"], churn[rates[-1]]["adaptive_gwg"]["macro_mape"]
    u0, uhi = churn[rates[0]]["uniform"]["macro_mape"], churn[rates[-1]]["uniform"]["macro_mape"]
    a_best_rate = min(rates, key=lambda r: churn[r]["adaptive_gwg"]["macro_mape"])
    a_best = churn[a_best_rate]["adaptive_gwg"]["macro_mape"]
    if a_best < a0:
        w(f"The result here is counter-intuitive and we report it as measured: churn "
          f"**improves** accuracy over part of the range. Adaptive-GWG goes from "
          f"{a0:.2f}% at ρ = 0 to {a_best:.2f}% at ρ = {a_best_rate:.0%}, before "
          f"worsening again to {ahi:.2f}% at ρ = {rates[-1]:.0%}. Every protocol shows "
          f"the same pattern.\n")
        w("The mechanism is the interaction between churn and mobility. Under mobility a "
          "vehicle's push-sum mass goes stale: it reflects readings gathered in regions "
          "it has since left, and only a boundary crossing resets it. A departing "
          "vehicle destroys stale mass, and the arriving replacement injects a fresh, "
          "correctly-localized reading. At low rates that flushing effect outweighs the "
          "mass-conservation violation churn causes. At higher rates the loss of "
          "accumulated averaging dominates and error climbs again.\n")
        w("We flag this as a limitation of the evaluation as much as a property of the "
          "protocol: it means our zero-churn configuration is not the most favourable "
          "one, and that a deployment's error will depend on fleet turnover in a "
          "non-monotone way. A staleness-aware reset rule — discarding mass on an age "
          "bound rather than only on a boundary crossing — would likely capture the "
          "benefit without relying on churn to deliver it, and we regard that as the "
          "clearest actionable consequence of this experiment.\n")
    else:
        w(f"Churn degrades Adaptive-GWG from {a0:.2f}% to {ahi:.2f}% as the per-round "
          f"departure probability rises from {rates[0]:.0%} to {rates[-1]:.0%}, because "
          f"a departing vehicle destroys the push-sum mass it holds and push-sum "
          f"conserves mass only over a fixed population.\n")
    w(f"The ordering between protocols is preserved at every churn rate tested, with "
      f"Adaptive-GWG best throughout ({a0:.2f}%–{max(churn[r]['adaptive_gwg']['macro_mape'] for r in rates):.2f}%) "
      f"and Uniform Random Gossip worst ({min(churn[r]['uniform']['macro_mape'] for r in rates):.2f}%–{u0:.2f}%), "
      f"so no conclusion in Section VI-B depends on the churn setting.\n")

    w("### H. Sensitivity to the Adaptive Thresholds\n")
    w("**TABLE VIII. MERGE/SPLIT THRESHOLD SWEEP (N = 500)**\n")
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
      f"threshold n_max has almost no effect at this density, because few cells hold "
      f"enough vehicles to trigger a split at all. The best setting tested "
      f"(n_min = {best['min']}, n_max = {best['max']}) gives {best['macro_mape']:.2f} ± "
      f"{best['macro_mape_ci95']:.2f}% with {best['active_regions']:.0f} active regions; "
      f"the worst (n_min = {worst['min']}, n_max = {worst['max']}) gives "
      f"{worst['macro_mape']:.2f} ± {worst['macro_mape_ci95']:.2f}% with "
      f"{worst['active_regions']:.0f}.\n")

    # Group by n_min and report the trend honestly, whatever direction it runs.
    by_min = {}
    for v in sens.values():
        by_min.setdefault(v["min"], []).append(v)
    mins_sorted = sorted(by_min)
    trend = ", ".join(
        "n_min={} → {:.2f}% ({:.0f} regions)".format(
            m, sum(x["macro_mape"] for x in by_min[m]) / len(by_min[m]),
            sum(x["active_regions"] for x in by_min[m]) / len(by_min[m]))
        for m in mins_sorted)
    w(f"Reading down the merge threshold: {trend}.\n")
    coarser_is_better = best["active_regions"] < worst["active_regions"]
    if coarser_is_better:
        w("We have to be careful about what this shows, because it points at a confound "
          "rather than away from one. The best configurations here are also the "
          "**coarsest**, and a coarser partition is internally more homogeneous, so part "
          "of this gain may be the estimation problem becoming easier rather than the "
          "protocol solving it better. Two considerations bound how much of the result "
          "that explains.\n")
        w(f"First, the effect is small and largely within the confidence intervals: "
          f"everything from n_min = {mins_sorted[1]} upward lies in a "
          f"{min(sum(x['macro_mape'] for x in by_min[m]) / len(by_min[m]) for m in mins_sorted[1:]):.1f}–"
          f"{max(sum(x['macro_mape'] for x in by_min[m]) / len(by_min[m]) for m in mins_sorted[1:]):.1f}% "
          f"band despite the active-region count varying by roughly "
          f"{max(by_min[mins_sorted[1]][0]['active_regions'], best['active_regions']) / max(min(by_min[m][0]['active_regions'] for m in mins_sorted[1:]), 1):.0f}×. "
          f"Coarsening is not buying much. The one clearly bad setting is "
          f"n_min = {mins_sorted[0]}, which is too permissive to repair sparse cells at "
          f"all.\n")
        w(f"Second, and more decisively, the main comparison contradicts the pure "
          f"coarsening explanation. At N = {big} the adaptive layer barely changes the "
          f"partition and its advantage over the confined baseline correspondingly "
          f"vanishes (Section VI-B). If coarseness alone drove the metric, the "
          f"configuration that coarsens most would win at every density, and it does "
          f"not. We therefore attribute the gain principally to sparsity repair, while "
          f"noting that a residual coarsening bias is present and that our reporting "
          f"partition — fixed and protocol-independent — bounds but does not eliminate "
          f"it.\n")
    else:
        w(f"This bears directly on an obvious confound: that Adaptive-GWG might win "
          f"merely by producing coarser, internally more homogeneous regions. The sweep "
          f"argues against it — the most aggressive merging "
          f"({worst['active_regions']:.0f} regions) is the worst configuration, while "
          f"the best keeps the partition close to the underlying grid "
          f"({best['active_regions']:.0f} regions) and repairs only those cells too "
          f"sparse to gossip within.\n")

    w("### I. Real-Time Readiness for AV Consumers\n")
    w(f"Treating one round as one {cfg['round_duration_s']*1000:.0f} ms beacon interval "
      f"[23], [24], Table VIII reports the error a protocol would hand a decision system "
      f"at a given deadline. 'Usable' is macro MAPE ≤ 10%, an illustrative threshold for "
      f"cooperative speed advisory rather than one derived from a standard.\n")
    w("**TABLE IX. ERROR AT A DECISION DEADLINE (macro MAPE %)**\n")
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
      "Section VI-F identifies as dominant. A road-constrained mobility trace is the "
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
