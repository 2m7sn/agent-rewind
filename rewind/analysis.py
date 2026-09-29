"""Win-probability for agents.

p(k) = chance the run still succeeds if we freeze the first k events and let the agent
live from there. p(0) is the agent's base rate, p(n) is what actually happened (0 or 1).
The event where p falls hardest is where the run was lost - usually far from where it crashed.
"""
from .agent import run as default_run


def p_at(events, k, n, llm_factory=None, edits=None, seed0=10_000, run=default_run):
    wins = 0
    for s in range(seed0, seed0 + n):
        llm = llm_factory() if llm_factory else None
        wins += not run(seed=s, prefix=events[:k], edits=edits, llm=llm)["fails"]
    return wins / n


def curve(events, n, llm_factory=None, run=default_run):
    # ponytail: n runs per event, O(len*n) agent runs. Use bisect() when runs cost money.
    return [p_at(events, k, n, llm_factory, run=run) for k in range(len(events))] + [p_at(events, len(events), 1, run=run)]


def blame(events, c, top=3):
    """Events ranked by how much success probability they burned."""
    drops = [(c[k] - c[k + 1], k) for k in range(len(events))]
    return [(k, d) for d, k in sorted(drops, reverse=True)[:top] if d > 0]


def bisect(events, n, llm_factory=None, thr=0.5, run=default_run):
    """Point of no return in O(log len) probes: last k with p(k) >= thr. Assumes p only falls."""
    probes = {0: p_at(events, 0, n, llm_factory, run=run)}
    if probes[0] < thr:
        return None, probes             # never winnable: the agent itself is the problem, not this run
    lo, hi = 0, len(events)             # invariant: p(lo) >= thr > p(hi)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        probes[mid] = p_at(events, mid, n, llm_factory, run=run)
        lo, hi = (mid, hi) if probes[mid] >= thr else (lo, mid)
    return lo, probes


def fork(events, at, out, n, llm_factory=None, run=default_run):
    """What if event `at` had returned `out`? Replays up to it, swaps the output, runs live n times."""
    return p_at(events, at + 1, n, llm_factory, edits={at: out}, run=run)
