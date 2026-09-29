"""The tape: every LLM reply and tool result an agent sees, in order.

Replaying a tape feeds the agent the exact same outputs, so it walks the exact same path.
Tools are still executed during replay (their results are thrown away) so the world's
side effects - a rollback, a refund, a deleted file - are rebuilt, not faked.
"""


class Divergence(Exception):
    pass


class Tape:
    def __init__(self, prefix=(), edits=None):
        self.prefix = list(prefix)      # recorded events to replay before going live
        self.edits = edits or {}        # event index -> output the agent sees instead
        self.events = []

    def step(self, kind, name, args, live):
        i = len(self.events)
        if i < len(self.prefix):
            ev = self.prefix[i]
            if (ev["kind"], ev["name"], ev["args"]) != (kind, name, args):
                raise Divergence(f"event {i}: tape has {ev['name']}({ev['args']}), agent did {name}({args})")
            if kind == "tool":
                live()                  # rebuild side effects, keep the recorded result
            out = ev["out"]
        else:
            out = live()
        out = self.edits.get(i, out)
        self.events.append({"i": i, "kind": kind, "name": name, "args": args, "out": out,
                            "live": i >= len(self.prefix)})
        return out
