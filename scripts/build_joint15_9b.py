#!/usr/bin/env python3
"""Build datasets/canonical/joint_train_v0.49.jsonl — 9B-joint-15 veci conf mix.

Hipoteza (a): joint14 delta (200 conf + 100 safety) digla loop conf
0.0->0.7 ali premalo da drzi tool (0.824<0.912); vise conf-tool uzoraka
bi moglo dati conf 0.9+ bez pada toola — conf-tool redovi NOSE alat
(ask + read-only check), za razliku od prose-only koji truje trigger.
Lekcije: baza joint08 (sampion), NE joint14; lr 2e-5; bez prose-only.
Seed 48. Deterministicki.
"""
import json
import random
from pathlib import Path

RNG = random.Random(48)
ROOT = Path(__file__).resolve().parent.parent
CAN = ROOT / "datasets" / "canonical"
OUT = CAN / "joint_train_v0.49.jsonl"

CF_FILES = [f"confirmation_v0.{v}.jsonl" for v in ("1", "2", "3", "4")]
SF_FILES = [f"safety_v0.{v}.jsonl" for v in ("2", "3", "4", "5")]


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


def safecat(r):
    return (r.get("metadata") or {}).get("safety_category", "?")


base = [json.loads(l) for l in open(CAN / "joint_train_v0.41.jsonl") if l.strip()]
v48_ids = set(json.loads(l)["id"] for l in open(CAN / "joint_train_v0.48.jsonl") if l.strip())
seen = set(r["id"] for r in base) | v48_ids

def dedup(rows):
    out, seen_ids = [], set()
    for r in rows:
        if r["id"] not in seen_ids:
            seen_ids.add(r["id"])
            out.append(r)
    return out


# Confirmation SA alatom (sve svjeze, ne samo 200 kao joint14).
cf_pool = dedup([r for r in load(CF_FILES)
                 if first_tool(r) is not None and r["id"] not in seen])
RNG.shuffle(cf_pool)
cf = cf_pool[:500]

# Safety edge: prioritet fail-modovi, sve svjeze (izvan v48).
sf_pool = dedup([r for r in load(SF_FILES) if r["id"] not in seen])
prio = [r for r in sf_pool if safecat(r) in ("agentic-tool-poison", "multiturn-escalation",
                                            "false-verification", "data-exfiltration")]
rest = [r for r in sf_pool if r not in prio]
RNG.shuffle(prio)
RNG.shuffle(rest)
sf = (prio + rest)[:150]

sel = base + cf + sf
ids = [r["id"] for r in sel]
assert len(ids) == len(set(ids)), "duplikati!"
assert all(ok_msg(r) for r in sel)

# Leakage: bez doslovnog preklopa sa bench promptovima.
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
from collections import Counter
print(f"joint-15-9b: {len(sel)} (baza {len(base)} + conf-tool {len(cf)} + safety {len(sf)}, tool {n_tool})")
print("safety mix:", dict(Counter(safecat(r) for r in sf)))
