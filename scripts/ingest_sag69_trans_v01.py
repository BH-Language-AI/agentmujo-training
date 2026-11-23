#!/usr/bin/env python3
"""Ingest Sag69/bosnian-dataset (MIT) -> translation v0.1 (samo pravi bs<->en parovi).

Ulaz:  datasets.load_dataset('Sag69/bosnian-dataset', split='train', streaming=True)
Izlaz: datasets/canonical/translation_v0.1.jsonl (dva smjera po paru)

Nalaz: bs_to_en/en_to_bs redovi NE sadrze engleski prijevod — output je
'English translation: <bs rijec> - <bs rijec> (vrsta) - <bs definicija>'.
Skript parsira par i uzima ga SAMO ako su bs i en strana razlicite,
obje 2-500 znakova, latinica, bez mojibakea i sume (>15% ne-slova).
direction==structured se preskace (bs==en + format sum).
Uporaba: .venv/bin/python scripts/ingest_sag69_trans_v01.py [--limit N]
"""
import argparse
import json
import re
import string
import sys
from pathlib import Path

CYR = re.compile(r"[Ѐ-џ]")
CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\xad\u200b-\u200f\u2028-\u202f\u2060\ufeff]")
COMB = re.compile(r"[\u0300-\u036f\u0483-\u0489]")
REPEAT = re.compile(r"(.)\1{3,}")
MOJI = ("�", "Ã", "Â", "â€", "Å¾", "Å¡", "Ä‡", "Ã©", "Ã¨")
DIACR = re.compile(r"[čćđšžČĆĐŠŽ]")
EN_WORD = re.compile(r"[A-Za-z]{3,}")
BS_WORD = re.compile(r"[A-Za-zČĆĐŠŽčćđšž]{3,}")
PREFIX = re.compile(r"^\s*(English|Bosnian) translation:\s*(.*)$", re.S)
PUNCT = set(string.punctuation + "—–…«»„“”‘’´`")

OUT = Path("datasets/canonical/translation_v0.1.jsonl")
SRC = "Sag69/bosnian-dataset bilingual (MIT)"


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def entropy_bad(t: str) -> bool:
    if not t:
        return True
    bad = sum(1 for c in t if not (c.isalpha() or c.isspace() or c in PUNCT))
    return bad / len(t) > 0.15


def side_ok(t: str) -> bool:
    return (2 <= len(t) <= 500 and not CYR.search(t) and "�" not in t
            and not CTRL.search(t) and not COMB.search(t)
            and not REPEAT.search(t) and not any(m in t for m in MOJI)
            and not entropy_bad(t))


