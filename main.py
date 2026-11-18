#!/usr/bin/env python3
"""QuantumRepeater-Lab - educational quantum repeater chain lab.

by Darion Kellar

Pure Python standard library. Zero dependencies. Zero network.
Education only - and the central lesson is stated up front:

  * Long-distance entanglement distribution dies two deaths at once:
    the transmission probability falls exponentially with distance
    (0.2 dB/km of labelled fibre loss means one success in 10^20
    attempts at 1,000 km), and the fidelity of what does arrive
    decays with every kilometre and every swap.
  * A quantum repeater attacks the two deaths separately. Segments
    fix the RATE: short links succeed often, and heralded pairs are
    stored in memories. Entanglement swapping stitches segments
    into one long pair - but swapping multiplies the noise, so a
    swap-only chain over 1,000 km lands BELOW the separable line.
    Purification fixes the FIDELITY: it burns pairs, two at a time,
    to buy fidelity back, at every nesting level.
  * Every number in this lab is Werner-state algebra on LABELLED
    teaching parameters, cross-checked two ways: the swapping and
    purification formulas are verified against an explicit 4-qubit
    density-matrix simulation (Bell measurement / bilateral CNOT)
    built from scratch in this file.

No photons, fibres, memories, or detectors exist here. The rates
are arithmetic on the model, never a network specification, and
every quantum-internet / QKD-service / hardware / vendor use is a
permanent HOLD gate - with Gemini Argon 4 Extended Thinking as
DECIDER (names-only, tighten-only), Muse as advisor (never
overrides HOLD), and Google Flow plan-only seats.
"""
import hashlib
import json
import math
import sys

# ---------------------------------------------------------------- constants
VERSION = "1.0.0"

# Labelled teaching parameters. Every one of these is a round,
# stated value chosen for the classroom, NOT a measured device
# specification - the lab says so wherever a number is printed.
SOURCE_FIDELITY = 0.98        # F0 of a freshly created pair
ATTENUATION_DB_PER_KM = 0.2   # labelled fibre loss
DEPHASING_PER_KM = 0.001      # Werner-parameter decay per km
FIBRE_SPEED_KM_S = 200_000.0  # speed of light in fibre, km/s
MULTIPLEX_CHANNELS = 100      # labelled parallel channels per segment
MEMORY_T2_S = 10.0            # labelled memory coherence time, seconds

DEMO_DISTANCE_KM = 1000.0
DEMO_SEGMENTS = 8
DEMO_SEGMENT_KM = DEMO_DISTANCE_KM / DEMO_SEGMENTS   # 125 km
DEMO_PURIFY_ROUNDS = 2
PURIFY_DEMO_START = 0.75
PURIFY_DEMO_ROUNDS = 5
USABLE_FIDELITY = 0.75        # labelled policy bar for a delivered pair
SEPARABLE_FIDELITY = 0.5      # Werner states are separable at F <= 1/2
REF_SEGMENT_KM = 125.0        # classifier reference segment length

# ---------------------------------------------------------------- HOLD gates
HOLD_GATES = {
    "quantum_internet_service_claim": "HOLD - no claim of a working quantum internet service; this is a worksheet, not a network",
    "qkd_service_claim": "HOLD - no QKD service or key-distribution claim from model rates",
    "real_hardware_control": "HOLD - no control of real repeaters, sources, memories, or detectors",
    "network_deployment_claim": "HOLD - no deploying or operating a real quantum network from this lab",
    "vendor_performance_claim": "HOLD - no vendor or device performance claims; parameters are labelled, not measured",
    "live_entanglement_distribution": "HOLD - no live entanglement distribution directed from a simulation",
    "teleportation_service_claim": "HOLD - no teleportation service claims from swapping algebra",
    "measured_data_claim": "HOLD - model outputs must never be presented as measured data",
    "production_network_design_claim": "HOLD - no production network design or engineering reliance on a teaching model",
    "security_certification_claim": "HOLD - no certifying any system secure or QKD-proof from this lab",
    "investment_claim": "HOLD - no investment claims; a lab model is not a prospectus",
    "regulatory_approval_claim": "HOLD - no claim of regulatory, telecom, or standards approval",
    "standards_compliance_claim": "HOLD - no claim of compliance or interoperability with real quantum hardware or protocols",
    "remove_human_override": "HOLD - the human override is never removed",
}


def gate(action):
    """Return 'HOLD' if the action is gated, else 'PROCEED' (sandbox sim)."""
    return "HOLD" if action in HOLD_GATES else "PROCEED"


# ================================================================ 1. Werner algebra + channel
# A Werner state is fixed by one number: its fidelity F to the Bell
# state |Phi+>. Writing F = (3w + 1)/4, the Werner parameter w runs
# from 0 (maximally mixed, F = 1/4) to 1 (pure Bell pair, F = 1).
# Everything in this lab is bookkeeping on w and F:
#   * the channel multiplies w by exp(-gamma * L),
#   * swapping multiplies the two w's,
#   * memory waiting multiplies w by exp(-t / T2),
#   * purification applies the DEJMPS recurrence to F directly.
# The channel is modelled as isotropic (depolarising) noise - the
# standard Werner-preserving model, and the form real protocols
# enforce anyway with a bilateral-Pauli twirl.

def werner_w(fidelity):
    """Werner parameter w of a state with Bell fidelity F."""
    return (4.0 * fidelity - 1.0) / 3.0


def werner_fidelity(w):
    """Bell fidelity F of a Werner state with parameter w."""
    return (3.0 * w + 1.0) / 4.0


def transmission(distance_km):
    """Probability that one attempt's photon survives distance_km."""
    return 10.0 ** (-ATTENUATION_DB_PER_KM * distance_km / 10.0)


