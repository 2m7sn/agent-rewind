from rewind.agent import run
from rewind.analysis import bisect, blame, curve, fork
from rewind.oncall import FULL_CHECKOUT_LOGS
from rewind.tape import Divergence, Tape

FAIL = next(t for t in (run(s) for s in range(100)) if t["fails"])


def test_replay_is_exact():
    r = run(seed=12345, prefix=FAIL["events"])
    assert [e["out"] for e in r["events"]] == [e["out"] for e in FAIL["events"]]
    assert r["fails"] == FAIL["fails"]
    assert not any(e["live"] for e in r["events"])


def test_replay_rebuilds_side_effects():
    # the checkout rollback in the tape must really re-happen, not just be echoed back
    assert any("checkout" in f for f in run(seed=1, prefix=FAIL["events"])["fails"])


def test_divergence_is_caught():
    t = Tape(prefix=[{"kind": "tool", "name": "get_alert", "args": {}, "out": "x"}])
    try:
        t.step("tool", "rollback", {}, lambda: None)
        assert False
    except Divergence:
        pass


def test_curve_blames_the_cause_not_the_crash():
    c = curve(FAIL["events"], 60)
    assert c[0] > 0.5 and c[-1] == 0
    lost = [FAIL["events"][k]["name"] for k, _ in blame(FAIL["events"], c)]
    assert lost[0] in ("search_logs", "llm")          # the lossy log read or the hasty guess
    assert "post_update" not in lost                   # not where it visibly failed


def test_bisect_and_fork():
    k, _ = bisect(FAIL["events"], 30)
    assert FAIL["events"][k]["name"] in ("search_logs", "llm") and k < len(FAIL["events"]) // 2
    at = next(e["i"] for e in FAIL["events"] if e["name"] == "search_logs")
    assert fork(FAIL["events"], at, FULL_CHECKOUT_LOGS, 30) == 1.0
