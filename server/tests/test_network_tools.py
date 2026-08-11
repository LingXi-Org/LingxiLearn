"""The capture pipeline and the simulator: the two things a chat window can't do."""

from __future__ import annotations

import pytest

from lingxilearn.tools.net import analysis, sim, synth
from lingxilearn.tools.net.pcapfile import PcapError, read_pcap, write_pcap

# --------------------------------------------------------------------------
# Captures
# --------------------------------------------------------------------------


def test_capture_is_a_real_pcap_file(capture):
    blob = capture.read_bytes()
    assert blob[:4].hex() == "d4c3b2a1"  # little-endian classic pcap magic
    assert int.from_bytes(blob[20:24], "little") == 1  # LINKTYPE_ETHERNET


def test_round_trip_preserves_every_frame(tmp_path):
    frames, _ = synth.build_web_slow()
    target = write_pcap(tmp_path / "rt.pcap", frames)
    parsed = read_pcap(target)
    assert len(parsed) == len(frames)
    for original, decoded in zip(frames, parsed, strict=True):
        assert decoded.raw == original[1]
        assert decoded.ts == pytest.approx(original[0], abs=1e-6)


def test_decoding_recovers_the_protocol_story(capture):
    frames = read_pcap(capture)
    assert frames[0].layers["dns"]["qname"] == "course.example.edu"
    assert frames[1].layers["dns"]["answers"] == ["203.0.113.42"]
    assert "SYN" in frames[2].layers["tcp"]["flag_names"]
    assert frames[5].layers["http"]["start_line"].startswith("GET ")


def test_waterfall_partitions_the_wall_clock(capture):
    """A budget that doesn't add up is a budget you can't grade against."""
    result = analysis.waterfall(read_pcap(capture))
    total = sum(result["buckets"].values()) + result["idle_ms"]
    assert total == pytest.approx(result["total_ms"], abs=0.2)


def test_waterfall_matches_the_synthesised_ground_truth(capture):
    buckets = analysis.waterfall(read_pcap(capture))["buckets"]
    assert buckets["dns"] == pytest.approx(121.4, abs=0.2)
    assert buckets["tcp_connect"] == pytest.approx(31.9, abs=0.2)
    assert buckets["ttfb"] == pytest.approx(188.6, abs=0.2)
    assert buckets["retransmission"] == pytest.approx(225.8, abs=0.5)


def test_retransmission_stall_beats_server_think_time(capture):
    """The pedagogical point of this capture: the obvious answer is wrong."""
    buckets = analysis.waterfall(read_pcap(capture))["buckets"]
    assert buckets["retransmission"] > buckets["ttfb"]


def test_gap_fill_is_detected_from_a_client_side_capture(capture):
    findings = analysis.detect_retransmissions(read_pcap(capture))
    kinds = {f["kind"] for f in findings}
    assert "gap_fill" in kinds  # the lost original is never on the wire
    assert "duplicate_ack" in kinds
    assert any(f.get("triggers_fast_retransmit") for f in findings)


def test_every_cited_bucket_frame_actually_exists(capture):
    frames = read_pcap(capture)
    numbers = {f.number for f in frames}
    result = analysis.waterfall(frames)
    for bucket, cited in result["bucket_frames"].items():
        assert set(cited) <= numbers, f"{bucket} cites a frame that isn't in the capture"


def test_malformed_capture_reports_a_usable_error(tmp_path):
    bad = tmp_path / "bad.pcap"
    bad.write_bytes(b"not a capture at all")
    with pytest.raises(PcapError):
        read_pcap(bad)


def test_missing_capture_reports_a_usable_error(tmp_path):
    with pytest.raises(PcapError):
        read_pcap(tmp_path / "nope.pcap")


# --------------------------------------------------------------------------
# Simulator
# --------------------------------------------------------------------------


@pytest.mark.parametrize("scenario", ["single-loss", "lossy-link"])
def test_oracle_delivers_everything(scenario):
    result = sim.score(scenario, 7, sim.oracle(scenario, 7)["actions"])
    assert result["delivered_intact"]
    assert result["efficiency"] == 1.0
    assert result["misconceptions"] == []


@pytest.mark.parametrize("seed", [7, 42, 1234])
def test_same_seed_reproduces_the_same_run(seed):
    a, b = sim.oracle("lossy-link", seed), sim.oracle("lossy-link", seed)
    assert a["ticks"] == b["ticks"]
    assert a["actions"] == b["actions"]


def test_different_seeds_diverge():
    assert sim.oracle("lossy-link", 7)["actions"] != sim.oracle("lossy-link", 99)["actions"]


def test_lossy_link_actually_loses_packets():
    stats = sim.score("lossy-link", 7, sim.oracle("lossy-link", 7)["actions"])["stats"]
    assert stats["retransmissions"] > 0


def test_never_recovering_is_caught_as_ignoring_the_timeout():
    actions = [{"op": "send"}] * 4 + [{"op": "wait"}] * 80
    result = sim.score("single-loss", 7, actions)
    assert not result["delivered_intact"]
    assert "ignores_timeout" in result["misconceptions"]


def test_retransmitting_the_window_is_caught_as_gbn_confusion():
    actions = (
        [{"op": "send"}] * 4
        + [{"op": "wait"}] * 8
        + [{"op": "retransmit_all"}]
        + [{"op": "wait"}] * 10
        + [{"op": "send"}] * 4
        + [{"op": "wait"}] * 40
    )
    result = sim.score("single-loss", 7, actions)
    assert "gbn_vs_sr_confusion" in result["misconceptions"]


def test_retransmitting_acked_data_is_caught_as_misreading_cumulative_ack():
    actions = [{"op": "send"}] * 2 + [{"op": "wait"}] * 8 + [{"op": "retransmit", "seq": 0}]
    result = sim.score("single-loss", 7, actions + [{"op": "wait"}] * 40)
    assert "cumulative_ack_misread" in result["misconceptions"]


def test_step_does_not_mutate_the_state_it_was_given():
    """Pure transitions are what make the console replayable and checkpointable."""
    state = sim.init("single-loss", 7)
    before = state["tick"], list(state["attempts"]), len(state["events"])
    sim.step(state, {"op": "send"})
    assert (state["tick"], list(state["attempts"]), len(state["events"])) == before
