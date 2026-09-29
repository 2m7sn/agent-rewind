"""rewind - time-travel debugger for AI agents.

  rewind demo                          record a failing run, find where it was lost, prove the fix
  rewind record [--seed S] [--real]    record one run to a tape (JSON)
  rewind curve TAPE [-n N]             win-probability per event + blame + HTML report
  rewind bisect TAPE [-n N]            point of no return in log2(events) probes (cheap on real models)
  rewind fork TAPE --at K --out TEXT   what if event K had returned TEXT?
"""
import argparse
import json
import sys
from pathlib import Path

from . import analysis, report
from .agent import run
from .oncall import FULL_CHECKOUT_LOGS, claude_llm

RED, DIM, BOLD, OFF = "\033[31m", "\033[2m", "\033[1m", "\033[0m"


def factory(tape):
    return (lambda: claude_llm(tape["model"])) if tape.get("model") else None


def save(tape, path):
    Path(path).write_text(json.dumps(tape, indent=1), encoding="utf-8")


def show(tape):
    c, blamed = tape.get("curve"), dict(tape.get("blame", []))
    for e in tape["events"]:
        head, body = report._label(e)
        p = f"{c[e['i']]:>4.0%} {'█' * round(c[e['i']] * 20):<20} " if c else ""
        hot = f"{RED}{BOLD}  −{blamed[e['i']]:.0%} ← lost here{OFF}" if e["i"] in blamed else ""
        print(f"{p}#{e['i']:<3}{head[:60]:<60}{DIM}{body[:50].splitlines()[0] if body else ''}{OFF}{hot}")
    print(f"{RED}FAILED: {'; '.join(tape['fails'])}{OFF}" if tape["fails"] else "PASSED")


def do_curve(tape, n):
    tape["n"] = n
    tape["curve"] = analysis.curve(tape["events"], n, factory(tape))
    tape["blame"] = analysis.blame(tape["events"], tape["curve"])
    return tape


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rewind", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["demo", "record", "show", "curve", "bisect", "fork"])
    ap.add_argument("tape", nargs="?", default="tape.json")
    ap.add_argument("-n", type=int, help="live replays per probe (default 40 offline, 5 on a real model)")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--real", action="store_true", help="use Claude (needs ANTHROPIC_API_KEY)")
    ap.add_argument("--model", default="claude-sonnet-5-5")
    ap.add_argument("--at", type=int)
    ap.add_argument("--out", help="replacement output for --at (text, or @file)")
    ap.add_argument("--html", default="report.html")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252

    if a.cmd in ("demo", "record"):
        a.n = a.n or (5 if a.real else 40)
        llm = (lambda: claude_llm(a.model)) if a.real else lambda: None
        seeds = [a.seed] if a.seed is not None else range(10 if a.real else 1000)  # cap paid attempts
        tape = next((t for t in (run(s, llm=llm()) for s in seeds) if t["fails"] or a.cmd == "record"), None)
        if tape is None:
            return print(f"No failing run in {len(seeds)} tries - this agent is doing fine here.")
        tape["model"] = a.model if a.real else None
        if a.cmd == "record":
            save(tape, a.tape)
            return show(tape)
        print(f"{BOLD}1. Recorded a failing on-call run (seed {tape['seed']}). The failure shows at the end:{OFF}")
        show(tape)
        print(f"\n{BOLD}2. Rewinding to every event, {a.n} live replays each...{OFF}")
        show(do_curve(tape, a.n))
        at = next(e["i"] for e in tape["events"] if e["name"] == "search_logs")
        p = analysis.fork(tape["events"], at, FULL_CHECKOUT_LOGS, a.n, factory(tape))
        tape["fork"] = {"at": at, "p": p, "n": a.n, "why": "log search returns every line instead of a 3-line sample"}
        print(f"\n{BOLD}3. Fork: replay to #{at}, give the agent full logs instead of a sample:{OFF} "
              f"success {tape['curve'][at + 1]:.0%} → {p:.0%}")
        save(tape, a.tape)
        report.render(tape, a.html)
        return print(f"\nTape → {a.tape}   Report → {a.html}")

    tape = json.loads(Path(a.tape).read_text(encoding="utf-8"))
    a.n = a.n or (5 if tape.get("model") else 40)
    if a.cmd == "show":
        show(tape)
    elif a.cmd == "curve":
        show(do_curve(tape, a.n))
        save(tape, a.tape)
        report.render(tape, a.html)
        print(f"Report → {a.html}")
    elif a.cmd == "bisect":
        k, probes = analysis.bisect(tape["events"], a.n, factory(tape))
        for i, p in sorted(probes.items()):
            print(f"  replay from #{i:<3} {p:>4.0%}")
        if k is None:
            return print("Never winnable: the agent fails from step 0. Fix the agent, not this run.")
        print(f"{BOLD}Point of no return: event #{k}{OFF} ({report._label(tape['events'][k])[0]}) "
              f"- {len(probes) * a.n} runs instead of {len(tape['events']) * a.n}")
    elif a.cmd == "fork":
        if a.at is None or a.out is None:
            sys.exit("fork needs --at and --out")
        out = Path(a.out[1:]).read_text(encoding="utf-8") if a.out.startswith("@") else a.out
        if tape["events"][a.at]["kind"] == "llm":
            out = json.loads(out)       # model events take a list of content blocks
        before = analysis.p_at(tape["events"], a.at + 1, a.n, factory(tape))
        after = analysis.fork(tape["events"], a.at, out, a.n, factory(tape))
        print(f"#{a.at} as recorded: {before:.0%}   #{a.at} edited: {BOLD}{after:.0%}{OFF}")


if __name__ == "__main__":
    main()
