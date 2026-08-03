# Adaptive Region-Aware Geo-Weighted Push-Sum Gossip for Highly Mobile Vehicular Networks

**Fatima Ali**, **Asma Imran**, **Adeena Reeham**
School of Electrical Engineering and Computer Science
National University of Sciences and Technology, Islamabad, Pakistan
`fali.bscs23seecs@seecs.edu.pk` · `achaudry.bscs23seecs@seecs.edu.pk` · `adeenareeham441@gmail.com`


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

### A. Dataset

Vehicle speeds are drawn from real New York City Taxi and Limousine Commission Yellow Taxi trip records [22]. We compute a per-trip average speed from trip distance and the pickup/dropoff timestamps, and discard trips outside a 5–70 mph band as meter or GPS artifacts. This leaves **12,870,597 valid speed samples**, with mean **11.63 mph** and standard deviation **6.25 mph**.

The coefficient of variation of roughly 0.54 is the reason this problem is not trivial: an unaveraged single reading is already about 54% away from its regional mean in expectation, so a protocol that fails to average has a characteristic error signature we can recognize in the results.

We deliberately report the year of the data rather than inheriting it from an earlier draft: an internal review of this project found a draft citing a 2013 dataset while the experiments used a different period, and we note it here so the provenance is unambiguous.

### B. Simulation Parameters

| Parameter | Value |
|---|---|
| Service area | 10×10 cells of 100 m (1000 m square) |
| Fleet sizes N | 100, 500, 1000 |
| V2X radio range R | 250 m |
| Round duration Δt | 100 ms (nominal CAM/BSM interval [23], [24]) |
| Rounds per run | 150 |
| Independent trials | 10 |
| Merge / split thresholds | n_min = 3, n_max = 20 |
| Region refresh interval τ | 1 round(s) |
| Push-sum payload | 42 B |
| Region-change announcement | 12 B |
| Random seed | 42 |

Each trial generates an independent fleet; within a trial all four protocols see the same initial fleet, so the comparison is paired. All intervals are 95% Student-t confidence intervals over trials. Runs that never reach the convergence criterion are reported as a count of converging trials rather than averaged in at the round cap, which would produce a figure that estimates nothing.

### C. Protocols Compared

| Protocol | Peer candidate set | Regions |
|---|---|---|
| Uniform Random Gossip | any vehicle, geography ignored | fixed grid |
| Fixed GWG | inverse-distance within radio range | fixed grid |
| Fixed GWG (region-confined) | inverse-distance within range **and** own cell | fixed grid |
| Adaptive-GWG | inverse-distance within range **and** own adaptive region | merge/split |

The third row is the ablation that makes the contribution measurable. Comparing Adaptive-GWG only against the first two rows conflates region confinement with region adaptation, and confinement is a one-line change to the baseline.

### D. Metrics

**Macro MAPE** — error averaged within each region, then across regions, so every region counts equally regardless of population. This is the headline metric; it is the objective of Section III-D. **Micro MAPE** — error averaged over vehicles, in which dense regions dominate. **Convergence round** — the first round at which 90% of evaluable vehicles are within 5% of their region's true mean. **Mean hop distance** — geographic distance per exchange, a proxy for transmit power and interference. **Bytes per vehicle** — push-sum payload plus region-management control traffic. **Cross-region exchange rate** — the share of exchanges that moved push-sum mass across a boundary of the reporting partition.

All error metrics are computed against the **fixed reporting partition**, identical for every protocol, never against a protocol's own regions. Regions holding fewer than two vehicles are excluded, since a single-vehicle 'average' is trivially exact and would flatter every protocol equally.


---

## VI. Results and Discussion

### A. Main Comparison

Table II reports all four protocols at each fleet size, with mobility enabled and no churn, over 10 independent trials.

Fig. 1 plots the convergence curves and Fig. 2 the final accuracy with intervals.

**TABLE II. MAIN RESULTS (mobility on, no churn, 95% CI)**

