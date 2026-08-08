# What Actually Makes Geo-Weighted Gossip Regional: An Ablation of Region-Aware Push-Sum for Vehicular Networks

**Fatima Ali**, **Asma Imran**, **Adeena Reeham**
School of Electrical Engineering and Computer Science
National University of Sciences and Technology, Islamabad, Pakistan
`fali.bscs23seecs@seecs.edu.pk` · `achaudry.bscs23seecs@seecs.edu.pk` · `adeenareeham441@gmail.com`

> **Status.** Sections I–IV and VIII are complete. Sections V–VII are generated from
> `results/results.json`, which is written by `src/gwg_simulation.py`. Every number below
> is traceable to that file; none are transcribed by hand. See `paper/NUMBERS.md` for the
> claim-to-evidence map.
>
> **Title decided.** The paper previously ran under *Adaptive Region-Aware Geo-Weighted
> Push-Sum Gossip for Highly Mobile Vehicular Networks*, which names the adaptive layer as
> the contribution — a claim Section VI-B does not support, since the improvement belongs
> to region confinement, with adaptation contributing nothing measurable. The team has
> settled on the title above, which matches the finding and frames the ablation as the
> contribution it is. It also fits a reproducibility or measurement-focused venue better,
> where a well-controlled negative result is the point rather than a disappointment.

---

## Abstract

Vehicle fleets — human-driven delivery and ride-hailing fleets, and increasingly
autonomous vehicles — need a live estimate of how fast traffic is moving in their own
part of a city, without routing every position report through a central server that
becomes a single point of failure, a bandwidth bottleneck, and a privacy liability.
Gossip-based averaging is the natural decentralized answer, but the existing protocols
each miss something: plain gossip ignores geography and provably converges to one
network-wide number rather than a per-region one; geographic gossip was designed for a
static sensor field and likewise computes a single global average; and VANET clustering
produces mobility-aware groups but is evaluated on how long a cluster survives, not on
whether anything computed inside it is accurate.

This paper studies Adaptive Region-Aware Geo-Weighted Push-Sum Gossip (Adaptive-GWG), a
leaderless protocol combining inverse-distance-weighted peer selection, directional
push-sum aggregation, and a region layer that merges sparse regions and splits dense ones
as vehicle density changes, with no vehicle acting as a coordinator. Our central
contribution is an ablation that this line of work — including our own earlier version of
it — does not report: we separate *confining gossip to a region* from *adapting the
region to density*, because the two are routinely bundled and only the second is claimed
as novel.

Evaluating on 12.87 million real speed samples from the NYC TLC Yellow Taxi record with
vehicles in continuous motion, we find that **region confinement accounts for the entire
improvement**. Restricting peer selection to the sender's own grid cell — a one-line
change to the fixed-grid baseline — reduces per-region error by 48–57% at realistic
densities. Adding density-driven region adaptation on top of that delivers no measurable
further benefit (−0.1% to −3.3%, with overlapping confidence intervals at every fleet
size) while adding control traffic; the best-performing threshold setting is the one that
changes the partition least. We further show that geographic weighting alone buys
locality of *communication* but not of *estimation*: it cuts mean hop distance by 84%
while leaving 68.9% of exchanges crossing region boundaries and accuracy nearly
unchanged. Finally, we identify a drift failure mode specific to running push-sum on a
mobile fleet, in which re-initialization at region boundaries progressively refills a
region with unaveraged readings and degrades error roughly fourfold from its minimum, and
show that periodic restart bounds it — while leaving unconfined gossip untouched,
confirming that its error floor is structural rather than a matter of scheduling.

**Index Terms** — gossip protocols, distributed averaging, push-sum, geographic gossip,
consensus, VANET, adaptive clustering, autonomous vehicles, cooperative perception,
Intelligent Transportation Systems.

---

## I. Introduction

### A. Motivation and Problem Statement

Consider a ride-hailing or delivery fleet with thousands of vehicles moving across a
city, or a fleet of autonomous vehicles planning routes through it. Both need the same
thing: a live, *local* estimate of average speed, to drive congestion warnings,
rerouting, and dispatch. The obvious design routes every vehicle's report to a central
server, and it fails in familiar ways. If the server goes down the whole fleet loses its
shared picture of traffic. As the fleet grows the server becomes a bandwidth bottleneck
and eventually a scalability ceiling. And centralizing raw location traces creates
privacy and jurisdictional exposure that most operators would rather not carry.

So: can a fleet work this out for itself, using only local peer-to-peer exchanges, with
no central coordinator, without falling apart as vehicles move between zones and drop in
and out of range?