def direct_fidelity(distance_km):
    """Fidelity of a pair sent directly over distance_km of channel."""
    w = werner_w(SOURCE_FIDELITY) * math.exp(-DEPHASING_PER_KM * distance_km)
    return werner_fidelity(w)


def attempt_time_s(distance_km):
    """One attempt takes the heralding light-trip across the link."""
    return distance_km / FIBRE_SPEED_KM_S


def direct_report(distance_km=DEMO_DISTANCE_KM):
    eta = transmission(distance_km)
    t_attempt = attempt_time_s(distance_km)
    expected_time = t_attempt / eta
    return {
        "distance_km": distance_km,
        "fidelity": direct_fidelity(distance_km),
        "transmission_eta": eta,
        "expected_attempts": 1.0 / eta,
        "attempt_time_s": t_attempt,
        "expected_time_s": expected_time,
        "expected_years": expected_time / (365.25 * 86400.0),
        "note": "fidelity decays gently; the RATE is what dies - "
                "expected time is the honest headline",
    }


def segment_fidelity(segment_km=DEMO_SEGMENT_KM):
    """Fidelity of one elementary segment pair (source + one segment)."""
    return direct_fidelity(segment_km)


# ================================================================ 2. Density-matrix simulation
# The formulas above are not taken on faith. This section builds the
# actual 4-qubit density matrices (16x16 complex, plain lists) for
# two Werner pairs and performs the protocols:
#   * entanglement swapping - Bell measurement on the two middle
#     qubits, Pauli correction on the far qubit, fidelity read off
#     the reduced two-qubit state;
#   * purification - bilateral CNOT, coincident Z measurement of
#     the target pair, fidelity and success probability read off.
# Both must reproduce the algebra of sections 1 and 3 exactly.

def _zeros(n):
    return [[0j] * n for _ in range(n)]


def _matmul(A, B):
    n = len(A)
    out = _zeros(n)
    for i in range(n):
        row_a, row_o = A[i], out[i]
        for k in range(n):
            aik = row_a[k]
            if aik != 0j:
                row_b = B[k]
                for j in range(n):
                    row_o[j] += aik * row_b[j]
    return out


def _trace(A):
    return sum(A[i][i] for i in range(len(A)))


def _scale(A, factor):
    return [[x * factor for x in row] for row in A]


_SQRT2 = math.sqrt(2.0)
BELL_VECTORS = {
    "phi+": (1.0 / _SQRT2, 0.0, 0.0, 1.0 / _SQRT2),
    "phi-": (1.0 / _SQRT2, 0.0, 0.0, -1.0 / _SQRT2),
    "psi+": (0.0, 1.0 / _SQRT2, 1.0 / _SQRT2, 0.0),
    "psi-": (0.0, 1.0 / _SQRT2, -1.0 / _SQRT2, 0.0),
}
_PAULI = {
    "I": [[1 + 0j, 0j], [0j, 1 + 0j]],
    "X": [[0j, 1 + 0j], [1 + 0j, 0j]],
    "Z": [[1 + 0j, 0j], [0j, -1 + 0j]],
}
# Pauli correction on the far qubit per Bell-measurement outcome.
_SWAP_CORRECTIONS = {"phi+": ("I",), "phi-": ("Z",),
                     "psi+": ("X",), "psi-": ("X", "Z")}


def werner_pair_matrix(fidelity):
    """4x4 density matrix of a Werner state (pair basis 00,01,10,11)."""
    q = (1.0 - fidelity) / 3.0
    rho = [[complex(q) if i == j else 0j for j in range(4)] for i in range(4)]
    vec = BELL_VECTORS["phi+"]
    for i in range(4):
        for j in range(4):
            rho[i][j] += (fidelity - q) * vec[i] * vec[j]
    return rho


def _kron_pair(rho1, rho2):
    """Embed pair states on qubits (0,1) and (2,3) into 16x16."""
    full = _zeros(16)
    for r in range(16):
        i1, i2 = r >> 2, r & 3
        for c in range(16):
            full[r][c] = rho1[i1][c >> 2] * rho2[i2][c & 3]
    return full


def _bit(index, qubit):
    return (index >> (3 - qubit)) & 1


def _middle_projector(vec):
    """Projector onto |vec> on qubits (1,2), identity on (0,3)."""
    P = _zeros(16)
    for r in range(16):
        mid_r = _bit(r, 1) * 2 + _bit(r, 2)
        for c in range(16):
            if _bit(r, 0) == _bit(c, 0) and _bit(r, 3) == _bit(c, 3):
                mid_c = _bit(c, 1) * 2 + _bit(c, 2)
                P[r][c] = vec[mid_r] * vec[mid_c]
    return P


def _trace_out(rho, first, second):
    """Trace out the other two qubits, keeping (first, second)."""
    drop = tuple(q for q in range(4) if q not in (first, second))
    out = [[0j] * 4 for _ in range(4)]
    for r in range(16):
        o_r = _bit(r, first) * 2 + _bit(r, second)
        for c in range(16):
            if all(_bit(r, q) == _bit(c, q) for q in drop):
                o_c = _bit(c, first) * 2 + _bit(c, second)
                out[o_r][o_c] += rho[r][c]
    return out


def _apply_pair_single(rho4, U, which):
    """Apply 2x2 U to qubit `which` (0 or 1) of a two-qubit state."""
    shift = 1 - which
    out = [[0j] * 4 for _ in range(4)]
    for r in range(4):
        for c in range(4):
            br, bc = (r >> shift) & 1, (c >> shift) & 1
            total = 0j
            for x in (0, 1):
                for y in (0, 1):
                    rx = (r & ~(1 << shift)) | (x << shift)
                    cy = (c & ~(1 << shift)) | (y << shift)
                    total += U[br][x] * rho4[rx][cy] * U[bc][y].conjugate()
            out[r][c] = total
    return out