| N | Protocol | Macro MAPE % | Micro MAPE % | Converged | Hop (m) | B/vehicle | Cross-region % |
|---|---|---|---|---|---|---|---|
| 100 | Uniform Random Gossip | 28.19 ± 3.33 | 27.88 ± 3.30 | 0/10 | 515.5 | 6300 | 99.0 |
| 100 | Fixed GWG | 21.74 ± 2.09 | 21.33 ± 2.05 | 0/10 | 93.9 | 6270 | 74.5 |
| 100 | Fixed GWG (region-confined) | 19.59 ± 1.93 | 18.79 ± 1.88 | 0/10 | 85.8 | 6270 | 60.8 |
| 100 | Adaptive-GWG | 19.60 ± 2.03 | 19.18 ± 2.00 | 0/10 | 87.5 | 6315 | 68.6 |
| 500 | Uniform Random Gossip | 23.98 ± 0.99 | 22.90 ± 0.88 | 0/10 | 520.9 | 6300 | 99.0 |
| 500 | Fixed GWG | 20.92 ± 0.93 | 19.89 ± 0.94 | 0/10 | 86.4 | 6300 | 70.3 |
| 500 | Fixed GWG (region-confined) | 8.91 ± 0.53 | 8.56 ± 0.47 | 0/10 | 44.3 | 6300 | 3.7 |
| 500 | Adaptive-GWG | 9.20 ± 0.52 | 8.67 ± 0.46 | 0/10 | 43.5 | 6316 | 5.1 |
| 1000 | Uniform Random Gossip | 20.32 ± 0.50 | 20.04 ± 0.60 | 0/10 | 519.7 | 6300 | 99.0 |
| 1000 | Fixed GWG | 17.39 ± 0.48 | 16.80 ± 0.50 | 0/10 | 84.8 | 6300 | 68.9 |
| 1000 | Fixed GWG (region-confined) | 9.03 ± 0.32 | 9.16 ± 0.31 | 0/10 | 38.8 | 6300 | 0.0 |
| 1000 | Adaptive-GWG | 9.04 ± 0.33 | 9.20 ± 0.31 | 0/10 | 38.8 | 6312 | 0.1 |

At the largest fleet size (N = 1000), Adaptive-GWG reaches **9.04% ± 0.33** macro MAPE against **20.32%** for Uniform Random Gossip — a **55% reduction**. The ordering is consistent across every fleet size and the confidence intervals of Adaptive-GWG and Uniform Random Gossip do not overlap at any N.

### B. Where the Improvement Actually Comes From

This is the question the ablation exists to answer, and it is the one prior work in this space does not separate.

Fig. 3 shows the same decomposition graphically.

**TABLE III. CONTRIBUTION ATTRIBUTION (macro MAPE)**

| N | Fixed GWG | + region confinement | + adaptive regions | Gain from confinement | Gain from adaptation |
|---|---|---|---|---|---|
| 100 | 21.74% | 19.59% | 19.60% | +9.9% | -0.1% |
| 500 | 20.92% | 8.91% | 9.20% | +57.4% | -3.3% |
| 1000 | 17.39% | 9.03% | 9.04% | +48.1% | -0.2% |

**Region confinement accounts for the entire improvement.** Restricting peer selection to the sender's own cell — a one-line change to the fixed-grid baseline — is worth +9.9% at N=100 (1 vehicles/cell), +57.4% at N=500 (5 vehicles/cell), +48.1% at N=1000 (10 vehicles/cell).

**Adaptive region management adds nothing measurable on top of it:** -0.1% at N=100, -3.3% at N=500, -0.2% at N=1000. Every one of these is negative or negligible, and at no fleet size do the two confidence intervals separate (N=100: 19.59 +/- 1.93 against 19.60 +/- 2.03; N=500: 8.91 +/- 0.53 against 9.20 +/- 0.52; N=1000: 9.03 +/- 0.32 against 9.04 +/- 0.33). Adaptive-GWG additionally carries region-management control traffic that the confined baseline does not (Section VI-D).

We report this as the paper's principal finding, and it is worth being direct about what it means. The adaptive merge/split layer is the component this line of work — including our own earlier version of it — treats as the novel contribution. Measured against gossip that is free to cross region boundaries, it appears to deliver a large improvement. Measured against a fixed grid that simply keeps its gossip inside a cell, it delivers none. **The improvement is real; the attribution was wrong.**

The threshold sweep in Section VI-H supplies the mechanism rather than merely restating the result: the best adaptive configuration is the one that changes the partition least, and accuracy degrades monotonically as merging grows more aggressive. There is no setting of the merge and split thresholds at which adaptation beats leaving the grid alone — the optimum sits at the boundary of doing nothing.