The question is sharper than it first appears, because the quantity wanted is *regional*.
A fleet-wide average speed is close to useless for rerouting — it smears a congested
downtown together with a free-flowing ring road. What a dispatcher or a route planner
needs is a per-zone estimate. This matters because the standard gossip-averaging
guarantee delivers the wrong thing: push-sum over a connected graph converges to the
average over that graph. If the gossip graph spans the whole city, every vehicle
converges to the *city-wide* mean, and the regional structure that motivated the exercise
is exactly what gets averaged away. Any regional protocol must therefore control which
pairs of vehicles are allowed to exchange mass, and it must do so while the vehicles are
moving between regions.

### B. Contributions

1. **A region-confinement analysis of geo-weighted push-sum.** We show that
   inverse-distance peer weighting, on its own, does not produce regional estimates —
   it shortens hops while still leaking mass across region boundaries, leaving an
   irreducible error floor. Confining exchanges to a region removes the floor. This is a
   small change to the protocol with a large effect, and it is the correct baseline
   against which any region-management scheme must be judged.

2. **A negative result on adaptive region management, from a controlled ablation.**
   Regions merge when sparse and split when dense, with no leader and no election.
   Isolated against a region-confined fixed grid, this mechanism delivers no measurable
   accuracy benefit at any fleet size we tested, while adding control traffic. The
   threshold sweep supplies the mechanism rather than merely the result: the optimum lies
   at the boundary of doing nothing, and accuracy degrades monotonically as merging grows
   more aggressive. We state the scope of this negative result carefully in Section VI-B —
   it holds for a grid already well matched to radio range and a roughly uniform vehicle
   distribution, which is the setting the protocol was designed and previously evaluated
   for.

3. **A drift failure mode for push-sum on a mobile fleet, and its remedy.**
   Re-initialization at region boundaries injects unaveraged weight-1 mass into regions
   where push-sum has concentrated mass, so error reaches a minimum after a few rounds
   and then degrades roughly fourfold. Periodic restart bounds it. Diagnostically, the
   remedy does nothing at all for unconfined gossip, which is the cleanest evidence we
   have that its error floor is a wrong-target problem rather than a convergence-rate one.

4. **Evaluation under mobility and churn, with the cost of adaptation charged to the
   protocol.** Vehicles move every round, cross region boundaries, and join and leave.
   Region-change announcements are counted against Adaptive-GWG's own bandwidth budget,
   so the accuracy/overhead trade-off is visible rather than assumed away.

5. **A reproducible artifact.** Every figure and table is regenerated by one command
   from real NYC TLC data; a test suite pins the protocol properties the analysis
   depends on (mass conservation, directional push-sum, merge correctness, metric
   validity); and the evaluation partition is protocol-independent, so no protocol can
   improve its own score by redefining what a region is.

Contribution 5 is not decoration. In the course of this work we audited an earlier
version of our own harness and found that its headline result did not survive: the
reported gains were attributable to region confinement rather than to adaptation, one
fleet size showed a large "win" from an adaptive rule that had relabelled zero vehicles,
and each protocol had been scored against its own partition of the fleet. The audit
scripts that establish this are included in the repository. We consider the resulting
narrower claim more useful than the broader one it replaces.

### C. Applicability to Autonomous and Connected Vehicle Fleets

Although we frame the problem around logistics fleets, it applies equally to autonomous
vehicles. Current AV stacks already broadcast position, heading, and speed to nearby
vehicles via V2X cooperative awareness messages (CAM) and basic safety messages (BSM),
so the peer-to-peer link Adaptive-GWG needs already exists. Cooperative perception —
where nearby AVs share what they sense to build a fuller picture than any single
vehicle's sensors provide — is structurally the same problem as per-zone aggregation,
with the same churn as vehicles enter and leave a neighbourhood at speed.

To be clear about scope: Adaptive-GWG is a decision-support layer for routing and
congestion detection, not a replacement for the collision-avoidance messaging that
dedicated V2X safety layers handle. Push-sum offers eventual consistency, which suits
decision support and does not meet the deterministic latency bound safety-critical
messaging requires.

---

## II. Related Work

### A. Gossip-Based Aggregation and Consensus

Gossip-based aggregation goes back to the epidemic replication protocols of Demers et
al. [1], sharpened by Karp et al.'s push-pull analysis [2]. Kempe, Kleinberg, and Demers
[3] were among the first to bias peer selection by distance, showing that a power-law
decay keeps convergence nearly as fast as uniform gossip while using far less
long-distance bandwidth. Kempe, Dobra, and Gehrke [4] extended gossip from spreading
rumors to computing aggregates through push-sum: each node keeps a `(value, weight)`
pair, pushes half of it to a partner each round while retaining the other half, and
because the network-wide sum is invariant, every node's ratio provably converges to the
true average. How fast this happens depends on the spectral gap of the gossip matrix
[4], [5], [6], a quantity that recurs throughout this literature.

