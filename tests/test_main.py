"""Tests for QuantumRepeater-Lab: Werner algebra, swapping and
purification (formula AND density-matrix simulation), the nested
chain, rate bookkeeping, classifier, gates, and determinism."""
import json
import math

import pytest

import main as m


# ---- Werner algebra + channel
def test_werner_roundtrip_and_endpoints():
    for f in (0.25, 0.5, 0.75, 0.9, 1.0):
        assert m.werner_fidelity(m.werner_w(f)) == pytest.approx(f, abs=1e-12)
    assert m.werner_w(1.0) == 1.0
    assert m.werner_w(0.25) == 0.0


def test_direct_fidelity_values():
    assert m.direct_fidelity(0.0) == pytest.approx(0.98, abs=1e-12)
    assert m.direct_fidelity(1000.0) == pytest.approx(0.518552, abs=1e-6)
    assert m.direct_fidelity(100.0) > m.direct_fidelity(500.0) \
        > m.direct_fidelity(1000.0)


def test_transmission_law():
    assert m.transmission(0.0) == 1.0
    assert m.transmission(1000.0) == pytest.approx(1e-20, rel=1e-9)
    assert m.transmission(125.0) == pytest.approx(10.0 ** -2.5, rel=1e-12)


def test_segment_fidelity_and_leaf_time():
    assert m.segment_fidelity() == pytest.approx(0.894223, abs=1e-6)
    leaf = m.leaf_node(125.0)
    assert leaf["cost"] == 1.0 and leaf["span"] == 125.0
    expected = (125.0 / 200_000.0) / (10.0 ** -2.5 * 100)
    assert leaf["T"] == pytest.approx(expected, rel=1e-12)


# ---- swapping: algebra
def test_swap_formula_is_w_product():
    for a, b in ((0.9, 0.8), (0.75, 0.75), (0.98, 0.6)):
        assert m.swap_fidelity(a, b) == pytest.approx(
            m.werner_fidelity(m.werner_w(a) * m.werner_w(b)), abs=1e-12)


def test_swap_edges():
    assert m.swap_fidelity(1.0, 1.0) == 1.0
    assert m.swap_fidelity(0.9, 0.7) == m.swap_fidelity(0.7, 0.9)
    assert 0.5 < m.swap_fidelity(0.9, 0.9) < 0.9


# ---- swapping: density-matrix simulation
def test_sim_swap_outcomes_all_match_formula():
    sim = m.simulate_swap(0.894223, 0.894223)
    assert sim["formula_fidelity"] == pytest.approx(
        m.swap_fidelity(0.894223, 0.894223), abs=1e-12)
    for outcome in sim["outcomes"].values():
        assert outcome["probability"] == pytest.approx(0.25, abs=1e-9)
        assert outcome["fidelity_after_correction"] == pytest.approx(
            sim["formula_fidelity"], abs=1e-9)


def test_sim_swap_asymmetric():
    sim = m.simulate_swap(0.85, 0.75)
    for outcome in sim["outcomes"].values():
        assert outcome["fidelity_after_correction"] == pytest.approx(
            m.swap_fidelity(0.85, 0.75), abs=1e-9)


def test_werner_pair_matrix_is_a_state():
    rho = m.werner_pair_matrix(0.8)
    assert sum(rho[i][i] for i in range(4)).real == pytest.approx(1.0, abs=1e-12)
    assert m._bell_fidelity(rho) == pytest.approx(0.8, abs=1e-12)


# ---- purification: algebra
def test_purify_round_075():
    f_out, p = m.purify_round(0.75)
    assert f_out == pytest.approx(0.788462, abs=1e-6)
    assert p == pytest.approx(0.722222, abs=1e-6)


def test_purify_fixed_point_and_direction():
    assert m.purify_round(0.5)[0] == pytest.approx(0.5, abs=1e-12)
    assert m.purify_round(0.9)[0] > 0.9
    assert m.purify_round(0.4)[0] < 0.4  # runs backward below 1/2


def test_purify_trajectory_and_cost():
    traj = m.purify_trajectory()
    outs = [row["fidelity_out"] for row in traj["rounds"]]
    assert outs == sorted(outs) and outs[-1] < 1.0
    assert outs[-1] == pytest.approx(0.923061, abs=1e-6)
    assert traj["final_cumulative_pairs_per_output"] > 100.0


