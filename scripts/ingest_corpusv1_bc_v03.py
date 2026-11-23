#!/usr/bin/env python3
"""Ingest HF hyper-efficient-system-llc/bosnian-corpus-v1 -> bosnian_core v0.3.

Ulaz:  globalna datoteka bosnian_corpus_all.txt (6.1GB) CITANA DIREKTNO IZ ZIP
       STREAMA (zipfile.open + TextIOWrapper) — nikad cijeli RAM, nikad
       ekstrakcija na disk. Zanemaruje genres/ (isti sadrzaj, bez zanr oznaka
       u globalnoj pa genre-balans nije moguc — prihvata se prirodna
       distribucija).
Izlaz: datasets/canonical/bosnian_core_v0.3.jsonl (CAP 300.000 redova).

Format: prefix-completion — user = prva recenica paragrafa,
        assistant = ostatak. Paragraf s 1 recenicom se preskace.
Paragrafi: uzastopne neprazne linije spojene razmakom; flush na praznu liniju
        ili prije prelaska 800 znakova; kandidat samo ako je 100-800 znakova.
Filteri (ovim redom): cirilica -> URL/email -> >30% non-letters (bez razmaka)
        -> DENY (validator) -> 2+ recenice -> dedup SHA1 -> CAP.
Dedup: set SHA1 hexdigest normalizovanog paragrafa (ocekivano do ~500k unosa).

Uporaba: .venv/bin/python scripts/ingest_corpusv1_bc_v03.py [--limit N] [--max-kept N]
"""
import argparse
import hashlib
import io
import json
import re
import sys
import time
import zipfile
from pathlib import Path

ZIP = Path("/home/sha/.cache/huggingface/hub/datasets--hyper-efficient-system-llc"
           "--bosnian-corpus-v1/snapshots/dc1adc40fc3dd787bcab4f2e65bb2d282c79a352"
           "/data/bosnian-corpus-1.0.zip")
INNER = "bosnian-corpus-1.0/corpus/bosnian_corpus_all.txt"
OUT = Path("datasets/canonical/bosnian_core_v0.3.jsonl")
SRC = "bosnian-corpus-v1 (CC-BY-SA-4.0)"
URL = "https://huggingface.co/datasets/hyper-efficient-system-llc/bosnian-corpus-v1"

CYR = re.compile(r"[Ѐ-џ]")
URL_MAIL = re.compile(r"https?://|www\.[^\s]+|[\w.+-]+@[\w-]+\.[\w.]+")
SENT_END = re.compile(r"[.!?…]+\s+")
WS = re.compile(r"\s+")

MIN_LEN, MAX_LEN = 100, 800
CAP_DEFAULT = 300_000


def norm(s: str) -> str:
    return WS.sub(" ", s.strip().lower())