The direction of the exchange matters more than it might appear. A symmetric exchange in
which both endpoints end holding the same `(value, weight)` pair leaves every weight
pinned at its initial value, degenerating to plain pairwise averaging [6]; the weight
only carries information when mass moves asymmetrically. We flag this because it is an
easy implementation error, and one we made in an earlier version of this work.

The closest prior work is Dimakis, Sarwate, and Wainwright's Geographic Gossip [7]. The
problem they address is that plain gossip spends almost all of its communication budget
on partners already close in the network graph, so a flat sensor field can need close to
Θ(n) rounds before every node's running average is even roughly correct. Their fix
combines geographic routing, to reach a distant partner in a few hops, with push-sum
averaging to combine values once that partner is found. On a random geometric graph this
reduces the rounds needed for ε-accuracy from Θ(n) to O(√n log n), and it is one of the
earliest protocols to combine geographic awareness with averaging in a single mechanism.
But it was evaluated only on static sensor fields, it computes one global average rather
than per-region estimates, and it has no concept of a region that can grow, shrink,
split, or merge.

Adaptive-GWG selects partners differently: rather than routing toward a randomly chosen
geographic target and then gossiping locally, it performs inverse-distance-weighted
selection directly among vehicles already reachable within a region, so closer peers are
contacted more often with no routing step. We also replace the single flat average with
per-region push-sum tracks, so dense and sparse parts of a city converge on their own
terms instead of being folded into one city-wide number. It is worth being precise about
what this buys: as Section VI shows, the geographic weighting alone shortens hops
substantially but does *not* by itself produce regional estimates, because weighted
selection still reaches across region boundaries. Confinement, not weighting, is what
makes the estimates regional.

Closer to our setting, Wei et al. study gossip inside a VANET rather than a static sensor
field [8]. Their concern sits one layer below ours: before a vehicle can gossip with
anyone it must work out who its current neighbours are, which is harder in a VANET than
in a fixed deployment because the neighbour set changes every few seconds as vehicles
overtake, turn, or drop out of range. Their GSIM-ND algorithm disseminates presence
information through gossip, incorporates sensing supplied by roadside units, and exploits
multi-packet reception, converging 40–90% faster than random, scan-based, or plain gossip
discovery. This complements our work rather than competing with it: Wei et al. solve
partner discovery, while Adaptive-GWG assumes that problem solved and addresses what
happens once a partner is found — how the shared value is combined and how the region
itself grows or shrinks. Their protocol depends on roadside-unit coverage and stops once
neighbours are found; it aggregates no shared quantity and has no notion of a region, so
the two lines sit at different layers and could plausibly be combined, with GSIM-ND
handling discovery and Adaptive-GWG handling aggregation.

Broadcast Gossip [9] and the consensus literature [10], [11], [12] generalize the same
averaging idea to broadcast channels and to directed, time-varying topologies, which
supplies a connectivity argument — joint connectivity over time — that fits vehicular
mobility reasonably well. Almost all of this work, however, is evaluated on small
multi-agent testbeds rather than at the scale or density of real vehicle traffic.

### B. VANET Clustering and Region Management

VANET clustering borrows its vocabulary from MANET routing, particularly Jiang et al.'s
CBRP [13], where an elected cluster head handles membership and inter-cluster routing.
Mukhtaruzzaman and Atiquzzaman's survey [14] groups the VANET clustering that followed
into intelligence-based, mobility-based, and multi-hop families. All are judged on the
same kind of metric — how long a cluster head lasts, how often clusters re-form, how
much control overhead this costs — and not on whether anything computed inside the
cluster is accurate.

Two region-based, density-aware protocols come closest to what we mean by adaptive
regions. SDPC [15] predicts where a vehicle will be a few seconds ahead, including
whether it is about to pass through an intersection, and uses that to select cluster
heads likely to remain stable longest. RCMS [16] models connectivity and inter-cluster
overlap jointly, grouping vehicles to minimize redundant coverage while keeping the
network connected. Both adapt to density and mobility in real time, which is the
behaviour we need, but neither gossips or aggregates anything, neither reasons about
convergence as the gossip literature does, and neither has a split/merge rule that is
not effectively a re-run of cluster-head election.

### C. Geographic Routing, Geocast, and Edge Infrastructure

