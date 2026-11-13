"""T3: calibrators recover their target, the leak check catches names, distance behaves."""
import random
import statistics

import pytest

from utils.killtests.t3 import calibrate as C


def test_split_quantile_recovers_coverage_on_toy_data():
    rng = random.Random(0)
    covs = []
    for _ in range(300):
        cal = [rng.random() for _ in range(500)]
        test = [rng.random() for _ in range(200)]
        q = C.split_quantile(cal, 0.1)
        covs.append(sum(x <= q for x in test) / len(test))
    assert abs(statistics.mean(covs) - 0.9) < 0.01


def test_spi_recovers_coverage_and_resists_shift():
    rng = random.Random(1)
    same, shifted, naive = [], [], []
    for _ in range(150):
        real = [rng.random() for _ in range(30)]
        test = [rng.random() for _ in range(200)]
        synth = [rng.random() for _ in range(800)]
        q = C.spi_threshold(real, synth, 0.1)
        same.append(sum(x <= q for x in test) / 200)
        synth2 = [0.7 * rng.random() for _ in range(800)]
        q2 = C.spi_threshold(real, synth2, 0.1)
        shifted.append(sum(x <= q2 for x in test) / 200)
        naive.append(sum(x <= C.split_quantile(synth2, 0.1) for x in test) / 200)
    assert abs(statistics.mean(same) - 0.9) < 0.02
    assert statistics.mean(shifted) > statistics.mean(naive) + 0.15


def test_too_few_scores_give_infinite_threshold():
    assert C.split_quantile([0.1] * 5, 0.1) == float("inf")


def test_prediction_set():
    assert C.prediction_set({"a": 0.95, "b": 0.04, "c": 0.01}, 0.1) == ["a"]
    assert sorted(C.prediction_set({"a": 0.5, "b": 0.45}, 0.6)) == ["a", "b"]


def _live_entities():
    from utils.config import load_env
    load_env()
    from utils.killtests import candidates
    e = candidates.entity("T1047")
    if e is None:
        pytest.skip("canonical snapshot not present")
    return candidates


def test_leak_check_catches_name_id_and_alias():
    cands = _live_entities()
    from utils.killtests.t3 import generate as G
    wmi = cands.entity("T1047")
    assert G.leaks("abuse of Windows Management Instrumentation", wmi)
    assert G.leaks("what is T1047", wmi)
    assert not G.leaks("a built-in administrative scripting interface on hosts", wmi)
    apt29 = cands.entity("G0016")
    al = G.aliases("attack").get("G0016", ())
    if al:
        assert G.leaks(f"the group called {al[0]}", apt29)


def test_distance_is_zero_for_names_and_high_for_descriptions():
    _live_entities()
    from utils.killtests.t3.run import distance
    assert distance("What is Windows Management Instrumentation?") == 0.0
    assert distance("adversaries leveraging covert relay networks of outdated routers") > 0.3