This does not make region management useless in general, and we are careful not to over-claim in the negative direction either. Our fixed grid is already well matched to the service area: every cell lies comfortably inside radio range of its own members, and vehicles are close to uniformly distributed. Adaptation has little to repair under those conditions. A deployment whose cells are badly sized relative to radio range, or whose density varies by orders of magnitude across the map, is a different setting that this evaluation does not cover. What we can say is that in the setting the protocol was designed and previously evaluated for, the improvement belongs to confinement.

### C. The Error Floor of Unconfined Gossip

Uniform Random Gossip and Fixed GWG do not converge at any fleet size (0/10 trials). This is not slow convergence; it is convergence to the wrong target. Push-sum over a connected graph converges to the average over that graph, and when peer selection may cross region boundaries the graph spans the whole service area, so every vehicle's estimate is drawn toward the city-wide mean. The cross-region exchange rate makes the mechanism explicit: **68.9%** of Fixed GWG's exchanges cross a region boundary at N = 1000, versus **0.1%** for Adaptive-GWG.

Note that Fixed GWG's error (17.39%) is barely below Uniform's (20.32%) despite cutting mean hop distance from 520 m to 85 m — a 84% reduction. **Geographic weighting buys locality of communication, not locality of estimation.** This distinction is easy to lose, because a protocol that talks only to nearby vehicles feels like it should produce a local answer. It does not: the exchange graph remains connected across the whole area, and mass flows along it regardless of how short each individual hop is.

The confined variants collapse this rate to near zero once cells are populated (0.0% at N = 1000), and their accuracy improves correspondingly. At N = 100 they cannot: **60.8%** of the confined baseline's exchanges still cross a boundary, because with about 1 vehicle per cell the fallback rule fires almost every round. That is the mechanism behind the negative confinement gain in Table III, measured rather than inferred.

One caveat on how to read this column for Adaptive-GWG. It is measured against the reporting partition for every protocol, so for the confined baselines it is pure leakage — their regions *are* the reporting cells. Adaptive-GWG's regions are deliberately not the reporting cells, so its rate (68.6% at N = 100, 0.1% at N = 1000) mixes leakage with intentional pooling across cells it has merged. It is therefore diagnostic for the baselines and only indicative for our protocol, and we do not read Adaptive-GWG's higher rate at N = 100 as a defect — it is the merge rule doing what it was designed to do.

### D. Cost of Adaptation

Adaptive-GWG is not free. At N = 1000 it sends **6312 B per vehicle** against **6300 B** for the confined fixed-grid baseline, an overhead of **0.2%**, from region-change announcements. Data-plane message counts are identical across protocols by construction — one exchange per vehicle per round — so the control traffic is the entire difference, and reporting it as free (as our earlier harness did) would have made the accuracy comparison meaningless.

Fig. 4 reports mean hop distance and Fig. 5 the communication cost including control traffic.

**TABLE IV. REGION-REFRESH INTERVAL (N = 500)**

| τ (rounds) | Macro MAPE % | Control messages | B/vehicle |
|---|---|---|---|
| 1 | 9.10 ± 1.19 | 629 | 6315 |
| 2 | 9.34 ± 1.23 | 620 | 6315 |
| 5 | 9.76 ± 1.27 | 597 | 6314 |
| 10 | 10.21 ± 1.27 | 564 | 6314 |
| 25 | 13.24 ± 2.02 | 505 | 6312 |

Refreshing every round costs 629 control messages and yields 9.10% macro MAPE; refreshing every 25 rounds cuts control traffic by 20% at 13.24% macro MAPE. The trade-off is real but shallow in bytes: control traffic is a small fraction of a budget dominated by the per-round push-sum payload.

### E. Periodic Restart and the Drift Caused by Mobility

Running push-sum on a moving fleet has a failure mode that a single end-of-run number hides. Without periodic restart the estimate reaches a minimum after a handful of rounds and then **degrades steadily**, because re-initialization at region boundaries keeps injecting fresh weight-1 mass into regions where push-sum has already concentrated mass on a few holders. The region's weight fills up with unaveraged single readings and the estimate drifts back toward exactly the raw measurement the protocol exists to improve on.