def parse_pair(direction: str, output: str):
    """Vrati (bs, en) ili None. Format je fiksan:
    '<rijec> - <rijec> (vrsta) - <definicija na bosanskom>'.
    Prva dva dijela su uvijek ista bs rijec -> nema prijevoda.
    Treci dio je definicija, NIKAD engleska glosa, pa se ne smije
    koristiti kao 'en' strana (inace nastaju lazni parovi poput
    'probitačno' -> 'korisno.'). Par postoji samo ako se prva dva
    dijela razlikuju i jezikoslovno odgovaraju smjeru."""
    m = PREFIX.match(output)
    if not m:
        return None
    parts = [p.strip() for p in m.group(2).split(" - ") if p.strip()]
    if len(parts) < 2:
        return None
    first = re.sub(r"\s*\(.*$", "", parts[0]).strip()
    second = re.sub(r"\s*\(.*$", "", parts[1]).strip()
    if not first or not second or norm(first) == norm(second):
        return None  # monolingvalni red (rijec + definicija), bez para
    if direction == "bs_to_en":
        bs, en = first, second
    else:
        bs, en = second, first
    if DIACR.search(en):
        return None
    if EN_WORD.search(en) and BS_WORD.search(bs) and norm(bs) != norm(en):
        return bs, en
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    from datasets import load_dataset

    from agentmujo_training.datasets.validator import validate_file
    from agentmujo_training.tools.registry import ToolRegistry

    stat = {"read": 0, "kept_pairs": 0, "kept_rows": 0, "skip_lang": 0,
            "skip_type": 0, "structured": 0, "no_prefix": 0, "no_pair": 0,
            "bad_side": 0, "dup": 0}
    dir_use: dict[str, int] = {}
    type_skip: dict[str, int] = {}
    seen: set[str] = set()
    rows: list[dict] = []

    ds = load_dataset("Sag69/bosnian-dataset", split="train", streaming=True)
    for r in ds:
        stat["read"] += 1
        if args.limit and stat["read"] > args.limit:
            break
        t = (r.get("type") or "").strip()
        d = (r.get("direction") or "").strip()
        if t != "bilingual_dictionary" or d not in ("bs_to_en", "en_to_bs"):
            if d == "structured":
                stat["structured"] += 1
            elif t != "bilingual_dictionary":
                stat["skip_type"] += 1
                type_skip[f"{t}/{d or '-'}"] = type_skip.get(f"{t}/{d or '-'}", 0) + 1
            else:  # bilingual_dictionary, ali direction definition/ostalo -> monolingvalno
                stat["skip_lang"] += 1
                type_skip[f"{t}/{d}"] = type_skip.get(f"{t}/{d}", 0) + 1
            continue
        out = (r.get("output") or "").strip()
        if not PREFIX.match(out):
            stat["no_prefix"] += 1
            continue
        pair = parse_pair(d, out)
        if not pair:
            stat["no_pair"] += 1
            continue
        bs, en = (p.strip() for p in pair)
        if not (side_ok(bs) and side_ok(en) and BS_WORD.search(bs)
                and EN_WORD.search(en)):
            stat["bad_side"] += 1
            continue
        key = norm(bs) + "\n" + norm(en)
        if key in seen:
            stat["dup"] += 1
            continue
        seen.add(key)
        stat["kept_pairs"] += 1
        dir_use[d] = dir_use.get(d, 0) + 1
        n = max(len(bs), len(en))
        diff = "easy" if n < 40 else "medium" if n < 120 else "hard"
        author = (r.get("author") or "").strip() or "unknown"
        word = (r.get("word") or "").strip()
        for i, (src_txt, tgt_txt, lab) in enumerate(
                ((bs, en, "engleski"), (en, bs, "bosanski"))):
            rows.append({
                "id": f"amj-tr-{len(rows) + 1:06d}",
                "version": "0.1.0",
                "language": "bs-ijekavica",
                "task": "translation",
                "difficulty": diff,
                "enable_thinking": False,
                "messages": [
                    {"role": "user", "content": f"Prevedi na {lab}: {src_txt}"},
                    {"role": "assistant", "content": tgt_txt},
                ],
                "metadata": {
                    "source": SRC,
                    "quality_tier": "SILVER",
                    "verification_status": "verified",
                    "license": "MIT",
                    "author": author,
                    "sag69_direction": d,
                    "sag69_word": word,
                },
            })
        stat["kept_rows"] = len(rows)
        if stat["read"] % 50000 == 0:
            print(f".. procitano {stat['read']}, parova {stat['kept_pairs']}", flush=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows),
                   encoding="utf-8")
    print(f"procitano: {stat['read']}")
    print(f"iskoristenost po direction: {dir_use}")
    print(f"zadrzano parova: {stat['kept_pairs']} -> redova: {len(rows)}")
    print(f"razlozi odbacivanja: structured={stat['structured']} "
          f"skip_type={stat['skip_type']} skip_other_dir={stat['skip_lang']} "
          f"{type_skip} no_prefix={stat['no_prefix']} "
          f"no_pair={stat['no_pair']} bad_side={stat['bad_side']} dup={stat['dup']}")
    print(f"-> {OUT}")

    reg = ToolRegistry("configs/tools.yaml")
    rep = validate_file(OUT, set(reg.names()), reg.validate_call)
    print(f"validate: total={rep['total']} accepted={rep['accepted']} "
          f"rejected={rep['rejected']} tiers={rep['tiers']}")
    if rep["rejected"]:
        print(json.dumps(rep["errors"][:10], ensure_ascii=False)[:2000])
        sys.exit(1)


if __name__ == "__main__":
    main()
