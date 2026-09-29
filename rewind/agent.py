"""The agent loop. Every model reply and tool result goes through the tape - that's the whole trick."""
import random

from .oncall import SYSTEM, TOOLS, World, mock_llm
from .tape import Tape

MAX_TURNS = 15


def run(seed=0, prefix=(), edits=None, llm=None):
    rng = random.Random(seed)
    world, tape = World(rng), Tape(prefix, edits)
    llm = llm or mock_llm(rng)
    messages = [{"role": "user", "content": "PagerDuty just paged you. Handle the incident."}]
    for _ in range(MAX_TURNS):
        blocks = tape.step("llm", "llm", None, lambda: llm(SYSTEM, messages, TOOLS))
        messages.append({"role": "assistant", "content": blocks})
        uses = [b for b in blocks if b["type"] == "tool_use"]
        if not uses:
            break
        messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": b["id"],
             "content": tape.step("tool", b["name"], b["input"], lambda: world.call(b["name"], b["input"]))}
            for b in uses]})
    return {"seed": seed, "events": tape.events, "fails": world.grade()}