def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def split_first(text: str) -> tuple[str, str] | None:
    """Prva recenica | ostatak. Granica tek kad je prefiks >= 30 znakova
    (stiti od '00. 00.' i kratkih skracenica). Oba dijela moraju imati >= 20."""
    for m in SENT_END.finditer(text):
        if m.start() >= 30:
            user, rest = text[:m.end()].strip(), text[m.end():].strip()
            if len(user) >= 20 and len(rest) >= 20:
                return user, rest
            return None
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", default=str(ZIP))
    ap.add_argument("--limit", type=int, default=0,
                    help="max paragrafa-kandidata za obradu (0 = svi)")
    ap.add_argument("--max-kept", type=int, default=CAP_DEFAULT)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    from agentmujo_training.datasets.validator import DENY_PATTERNS
    deny = [re.compile(p) for p in DENY_PATTERNS]

    stat = {"lines": 0, "paras": 0, "kept": 0, "len": 0, "cyrillic": 0,
            "url_mail": 0, "nonletters": 0, "deny": 0, "single_sent": 0,
            "dup": 0, "decode_err": 0}
    diff_ct = {"easy": 0, "medium": 0, "hard": 0}
    seen: set[str] = set()
    t0 = time.time()

    outp = Path(a.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    fh = outp.open("w", encoding="utf-8")
    buf: list[str] = []
    buf_len = 0
    stopped = False

    def flush() -> bool:  # True = stani (CAP)
        nonlocal buf, buf_len
        if not buf:
            return False
        para = WS.sub(" ", " ".join(buf)).strip()
        buf, buf_len = [], 0
        if not (MIN_LEN <= len(para) <= MAX_LEN):
            stat["len"] += 1
            return False
        stat["paras"] += 1
        if CYR.search(para):
            stat["cyrillic"] += 1
            return False
        if URL_MAIL.search(para):
            stat["url_mail"] += 1
            return False
        if sum(1 for c in para if not c.isalpha() and not c.isspace()) / len(para) > 0.30:
            stat["nonletters"] += 1
            return False
        if any(p.search(para) for p in deny):
            stat["deny"] += 1
            return False
        sp = split_first(para)
        if sp is None:
            stat["single_sent"] += 1
            return False
        key = sha1(norm(para))
        if key in seen:
            stat["dup"] += 1
            return False
        seen.add(key)
        user, rest = sp
        n = len(para)
        diff = "easy" if n < 200 else "medium" if n < 500 else "hard"
        diff_ct[diff] += 1
        stat["kept"] += 1
        fh.write(json.dumps({
            "id": f"amj-bc3-{stat['kept']:06d}",
            "version": "0.3.0",
            "language": "bs-ijekavica",
            "task": "bosnian-core",
            "difficulty": diff,
            "enable_thinking": False,
            "messages": [
                {"role": "user", "content": user},
                {"role": "assistant", "content": rest},
            ],
            "metadata": {
                "source": SRC,
                "quality_tier": "SILVER",
                "verification_status": "verified",
                "license": "CC-BY-SA-4.0",
                "url": URL,
            },
        }, ensure_ascii=False) + "\n")
        if stat["kept"] >= a.max_kept:
            return True
        if a.limit and stat["paras"] >= a.limit:
            return True
        return False

    with zipfile.ZipFile(a.zip) as z:
        with z.open(INNER) as raw:
            # shortcut: errors='replace' umjesto strict — jedna neispravna
            # sekvenca ne smije srusiti 6GB stream; '�' se lako catcherom vidi.
            txt = io.TextIOWrapper(raw, encoding="utf-8", errors="replace", newline="")
            for line in txt:
                stat["lines"] += 1
                if "�" in line:
                    stat["decode_err"] += 1
                    line = line.replace("�", "")
                s = line.strip()
                if not s:
                    if flush():
                        stopped = True
                        break
                    continue
                if buf and buf_len + 1 + len(s) > MAX_LEN:
                    if flush():
                        stopped = True
                        break
                buf.append(s)
                buf_len += 1 + len(s) if buf_len else len(s)
                if stat["lines"] % 2_000_000 == 0:
                    dt = time.time() - t0
                    print(f".. linija {stat['lines']}, paragrafa {stat['paras']}, "
                          f"zadrzano {stat['kept']} ({stat['lines']/dt:,.0f} lin/s)",
                          flush=True)
            else:
                flush()
    fh.close()

    dt = time.time() - t0
    total_rej = stat["paras"] - stat["kept"]
    print(f"procitano linija: {stat['lines']}")
    print(f"paragrafi 100-800: {stat['paras']}")
    print(f"zadrzano: {stat['kept']} (CAP {'dostignut' if stopped and stat['kept'] >= a.max_kept else 'nije dostignut'})")
    print(f"odbaceno: {total_rej} | duzina={stat['len']} cirilica={stat['cyrillic']} "
          f"url_mail={stat['url_mail']} nonletters={stat['nonletters']} "
          f"deny={stat['deny']} jedna_recenica={stat['single_sent']} dedup={stat['dup']} "
          f"decode_fix={stat['decode_err']}")
    print(f"difficulty: {diff_ct}")
    print(f"vrijeme: {dt:.1f}s | {stat['lines']/max(dt, .1):,.0f} lin/s, "
          f"{stat['kept']/max(dt, .1):,.0f} red/s")
    print(f"distribucija: prirodna (globalna datoteka nema zanr oznake) -> {a.out}")

    from agentmujo_training.datasets.validator import validate_file
    from agentmujo_training.tools.registry import ToolRegistry
    reg = ToolRegistry("configs/tools.yaml")
    rep = validate_file(outp, set(reg.names()), reg.validate_call)
    print(f"validate: total={rep['total']} accepted={rep['accepted']} "
          f"rejected={rep['rejected']} tiers={rep['tiers']}")
    if rep["rejected"]:
        print(json.dumps(rep["errors"][:10], ensure_ascii=False)[:2000])
        sys.exit(1)


if __name__ == "__main__":
    main()