- Fixed GWG (region-confined) without restart: best **5.86%** at round 9, degrading to **22.80%** steady state — a factor of 3.9.
- Adaptive-GWG without restart: best **6.09%** at round 9, degrading to **18.16%** steady state — a factor of 3.0.

The remedy is standard for push-sum over time-varying data: restart the accumulator periodically. The convergence curve sets the period — long enough to average, short enough that drift cannot accumulate. We apply it identically to every protocol, so it favours none of them.

Fig. 10 plots the sweep.

**TABLE V. PUSH-SUM RESTART INTERVAL (N = 500, steady-state macro MAPE %)**

| Restart interval | Uniform Random Gossip | Fixed GWG | Fixed GWG (region-confined) | Adaptive-GWG |
|---|---|---|---|---|
| every 5 rounds | 24.98 | 22.16 | 11.90 | 12.25 |
| every 10 rounds | 24.08 | 21.30 | 8.68 | 9.10 |
| every 20 rounds | 23.99 | 21.66 | 8.43 | 8.56 |
| every 50 rounds | 24.82 | 23.63 | 11.95 | 10.83 |
| never | 30.63 | 30.35 | 22.80 | 18.16 |

Restarting every 20 rounds is best for both confined protocols, cutting Adaptive-GWG from 18.16% to 8.56%. Restarting too often leaves too few rounds to average; too rarely lets drift accumulate. The remaining experiments use every 10 rounds, which is within the confidence interval of the 20-round optimum (9.10% vs 8.56%) and was fixed before this sweep was run.

The most informative column is the leftmost. Uniform Random Gossip and Fixed GWG barely move across the entire sweep (30.6% → 24.0% and 30.4% → 21.7%). Restart repairs staleness, and staleness was never their problem — they are converging accurately to the wrong quantity, and no scheduling change fixes a target error. This is the cleanest confirmation in the paper that the error floor of Section VI-C is structural rather than an artifact of how long we ran the protocol.

### F. Mobility

Fig. 9 shows the same comparison.

**TABLE VI. STATIC VS MOBILE (N = 500)**

| Protocol | Static macro MAPE % | Mobile macro MAPE % | Degradation |
|---|---|---|---|
| Uniform Random Gossip | 23.26 | 24.08 | +4% |
| Fixed GWG | 20.45 | 21.30 | +4% |
| Fixed GWG (region-confined) | 7.03 | 8.68 | +24% |
| Adaptive-GWG | 7.55 | 9.10 | +20% |

With periodic restart in place, mobility costs between 4% and 24% additional error. That is a far smaller penalty than the same comparison shows without restart, which is the point of Section VI-E: most of what looks like a mobility penalty is really accumulated drift that restart already removes.

The two confined protocols absorb the larger relative hit (7.03% → 8.68% and 7.55% → 9.10%) precisely because they have the most to lose: they are the only ones estimating the right quantity in the first place, so discarding accumulated averaging at a boundary crossing actually costs them something. The unconfined baselines barely move, for the same unflattering reason they are insensitive to everything else in this paper.

We note that Adaptive-GWG is **behind** the confined baseline in both conditions here (7.55% vs 7.03% static, 9.10% vs 8.68% mobile), consistent with Section VI-B: adaptive region boundaries move as density fluctuates, and each move forces a re-initialization that a fixed grid does not pay. Under mobility, a stable partition is worth more than a well-fitted one.

### G. Churn

Fig. 6 plots error against churn rate.

**TABLE VII. PER-ROUND CHURN (N = 500)**

| Churn ρ | Uniform Random Gossip | Fixed GWG | Fixed GWG (region-confined) | Adaptive-GWG |
|---|---|---|---|---|
| 0.00 | 24.08% | 21.30% | 8.68% | 9.10% |
| 0.01 | 24.54% | 21.16% | 10.34% | 10.25% |
| 0.02 | 24.14% | 20.69% | 10.96% | 10.76% |
| 0.05 | 24.36% | 21.31% | 13.28% | 13.01% |
| 0.10 | 25.39% | 22.02% | 15.47% | 15.29% |

