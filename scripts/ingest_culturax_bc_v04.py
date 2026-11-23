#!/usr/bin/env python3
"""Ingest uonlp/CulturaX bs -> bosnian_core v0.4 (streaming, prefix-completion).

Ulaz:  datasets.load_dataset('uonlp/CulturaX', 'bs', split='train', streaming=True);
       fallback: ista bez configa uz filter language=='bs' (ako red ima polje
       language; inace se uzima sve jer je izvor vec jezicki podkorpus).
       Kolone: text (+ timestamp/url/source koje se ne koriste).
Izlaz: datasets/canonical/bosnian_core_v0.4.jsonl (CAP 100.000 redova;
       stvarni bs podkorpus je sican: 1237 dokumenata / ~40k tokena, pa se
       ocekuje tek stotinjak redova — CAP se tada naprosto ne dostize).

Format: prefix-completion kao BC v0.3 — user = prva recenica paragrafa
        (>= 30 znakova prefiksa, oba dijela >= 20), assistant = ostatak;
        min 2 recenice; paragrafi 100-800 znakova (spajanje uzastopnih
        nepraznih linija, flush na praznu liniju ili prije 800 znakova).
Filteri (ovim redom): cirilica -> URL/email -> >30% non-letters (bez razmaka)
        -> DENY (validator) -> 1 recenica -> dedup -> CAP.
Dedup: unutar novog set SHA1(norm(para)); protiv v0.1/v0.2/v0.3 samo
        SHA1(norm(user+' '+assistant)[:60]) — v0.3 ima 300k redova pa se puni
        tekst ne drzi u RAM-u, samo 20-bajtni hashovi prefiksa.
ID namespace: amj-bc4-%06d.

Uporaba: .venv/bin/python scripts/ingest_culturax_bc_v04.py [--limit N] [--max-kept N]
NAPOMENA: dataset je gated — prije pokretanja prihvatiti uvjete na
https://huggingface.co/datasets/uonlp/CulturaX i biti logiran (hf auth login).
"""
import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

OUT = Path("datasets/canonical/bosnian_core_v0.4.jsonl")
OLD_FILES = [
    Path("datasets/canonical/bosnian_core_v0.1.jsonl"),
    Path("datasets/canonical/bosnian_core_v0.2.jsonl"),
    Path("datasets/canonical/bosnian_core_v0.3.jsonl"),
]
SRC = "CulturaX bs (ODC-BY-1.0; OSCAR-CC0-meta/Common-Crawl-text)"
LICENSE = ("ODC-BY-1.0 (mC4) + CC0-1.0 metadata (OSCAR); "
           "text Common-Crawl-derived, see mC4/OSCAR terms")
URL = "https://huggingface.co/datasets/uonlp/CulturaX"

CYR = re.compile(r"[Ѐ-џ]")
URL_MAIL = re.compile(r"https?://|www\.[^\s]+|[\w.+-]+@[\w-]+\.[\w.]+")
SENT_END = re.compile(r"[.!?…]+\s+")
WS = re.compile(r"\s+")

MIN_LEN, MAX_LEN = 100, 800
CAP_DEFAULT = 100_000


def norm(s: str) -> str:
    return WS.sub(" ", s.strip().lower())


def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def old_prefix_hashes(paths: list[Path]) -> set[str]:
    """SHA1(norm(user+' '+assistant)[:60]) za v0.1/v0.2/v0.3 — samo hashovi."""
    out: set[str] = set()
    for p in paths:
        if not p.exists():
            print(f"upozorenje: {p} ne postoji, preskacem", flush=True)
            continue
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msgs = r.get("messages") or []
                users = [m.get("content", "") for m in msgs if m.get("role") == "user"]
                assists = [m.get("content", "") for m in msgs if m.get("role") == "assistant"]
                if users and assists:
                    out.add(sha1(norm(users[0] + " " + assists[-1])[:60]))
    return out


def split_first(text: str) -> tuple[str, str] | None:
    """Prva recenica | ostatak. Granica tek kad je prefiks >= 30 znakova;
    oba dijela moraju imati >= 20 (kao v0.3)."""
    for m in SENT_END.finditer(text):
        if m.start() >= 30:
            user, rest = text[:m.end()].strip(), text[m.end():].strip()
            if len(user) >= 20 and len(rest) >= 20:
                return user, rest
            return None
    return None


def paragraphs(text: str):
    """Uzastopne neprazne linije spojene razmakom; yield kandidata 100-800."""
    buf: list[str] = []
    buf_len = 0
    for line in text.splitlines():
        s = line.strip()
        if not s:
            if buf:
                yield WS.sub(" ", " ".join(buf)).strip()
                buf, buf_len = [], 0
            continue
        if buf and buf_len + 1 + len(s) > MAX_LEN:
            yield WS.sub(" ", " ".join(buf)).strip()
            buf, buf_len = [], 0
        buf.append(s)
        buf_len = 1 + buf_len + len(s) if buf_len else len(s)
    if buf:
        yield WS.sub(" ", " ".join(buf)).strip()