Greedy Perimeter Stateless Routing [17] and geographic hash tables [18] provide the basic
tools for addressing a location or a region, but both are built to deliver a single
message to a destination, not to refine a running estimate through repeated exchange.
Edge, fog, and blockchain proposals for the Internet of Vehicles [19], [20] address a
different problem — trust, offloading, monetization. These are useful concerns but
largely orthogonal to whether an aggregate computed across a region is accurate, and
on-chain consensus is in any case far too slow for the sub-second budget a vehicular
protocol works within.

### D. Research Gap

Table I positions the families discussed above against the properties Adaptive-GWG
needs: no leader, tolerance for mobility, geographic awareness, regions that adapt, and
an averaging guarantee.

**TABLE I. COMPARATIVE POSITIONING OF RELATED WORK**

| Family | Leaderless | Mobility tol. | Geo-aware | Adaptive regions | Averaging guarantee |
|---|---|---|---|---|---|
| Push-sum / consensus [4], [10], [11] | Yes | Limited | No | No | Yes |
| Geographic Gossip [7] | Yes | No (static) | Yes | No | Yes (global only) |
| VANET gossip / neighbour discovery [8] | Yes | Yes | Partial (RSU-assisted) | No | No |
| VANET clustering [13], [14] | No | Yes | Partial | No | No |
| Region-based adaptive (SDPC/RCMS) [15], [16] | No | Yes | Yes | Yes | No |
| **Adaptive-GWG (this paper)** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes (per-region)** |

Push-sum and its relatives have the averaging guarantee but no adaptive regions.
VANET-specific gossip work is mobility-tolerant and partly geo-aware through roadside
sensing, but stops at neighbour discovery and never aggregates. Region-based VANET
clustering has adaptive, mobility-tolerant regions but no averaging guarantee. We found
nothing with all five properties at once.

This picture matches the wider VANET dissemination literature. Shahwani et al.'s survey
[21] organizes push- and pull-based dissemination schemes, including several gossip and
epidemic-style methods, around delay, reliability, and overhead trade-offs for
*delivering a message* — not around producing a statistically accurate aggregate. None
of the schemes it catalogs update a running estimate the way push-sum does, and none
treat region formation as something that adapts to density. This is a useful external
check on our reading: the gap is not an artifact of which papers we happened to place in
Table I, but a genuine split between how the dissemination and mobility-management
communities frame the problem.

The gap is therefore in how these pieces fit together rather than in any single missing
piece; every individual component already exists somewhere. What is missing is a protocol
that treats density-driven regional decomposition as part of the aggregation mechanism's
own convergence story, rather than as something handed to it by an external clustering
algorithm, or ignored entirely by treating the network as one graph. That is the gap
Adaptive-GWG addresses — and, as Section VI reports, closing it turns out to deliver less
than one might assume, for reasons we believe are more informative than a larger headline
number would have been.

---

## III. System Model

### A. Network and Mobility Model

We model a service area of side *L* partitioned into a *G* × *G* lattice of square cells
of side *s*, so *L* = *G·s*. A fleet of *N* vehicles occupies this area. Vehicle *i* has
position **p**ᵢ(t) = (xᵢ(t), yᵢ(t)) and a heading θᵢ(t) that evolves as a random walk,
θᵢ(t+1) = θᵢ(t) + ηᵢ, with ηᵢ ~ 𝒩(0, σ²θ). Vehicles reflect off the service-area boundary.
Each round advances wall-clock time by Δt, and vehicle *i* travels vᵢ(t)·Δt metres along
its heading, where vᵢ(t) is its own current speed. Mobility is therefore not a separate
parameter to be tuned: vehicles move at the speeds the protocol is estimating.

Two vehicles may exchange messages when ‖**p**ᵢ − **p**ⱼ‖ ≤ *R*, the V2X radio range. The
communication graph 𝒢(t) = (V, E(t)) with E(t) = {(i,j) : ‖**p**ᵢ − **p**ⱼ‖ ≤ R} is
therefore time-varying, and neither its connectivity nor its degree distribution is
assumed constant.

### B. Observation Model

Each vehicle observes a local speed vᵢ(t). We model this as a base draw bᵢ from the
empirical distribution of real trip speeds (Section V-A), modulated by a spatial
congestion field c(·) evaluated at the vehicle's current cell:

> vᵢ(t) = clip( bᵢ · c(cell(**p**ᵢ(t))), v_min, v_max )

with c(·) rising monotonically from the congested centre of the service area to its
free-flowing periphery. This is what makes the problem regional: without a spatial field,
the per-region means are all equal in expectation and any protocol, including one that
computes the global average, appears correct. The congestion field is the minimal
structure needed for a regional estimator to be distinguishable from a global one.

