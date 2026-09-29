"""One self-contained HTML file: the win-probability curve + the run, event by event."""
import html


def _label(e):
    if e["kind"] == "tool":
        args = ", ".join(f"{k}={v}" for k, v in e["args"].items())
        return f"{e['name']}({args})", str(e["out"])
    text = " ".join(b["text"] for b in e["out"] if b["type"] == "text")
    call = next((f"→ {b['name']}" for b in e["out"] if b["type"] == "tool_use"), "→ stop")
    return f"model {call}", text


def render(trace, path):
    ev, c = trace["events"], trace["curve"]
    blamed = {k: d for k, d in trace["blame"]}
    W, H, pad = 900, 240, 36
    x = lambda k: pad + k * (W - 2 * pad) / max(len(c) - 1, 1)
    y = lambda p: H - pad - p * (H - 2 * pad)
    pts = " ".join(f"{x(k)},{y(p)} {x(k + 1)},{y(p)}" for k, p in enumerate(c[:-1])) + f" {x(len(c) - 1)},{y(c[-1])}"
    marks = "".join(f'<line x1="{x(k + 1)}" x2="{x(k + 1)}" y1="{pad}" y2="{H - pad}" class="mark"/>'
                    f'<text x="{x(k + 1) + 4}" y="{pad + 12}" class="mt">#{k} −{d:.0%}</text>' for k, d in blamed.items())
    grid = "".join(f'<line x1="{pad}" x2="{W - pad}" y1="{y(g)}" y2="{y(g)}" class="grid"/>'
                   f'<text x="4" y="{y(g) + 4}" class="ax">{g:.0%}</text>' for g in (0, .5, 1))
    rows = []
    for e in ev:
        head, body = _label(e)
        d = blamed.get(e["i"])
        badge = f'<span class="drop">−{d:.0%} win prob</span>' if d else ""
        rows.append(f'<li class="{e["kind"]}{" hot" if d else ""}"><div class="h"><b>#{e["i"]}</b> '
                    f'<code>{html.escape(head)}</code>{badge}<span class="p">{c[e["i"]]:.0%} → {c[e["i"] + 1]:.0%}</span></div>'
                    f'<pre>{html.escape(body)}</pre></li>')
    fork = trace.get("fork")
    fork_html = (f'<div class="fork"><b>Counterfactual.</b> Replay to #{fork["at"]}, swap its output '
                 f'({html.escape(fork["why"])}), go live ×{fork["n"]}: success '
                 f'<b>{c[fork["at"] + 1]:.0%} → {fork["p"]:.0%}</b>.</div>') if fork else ""
    lost = trace["blame"][0][0] if trace["blame"] else len(ev) - 1
    page = f"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>agent-rewind report</title><style>
:root{{--bg:#0d1117;--fg:#e6edf3;--mut:#8b949e;--line:#30363d;--acc:#58a6ff;--bad:#f85149;--card:#161b22}}
@media (prefers-color-scheme:light){{:root{{--bg:#fff;--fg:#1f2328;--mut:#656d76;--line:#d0d7de;--card:#f6f8fa;--acc:#0969da;--bad:#cf222e}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;max-width:960px;margin:auto;padding:24px 16px}}
h1{{font-size:22px;margin:0}} .sub{{color:var(--mut);margin:4px 0 20px}}
svg{{width:100%;height:auto;background:var(--card);border:1px solid var(--line);border-radius:8px}}
polyline{{fill:none;stroke:var(--acc);stroke-width:2.5}} .grid{{stroke:var(--line)}} .ax,.mt{{fill:var(--mut);font-size:11px}}
.mark{{stroke:var(--bad);stroke-dasharray:4 3}} .mt{{fill:var(--bad)}}
ol{{list-style:none;padding:0}} li{{border:1px solid var(--line);border-radius:8px;margin:8px 0;padding:8px 12px;background:var(--card)}}
li.hot{{border-color:var(--bad)}} .h{{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}} .p{{margin-left:auto;color:var(--mut);font-variant-numeric:tabular-nums}}
.drop{{color:var(--bad);font-weight:600}} pre{{white-space:pre-wrap;color:var(--mut);margin:4px 0 0;font-size:13px}}
ul.fails{{list-style:none;padding:0;color:var(--bad)}} ul.fails li{{border-color:var(--bad)}} .fork{{border-left:3px solid var(--acc);padding:8px 12px;margin:16px 0;background:var(--card)}}
</style>
<h1>Run lost at event #{lost}. It only failed visibly at event #{len(ev) - 1}.</h1>
<p class="sub">seed {trace["seed"]} · {len(ev)} events · each point = success rate of {trace["n"]} live replays from that event</p>
<svg viewBox="0 0 {W} {H}">{grid}<polyline points="{pts}"/>{marks}</svg>
<ul class="fails">{"".join(f"<li>{html.escape(f)}</li>" for f in trace["fails"])}</ul>
{fork_html}<ol>{"".join(rows)}</ol>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)

