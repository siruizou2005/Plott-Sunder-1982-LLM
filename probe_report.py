#!/usr/bin/env python3
"""The three numbers a vendor probe exists to produce.

Not a metrics module — `ps1982/metrics.py` scores the experiment. This answers the prior
question: is this model usable for the experiment at all? Each check corresponds to a
failure that was measured on a real run and that would otherwise be invisible.

  ./probe_report.py runs/probes/probe_qwen/<stamp>.jsonl
"""

from __future__ import annotations

import collections
import glob
import json
import re
import sys

# Market 3's correct prior expected values, and the answers a model gives when it reaches
# for a 50/50 prior instead of the bingo cage's 16-in-40.
CORRECT = {"I": 220, "II": 210, "III": 155}
NAIVE = {"I": 250, "II": 225, "III": 150}


def load(path):
    out = []
    for line in open(path, encoding="utf-8"):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            break                                  # a run mid-write: torn last line
    return out


def arithmetic(pairs, seat_type):
    """Count texts that state the market's true prior EV against ones that state the 50/50.

    Only texts naming exactly one of the two are counted; a text naming both, or neither,
    says nothing about which prior the model used.
    """
    right = wrong = 0
    for seat, text in pairs:
        t = seat_type.get(seat)
        if not t:
            continue
        nums = {int(x) for x in re.findall(r"\b\d{3}\b", text or "")}
        right += CORRECT[t] in nums and NAIVE[t] not in nums
        wrong += NAIVE[t] in nums and CORRECT[t] not in nums
    return right, wrong


def main(path):
    ev = load(path)
    if not ev:
        sys.exit(f"no events in {path}")
    seat_type = {}
    for e in ev:
        if e["type"] == "session_start":
            seat_type = e["payload"].get("seat_types", {})

    calls = [e for e in ev if e["type"] == "model_turn"]
    by_purpose = collections.defaultdict(lambda: collections.Counter())
    api_err = malformed = no_reasoning = 0
    latency = []
    for e in calls:
        p = e["payload"]
        k = p.get("purpose", "?")
        u = p.get("usage") or {}
        by_purpose[k]["n"] += 1
        by_purpose[k]["in"] += u.get("prompt_tokens", 0)
        by_purpose[k]["out"] += u.get("completion_tokens", 0)
        latency.append(p.get("latency_s", 0) or 0)
        err = str(p.get("error") or "")
        # These are different failures: an API error means the model never answered, so a
        # skipped turn was not the agent's choice. Unparseable JSON means it answered and
        # the answer was malformed — that is the model, and it is what we are measuring.
        if err and "unparseable" not in err.lower():
            api_err += 1
        elif err:
            malformed += 1
        no_reasoning += not (p.get("reasoning") or "").strip()

    print(f"\n  {'通道':16s}{'调用':>7s}{'平均输入':>9s}{'平均输出':>9s}")
    tn = ti = to = 0
    for k, v in sorted(by_purpose.items(), key=lambda x: -x[1]["n"]):
        print(f"  {k:16s}{v['n']:>7d}{v['in']//max(1,v['n']):>9d}{v['out']//max(1,v['n']):>9d}")
        tn += v["n"]; ti += v["in"]; to += v["out"]

    span = 0.0
    for a, b in ((ev[0], ev[-1]),):
        from datetime import datetime
        f = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
        span = (f(b["ts"]) - f(a["ts"])).total_seconds()

    print(f"\n  ① 算术 —— 是否用摇奖笼(16/40)而非 50/50")
    refl = arithmetic([(e["seat"], e["payload"]["text"]) for e in ev
                       if e["type"] == "reflection"], seat_type)
    bc = arithmetic([(r["seat"], r.get("why") or "") for e in ev
                     if e["type"] == "broadcast" for r in e["payload"]["responses"]], seat_type)
    r, w = refl[0] + bc[0], refl[1] + bc[1]
    tot = r + w
    verdict = "✓ 可用" if tot and r / tot >= 0.85 else ("⚠ 边缘" if tot and r / tot >= 0.6 else "✗ 不可用")
    print(f"     正确 {r}   50/50 {w}   正确率 {100*r/tot if tot else 0:.0f}%   {verdict}")
    print(f"     (对照: DeepSeek thinking 关 = 33% 正确, 开 = 92%)")

    print(f"\n  ② JSON 与调用健康")
    viol = collections.Counter(e["payload"].get("reason") for e in ev if e["type"] == "violation")
    print(f"     调用 {tn}   输出不可解析 {malformed} ({100*malformed/max(1,tn):.1f}%)"
          f"   API 失败 {api_err}")
    print(f"     推理内容缺失 {no_reasoning}/{tn}"
          f"{'   ⚠ thinking 可能没生效' if no_reasoning == tn else ''}")
    print(f"     违规 {dict(viol) or '无'}   成交 {sum(1 for e in ev if e['type']=='trade')}")

    print(f"\n  ③ 吞吐 —— 把 26 场的时间估计钉死")
    lat = sorted(latency)
    print(f"     墙钟 {span/60:.1f} min   输出 {to:,} tok   聚合 {to/max(1,span):.0f} tok/s")
    print(f"     单次延迟 中位 {lat[len(lat)//2]:.1f}s   P90 {lat[int(.9*len(lat))]:.1f}s")
    full = to / max(1, tn) * 3498 * 26          # 3498 calls/session measured on market 3
    print(f"     26 场推算: {full/1e6:.0f}M 输出 tok"
          f" → {full/max(1e-9, to/max(1,span))/3600:.1f} h"
          f" → GPU 约 ${full/max(1e-9, to/max(1,span))/3600*4.40:.0f}")


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else None
    if not p:
        c = sorted(glob.glob("runs/**/probe_qwen/*.jsonl", recursive=True))
        p = c[-1] if c else sys.exit("usage: ./probe_report.py <log.jsonl>")
    main(p)
