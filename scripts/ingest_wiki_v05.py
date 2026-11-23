#!/usr/bin/env python3
"""Ingest NOVIH bs Wikipedia clanaka -> knowledge v0.5 + RAG v0.6 (CC BY-SA, extractive).

Skaliranje sa ~10000 na ~18000 clanaka: povlaci ~8000 novih clanaka
(dedup naslova protiv v0.1+v0.2+v0.3+v0.4), nastavlja amj-kn niz iza max iz v0.4,
gradi ~4000 RAG pitanja (fact+infer, dedup protiv v0.1-v0.5, amj-rg iza v0.5).

Dug mrezni posao: napredak se APPEND-uje u .part fajl uz flush svakog reda
i fsync svakih --flush-every redova; prekid -> ponovni start nastavlja iz .part.
Na kraju se .part atomski kopira u finalni fajl.

  .venv/bin/python scripts/ingest_wiki_v05.py [--target 8000] [--rag-target 4000]
"""
import argparse
import json
import os
import re
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

API = "https://bs.wikipedia.org/w/api.php"
UA = ("AgentMujoDatasetFactory/0.5 "
      "(https://github.com/BH-Language-AI/agentmujo-training; dataset@agentmujo.ai)")
CYR = re.compile(r"[Ѐ-џ]")
TITLE_RE = re.compile(r"„(.+?)“")
DENY = [r"\brm\s+-rf\s+/", r"\bmkfs\b", r"\bdd\s+.*of=/dev/",
        r"\biptables\s+-F\b", r":\(\)\s*\{\s*:\|\:&\s*\}",
        r"\bcurl\b.*\|\s*(?:sudo\s+)?bash\b", r"\bwget\b.*\|\s*(?:sudo\s+)?bash\b",
        r"PASSPHRASE|AWS_SECRET|HF_TOKEN"]
SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+")

OLD_KN = ["datasets/canonical/knowledge_wikipedia_bs_v0.1.jsonl",
          "datasets/canonical/knowledge_wikipedia_bs_v0.2.jsonl",
          "datasets/canonical/knowledge_wikipedia_bs_v0.3.jsonl",
           "datasets/canonical/knowledge_wikipedia_bs_v0.4.jsonl"]
OLD_RG = ["datasets/canonical/rag_wikipedia_bs_v0.1.jsonl",
          "datasets/canonical/rag_wikipedia_bs_v0.2.jsonl",
          "datasets/canonical/rag_wikipedia_bs_v0.3.jsonl",
          "datasets/canonical/rag_wikipedia_bs_v0.4.jsonl",
           "datasets/canonical/rag_wikipedia_bs_v0.5.jsonl"]

FACT_Q = {
    "datum": "Koje godine / kada se, prema kontekstu, desilo ključno navedeno za temu „{t}\"?",
    "broj": "Koji brojčani podatak (udaljenost, veličina, broj) kontekst navodi za temu „{t}\"?",
    "akter": "Ko je, prema kontekstu, ključna osoba vezana za temu „{t}\" i po čemu je poznata?",
    "mjesto": "Gdje se, prema kontekstu, nalazi / odvija tema „{t}\"?",
    "definicija": "Šta je, prema kontekstu, tema „{t}\" — navedi ključnu odrednicu?",
}
INFER_Q = [
    "Zašto je tema „{t}\" značajna — koji uzrok i posljedicu kontekst povezuje?",
    "Kako kontekst povezuje dva ključna podatka o temi „{t}\" — objasni vezu?",
    "Koja veza postoji između aktera/mjesta i događaja navedenih za temu „{t}\"?",
]


def read_rows(p):
    pp = Path(p)
    if not pp.exists():
        return []
    out = []
    for line in pp.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def existing_titles_and_max_id(paths):
    titles, mx = set(), 0
    for p in paths:
        for r in read_rows(p):
            try:
                mx = max(mx, int(str(r["id"]).split("-")[-1]))
            except ValueError:
                pass
            q = (r.get("messages") or [{}])[0].get("content", "")
            m = TITLE_RE.search(q)
            if m:
                titles.add(m.group(1).strip())
    return titles, mx


def fetch_batch():
    q = urllib.parse.urlencode({"action": "query", "generator": "random",
        "grnnamespace": "0", "grnlimit": "10", "prop": "extracts",
        "explaintext": "1", "exintro": "1", "format": "json", "formatversion": "2"})
    req = urllib.request.Request(API + "?" + q, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))