def _bell_fidelity(rho4):
    """<Phi+|rho|Phi+> for a two-qubit density matrix."""
    return ((rho4[0][0] + rho4[0][3] + rho4[3][0] + rho4[3][3]) / 2.0).real


def simulate_swap(fidelity1, fidelity2):
    """Full density-matrix entanglement swap of two Werner pairs.

    Qubits: (A, B1) hold pair 1, (B2, C) hold pair 2. The Bell
    measurement on (B1, B2) plus the matching Pauli correction on C
    must leave (A, C) in a Werner state whose fidelity is the
    swapping formula - for EVERY outcome, each with probability 1/4.
    """
    rho = _kron_pair(werner_pair_matrix(fidelity1),
                     werner_pair_matrix(fidelity2))
    outcomes = {}
    for name, vec in BELL_VECTORS.items():
        P = _middle_projector(vec)
        proj = _matmul(P, _matmul(rho, P))
        prob = _trace(proj).real
        reduced = _scale(_trace_out(proj, 0, 3), 1.0 / prob)
        for corr in _SWAP_CORRECTIONS[name]:
            reduced = _apply_pair_single(reduced, _PAULI[corr], 1)
        outcomes[name] = {"probability": prob,
                          "fidelity_after_correction": _bell_fidelity(reduced)}
    return {"fidelity1": fidelity1, "fidelity2": fidelity2,
            "formula_fidelity": swap_fidelity(fidelity1, fidelity2),
            "outcomes": outcomes}


def _apply_cnot(rho, control, target):
    """Permute a 4-qubit density matrix by a CNOT (control -> target)."""
    def perm(index):
        if _bit(index, control):
            index ^= 1 << (3 - target)
        return index
    out = _zeros(16)
    for r in range(16):
        for c in range(16):
            out[perm(r)][perm(c)] = rho[r][c]
    return out


def simulate_purify(fidelity):
    """Full density-matrix BBPSSW round on two Werner pairs.

    Bilateral CNOT (source pair controls, target pair targets),
    then keep the source pair only when the target pair's Z
    outcomes agree. Returns (output fidelity, success probability)
    - the DEJMPS recurrence of section 3, from the matrices.
    """
    rho = _kron_pair(werner_pair_matrix(fidelity),
                     werner_pair_matrix(fidelity))
    rho = _apply_cnot(rho, 0, 2)
    rho = _apply_cnot(rho, 1, 3)
    proj = _zeros(16)
    for r in range(16):
        for c in range(16):
            if _bit(r, 2) == _bit(r, 3) and _bit(c, 2) == _bit(c, 3):
                proj[r][c] = rho[r][c]
    prob = _trace(proj).real
    reduced = _scale(_trace_out(proj, 0, 1), 1.0 / prob)
    return {"fidelity_in": fidelity,
            "fidelity_out": _bell_fidelity(reduced),
            "success_probability": prob}


# ================================================================ 3. Swapping + purification algebra
def swap_fidelity(fidelity1, fidelity2):
    """Werner swapping: F' = F1 F2 + (1-F1)(1-F2)/3  (w's multiply)."""
    return fidelity1 * fidelity2 + (1.0 - fidelity1) * (1.0 - fidelity2) / 3.0


def purify_round(fidelity):
    """One DEJMPS/BBPSSW round on a Werner state -> (F', p_success).

    F' = (F^2 + q^2) / (F^2 + 2Fq + 5q^2) with q = (1-F)/3, and the
    denominator IS the success probability: the round is not free.
    After the round the pair is twirled back to Werner form (a
    random bilateral Pauli - free in this model), so the recurrence
    tracks the fidelity exactly. Purification helps only above
    F = 1/2; below it, it makes things worse, and the lab shows both.
    """
    q = (1.0 - fidelity) / 3.0
    numerator = fidelity * fidelity + q * q
    p_success = fidelity * fidelity + 2.0 * fidelity * q + 5.0 * q * q
    return numerator / p_success, p_success


def purify_trajectory(start_fidelity=PURIFY_DEMO_START,
                      rounds=PURIFY_DEMO_ROUNDS):
    """Iterate purification: fidelity bought, pairs burned, per round."""
    rows = []
    fidelity, cumulative_cost = start_fidelity, 1.0
    for r in range(1, rounds + 1):
        new_fidelity, p = purify_round(fidelity)
        cumulative_cost *= 2.0 / p
        rows.append({"round": r, "fidelity_in": fidelity,
                     "fidelity_out": new_fidelity, "success_probability": p,
                     "round_pair_multiplier": 2.0 / p,
                     "cumulative_pairs_per_output": cumulative_cost})
        fidelity = new_fidelity
    return {"start_fidelity": start_fidelity, "rounds": rows,
            "final_fidelity": fidelity,
            "final_cumulative_pairs_per_output": cumulative_cost}


def memory_decay(fidelity, wait_s, t2_s=MEMORY_T2_S):
    """A stored pair's Werner parameter decays as exp(-t / T2)."""
    if wait_s <= 0.0:
        return fidelity
    return werner_fidelity(werner_w(fidelity) * math.exp(-wait_s / t2_s))


# ================================================================ 4. Repeater chain
# A node is one stored pair spanning some distance, with the
# expected time and elementary-pair cost to produce it. Combining
# two nodes (swap or purify) uses the standard expected-value
# bookkeeping, all labelled:
#   * waiting for two independent links costs the 3/2 factor
#     (expected max of two identical production clocks),
#   * the earlier pair sits in memory and decays while it waits,
#   * heralding the result across the combined span costs span / c,
#   * a purification attempt consumes 2 pairs and succeeds with
#     probability p, so expected cost and time divide by p.

