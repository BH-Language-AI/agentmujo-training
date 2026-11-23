#!/usr/bin/env python3
"""Ingest SWE-Gym/SWE-Gym train -> swe_gym_train v0.1 (coding ekspanzija).

Ulaz:  datasets.load_dataset('SWE-Gym/SWE-Gym', split='train', streaming=True)
Izlaz: datasets/canonical/swe_gym_train_v0.1.jsonl (CAP 1500 redova)

Provjere (2026-11-03): card license MIT; samo train split (2438);
overlap instance_id vs SWE-bench dev/test = 0 -> nema eval kontaminacije.

Format: user = bs uvod + EN problem_statement (skracen ~1500 znakova),
assistant = opis rjesenja na bosanskom (cijeli patch SAMO ako <=100 linija,
inace sumarni opis: fajlovi, +/- statistika, testovi).
Dedup: instance_id unutar runa + sadrzajno protiv postojecih coding redova.
Uporaba: .venv/bin/python scripts/ingest_swegym_v01.py
"""
import argparse
import json
import re
import sys
from pathlib import Path

OUT = Path("datasets/canonical/swe_gym_train_v0.1.jsonl")
SRC = "SWE-Gym train (MIT)"
CODING_FILES = sorted(Path("datasets/canonical").glob("coding_repo_v0.*.jsonl"))


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def old_keys() -> set[str]:
    seen = set()
    for f in CODING_FILES:
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            msgs = r.get("messages") or []
            users = [m.get("content", "") for m in msgs if m.get("role") == "user"]
            assists = [m.get("content", "") for m in msgs if m.get("role") == "assistant"]
            if users and assists:
                seen.add(norm(users[0]) + "\n" + norm(assists[-1]))
    return seen


def short(text: str, limit: int = 1500) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = max(text.rfind("\n", 0, limit), text.rfind(" ", 0, limit))
    return text[: cut if cut > limit // 2 else limit].rstrip() + " […]"


def patch_summary(patch: str) -> tuple[list[str], int, int, int]:
    files, add, dele = [], 0, 0
    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            files.append(line[6:])
        elif line.startswith("+") and not line.startswith("+++"):
            add += 1
        elif line.startswith("-") and not line.startswith("---"):
            dele += 1
    return files, add, dele, len(patch.splitlines())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=1500)
    args = ap.parse_args()
    from datasets import load_dataset
    from agentmujo_training.datasets.validator import DENY_PATTERNS
    deny = [re.compile(p) for p in DENY_PATTERNS]

    seen = old_keys()
    print(f"postojecih coding kljuceva: {len(seen)}", flush=True)
    seen_ids: set[str] = set()
    rows: list[dict] = []
    stat = {"read": 0, "dup_id": 0, "dup_content": 0, "empty": 0, "safety_deny": 0, "full_patch": 0, "summarized": 0}

    for r in load_dataset("SWE-Gym/SWE-Gym", split="train", streaming=True):
        stat["read"] += 1
        iid, ps, patch = r.get("instance_id") or "", (r.get("problem_statement") or "").strip(), r.get("patch") or ""
        if not iid or not ps:
            stat["empty"] += 1
            continue
        if iid in seen_ids:
            stat["dup_id"] += 1
            continue
        seen_ids.add(iid)
        ps_short = short(ps)
        _files, add, dele, nlines = patch_summary(patch)
        if patch.strip() and nlines <= 100:
            sol = ("Rješenje (patch iz repozitorija, skraćeno na suštinu):\n"
                   f"```diff\n{patch.strip()}\n```")
            stat["full_patch"] += 1
        else:
            fnames = ", ".join(f"`{f}`" for f in _files[:10]) or "nepoznati fajlovi"
            tests = ", ".join(f"`{t}`" for t in (r.get("FAIL_TO_PASS") or [])[:5])
            sol = (f"Rješenje mijenja {fnames} (+{add}/-{dele} linija u {nlines} linija diffa). "
                   + (f"Popravka prolazi testove: {tests}." if tests else "Vezani testovi navedeni su u FAIL_TO_PASS polju izvora."))
            stat["summarized"] += 1
        user = (f"Riješi sljedeći problem iz repozitorija `{r.get('repo')}` "
                f"(SWE-Gym instanca `{iid}`). Opis problema na engleskom:\n\n{ps_short}")
        asst = (f"Analiza problema: {short(ps, 400)}\n\n{sol}\n\n"
                f"Repozitorij: `{r.get('repo')}`, instanca `{iid}`.")
        key = norm(user) + "\n" + norm(asst)
        if any(p.search(user) or p.search(asst) for p in deny):
            stat["safety_deny"] += 1
            continue
        if key in seen:
            stat["dup_content"] += 1
            continue
        seen.add(key)
        n = len(ps)
        diff = "easy" if n < 800 else "medium" if n < 2500 else "hard"
        rows.append({
            "id": f"amj-sg-{len(rows) + 1:06d}",
            "version": "0.1.0",
            "language": "bs-ijekavica",
            "task": "coding",
            "difficulty": diff,
            "messages": [{"role": "user", "content": user},
                         {"role": "assistant", "content": asst}],
            "metadata": {"source": SRC, "quality_tier": "SILVER",
                         "verification_status": "verified", "license": "MIT",
                         "instance_id": iid, "repo": r.get("repo")},
        })
        if len(rows) >= args.limit:
            break

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")
    print(f"procitano: {stat['read']}, zadrzano: {len(rows)}, dup_id: {stat['dup_id']}, "
          f"dup_content: {stat['dup_content']}, prazno: {stat['empty']}, safety_deny: {stat['safety_deny']}, "
          f"full_patch: {stat['full_patch']}, sumarizovano: {stat['summarized']} -> {OUT}")

    from agentmujo_training.datasets.validator import validate_file
    from agentmujo_training.tools.registry import ToolRegistry
    reg = ToolRegistry("configs/tools.yaml")
    rep = validate_file(OUT, set(reg.names()), reg.validate_call)
    print(f"validate: total={rep['total']} accepted={rep['accepted']} "
          f"rejected={rep['rejected']} tiers={rep['tiers']}")
    if rep["rejected"]:
        print(json.dumps(rep["errors"][:10], ensure_ascii=False)[:2000])
        sys.exit(1)


if __name__ == "__main__":
    main()