def open_stream(limit: int):
    from datasets import load_dataset
    try:
        return load_dataset("uonlp/CulturaX", "bs", split="train", streaming=True), True
    except Exception as e:
        print(f"'bs' config nedostupan ({type(e).__name__}: {str(e)[:200]}), "
              "pokusavam bez configa uz filter language=='bs'", flush=True)
    ds = load_dataset("uonlp/CulturaX", split="train", streaming=True)
    if limit:
        return ds, False
    return ds, False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="samo prvih N dokumenata (0 = svi)")
    ap.add_argument("--max-kept", type=int, default=CAP_DEFAULT)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    from agentmujo_training.datasets.validator import DENY_PATTERNS
    deny = [re.compile(p) for p in DENY_PATTERNS]

    old60 = old_prefix_hashes(OLD_FILES)
    print(f"stari prefix-hashovi: {len(old60)}", flush=True)
    seen: set[str] = set()

    stat = {"docs": 0, "paras": 0, "kept": 0, "len": 0, "cyrillic": 0,
            "url_mail": 0, "nonletters": 0, "deny": 0, "single_sent": 0,
            "dup_new": 0, "dup_old": 0, "skipped_lang": 0}
    diff_ct = {"easy": 0, "medium": 0, "hard": 0}

    outp = Path(a.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    n = 0
    with outp.open("w", encoding="utf-8") as fh:
        ds, _ = open_stream(a.limit)
        for row in ds:
            if a.limit and stat["docs"] >= a.limit:
                break
            stat["docs"] += 1
            if isinstance(row, dict) and "language" in row and row["language"] not in ("bs", None, ""):
                if str(row["language"]).strip().lower() != "bs":
                    stat["skipped_lang"] += 1
                    continue
            text = (row.get("text") or "") if isinstance(row, dict) else str(row)
            if not text.strip():
                continue
            for para in paragraphs(text):
                if stat["kept"] >= a.max_kept:
                    break
                stat["paras"] += 1
                if not (MIN_LEN <= len(para) <= MAX_LEN):
                    stat["len"] += 1
                    continue
                if CYR.search(para):
                    stat["cyrillic"] += 1
                    continue
                if URL_MAIL.search(para):
                    stat["url_mail"] += 1
                    continue
                if sum(1 for c in para if not c.isalpha() and not c.isspace()) / len(para) > 0.30:
                    stat["nonletters"] += 1
                    continue
                if any(p.search(para) for p in deny):
                    stat["deny"] += 1
                    continue
                sp = split_first(para)
                if sp is None:
                    stat["single_sent"] += 1
                    continue
                key = sha1(norm(para))
                if key in seen:
                    stat["dup_new"] += 1
                    continue
                seen.add(key)
                if sha1(norm(para)[:60]) in old60:
                    stat["dup_old"] += 1
                    continue
                user, rest = sp
                n = len(para)
                diff = "easy" if n < 200 else "medium" if n < 500 else "hard"
                diff_ct[diff] += 1
                stat["kept"] += 1
                fh.write(json.dumps({
                    "id": f"amj-bc4-{stat['kept']:06d}",
                    "version": "0.4.0",
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
                        "license": LICENSE,
                        "url": URL,
                    },
                }, ensure_ascii=False) + "\n")
            if stat["kept"] >= a.max_kept:
                break
            if stat["docs"] % 5000 == 0:
                print(f".. dokumenata {stat['docs']}, zadrzano {stat['kept']}", flush=True)

    dt = time.time() - t0
    total_rej = stat["paras"] - stat["kept"]
    print(f"procitano dokumenata: {stat['docs']}")
    print(f"paragrafi-kandidati: {stat['paras']}")
    print(f"zadrzano: {stat['kept']} (CAP {'dostignut' if stat['kept'] >= a.max_kept else 'nije dostignut'})")
    print(f"odbaceno: {total_rej} | duzina={stat['len']} cirilica={stat['cyrillic']} "
          f"url_mail={stat['url_mail']} nonletters={stat['nonletters']} "
          f"deny={stat['deny']} jedna_recenica={stat['single_sent']} "
          f"dedup_new={stat['dup_new']} dedup_old={stat['dup_old']} "
          f"preskoceno_jezik={stat['skipped_lang']}")
    print(f"difficulty: {diff_ct}")
    print(f"vrijeme: {dt:.1f}s -> {a.out}")

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