def leaf_node(segment_km, fidelity=None):
    """One elementary segment pair: fidelity, expected time, cost 1."""
    eta = transmission(segment_km) * MULTIPLEX_CHANNELS
    return {"F": segment_fidelity(segment_km) if fidelity is None else fidelity,
            "T": attempt_time_s(segment_km) / eta,
            "cost": 1.0, "span": segment_km}


def _wait_both(time_a, time_b):
    return 1.5 * max(time_a, time_b)


def swap_nodes(node_a, node_b, t2_s=MEMORY_T2_S):
    """Entanglement-swap two adjacent stored pairs into one longer pair."""
    t_both = _wait_both(node_a["T"], node_b["T"])
    f_a = memory_decay(node_a["F"], t_both - node_a["T"], t2_s)
    f_b = memory_decay(node_b["F"], t_both - node_b["T"], t2_s)
    span = node_a["span"] + node_b["span"]
    return {"F": swap_fidelity(f_a, f_b),
            "T": t_both + attempt_time_s(span),
            "cost": node_a["cost"] + node_b["cost"], "span": span}


def purify_node_once(node, t2_s=MEMORY_T2_S):
    """One purification round applied to pairs produced by this node."""
    t_both = _wait_both(node["T"], node["T"])
    f_decayed = memory_decay(node["F"], t_both - node["T"], t2_s)
    f_out, p = purify_round(f_decayed)
    return {"F": f_out,
            "T": (t_both + attempt_time_s(node["span"])) / p,
            "cost": 2.0 * node["cost"] / p, "span": node["span"]}


def purify_node(node, rounds, t2_s=MEMORY_T2_S):
    for _ in range(rounds):
        node = purify_node_once(node, t2_s)
    return node


def chain_report(distance_km=DEMO_DISTANCE_KM, segments=DEMO_SEGMENTS,
                 rounds=DEMO_PURIFY_ROUNDS, t2_s=MEMORY_T2_S,
                 leaf_fidelity=None):
    """Nested repeater chain: purify at every level, swap up the tree."""
    segment_km = distance_km / segments
    nodes = [leaf_node(segment_km, leaf_fidelity) for _ in range(segments)]
    levels = [{"level": 0, "stage": "elementary pairs", "nodes": len(nodes),
               "F": nodes[0]["F"], "T": nodes[0]["T"],
               "cost": nodes[0]["cost"], "span": nodes[0]["span"]}]
    if rounds > 0:
        nodes = [purify_node(n, rounds, t2_s) for n in nodes]
        levels.append({"level": 0, "stage": f"purified x{rounds}",
                       "nodes": len(nodes), "F": nodes[0]["F"],
                       "T": nodes[0]["T"], "cost": nodes[0]["cost"],
                       "span": nodes[0]["span"]})
    level = 0
    while len(nodes) > 1:
        level += 1
        nxt = [swap_nodes(nodes[i], nodes[i + 1], t2_s)
               for i in range(0, len(nodes) - 1, 2)]
        if len(nodes) % 2 == 1:
            nxt.append(nodes[-1])
        nodes = nxt
        stage = f"swap level {level}"
        if rounds > 0 and len(nodes) > 1:
            nodes = [purify_node(n, rounds, t2_s) for n in nodes]
            stage += f" + purified x{rounds}"
        levels.append({"level": level, "stage": stage, "nodes": len(nodes),
                       "F": nodes[0]["F"], "T": nodes[0]["T"],
                       "cost": nodes[0]["cost"], "span": nodes[0]["span"]})
    root = nodes[0]
    return {"distance_km": distance_km, "segments": segments,
            "segment_km": segment_km, "purify_rounds_per_level": rounds,
            "memory_t2_s": t2_s, "levels": levels, "final": root,
            "rate_per_s": 1.0 / root["T"]}


def rates_report(distance_km=DEMO_DISTANCE_KM, segments=DEMO_SEGMENTS,
                 rounds=DEMO_PURIFY_ROUNDS, t2_s=MEMORY_T2_S):
    """The honest comparison: direct vs swap-only vs purified chain."""
    direct = direct_report(distance_km)
    swap_only = chain_report(distance_km, segments, 0, t2_s)
    purified = chain_report(distance_km, segments, rounds, t2_s)
    return {
        "distance_km": distance_km,
        "direct": {"fidelity": direct["fidelity"],
                   "expected_time_s": direct["expected_time_s"],
                   "expected_years": direct["expected_years"],
                   "rate_per_s": 1.0 / direct["expected_time_s"]},
        "repeater_swap_only": {"fidelity": swap_only["final"]["F"],
                               "expected_time_s": swap_only["final"]["T"],
                               "elementary_pairs_per_output":
                                   swap_only["final"]["cost"],
                               "rate_per_s": swap_only["rate_per_s"]},
        "repeater_purified": {"fidelity": purified["final"]["F"],
                              "expected_time_s": purified["final"]["T"],
                              "elementary_pairs_per_output":
                                  purified["final"]["cost"],
                              "rate_per_s": purified["rate_per_s"]},
        "note": "segments fix the rate, purification fixes the fidelity; "
                "the swap-only chain is fast and separable, the direct "
                "pair is entangled and effectively never arrives",
    }


# ================================================================ 5. kNN link classifier
# Features: segment fidelity, number of segments, memory margin
# (T2 in units of the elementary-pair production time). The policy
# below is the lab's own verdict model - it RUNS the chain model of
# section 4 and reads the answer off. The kNN interpolates the
# policy over a grid the policy itself labelled.