Because vᵢ depends on **p**ᵢ(t), a vehicle's observation changes as it drives between
zones. The estimation target is therefore non-stationary from any individual vehicle's
point of view, while the *regional* means remain stable — which is precisely the
tracking problem a fleet faces.

### C. Churn Model

At each round, every vehicle independently departs with probability ρ and is replaced by
a newly arrived vehicle at a uniformly random position with a fresh speed draw, holding
*N* constant. A departing vehicle takes whatever push-sum mass it holds with it. This is
not an artifact of the model: push-sum conserves mass only over a fixed population, so
churn is exactly the condition under which its accuracy guarantee is stressed, and it
must be measured rather than assumed benign.

### D. Problem Statement

Let 𝒫 = {P₁, …, P_K} be a partition of the service area into *reporting regions*, and let
Vₖ(t) = {i : **p**ᵢ(t) ∈ Pₖ} be the vehicles in region *k* at time *t*. The true regional
average is

> μₖ(t) = (1/|Vₖ(t)|) · Σ_{i ∈ Vₖ(t)} vᵢ(t)

Each vehicle maintains an estimate v̂ᵢ(t). The objective is that every vehicle's estimate
tracks the average of the region *it is currently in*:

> minimize  (1/K) · Σₖ (1/|Vₖ(t)|) · Σ_{i ∈ Vₖ(t)} |v̂ᵢ(t) − μₖ(t)| / μₖ(t)

subject to (i) no vehicle acting as coordinator, aggregator, or cluster head; (ii)
exchanges only along edges of 𝒢(t); and (iii) O(1) state and O(1) messages per vehicle
per round.

Two points about this formulation matter for the evaluation. First, the outer average
over regions weights every region equally regardless of population — a macro-average —
so a protocol cannot score well by serving dense regions and neglecting sparse ones.
Second, and critically, **𝒫 is fixed and protocol-independent**. A protocol's internal
notion of a region is free to differ from 𝒫; it is still scored against 𝒫. Without this
constraint a protocol can lower its own reported error simply by merging cells into
larger, internally more homogeneous regions, which measures the coarseness of its
partition rather than the quality of its estimates.

### E. Notation

| Symbol | Meaning |
|---|---|
| N | fleet size |
| G, s, L | grid dimension, cell side, service-area side (L = G·s) |
| R | V2X radio range |
| Δt | round duration (one beacon interval) |
| vᵢ(t), v̂ᵢ(t) | vehicle *i*'s true and estimated speed |
| (yᵢ, wᵢ) | vehicle *i*'s push-sum value and weight |
| 𝒫, Pₖ, μₖ | reporting partition, region *k*, its true mean |
| ℛᵢ(t) | vehicle *i*'s protocol-assigned region |
| ρ | per-round churn probability |
| n_min, n_max | merge and split thresholds |
| τ | region-refresh interval, in rounds |

---

## IV. Proposed Method: Adaptive-GWG

Adaptive-GWG runs three mechanisms concurrently on every vehicle, with no coordinator at
any level. Each round, a vehicle (1) updates its region label from local density, (2)
selects a peer by inverse-distance weighting within that region, and (3) performs one
directional push-sum exchange.

### A. Push-Sum Aggregation

Each vehicle *i* maintains a value yᵢ and a weight wᵢ, initialized to yᵢ = vᵢ and wᵢ = 1,
with estimate v̂ᵢ = yᵢ / wᵢ. When *i* gossips with peer *j* it retains half of its mass and
pushes the other half:

> yᵢ ← yᵢ/2,  wᵢ ← wᵢ/2
> yⱼ ← yⱼ + yᵢ/2,  wⱼ ← wⱼ + wᵢ/2

The sums Σyᵢ and Σwᵢ are invariant, so over a connected exchange graph every ratio
converges to the mass-weighted mean [4]. The asymmetry is essential and is what
distinguishes push-sum from pairwise averaging: if instead both endpoints ended holding
the same pair, every weight would remain at 1 for the entire run and the weight channel
would carry no information at all. We state this explicitly because it is an easy error
to make silently — `tests/test_gwg.py::test_push_sum_is_directional` exists to prevent it.

**Re-initialization on region change.** When a vehicle's region label changes — because it
drove across a boundary, or because the region layer re-partitioned around it — the mass
it holds belongs to its former region. Carrying that mass forward would inject one
region's average into another. The vehicle therefore resets to (yᵢ, wᵢ) = (vᵢ, 1). This
sacrifices strict global mass conservation in exchange for correct regional attribution,
and it is the dominant cost of mobility in our results: every boundary crossing discards
accumulated averaging work. All protocols compared here pay this cost under the same rule.