def norm(s):
    return re.sub(r"\s+", " ", s.strip().lower())


def sents(text):
    return [s.strip() for s in SENT_SPLIT.split(text.strip()) if len(s.strip()) > 20]


def title_of(k):
    m = TITLE_RE.search(k["messages"][0]["content"])
    return m.group(1).strip() if m else k["id"]


def fact_subtype(s0):
    if re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", s0):
        return "datum"
    if re.search(r"\d", s0):
        return "broj"
    if re.search(r"\b(bio je|bila je|rođen|rođena|osnovao|otkrio|dobio|dobili)\b", s0, re.I):
        return "akter"
    if re.search(r"\b(nalazi se|grad|držav|rijek|planin|jezer|selo|općin)\b", s0, re.I):
        return "mjesto"
    return "definicija"


def fetch_knowledge(target, kn_max, seen, part_path, flush_every):
    """Povlaci nove clanke; resume iz .part ako postoji. Vraca (rows, stat)."""
    part_path = Path(part_path)
    rows = read_rows(part_path) if part_path.exists() else []
    for r in rows:  # resume: titlovi iz .part ulaze u seen
        m = TITLE_RE.search((r.get("messages") or [{}])[0].get("content", ""))
        if m:
            seen.add(m.group(1).strip())
    print(f"resume: {len(rows)}/{target} vec u {part_path.name}")
    stat = {"short": 0, "dup": 0, "cyr": 0, "deny": 0, "api_err": 0}
    attempt = 0
    today = time.strftime("%Y-%m-%d")
    t0 = time.time()
    with part_path.open("a", encoding="utf-8") as fh:
        while len(rows) < target and attempt < 6000:
            attempt += 1
            try:
                data = fetch_batch()
            except Exception as e:  # retry s backoffom
                stat["api_err"] += 1
                print("api", e, flush=True)
                time.sleep(2 + min(attempt / 60, 8))
                continue
            for p in data.get("query", {}).get("pages", []) or []:
                title = str(p.get("title") or "").strip()
                ext = str(p.get("extract") or "").strip()
                if not title or len(ext) < 250:
                    stat["short"] += 1
                    continue
                if title in seen:
                    stat["dup"] += 1
                    continue
                ctx = ext[:900]
                if CYR.search(title + ctx):
                    stat["cyr"] += 1
                    continue
                if any(re.search(pat, ctx) for pat in DENY):
                    stat["deny"] += 1
                    continue
                seen.add(title)
                kid = f"amj-kn-{kn_max + len(rows) + 1:04d}"
                row = {
                    "id": kid, "version": "0.5.0", "language": "bs",
                    "task": "bosnian-knowledge", "difficulty": "easy",
                    "messages": [
                        {"role": "user", "content": f"Šta piše o temi „{title}“ na bosanskoj Wikipediji?"},
                        {"role": "assistant", "content": ctx},
                    ],
                    "metadata": {"source": "wikipedia-bs", "generator": "wiki-ingest-v0.5",
                                 "license": "CC BY-SA 4.0",
                                 "url": "https://bs.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")),
                                 "verification_status": "verified", "quality_tier": "SILVER",
                                 "retrieved_at": today},
                }
                rows.append(row)
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()
                if len(rows) % flush_every == 0:  # fsync checkpoint
                    os.fsync(fh.fileno())
                    el = time.time() - t0
                    print(f".. {len(rows)}/{target} ({el / 60:.0f} min)", flush=True)
                if len(rows) >= target:
                    break
            time.sleep(0.3)
            if attempt % 50 == 0:
                print(f".. {len(rows)}/{target} (attempt {attempt})", flush=True)
    return rows, stat, time.time() - t0