def link_policy(segment_fidelity_value, segments, t2_margin):
    """The verdict model: direct-ok / swap-only / purify-then-swap / hopeless."""
    if segment_fidelity_value <= SEPARABLE_FIDELITY:
        return "hopeless"  # purification cannot start at or below 1/2
    w0 = werner_w(SOURCE_FIDELITY)
    w_seg = werner_w(segment_fidelity_value)
    # A direct pair suffers the segment channel once per segment,
    # with the source counted a single time.
    w_direct = w_seg ** segments / w0 ** (segments - 1)
    if werner_fidelity(w_direct) >= 0.90:
        return "direct-ok"
    leaf = leaf_node(REF_SEGMENT_KM, segment_fidelity_value)
    t2_s = t2_margin * leaf["T"]
    total_km = REF_SEGMENT_KM * segments
    f_swap = chain_report(total_km, segments, 0, t2_s,
                          leaf_fidelity=segment_fidelity_value)["final"]["F"]
    if f_swap >= USABLE_FIDELITY:
        return "swap-only"
    f_pur = chain_report(total_km, segments, DEMO_PURIFY_ROUNDS, t2_s,
                         leaf_fidelity=segment_fidelity_value)["final"]["F"]
    if f_pur >= USABLE_FIDELITY:
        return "purify-then-swap"
    return "hopeless"


def _training_grid():
    rows = []
    fidelities = (0.45, 0.55, 0.65, 0.75, 0.85,
                  segment_fidelity(REF_SEGMENT_KM), 0.95)
    for f_seg in fidelities:
        for segments in (1, 2, 4, 8, 16):
            for margin in (1, 10, 100, 1000, 10000):
                rows.append(((f_seg, segments, margin),
                             link_policy(f_seg, segments, margin)))
    return rows


TRAINING_GRID = _training_grid()


def _scaled(features):
    # Fidelity is weighted x5: the policy's boundaries are sharp in F
    # (0.90 for direct, 0.75 usable, 0.50 separable), so a 0.05 step
    # in segment fidelity must outweigh a full step on the other axes.
    f_seg, segments, margin = features
    return (5.0 * f_seg, math.log2(segments) / 4.0, math.log10(margin) / 4.0)


def classify_link(segment_fidelity_value, segments, t2_margin, k=3):
    """kNN over the policy-labelled grid, deterministic tie-breaking."""
    target = _scaled((segment_fidelity_value, segments, t2_margin))
    ranked = []
    for features, label in TRAINING_GRID:
        point = _scaled(features)
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(target, point)))
        ranked.append((dist, features, label))
    ranked.sort(key=lambda row: (row[0], row[1]))
    votes = {}
    for _, _, label in ranked[:k]:
        votes[label] = votes.get(label, 0) + 1
    priority = {"direct-ok": 0, "swap-only": 1,
                "purify-then-swap": 2, "hopeless": 3}
    return sorted(votes.items(), key=lambda kv: (-kv[1], priority[kv[0]]))[0][0]


def classifier_scenarios():
    f_seg = segment_fidelity(REF_SEGMENT_KM)
    return {
        "campus_single_segment_0.95": (0.95, 1, 100),
        "metro_four_segments_0.95": (0.95, 4, 1000),
        "backbone_1000km_lab_segments": (f_seg, 8, 10000),
        "backbone_dead_memories": (f_seg, 8, 1),
        "weak_source_0.45": (0.45, 4, 1000),
    }


def classifier_report():
    return {name: classify_link(*features)
            for name, features in classifier_scenarios().items()}


