#!/usr/bin/env python3
"""Build datasets/canonical/joint_train_v0.50.jsonl — 9B-joint-16 restraint.

Hipoteza brief §3-4: mali, ostri restraint delta (60 GOLD redova: ask/refuse
prije mutacije, check-confirm-act, plan-first, log-lesson, HL-over-terminal)
na joint08 bazi. Lekcije joint09-15: prose-only truje trigger, veliki mix
diluira tool preciznost — zato SAMO 60 redova, svi sa kanonskim tool
formatom (osim cistih refusala). lr 2e-5 nastavak, 1 epoha.
Seed 49. Deterministicki.
"""
import json
import random
from pathlib import Path

RNG = random.Random(49)
ROOT = Path(__file__).resolve().parent.parent
CAN = ROOT / "datasets" / "canonical"
OUT = CAN / "joint_train_v0.50.jsonl"


def ok_msg(r):
    ms = r.get("messages")
    return bool(ms) and isinstance(ms, list) and len(ms) >= 2


def first_tool(row):
    for m in row.get("messages", []):
        tcs = m.get("tool_calls") or []
        if tcs:
            return tcs[0].get("name")
    return None


base = [json.loads(l) for l in open(CAN / "joint_train_v0.41.jsonl") if l.strip()]
seen = set(r["id"] for r in base)
rest = [json.loads(l) for l in open(CAN / "restraint_v0.1.jsonl") if l.strip()]
rest = [r for r in rest if r["id"] not in seen]
assert len(rest) == 60, f"ocekivano 60 restraint redova, nadjeno {len(rest)}"

sel = base + rest
ids = [r["id"] for r in sel]
assert len(ids) == len(set(ids)), "duplikati!"
assert all(ok_msg(r) for r in sel)

bench_prompts = set()
for v in ("0.1", "0.2", "0.3", "0.4", "0.5", "0.6"):
    p = ROOT / "benchmark" / f"cases_v{v}.jsonl"
    if p.exists():
        bench_prompts.update(json.loads(l)["prompt"] for l in open(p) if l.strip())


def first_user(row):
    ms = row.get("messages", [])
    return next((m.get("content", "") for m in ms if m.get("role") == "user"), "")


overlap = [r["id"] for r in sel if first_user(r) in bench_prompts]
assert not overlap, f"bench overlap: {overlap[:5]}"

RNG.shuffle(sel)
n_tool = sum(1 for r in sel if first_tool(r))
OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in sel) + "\n")
print(f"joint-16-9b: {len(sel)} (baza {len(base)} + restraint {len(rest)}, tool {n_tool})")