**Periodic restart.** Re-initialization interacts badly with push-sum's tendency to
concentrate mass on a few holders. A vehicle that resets injects fresh weight-1 mass into
a region whose accumulated weight sits elsewhere; as crossings accumulate, the region's
weight fills up with unaveraged single readings and the estimate drifts back toward
precisely the raw measurement the protocol exists to improve on. Measured over 150 rounds
this is not a subtle effect — the error reaches a minimum after a handful of rounds and
then degrades several-fold (Section VI-E).

Every vehicle therefore restarts its accumulator on a fixed schedule, every τ_r rounds,
which bounds how much drift can accumulate. Restart is local and requires no coordination:
the schedule is a constant, not a negotiated epoch, so it introduces no leader and no
synchronization messages. Periodic restart is the standard remedy for running push-sum on
time-varying input, and we apply it identically to all four protocols so that it cannot
favour ours. Section VI-E reports the sweep that sets τ_r, and — more usefully — shows
that restart does nothing for the unconfined baselines, because staleness was never what
was wrong with them.

### B. Geo-Weighted Peer Selection

Vehicle *i* selects peer *j* from its candidate set 𝒞ᵢ(t) with probability

> Pr[j] = (1 / max(dᵢⱼ, d₀)) / Σ_{k ∈ 𝒞ᵢ(t)} (1 / max(dᵢₖ, d₀))

where dᵢⱼ = ‖**p**ᵢ − **p**ⱼ‖ and d₀ = 1 m regularizes the near field. Inverse-distance
weighting biases exchange toward nearby vehicles, shortening the geographic hop each
message travels — which in a real deployment translates into lower transmit power,
less interference, and fewer relayed hops.

The candidate set is what distinguishes the protocol variants we compare:

| Variant | 𝒞ᵢ(t) |
|---|---|
| Uniform Random Gossip | all vehicles, ignoring geography |
| Fixed GWG | all vehicles within radio range R |
| Fixed GWG (region-confined) | vehicles within R **and** in *i*'s own fixed cell |
| Adaptive-GWG | vehicles within R **and** in *i*'s own adaptive region |

The third row is the ablation. It is not a strawman but the strongest simple baseline we
could construct, and separating it from the fourth row is what allows the contribution of
the adaptive layer to be measured rather than assumed. Confined variants fall back to the
full radio neighbourhood when fewer than two same-region peers are reachable, so an
isolated vehicle is never silenced.

### C. Adaptive Region Management

Every τ rounds, each vehicle recomputes its region label from the density it observes
locally. Let Cₖ be the vehicle set of fixed cell *k*:

- **Split.** If |Cₖ| > n_max, the cell is divided into four quadrant sub-regions about its
  centre. Dense downtown cells are thereby resolved more finely, so a single cell cannot
  average a congested block together with a clear one.
- **Merge.** If |Cₖ| < n_min, its vehicles *join* the nearest established region, adopting
  that region's label so that the two groups genuinely pool their readings. A merge that
  assigns the sparse group a fresh label of its own does not merge anything — it creates
  a second small region — and
  `tests/test_gwg.py::test_merge_actually_merges` guards against this.
- **Otherwise** the cell is retained unchanged.

When density is low enough that no cell qualifies as a merge target, sparse units are
agglomerated with their nearest neighbours until each pooled region reaches n_min or a
single region remains. This is the regime the merge rule was designed for; Section VI-B
reports that even here it does not outperform simply leaving the grid alone.

The rule is leaderless: it is a deterministic function of locally observable density, so
every vehicle in a cell computes the same label without negotiation, election, or a
designated head. There is no head to fail and none to compromise. Each vehicle whose
label changes announces it to its neighbourhood, and we charge those announcements to
Adaptive-GWG's bandwidth budget (Section VI-D) — a protocol that adapts is not free, and
reporting it as free would make the accuracy comparison meaningless.

### D. Complexity

Per vehicle per round: one push-sum message (O(1) state, a `(value, weight, position,
timestamp)` payload), a peer draw over the reachable neighbourhood, and — every τ rounds
— a density count over the same neighbourhood. State is O(1) in fleet size. The region
rule requires no global view: a vehicle needs only the count of vehicles in its own cell,
which the V2X beacons it already receives supply.

### E. Design Rationale and Limits of the Guarantee

Push-sum's convergence guarantee holds over a connected graph with fixed membership.
Adaptive-GWG satisfies neither condition exactly: confinement deliberately disconnects
the exchange graph into per-region components (that is the point — it is what makes the
estimate regional rather than global), and mobility and churn change component membership
continuously. What the protocol inherits is therefore a per-region guarantee that holds
between re-partitioning events, over intervals in which a region's membership is stable
and its induced subgraph connected. The empirical question — how much accuracy survives
when those intervals are short — is what Sections VI-B and VI-E measure. We prefer to
state this plainly rather than to claim an unconditional guarantee that the mobility model
does not support.