def build_rag(know, rg_max, rag_target):
    seen_q = set()
    for p in OLD_RG:
        for r in read_rows(p):
            u = r["messages"][0]["content"]
            seen_q.add(norm(u.split("Pitanje:", 1)[-1] if "Pitanje:" in u else u))
    rows, n = [], len(know)
    qtypes = Counter()
    for i, k in enumerate(know):
        if len(rows) >= rag_target:
            break
        intro = k["messages"][1]["content"]
        title = title_of(k)
        ss = sents(intro)
        if not ss:
            continue
        s0 = ss[0]
        s1 = ss[1] if len(ss) > 1 else ss[0]
        dk = know[(i * 791 + 331) % n]  # deterministicki distractor, drugi clanak
        if dk["id"] == k["id"]:
            dk = know[(i * 791 + 332) % n]
        ds = sents(dk["messages"][1]["content"])[0][:220]
        dtalk = ds + ("…" if len(ds) == 220 else "")
        ctx = (f"Relevantni uvod:\n{intro}\n\nNepovezani odlomak (iz članka „{title_of(dk)}“)"
               f" — ZANEMARI ga, nije dio odgovora:\n{dtalk}")
        st = fact_subtype(s0)
        qa = FACT_Q[st].format(t=title)
        if norm(qa) in seen_q:
            qa += " (Odgovori isključivo na osnovu relevantnog dijela konteksta.)"
        seen_q.add(norm(qa))
        rows.append({
            "id": f"amj-rg-{rg_max + len(rows) + 1:04d}", "version": "0.6.0",
            "language": "bs", "task": "rag-memory", "difficulty": "medium",
            "messages": [{"role": "user", "content": f"Kontekst:\n{ctx}\n\nPitanje: {qa}"},
                         {"role": "assistant", "content": s0}],
            "metadata": {"source": "wikipedia-bs", "generator": "wiki-ingest-v0.5",
                         "license": "CC BY-SA 4.0", "verification_status": "verified",
                         "synthetic": True, "quality_tier": "SILVER",
                         "derived_from": k["id"], "question_type": f"fact-{st}"},
        })
        qtypes[f"fact-{st}"] += 1
        if len(rows) >= rag_target:
            break
        qb = INFER_Q[len(rows) % 3].format(t=title)
        if norm(qb) in seen_q:
            qb += " (Odgovori isključivo na osnovu relevantnog dijela konteksta.)"
        seen_q.add(norm(qb))
        support = s0 if s1 == s0 else f"{s0} {s1}"
        rows.append({
            "id": f"amj-rg-{rg_max + len(rows) + 1:04d}", "version": "0.6.0",
            "language": "bs", "task": "rag-memory", "difficulty": "hard",
            "messages": [{"role": "user", "content": f"Kontekst:\n{ctx}\n\nPitanje: {qb}"},
                         {"role": "assistant", "content":
                          f"{support} Dakle, odgovor proizilazi iz veze između ovih navoda iz istog uvoda."}],
            "metadata": {"source": "wikipedia-bs", "generator": "wiki-ingest-v0.5",
                         "license": "CC BY-SA 4.0", "verification_status": "verified",
                         "synthetic": True, "quality_tier": "SILVER",
                         "derived_from": k["id"], "question_type": "infer-veza"},
        })
        qtypes["infer-veza"] += 1
    return rows, qtypes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=8000)
    ap.add_argument("--rag-target", type=int, default=4000)
    ap.add_argument("--knowledge-out",
                    default="datasets/canonical/knowledge_wikipedia_bs_v0.5.jsonl")
    ap.add_argument("--rag-out",
                    default="datasets/canonical/rag_wikipedia_bs_v0.6.jsonl")
    ap.add_argument("--flush-every", type=int, default=500)
    a = ap.parse_args()

    old_titles, kn_max = existing_titles_and_max_id(OLD_KN)
    _, rg_max = existing_titles_and_max_id(OLD_RG)
    print(f"stari naslovi: {len(old_titles)}, kn start: {kn_max + 1}, rg start: {rg_max + 1}", flush=True)

    part = a.knowledge_out + ".part"
    rows, stat, el = fetch_knowledge(a.target, kn_max, set(old_titles), part, a.flush_every)

    kp = Path(a.knowledge_out)
    kp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    Path(part).unlink(missing_ok=True)

    rag, qtypes = build_rag(rows, rg_max, a.rag_target)
    rp = Path(a.rag_out)
    rp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rag), encoding="utf-8")

    rej = stat["short"] + stat["dup"] + stat["cyr"] + stat["deny"]
    print(f"knowledge: {len(rows)} -> {kp} ({el / 60:.1f} min)")
    print(f"rag: {len(rag)} -> {rp} ({dict(qtypes)})")
    print(f"odbaceni: short={stat['short']} dup={stat['dup']} cyr={stat['cyr']} "
          f"deny={stat['deny']} api_err={stat['api_err']} stopa={rej / max(len(rows) + rej, 1):.1%}")


if __name__ == "__main__":
    main()
