#!/usr/bin/env python3
"""Build datasets/canonical/joint_train_v0.45.jsonl — 9B-joint-11 careful delta.

Lekcija joint10 (tool 0.867->0.167, brbljanje): 45% non-tool proze + lr 5e-5
na dvaput-nastavljenom LoRA = divergencija (train loss 0.483 varao, gap 0.72).
Pravila: (1) baza joint08 (sampion, loop-verifikovan), NE joint10;
(2) MALI delta: joint08 mix (1850) + 100 prose-first + 12 override;
(3) lr 2e-5 za nastavke (pola od fresh SFT) — sprijeciti divergenciju.
Seed 44. Deterministicki.
"""
import json
import random
from pathlib import Path

RNG = random.Random(44)
ROOT = Path(__file__).resolve().parent.parent
CAN = ROOT / "datasets" / "canonical"
OUT = CAN / "joint_train_v0.45.jsonl"

CF_FILES = [f"confirmation_v0.{v}.jsonl" for v in ("1", "2", "3", "4")]
SF_FILES = [f"safety_v0.{v}.jsonl" for v in ("3", "4", "5")]
FC1 = ["function_calling_v0.1.jsonl"]


def load(files):
    rows = []
    for f in files:
        p = CAN / f
        if p.exists():
            rows += [json.loads(l) for l in open(p) if l.strip()]
    return rows


def ok_msg(r):
    ms = r.get("messages")
    return bool(ms) and isinstance(ms, list) and len(ms) >= 2


def first_tool(row):
    for m in row.get("messages", []):
        tcs = m.get("tool_calls") or []
        if tcs:
            return tcs[0].get("name")
    return None


def first_user(row):
    ms = row.get("messages", [])
    return next((m.get("content", "") for m in ms if m.get("role") == "user"), "")


def first_asst_no_tool(row):
    ms = [m for m in row.get("messages", []) if m.get("role") == "assistant"]
    return bool(ms) and not (ms[0].get("tool_calls") or [])


base = [json.loads(l) for l in open(CAN / "joint_train_v0.41.jsonl") if l.strip()]
seen = set(r["id"] for r in base)

sf = load(SF_FILES)
cf = [r for r in load(CF_FILES) if first_tool(r) is None]
prose_pool = [r for r in sf + cf if first_asst_no_tool(r) and r["id"] not in seen]
RNG.shuffle(prose_pool)
prose = prose_pool[:100]

ov_pool = [r for r in load(FC1)
           if "terminal" in first_user(r).lower()
           and first_tool(r) not in (None, "terminal")
           and r["id"] not in seen]
RNG.shuffle(ov_pool)
ov = ov_pool[:12]

sel = base + prose + ov
ids = [r["id"] for r in sel]
assert len(ids) == len(set(ids)), "duplikati!"
assert all(ok_msg(r) for r in sel)
RNG.shuffle(sel)
OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in sel) + "\n")
print(f"joint-11-9b: {len(sel)} (baza {len(base)} + prose {len(prose)} + override {len(ov)})")