---

## V. Experimental Setup

*[Generated from `results/results.json` — see `paper/RESULTS.md`.]*

## VI. Results and Discussion

*[Generated from `results/results.json` — see `paper/RESULTS.md`.]*

## VII. Limitations and Threats to Validity

*[Generated from `results/results.json` — see `paper/RESULTS.md`.]*

---

## VIII. Conclusion

We set out to give a vehicle fleet a live, per-region estimate of traffic speed with no
central server and no cluster head, and — the part that turned out to matter — to
establish how much of the resulting improvement is attributable to each mechanism rather
than to the combination.

The answer is that **region confinement does the work**. Restricting gossip to the
sender's own cell reduces per-region error by 48–57% at realistic densities. Adding
density-driven region adaptation on top of that contributes nothing measurable: the gains
are −0.1% to −3.3%, the confidence intervals overlap at every fleet size, and the best
threshold configuration is the one that leaves the partition closest to untouched. The
improvement previously reported for adaptive regions — including in our own earlier
version of this work — is real, but it belongs to confinement, and it appeared to belong
to adaptation only because the comparison was against gossip free to cross region
boundaries.

A second finding is worth as much as the first, and it is easy to miss without the
ablation. Geographic weighting cuts the distance a message travels by 84% and barely
improves accuracy at all. It buys locality of *communication*, not locality of
*estimation*. This is genuinely counter-intuitive — a protocol that talks only to nearby
vehicles feels as though it should produce a local answer — but the exchange graph stays
connected across the whole service area, and push-sum mass flows along it however short
each individual hop is. 68.9% of Fixed GWG's exchanges cross a region boundary, and no
number of additional rounds repairs a wrong target. Periodic restart demonstrates the same
point from the other side: it improves the confined protocols roughly fourfold and leaves
the unconfined ones essentially unchanged, because staleness was never what was wrong
with them.

We want to be careful about the scope of the negative result. Our grid is already well
matched to radio range, every cell lies inside its own members' communication radius, and
vehicles are close to uniformly distributed — conditions under which adaptation has
little to repair. A deployment with badly sized cells, or density varying by orders of
magnitude across the map, is a different setting that this evaluation does not cover. The
defensible claim is narrower and, we think, more useful: in the setting this protocol was
designed and previously evaluated for, adaptive region management is not what makes it
work, and any future proposal in this space should report a region-confined fixed grid as
a baseline before claiming otherwise.

Three directions follow. First, the merge and split thresholds are driven by vehicle
count; driving them instead by observed estimate variance would let a region adapt to the
heterogeneity of what it is measuring rather than to how many vehicles happen to be
inside it, which is the version of adaptation our results do not rule out. Second,
re-initialization discards accumulated averaging on every boundary crossing and is the
mechanism behind both the mobility penalty and the drift failure mode; transferring
partial mass between regions in proportion to residence time, or expiring mass on an age
bound rather than only at a boundary, would address both at once. Third, pairing this
work with a VANET neighbour-discovery layer such as GSIM-ND [8] would close the loop
between finding a partner and deciding what to compute with one — adjacent layers that
have so far been studied separately.

---

## Reproducing this paper

```bash
python3 -m venv venv && source venv/bin/activate
pip install pandas pyarrow numpy matplotlib

# 1. real data -> data/processed/nyc_speeds.npy
python3 src/extract_speeds.py

# 2. all experiments -> results/results.json + results/figures/*.png
python3 src/gwg_simulation.py

# 3. protocol correctness
python3 tests/test_gwg.py

# 4. the audit that motivated the rewrite (runs against the archived v1)
python3 scripts/audit_baseline_claims.py
python3 scripts/audit_ablation.py
```

---

## References

[1] A. Demers, D. Greene, C. Hauser, W. Irish, J. Larson, S. Shenker, H. Sturgis, D.
Swinehart, and D. Terry, "Epidemic algorithms for replicated database maintenance," in
*Proc. ACM PODC*, 1987, pp. 1–12.

[2] R. Karp, C. Schindelhauer, S. Shenker, and B. Vöcking, "Randomized rumor spreading,"
in *Proc. IEEE FOCS*, 2000, pp. 565–574.

[3] D. Kempe, J. Kleinberg, and A. Demers, "Spatial gossip and resource location
protocols," in *Proc. ACM STOC*, 2001, pp. 163–172.

[4] D. Kempe, A. Dobra, and J. Gehrke, "Gossip-based computation of aggregate
information," in *Proc. IEEE FOCS*, 2003, pp. 482–491.