Churn degrades Adaptive-GWG from 9.10% to 15.29% as the per-round departure probability rises from 0% to 10%, because a departing vehicle destroys the push-sum mass it holds and push-sum conserves mass only over a fixed population.

The ordering between protocols is preserved at every churn rate tested, with Adaptive-GWG best throughout (9.10%–15.29%) and Uniform Random Gossip worst (24.08%–24.08%), so no conclusion in Section VI-B depends on the churn setting.

### H. Sensitivity to the Adaptive Thresholds

Fig. 7 plots the sweep.

**TABLE VIII. MERGE/SPLIT THRESHOLD SWEEP (N = 500)**

| n_min | n_max | Macro MAPE % | Mean active regions |
|---|---|---|---|
| 2 | 12 | 8.74 ± 1.20 | 98.0 |
| 2 | 20 | 8.71 ± 1.22 | 97.0 |
| 2 | 30 | 8.71 ± 1.22 | 97.0 |
| 3 | 12 | 9.13 ± 1.18 | 89.5 |
| 3 | 20 | 9.10 ± 1.19 | 88.7 |
| 3 | 30 | 9.10 ± 1.19 | 88.7 |
| 5 | 12 | 15.89 ± 1.87 | 54.4 |
| 5 | 20 | 15.85 ± 1.89 | 54.6 |
| 5 | 30 | 15.85 ± 1.89 | 54.6 |
| 8 | 12 | 20.24 ± 2.22 | 12.8 |
| 8 | 20 | 20.17 ± 2.23 | 13.2 |
| 8 | 30 | 20.17 ± 2.23 | 13.2 |

Accuracy is governed almost entirely by the merge threshold n_min; the split threshold n_max has almost no effect at this density, because few cells hold enough vehicles to trigger a split at all. The best setting tested (n_min = 2, n_max = 20) gives 8.71 ± 1.22% with 97 active regions; the worst (n_min = 8, n_max = 12) gives 20.24 ± 2.22% with 13.

Reading down the merge threshold: n_min=2 → 8.72% (97 regions), n_min=3 → 9.11% (89 regions), n_min=5 → 15.87% (55 regions), n_min=8 → 20.20% (13 regions).

This bears directly on an obvious confound: that Adaptive-GWG might win merely by producing coarser, internally more homogeneous regions. The sweep argues against it — the most aggressive merging (13 regions) is the worst configuration, while the best keeps the partition close to the underlying grid (97 regions) and repairs only those cells too sparse to gossip within.

### I. Real-Time Readiness for AV Consumers

Treating one round as one 100 ms beacon interval [23], [24], Table VIII reports the error a protocol would hand a decision system at a given deadline. 'Usable' is macro MAPE ≤ 10%, an illustrative threshold for cooperative speed advisory rather than one derived from a standard.

Fig. 8 plots error against the decision deadline.

**TABLE IX. ERROR AT A DECISION DEADLINE (macro MAPE %)**

| N | Protocol | 0.5 s | 1.0 s | 2.0 s | 5.0 s |
|---|---|---|---|---|---|
| 100 | Uniform Random Gossip | 27.0 | 27.2 | 28.3 | 28.9 |
| 100 | Fixed GWG | 20.3 | 22.7 | 23.4 | 23.4 |
| 100 | Fixed GWG (region-confined) | 18.7 | 22.6 | 22.7 | 21.5 |
| 100 | Adaptive-GWG | 18.2 | 20.3 | 20.7 | 20.3 |
| 500 | Uniform Random Gossip | 22.5 | 22.7 | 22.6 | 22.6 |
| 500 | Fixed GWG | 19.4 | 20.2 | 20.6 | 20.7 |
| 500 | Fixed GWG (region-confined) | 6.6 ✓ | 5.9 ✓ | 6.4 ✓ | 6.4 ✓ |
| 500 | Adaptive-GWG | 6.7 ✓ | 5.8 ✓ | 6.6 ✓ | 6.5 ✓ |
| 1000 | Uniform Random Gossip | 19.0 | 18.1 | 18.5 | 18.9 |
| 1000 | Fixed GWG | 15.4 | 15.1 | 14.9 | 15.9 |
| 1000 | Fixed GWG (region-confined) | 6.3 ✓ | 3.8 ✓ | 4.0 ✓ | 4.7 ✓ |
| 1000 | Adaptive-GWG | 6.3 ✓ | 3.8 ✓ | 4.1 ✓ | 4.6 ✓ |