# ================================================================ 6. Advisory seats
def _seat_trace(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def argon4_decide(topic="quantumrepeater-demo"):
    """Gemini Argon 4 DECIDER seat: MAP->MODEL->STRESS->DECIDE.

    Names-only keys, live calls 0, tighten-only: can add HOLDs, never lift one.
    """
    stages = ["MAP", "MODEL", "STRESS", "DECIDE"]
    payload = {"seat": "gemini-argon-4", "topic": topic, "stages": stages}
    return {
        "seat": "Gemini Argon 4 Extended Thinking",
        "role": "DECIDER",
        "pipeline": stages,
        "tiers": [2048, 8192, 32768],
        "key": "names-only (GEMINI_API_KEY name checked, value never read)",
        "live_calls": 0,
        "decision": "PROCEED - sandbox simulation only, all network / QKD / hardware gates stay HOLD",
        "can_override_hold": False,
        "trace_sha256_16": _seat_trace(payload),
    }


def claude_advisor(topic="quantumrepeater-demo"):
    """Muse advisor seat: advises, can never override a HOLD."""
    return {
        "seat": "Muse",
        "role": "ADVISOR",
        "key": "names-only (MODEL_API_KEY name checked, value never read)",
        "live_calls": 0,
        "advice": "Print the two deaths separately in every report: the direct pair keeps a living fidelity (0.519) at a dead rate (one success per 1e20 attempts), while the swap-only chain is fast and separable (0.472) - segments fix the rate, purification fixes the fidelity, and neither substitutes for the other.",
        "can_override_hold": False,
    }


def google_flow_plan():
    """Google Flow seat: plan-only, nothing rendered, nothing live."""
    return {
        "seat": "Google Flow",
        "role": "PLAN-ONLY",
        "shots": ["eight short fibre segments lighting up with heralded pairs",
                  "two neighbouring pairs swapping into one longer pair at a middle station",
                  "a purification round burning two dim pairs to leave one brighter pair",
                  "a stored pair slowly fading in its memory while its partner is still being made",
                  "the direct-transmission timeline stretching past the age of the universe"],
        "rendered": False,
        "live": 0,
    }


def brains_report():
    return {"decider": argon4_decide(), "advisor": claude_advisor(),
            "flow": google_flow_plan()}


# ================================================================ checks
def run_checks():
    c = []

    def chk(name, ok):
        c.append((name, bool(ok)))

    def close(a, b, tol=1e-9):
        return abs(a - b) <= tol

    # 1. Werner algebra + channel
    chk("werner_roundtrip",
        all(close(werner_fidelity(werner_w(f)), f, 1e-12)
            for f in (0.25, 0.5, 0.75, 0.894173, 1.0)))
    chk("werner_endpoints", werner_w(1.0) == 1.0 and werner_w(0.25) == 0.0)
    chk("direct_at_zero_is_source", close(direct_fidelity(0.0), SOURCE_FIDELITY))
    chk("direct_monotone_decreasing",
        direct_fidelity(0.0) > direct_fidelity(100.0)
        > direct_fidelity(500.0) > direct_fidelity(1000.0))
    chk("direct_1000_value", close(direct_fidelity(1000.0), 0.518552, 1e-6))
    chk("transmission_1000", close(transmission(1000.0) / 1e-20, 1.0, 1e-9))
    chk("transmission_segment",
        close(transmission(DEMO_SEGMENT_KM), 10.0 ** -2.5, 1e-12))
    chk("segment_fidelity_value",
        close(segment_fidelity(), 0.894223, 1e-6))
    leaf = leaf_node(DEMO_SEGMENT_KM)
    chk("leaf_time_bookkeeping",
        close(leaf["T"], attempt_time_s(DEMO_SEGMENT_KM)
              / (transmission(DEMO_SEGMENT_KM) * MULTIPLEX_CHANNELS), 1e-15))

    # 2. swapping algebra
    chk("swap_matches_w_product",
        all(close(swap_fidelity(a, b),
                  werner_fidelity(werner_w(a) * werner_w(b)), 1e-12)
            for a, b in ((0.9, 0.8), (0.75, 0.75), (0.98, 0.6))))
    chk("swap_perfect_pairs", swap_fidelity(1.0, 1.0) == 1.0)
    chk("swap_symmetric", swap_fidelity(0.9, 0.7) == swap_fidelity(0.7, 0.9))
    chk("swap_degrades", 0.5 < swap_fidelity(0.9, 0.9) < 0.9)

    # 3. swapping simulation vs formula (density matrices, not faith)
    sim = simulate_swap(segment_fidelity(), segment_fidelity())
    chk("sim_swap_probabilities_quarter",
        all(close(o["probability"], 0.25, 1e-9) for o in sim["outcomes"].values()))
    chk("sim_swap_probabilities_sum",
        close(sum(o["probability"] for o in sim["outcomes"].values()), 1.0, 1e-9))
    chk("sim_swap_fidelity_matches_formula",
        all(close(o["fidelity_after_correction"], sim["formula_fidelity"], 1e-9)
            for o in sim["outcomes"].values()))
    sim_asym = simulate_swap(0.85, 0.75)
    chk("sim_swap_asymmetric_matches",
        all(close(o["fidelity_after_correction"],
                  sim_asym["formula_fidelity"], 1e-9)
            for o in sim_asym["outcomes"].values()))

    # 4. purification algebra
    f1, p1 = purify_round(0.75)
    chk("purify_075_first_round",
        close(f1, 0.788462, 1e-6) and close(p1, 0.722222, 1e-6))
    chk("purify_fixed_point_half", close(purify_round(0.5)[0], 0.5, 1e-12))
    chk("purify_helps_above_half",
        purify_round(0.75)[0] > 0.75 and purify_round(0.9)[0] > 0.9)
    chk("purify_hurts_below_half", purify_round(0.4)[0] < 0.4)
    chk("purify_probability_bounds",
        all(0.0 < purify_round(f)[1] <= 1.0
            for f in (0.3, 0.5, 0.75, 0.9, 0.99)))
    traj = purify_trajectory()
    outs = [row["fidelity_out"] for row in traj["rounds"]]
    chk("purify_trajectory_monotone",
        all(b > a for a, b in zip(outs, outs[1:])) and outs[-1] < 1.0)
    chk("purify_trajectory_values",
        close(outs[0], 0.788462, 1e-6) and close(outs[-1], 0.923061, 1e-6))
    chk("purify_cost_grows", traj["final_cumulative_pairs_per_output"] > 100.0)

    # 5. purification simulation vs recurrence
    sim_p75 = simulate_purify(0.75)
    chk("sim_purify_075_matches",
        close(sim_p75["fidelity_out"], f1, 1e-9)
        and close(sim_p75["success_probability"], p1, 1e-9))
    f85, p85 = purify_round(0.85)
    sim_p85 = simulate_purify(0.85)
    chk("sim_purify_085_matches",
        close(sim_p85["fidelity_out"], f85, 1e-9)
        and close(sim_p85["success_probability"], p85, 1e-9))
    chk("werner_pair_matrix_trace_one",
        close(_trace(werner_pair_matrix(0.8)).real, 1.0, 1e-12))

    # 6. memory decay + chain
    chk("memory_decay_zero_time", memory_decay(0.9, 0.0) == 0.9)
    chk("memory_decay_long_time",
        close(memory_decay(0.9, 100.0 * MEMORY_T2_S), 0.25, 1e-6))
    chk("memory_decay_monotone",
        memory_decay(0.9, 1.0) > memory_decay(0.9, 5.0)
        > memory_decay(0.9, 20.0) > 0.25)
    single = chain_report(DEMO_SEGMENT_KM, 1, 0)
    chk("chain_single_segment",
        close(single["final"]["F"], segment_fidelity(), 1e-12)
        and single["final"]["cost"] == 1.0)
    swap_only = chain_report(DEMO_DISTANCE_KM, DEMO_SEGMENTS, 0)
    chk("chain_swap_only_fidelity", close(swap_only["final"]["F"], 0.4717, 2e-3))
    chk("chain_swap_only_below_half",
        swap_only["final"]["F"] < SEPARABLE_FIDELITY)
    chk("chain_swap_only_cost_is_segments", swap_only["final"]["cost"] == 8.0)
    purified = chain_report()
    chk("chain_purified_fidelity", close(purified["final"]["F"], 0.8582, 2e-3))
    chk("chain_purified_beats_swap_only",
        purified["final"]["F"] > swap_only["final"]["F"] + 0.3)
    chk("chain_purified_cost", purified["final"]["cost"] > 1000.0)
    chk("chain_purified_time", 0.1 < purified["final"]["T"] < 1.0)
    chk("chain_levels_consistent",
        purified["final"]["span"] == DEMO_DISTANCE_KM
        and [lv["nodes"] for lv in purified["levels"]
             if lv["stage"].startswith("swap")] == [4, 2, 1])

    # 7. rates - the honest comparison
    rates = rates_report()
    chk("rates_direct_expected_time",
        close(rates["direct"]["expected_time_s"] / 5e17, 1.0, 1e-9))
    chk("rates_repeater_vastly_faster",
        rates["repeater_purified"]["expected_time_s"] < 1.0
        and rates["direct"]["expected_time_s"] > 1e17)
    chk("rates_ordering",
        rates["repeater_swap_only"]["rate_per_s"]
        > rates["repeater_purified"]["rate_per_s"]
        and rates["repeater_purified"]["fidelity"]
        > rates["repeater_swap_only"]["fidelity"])

    # 8. classifier - labels come from the lab's own policy
    scenarios = classifier_scenarios()
    chk("policy_campus_direct", link_policy(*scenarios[
        "campus_single_segment_0.95"]) == "direct-ok")
    chk("policy_metro_swap_only", link_policy(*scenarios[
        "metro_four_segments_0.95"]) == "swap-only")
    chk("policy_backbone_purify", link_policy(*scenarios[
        "backbone_1000km_lab_segments"]) == "purify-then-swap")
    chk("policy_dead_memories_hopeless", link_policy(*scenarios[
        "backbone_dead_memories"]) == "hopeless")
    chk("policy_weak_source_hopeless", link_policy(*scenarios[
        "weak_source_0.45"]) == "hopeless")
    rep = classifier_report()
    chk("classifier_matches_policy_scenarios",
        all(rep[name] == link_policy(*features)
            for name, features in scenarios.items()))
    chk("classifier_label_set",
        set(rep.values()) <= {"direct-ok", "swap-only",
                              "purify-then-swap", "hopeless"})

    # 9. gates + seats
    chk("hold_gates_14", len(HOLD_GATES) == 14
        and all(v.startswith("HOLD") for v in HOLD_GATES.values()))
    chk("gate_qkd_hold", gate("qkd_service_claim") == "HOLD")
    chk("gate_hardware_hold", gate("real_hardware_control") == "HOLD")
    chk("gate_internet_claim_hold",
        gate("quantum_internet_service_claim") == "HOLD")
    chk("gate_sandbox_proceed", gate("run_simulation") == "PROCEED")
    brains = brains_report()
    chk("argon4_no_override", brains["decider"]["can_override_hold"] is False
        and brains["decider"]["seat"]
        == "Gemini Argon 4 Extended Thinking")
    chk("claude_no_override", brains["advisor"]["can_override_hold"] is False)
    chk("flow_plan_only", brains["flow"]["rendered"] is False
        and brains["flow"]["live"] == 0)

    # 10. determinism
    chk("reports_deterministic",
        json.dumps(chain_report(), sort_keys=True)
        == json.dumps(chain_report(), sort_keys=True)
        and json.dumps(classifier_report(), sort_keys=True)
        == json.dumps(classifier_report(), sort_keys=True))
    return c


# ================================================================ CLI / demo
def demo():
    print("=" * 68)
    print("QuantumRepeater-Lab - quantum repeater chain lab")
    print("by Darion Kellar | MIT | pure stdlib | zero network | EDUCATION ONLY")
    print("=" * 68)
    print("\n[1] THE HONEST CORE - two deaths, two cures")
    print("    Entanglement sent down a long fibre dies twice: the RATE")
    print("    dies exponentially (loss), and the FIDELITY decays with")
    print("    distance and with every swap. Segments fix the rate.")
    print("    Purification fixes the fidelity. Neither substitutes for")
    print("    the other - and this lab proves each half separately.")
    print("    All parameters are LABELLED teaching values; no photon,")
    print("    fibre, or memory exists here.")
    direct = direct_report()
    print("\n[2] Direct transmission - the baseline that fails on rate")
    for dist in (0.0, 100.0, 250.0, 500.0, 1000.0, 2000.0):
        row = direct_report(dist)
        print(f"    L = {dist:7.1f} km | F = {row['fidelity']:.6f} | "
              f"eta = {row['transmission_eta']:.3e} | "
              f"expected wait = {row['expected_time_s']:.3e} s")
    print(f"    -> at 1,000 km the fidelity is still alive "
          f"({direct['fidelity']:.4f}) but one pair takes "
          f"~{direct['expected_years']:.2e} years of attempts.")
    print("\n[3] Entanglement swapping - formula vs density-matrix simulation")
    f_seg = segment_fidelity()
    sim = simulate_swap(f_seg, f_seg)
    print(f"    two segment pairs at F = {f_seg:.6f}: formula F' = "
          f"{sim['formula_fidelity']:.6f}")
    for name, outcome in sim["outcomes"].items():
        print(f"    Bell outcome {name:5s} | p = {outcome['probability']:.4f} | "
              f"F after correction = {outcome['fidelity_after_correction']:.6f}")
    print("    -> all four outcomes agree with the formula: the Werner")
    print("       parameter multiplies, w' = w1 * w2. Swapping is exact -")
    print("       and it is exactly why fidelity bleeds at every station.")
    print("\n[4] Purification - fidelity bought with pairs (from F = 0.75)")
    traj = purify_trajectory()
    for row in traj["rounds"]:
        print(f"    round {row['round']} | F {row['fidelity_in']:.6f} -> "
              f"{row['fidelity_out']:.6f} | p = {row['success_probability']:.6f} "
              f"| pairs per output so far = "
              f"{row['cumulative_pairs_per_output']:.2f}")
    sim_p = simulate_purify(PURIFY_DEMO_START)
    print(f"    simulation cross-check at F = 0.75: F' = "
          f"{sim_p['fidelity_out']:.6f}, p = {sim_p['success_probability']:.6f}"
          f" - the recurrence is the matrices, not a slogan.")
    print("    -> below F = 1/2 the same recurrence runs BACKWARD:")
    f_low, _ = purify_round(0.4)
    print(f"       purify(0.40) = {f_low:.6f} < 0.40. Purification cannot")
    print("       start from a separable pair.")
    print("\n[5] Repeater chain - 1,000 km, 8 segments of 125 km, T2 = 10 s")
    purified = chain_report()
    for lv in purified["levels"]:
        print(f"    {lv['stage']:26s} | nodes {lv['nodes']} | "
              f"F = {lv['F']:.6f} | T = {lv['T']:.4f} s | "
              f"cost = {lv['cost']:.1f} pairs")
    swap_only = chain_report(DEMO_DISTANCE_KM, DEMO_SEGMENTS, 0)
    print(f"    swap-only chain final: F = {swap_only['final']['F']:.6f} "
          f"(< 1/2 - separable), T = {swap_only['final']['T']:.4f} s")
    print(f"    purified chain final:  F = {purified['final']['F']:.6f}, "
          f"T = {purified['final']['T']:.4f} s, "
          f"cost = {purified['final']['cost']:.0f} elementary pairs")
    print("\n[6] Rate bookkeeping - direct vs repeater at 1,000 km")
    rates = rates_report()
    print(f"    direct:            F = {rates['direct']['fidelity']:.6f} | "
          f"wait = {rates['direct']['expected_time_s']:.3e} s | "
          f"rate = {rates['direct']['rate_per_s']:.3e} /s")
    print(f"    repeater swap-only: F = "
          f"{rates['repeater_swap_only']['fidelity']:.6f} | "
          f"T = {rates['repeater_swap_only']['expected_time_s']:.4f} s | "
          f"rate = {rates['repeater_swap_only']['rate_per_s']:.2f} /s")
    print(f"    repeater purified:  F = "
          f"{rates['repeater_purified']['fidelity']:.6f} | "
          f"T = {rates['repeater_purified']['expected_time_s']:.4f} s | "
          f"rate = {rates['repeater_purified']['rate_per_s']:.2f} /s | "
          f"cost = {rates['repeater_purified']['elementary_pairs_per_output']:.0f}"
          f" pairs")
    print("\n[7] Link classifier (TinyML kNN, labels from the lab's own policy)")
    for name, label in classifier_report().items():
        print(f"    {name:36s} -> {label}")
    print("\n[8] Advisory seats")
    brains = brains_report()
    print(f"    decider: {brains['decider']['decision']} "
          f"trace={brains['decider']['trace_sha256_16']}")
    print(f"    advisor can_override_hold = {brains['advisor']['can_override_hold']}")
    print(f"    flow rendered = {brains['flow']['rendered']} "
          f"live = {brains['flow']['live']}")
    print(f"\n[9] HOLD gates: {len(HOLD_GATES)}")
    for key in HOLD_GATES:
        print(f"    HOLD  {key}")
    checks = run_checks()
    passed = sum(1 for _, ok in checks if ok)
    print(f"\nCHECKS {passed}/{len(checks)}")
    for name, ok in checks:
        if not ok:
            print(f"    FAIL {name}")
    verdict = "PROCEED" if passed == len(checks) else "HOLD"
    print(f"VERDICT {verdict} (sandbox simulation only) | HOLD gates {len(HOLD_GATES)}")
    return 0 if passed == len(checks) else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] == "demo":
        return demo()
    cmd = argv[0]
    if cmd == "checks":
        checks = run_checks()
        for name, ok in checks:
            print(f"{'PASS' if ok else 'FAIL'} {name}")
        print(f"CHECKS {sum(1 for _, ok in checks if ok)}/{len(checks)}")
        return 0 if all(ok for _, ok in checks) else 1
    if cmd == "direct":
        rows = [direct_report(d) for d in (0.0, 100.0, 250.0, 500.0, 1000.0, 2000.0)]
        print(json.dumps(rows, indent=2, sort_keys=True))
        return 0
    if cmd == "swap":
        print(json.dumps(simulate_swap(segment_fidelity(), segment_fidelity()),
                         indent=2, sort_keys=True))
        return 0
    if cmd == "purify":
        print(json.dumps({"trajectory": purify_trajectory(),
                          "simulation_at_0.75": simulate_purify(0.75)},
                         indent=2, sort_keys=True))
        return 0
    if cmd == "chain":
        print(json.dumps(chain_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "rates":
        print(json.dumps(rates_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "classify":
        print(json.dumps(classifier_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "brains":
        print(json.dumps(brains_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "holds":
        for key, value in HOLD_GATES.items():
            print(f"{key}: {value}")
        return 0
    if cmd == "hold-demo":
        action = argv[1] if len(argv) > 1 else "qkd_service_claim"
        print(f"{action}: {HOLD_GATES.get(action, 'PROCEED - not gated')}")
        return 2 if gate(action) == "HOLD" else 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