[5] S. Boyd, A. Ghosh, B. Prabhakar, and D. Shah, "Gossip algorithms: Design, analysis
and applications," in *Proc. IEEE INFOCOM*, 2005, pp. 1653–1664.

[6] S. Boyd, A. Ghosh, B. Prabhakar, and D. Shah, "Randomized gossip algorithms," *IEEE
Trans. Information Theory*, vol. 52, no. 6, pp. 2508–2530, 2006.

[7] A. D. Dimakis, A. D. Sarwate, and M. J. Wainwright, "Geographic gossip: Efficient
averaging for sensor networks," *IEEE Trans. Signal Processing*, vol. 56, no. 3, pp.
1205–1216, 2008.

[8] Z. Wei, Q. Chen, H. Yang, H. Wu, Z. Feng, and F. Ning, "Neighbor discovery for VANET
with gossip mechanism and multipacket reception," *IEEE Internet of Things Journal*, vol.
9, no. 13, pp. 10502–10515, Jul. 2022.

[9] T. C. Aysal, M. E. Yildiz, A. D. Sarwate, and A. Scaglione, "Broadcast gossip
algorithms for consensus," *IEEE Trans. Signal Processing*, vol. 57, no. 7, pp.
2748–2761, 2009.

[10] R. Olfati-Saber and R. M. Murray, "Consensus problems in networks of agents with
switching topology and time-delays," *IEEE Trans. Automatic Control*, vol. 49, no. 9, pp.
1520–1533, 2004.

[11] W. Ren and R. W. Beard, "Consensus seeking in multiagent systems under dynamically
changing interaction topologies," *IEEE Trans. Automatic Control*, vol. 50, no. 5, pp.
655–661, 2005.

[12] R. Olfati-Saber, J. A. Fax, and R. M. Murray, "Consensus and cooperation in
networked multi-agent systems," *Proc. IEEE*, vol. 95, no. 1, pp. 215–233, 2007.

[13] M. Jiang, J. Li, and Y. C. Tay, "Cluster based routing protocol (CBRP) functional
specification," IETF MANET Working Group, Internet-Draft, 1999.

[14] M. Mukhtaruzzaman and M. Atiquzzaman, "Clustering in vehicular ad hoc network:
Algorithms and challenges," *Computers & Electrical Engineering*, vol. 88, art. 106851,
2020.

[15] M. Mukhtaruzzaman and M. Atiquzzaman, "Stable dynamic feedback-based predictive
clustering protocol for vehicular ad hoc networks," *Computer Networks*, vol. 235, art.
109960, 2023.

[16] B. Liu, Z. Fang, W. Wang, X. Shao, W. Wei, D. Jia, E. Wang, and S. Xiong, "A
region-based collaborative management scheme for dynamic clustering in green VANET,"
arXiv:2110.02565, 2021.

[17] B. Karp and H. T. Kung, "GPSR: Greedy perimeter stateless routing for wireless
networks," in *Proc. ACM/IEEE MobiCom*, 2000, pp. 243–254.

[18] S. Ratnasamy, B. Karp, L. Yin, F. Yu, D. Estrin, R. Govindan, and S. Shenker, "GHT:
A geographic hash table for data-centric storage," in *Proc. ACM WSNA*, 2002, pp. 78–87.

[19] A. Queiroz, E. Oliveira, M. Barbosa, and K. Dias, "A survey on blockchain and edge
computing applied to the Internet of Vehicles," in *Proc. IEEE ANTS Workshops*, 2020.

[20] M. B. Mollah, J. Zhao, D. Niyato, Y. L. Guan, C. Yuen, S. Sun, K.-Y. Lam, and L. H.
Koh, "Blockchain for the Internet of Vehicles towards intelligent transportation systems:
A survey," *IEEE Internet of Things Journal*, vol. 8, no. 6, pp. 4157–4185, 2021.

[21] H. Shahwani, S. A. Shah, M. Ashraf, M. Akram, J. Jeong, and J. Shin, "A
comprehensive survey on data dissemination in vehicular ad hoc networks," *Vehicular
Communications*, vol. 34, art. 100420, 2022.

[22] NYC Taxi and Limousine Commission, "TLC Trip Record Data," 2026. [Online].
Available: https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page

[23] ETSI, "Intelligent Transport Systems (ITS); Vehicular Communications; Basic Set of
Applications; Part 2: Specification of Cooperative Awareness Basic Service," ETSI EN 302
637-2 V1.4.1, 2019.

[24] SAE International, "V2X Communications Message Set Dictionary," SAE J2735, 2020.
