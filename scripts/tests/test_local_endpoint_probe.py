"""Cover for the three things the probe must not get wrong.

Each of these guards a failure this repository has actually suffered. A gate
that passes the wrong weights produced Q12 — three architectures behind one
alias, none of them recorded. A refusal body that is summarised instead of kept
produced two misdiagnoses of the judge's 400s on `:9090`. And a ladder that
keeps climbing past a failing rung measures the queue rather than the model,
which is the one number every later step is going to inherit.
"""

from __future__ import annotations

from scripts.local_endpoint_probe import (
    Call,
    bisect_ceiling,
    find_knee,
    identity_verdict,
    percentile,
    rung_stop_reason,
    summarize_rung,
)


def _calls(latencies, *, tokens=100, ok=True, body=None):
    return [
        Call(ok=ok, latency_s=lat, completion_tokens=tokens if ok else 0, body=body)
        for lat in latencies
    ]


class TestIdentityGate:
    def test_a_wrong_served_id_does_not_pass(self):
        # The live case on 2026-09-13: the alias `local` answered gemma while
        # the experiment was written for MiniCPM.
        verdict = identity_verdict("gemma-4-26B-it", "minicpm")
        assert verdict["passed"] is False
        assert verdict["served_model"] == "gemma-4-26B-it"

    def test_a_matching_substring_passes_case_insensitively(self):
        assert identity_verdict("MiniCPM5-2B-Q8", "minicpm")["passed"] is True

    def test_an_unreachable_endpoint_does_not_pass(self):
        # None must never be read as "no objection".
        assert identity_verdict(None, "minicpm")["passed"] is False

    def test_the_empty_expectation_is_not_a_wildcard_for_a_dead_endpoint(self):
        assert identity_verdict(None, "")["passed"] is False


class TestCeilingBisect:
    def test_finds_the_boundary_and_keeps_the_refusal_verbatim(self):
        body = '{"error":{"message":"n_predict 8192 > n_ctx 4096","code":400}}'

        def accepts(n):
            return (n <= 4096, None if n <= 4096 else body)

        result = bisect_ceiling(accepts, start=256, cap=1 << 20)
        assert result["largest_accepted"] == 4096
        assert result["smallest_refused"] == 4097
        # Verbatim: not a code, not a summary, not a truncation.
        assert result["refusal_body"] == body

    def test_a_refusal_at_the_starting_probe_stops_rather_than_bisecting(self):
        def accepts(n):
            return (False, "refused")

        result = bisect_ceiling(accepts, start=256)
        assert result["largest_accepted"] is None
        assert result["smallest_refused"] == 256
        assert "256" in result["note"]

    def test_a_server_that_never_refuses_reports_the_cap_not_a_ceiling(self):
        result = bisect_ceiling(lambda n: (True, None), start=256, cap=1024)
        assert result["largest_accepted"] == 1024
        assert result["smallest_refused"] is None
        assert "no ceiling" in result["note"]

    def test_it_does_not_probe_past_the_cap(self):
        seen = []

        def accepts(n):
            seen.append(n)
            return (True, None)

        bisect_ceiling(accepts, start=256, cap=2048)
        assert max(seen) <= 2048


class TestStopReasons:
    def test_a_clean_rung_continues(self):
        rung = summarize_rung(2, _calls([1.0] * 10), wall_s=5.0, loadavg=1.0)
        assert rung_stop_reason(rung, rung1_p50=1.0, cores=16) is None

    def test_any_error_stops_the_ladder(self):
        calls = _calls([1.0] * 9) + _calls([1.0], ok=False, body="HTTP 503 no slot")
        rung = summarize_rung(8, calls, wall_s=5.0, loadavg=1.0)
        assert "errored" in (rung_stop_reason(rung, rung1_p50=1.0, cores=16) or "")

    def test_a_p95_blowout_stops_the_ladder(self):
        # Nine fast calls and one that queued: p95 is the queued one.
        rung = summarize_rung(12, _calls([1.0] * 9 + [9.0]), wall_s=10.0, loadavg=1.0)
        assert "exceeds 4x rung-1 p50" in (rung_stop_reason(rung, rung1_p50=1.0, cores=16) or "")

    def test_a_saturated_box_stops_the_ladder(self):
        rung = summarize_rung(8, _calls([1.0] * 10), wall_s=5.0, loadavg=20.0)
        assert "load average" in (rung_stop_reason(rung, rung1_p50=1.0, cores=16) or "")

    def test_errors_are_reported_before_latency(self):
        # A rung that both errored and blew out names the error: a 503 explains
        # the latency, and the reverse ordering would hide the cause.
        calls = _calls([1.0] * 9) + _calls([40.0], ok=False, body="HTTP 503")
        rung = summarize_rung(12, calls, wall_s=40.0, loadavg=1.0)
        assert "errored" in (rung_stop_reason(rung, rung1_p50=1.0, cores=16) or "")


class TestSummary:
    def test_throughput_is_aggregate_over_the_wall_clock(self):
        # Ten calls of 100 tokens in 5 seconds of wall clock is 200 tok/s,
        # regardless of what any single stream managed.
        rung = summarize_rung(4, _calls([2.0] * 10, tokens=100), wall_s=5.0, loadavg=1.0)
        assert rung.tokens_per_s == 200.0
        assert rung.per_call_tokens_per_s == 50.0

    def test_failures_are_counted_and_their_bodies_sampled(self):
        calls = _calls([1.0] * 8) + _calls([1.0, 1.0], ok=False, body="HTTP 400 context")
        rung = summarize_rung(8, calls, wall_s=4.0, loadavg=1.0)
        assert (rung.ok, rung.errors) == (8, 2)
        assert "HTTP 400 context" in rung.error_samples[0]

    def test_a_failed_call_contributes_no_tokens(self):
        calls = _calls([1.0] * 5) + _calls([1.0] * 5, ok=False)
        rung = summarize_rung(4, calls, wall_s=5.0, loadavg=1.0)
        assert rung.completion_tokens == 500


class TestKnee:
    def test_a_plateau_prefers_the_lower_concurrency(self):
        # 4 buys nothing over 2, so 2 is the answer: same output, calmer box.
        rungs = [
            summarize_rung(1, _calls([1.0] * 10, tokens=100), wall_s=10.0, loadavg=1.0),
            summarize_rung(2, _calls([1.0] * 10, tokens=100), wall_s=5.0, loadavg=1.0),
            summarize_rung(4, _calls([1.0] * 10, tokens=100), wall_s=4.9, loadavg=1.0),
        ]
        assert find_knee(rungs) == 2

    def test_a_rung_that_errored_is_never_chosen(self):
        good = summarize_rung(1, _calls([1.0] * 10, tokens=100), wall_s=10.0, loadavg=1.0)
        bad = summarize_rung(8, _calls([1.0] * 9) + _calls([1.0], ok=False), wall_s=1.0, loadavg=1.0)
        assert find_knee([good, bad]) == 1

    def test_no_usable_rung_falls_back_to_one(self):
        assert find_knee([]) == 1


class TestPercentile:
    def test_nearest_rank(self):
        values = [float(i) for i in range(1, 11)]
        assert percentile(values, 50) == 5.0
        assert percentile(values, 95) == 10.0

    def test_empty_is_zero_not_an_exception(self):
        assert percentile([], 95) == 0.0
