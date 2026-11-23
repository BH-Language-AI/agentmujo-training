#!/usr/bin/env python3
"""Ingest Sag69/bosnian-dataset (MIT) -> bosnian_core v0.2 (samo Bosnian redovi).

Ulaz:  datasets.load_dataset('Sag69/bosnian-dataset', split='train', streaming=True)
Izlaz: datasets/canonical/bosnian_core_v0.2.jsonl (cilj: sto vise cistih redova)

Filteri (strogo, ovim redom): latinica only -> kontrolni znakovi/mojibake
-> output 20-1500 znakova -> instruction neprazan -> dedup (unutar novog +
protiv v0.1). Plus validator-nuzni: DENY obrasci i EN-smjer prijevoda.
Uporaba: .venv/bin/python scripts/ingest_sag69_bc_v02.py
"""
import argparse
import json
import re
import sys
from pathlib import Path

CYR = re.compile(r"[Ѐ-џ]")
CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\xad\u200b-\u200f\u2028-\u202f\u2060\ufeff]")
COMB = re.compile(r"[\u0300-\u036f\u0483-\u0489]")
REPEAT = re.compile(r"(.)\1{3,}")
MOJI = ("�", "Ã", "Â", "â€", "Å¾", "Å¡", "Ä‡", "Ä‡", "Ã©", "Ã¨")
DIACR = re.compile(r"[čćđšžČĆĐŠŽ]")
EN_DIR = "prevedi na engleski"

OLD = Path("datasets/canonical/bosnian_core_v0.1.jsonl")
OUT = Path("datasets/canonical/bosnian_core_v0.2.jsonl")
SRC = "Sag69/bosnian-dataset (MIT)"


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def old_keys_and_max() -> tuple[set[str], int]:
    seen, mx = set(), 0
    for line in OLD.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        try:
            mx = max(mx, int(r["id"].split("-")[-1]))
        except (ValueError, KeyError):
            pass
        msgs = r.get("messages") or []
        users = [m.get("content", "") for m in msgs if m.get("role") == "user"]
        assists = [m.get("content", "") for m in msgs if m.get("role") == "assistant"]
        if users and assists:
            seen.add(norm(users[0]) + "\n" + norm(assists[-1]))
    return seen, mx


def bad_caps_punct(t: str) -> bool:
    if REPEAT.search(t):
        return True
    alpha = [c for c in t if c.isalpha()]
    if len(alpha) >= 20 and sum(c.isupper() for c in alpha) / len(alpha) > 0.7:
        return True
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="samo prvih N procitanih redova (0 = svi)")
    args = ap.parse_args()
    from datasets import load_dataset

    from agentmujo_training.datasets.validator import DENY_PATTERNS
    deny = [re.compile(p) for p in DENY_PATTERNS]

    seen_v01, mx = old_keys_and_max()
    seen = set(seen_v01)
    print(f"v0.1: {len(seen_v01)} kljuceva, max id = {mx}", flush=True)

    stat = {"read": 0, "kept": 0, "skip_lang_en": 0, "skip_lang_bi": 0,
            "skip_lang_other": 0, "cyrillic": 0, "control_mojibake": 0,
            "caps_punct": 0, "len": 0, "empty_instruction": 0,
            "safety_deny": 0, "en_direction": 0, "dup_new": 0, "dup_v01": 0}
    type_ct: dict[str, int] = {}
    diff_ct = {"easy": 0, "medium": 0, "hard": 0}

    rows: list[dict] = []
    ds = load_dataset("Sag69/bosnian-dataset", split="train", streaming=True)
    for r in ds:
        stat["read"] += 1
        if args.limit and stat["read"] > args.limit:
            break
        lang = (r.get("language") or "").strip()
        if lang != "Bosnian":
            stat["skip_lang_en" if lang == "English"
                 else "skip_lang_bi" if lang == "Bilingual"
                 else "skip_lang_other"] += 1
            continue
        instr = (r.get("instruction") or "").strip()
        inp = (r.get("input") or "").strip()
        out = (r.get("output") or "").strip()
        user = instr + ("\n" + inp if inp else "")
        blob = user + "\n" + out
        if CYR.search(blob):
            stat["cyrillic"] += 1
            continue
        if ("�" in blob or CTRL.search(blob) or COMB.search(blob)
                or any(m in blob for m in MOJI)
                or not re.search(r"[A-Za-zČĆĐŠŽčćđšž]{3,}", out)):
            stat["control_mojibake"] += 1
            continue
        if bad_caps_punct(blob):
            stat["caps_punct"] += 1
            continue
        if not 20 <= len(out) <= 1500:
            stat["len"] += 1
            continue
        if not instr:
            stat["empty_instruction"] += 1
            continue
        if any(p.search(out) for p in deny):
            stat["safety_deny"] += 1
            continue
        if user.strip().lower().startswith(EN_DIR) and DIACR.search(out):
            stat["en_direction"] += 1
            continue
        key = norm(user) + "\n" + norm(out)
        if key in seen_v01:
            stat["dup_v01"] += 1
            continue
        if key in seen:
            stat["dup_new"] += 1
            continue
        seen.add(key)
        n = len(out)
        diff = "easy" if n < 150 else "medium" if n < 500 else "hard"
        diff_ct[diff] += 1
        t = (r.get("type") or "unknown").strip() or "unknown"
        type_ct[t] = type_ct.get(t, 0) + 1
        rows.append({
            "id": f"amj-bc-{mx + len(rows) + 1:04d}",
            "version": "0.2.0",
            "language": "bs-ijekavica",
            "task": "bosnian-core",
            "difficulty": diff,
            "enable_thinking": False,
            "messages": [
                {"role": "user", "content": user},
                {"role": "assistant", "content": out},
            ],
            "metadata": {
                "source": SRC,
                "quality_tier": "SILVER",
                "verification_status": "verified",
                "license": "MIT",
                "author": (r.get("author") or "").strip() or "unknown",
                "sag69_type": t,
            },
        })
        if stat["read"] % 50000 == 0:
            print(f".. procitano {stat['read']}, zadrzano {len(rows)}", flush=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                   encoding="utf-8")

    dropped = stat["read"] - (stat["skip_lang_en"] + stat["skip_lang_bi"]
                              + stat["skip_lang_other"]) - len(rows)
    print(f"procitano: {stat['read']}")
    print(f"preskoceno (jezik): en={stat['skip_lang_en']} "
          f"bi={stat['skip_lang_bi']} other={stat['skip_lang_other']}")
    print(f"zadrzano: {len(rows)}")
    print(f"odbaceno (Bosnian): {dropped} | cirilica={stat['cyrillic']} "
          f"mojibake_kontrolni={stat['control_mojibake']} caps_punct={stat['caps_punct']} "
          f"duzina={stat['len']} prazna_instrukcija={stat['empty_instruction']} "
          f"safety_deny={stat['safety_deny']} en_smjer={stat['en_direction']} "
          f"dedup_v01={stat['dup_v01']} dedup_new={stat['dup_new']}")
    print(f"tipovi: {type_ct}")
    print(f"difficulty: {diff_ct}")
    print(f"-> {OUT}")

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