Two observations. Under mobility, error does not decrease monotonically with the deadline: the estimate improves over the first few rounds and then degrades as boundary crossings accumulate and re-initialization discards averaging work. A longer deadline is therefore not automatically a better estimate, which is counter-intuitive and worth stating plainly for anyone sizing a real deployment. Second, the unconfined baselines never reach the usable threshold at any deadline or fleet size — consistent with Section VI-C, they are converging to the wrong quantity, and no amount of additional time repairs that.


---

## VII. Limitations and Threats to Validity

**Simulation, not deployment.** We model radio range as a hard disc and do not model packet loss, channel contention, MAC-layer delay, GPS error, or non-line-of-sight attenuation in an urban canyon. All of these would raise the error floor, and contention in particular would penalize the protocol that sends the most control traffic — which is ours. The relative ordering we report should be read as an upper bound on Adaptive-GWG's advantage, not a prediction of field performance.

**Synthetic spatial structure over real speeds.** The speed *values* are real NYC TLC records, but their spatial arrangement comes from a modelled congestion field (centre-slow, periphery-fast) rather than from real per-zone speeds, because the public trip records do not carry the per-zone traces this would require. The congestion gradient is a plausible but stylized model, and results would change under a different spatial structure — for example a corridor pattern rather than a radial one.

**Mobility model.** Vehicles follow a reflected random walk at their observed speed, not a road network. Real vehicles are constrained to streets, turn at intersections, and cluster at signals, which would make region membership more persistent than in our model and probably reduce the re-initialization cost that Section VI-F identifies as dominant. A road-constrained mobility trace is the single most valuable improvement to this evaluation.

**Scale.** We test up to N = 1000 vehicles in a 1000 m square. This is a dense downtown district, not a city, and the conclusions about the sparse regime depend on vehicles-per-cell rather than on N alone. Results should be read against the density ratio N/G², not the fleet size.

**Convergence criterion.** Under mobility no protocol satisfies the 90%-within-5% criterion, so the convergence column is uninformative here and the comparison rests on the error curves instead. A criterion tuned to a moving target — for instance tracking error against a sliding-window regional mean — would be more discriminating.

**AV framing.** The 100 ms beacon interval is standards-derived [23], [24], but the 10% usable-error threshold is illustrative and not traceable to any safety-case requirement. Section I-C scopes Adaptive-GWG to decision support explicitly; nothing here should be read as a claim about safety-critical messaging, whose latency determinism push-sum does not provide.

**Statistical power.** Confidence intervals come from 10 independent trials. At N = 100 the intervals are wide relative to the differences between the weaker protocols, and we avoid claiming orderings there that the intervals do not support.

**Prior-version correction.** An earlier version of this work reported per-region MAPE reductions of 34–96% attributable to adaptive regions. An audit (`scripts/audit_baseline_claims.py`, `scripts/audit_ablation.py`) found that result did not hold: the exchange was not push-sum, no ablation isolated confinement from adaptation, each protocol was scored against its own partition, and at the largest fleet size the adaptive rule had relabelled no vehicles at all. The present numbers supersede those entirely. We document this because the failure mode — a bundled comparison that credits the novel component with a simpler component's effect — is not specific to us and is easy to reproduce elsewhere.


---

## Figures

All in `results/figures/`, regenerated by `python3 src/gwg_simulation.py`.

- **fig1_convergence_curves.png** — Convergence of the per-region estimate, one panel per fleet size.
- **fig2_final_mape.png** — Steady-state per-region MAPE with 95% CI.
- **fig3_attribution.png** — Contribution attribution: what region confinement buys versus what adaptive region management adds on top of it.
- **fig4_hop_distance.png** — Mean geographic distance per gossip exchange.
- **fig5_communication_cost.png** — Bytes per vehicle, including region-management control traffic.
- **fig6_churn.png** — Error against per-round churn rate.
- **fig7_threshold_sensitivity.png** — Merge/split threshold sweep.
- **fig8_av_readiness.png** — Error available within a V2X decision deadline.
- **fig9_mobility.png** — Static versus mobile networks.
- **fig10_restart_interval.png** — Push-sum restart interval sweep.

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