# ---- purification: density-matrix simulation
def test_sim_purify_matches_recurrence():
    for f in (0.75, 0.85):
        f_out, p = m.purify_round(f)
        sim = m.simulate_purify(f)
        assert sim["fidelity_out"] == pytest.approx(f_out, abs=1e-9)
        assert sim["success_probability"] == pytest.approx(p, abs=1e-9)


# ---- memory decay + chain
def test_memory_decay():
    assert m.memory_decay(0.9, 0.0) == 0.9
    assert m.memory_decay(0.9, 100.0 * m.MEMORY_T2_S) == pytest.approx(
        0.25, abs=1e-6)
    assert m.memory_decay(0.9, 1.0) > m.memory_decay(0.9, 5.0) > 0.25


def test_chain_single_segment_is_leaf():
    rep = m.chain_report(125.0, 1, 0)
    assert rep["final"]["F"] == pytest.approx(m.segment_fidelity(), abs=1e-12)
    assert rep["final"]["cost"] == 1.0


def test_chain_swap_only_is_separable():
    rep = m.chain_report(1000.0, 8, 0)
    assert rep["final"]["F"] == pytest.approx(0.471701, abs=2e-6)
    assert rep["final"]["F"] < 0.5
    assert rep["final"]["cost"] == 8.0


def test_chain_purified_delivers():
    rep = m.chain_report()
    assert rep["final"]["F"] == pytest.approx(0.858245, abs=2e-6)
    assert rep["final"]["cost"] > 1000.0
    assert 0.1 < rep["final"]["T"] < 1.0
    assert rep["final"]["span"] == 1000.0
    stages = [lv["nodes"] for lv in rep["levels"]
              if lv["stage"].startswith("swap")]
    assert stages == [4, 2, 1]


# ---- rates
def test_rates_comparison():
    rates = m.rates_report()
    assert rates["direct"]["expected_time_s"] == pytest.approx(5e17, rel=1e-9)
    assert rates["direct"]["fidelity"] == pytest.approx(0.518552, abs=1e-6)
    assert rates["repeater_swap_only"]["rate_per_s"] \
        > rates["repeater_purified"]["rate_per_s"]
    assert rates["repeater_purified"]["fidelity"] \
        > rates["repeater_swap_only"]["fidelity"]


# ---- classifier
def test_policy_scenarios():
    s = m.classifier_scenarios()
    assert m.link_policy(*s["campus_single_segment_0.95"]) == "direct-ok"
    assert m.link_policy(*s["metro_four_segments_0.95"]) == "swap-only"
    assert m.link_policy(*s["backbone_1000km_lab_segments"]) \
        == "purify-then-swap"
    assert m.link_policy(*s["backbone_dead_memories"]) == "hopeless"
    assert m.link_policy(*s["weak_source_0.45"]) == "hopeless"


def test_classifier_matches_policy_on_scenarios():
    rep = m.classifier_report()
    for name, features in m.classifier_scenarios().items():
        assert rep[name] == m.link_policy(*features)


def test_classifier_labels_are_the_four_verdicts():
    assert set(m.classifier_report().values()) <= {
        "direct-ok", "swap-only", "purify-then-swap", "hopeless"}


# ---- gates + seats
def test_hold_gates():
    assert len(m.HOLD_GATES) == 14
    assert all(v.startswith("HOLD") for v in m.HOLD_GATES.values())
    assert m.gate("qkd_service_claim") == "HOLD"
    assert m.gate("real_hardware_control") == "HOLD"
    assert m.gate("quantum_internet_service_claim") == "HOLD"
    assert m.gate("run_simulation") == "PROCEED"


def test_seats_never_override():
    brains = m.brains_report()
    assert brains["decider"]["can_override_hold"] is False
    assert brains["decider"]["seat"] == "Gemini Argon 4 Extended Thinking"
    assert brains["advisor"]["can_override_hold"] is False
    assert brains["flow"]["rendered"] is False
    assert brains["flow"]["live"] == 0


def test_hold_demo_exits_2():
    assert m.main(["hold-demo"]) == 2
    assert m.main(["hold-demo", "qkd_service_claim"]) == 2


# ---- determinism
def test_reports_deterministic():
    assert json.dumps(m.chain_report(), sort_keys=True) \
        == json.dumps(m.chain_report(), sort_keys=True)
    assert json.dumps(m.classifier_report(), sort_keys=True) \
        == json.dumps(m.classifier_report(), sort_keys=True)


def test_demo_and_checks_pass(capsys):
    assert m.main(["checks"]) == 0
    out = capsys.readouterr().out
    assert "CHECKS 59/59" in out or "CHECKS" in out
