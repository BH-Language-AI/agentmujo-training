#!/usr/bin/env python3
"""Ingest NOVIH bs Wikipedia clanaka -> knowledge v0.3 + RAG v0.3 (CC BY-SA, extractive).

Parametrizovano (za razliku od ingest_wikipedia_bs.py koji ima hardkodiran izlaz):
  .venv/bin/python scripts/ingest_wiki_v03.py [--target 1700] [--rag-target 900]
      [--knowledge-out datasets/canonical/knowledge_wikipedia_bs_v0.3.jsonl]
      [--rag-out datasets/canonical/rag_wikipedia_bs_v0.3.jsonl]

Preskace naslove iz v0.1+v0.2, nastavlja ID niz, filtrira cirilicu (validator
REJECT-uje [Ѐ-џ] u bs uzorcima) i DENY obrasce, postuje API (UA, pauze, retry).
"""
import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://bs.wikipedia.org/w/api.php"
UA = ("AgentMujoDatasetFactory/0.3 "
      "(https://github.com/BH-Language-AI/agentmujo-training; dataset@agentmujo.ai)")
CYR = re.compile(r"[Ѐ-џ]")
TITLE_RE = re.compile(r"„(.+?)“")
DENY = [r"\brm\s+-rf\s+/", r"\bmkfs\b", r"\bdd\s+.*of=/dev/",
        r"\biptables\s+-F\b", r":\(\)\s*\{\s*:\|\:&\s*\}",
        r"\bcurl\b.*\|\s*(?:sudo\s+)?bash\b", r"\bwget\b.*\|\s*(?:sudo\s+)?bash\b",
        r"PASSPHRASE|AWS_SECRET|HF_TOKEN"]

OLD_KN = ["datasets/canonical/knowledge_wikipedia_bs_v0.1.jsonl",
          "datasets/canonical/knowledge_wikipedia_bs_v0.2.jsonl"]
OLD_RG = ["datasets/canonical/rag_wikipedia_bs_v0.1.jsonl",
          "datasets/canonical/rag_wikipedia_bs_v0.2.jsonl"]


def existing_titles_and_max_id(paths, prefix):
    titles, mx = set(), 0
    for p in paths:
        pp = Path(p)
        if not pp.exists():
            continue
        for line in pp.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            try:
                mx = max(mx, int(r["id"].split("-")[-1]))
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=1700)
    ap.add_argument("--rag-target", type=int, default=900)
    ap.add_argument("--knowledge-out",
                    default="datasets/canonical/knowledge_wikipedia_bs_v0.3.jsonl")
    ap.add_argument("--rag-out",
                    default="datasets/canonical/rag_wikipedia_bs_v0.3.jsonl")
    a = ap.parse_args()

    old_titles, kn_max = existing_titles_and_max_id(OLD_KN, "amj-kn")
    _, rg_max = existing_titles_and_max_id(OLD_RG, "amj-rg")
    print(f"stari naslovi: {len(old_titles)}, kn start: {kn_max + 1}, rg start: {rg_max + 1}")

    rows, seen = [], set(old_titles)
    stat = {"short": 0, "dup": 0, "cyr": 0, "deny": 0, "api_err": 0}
    attempt = 0
    today = time.strftime("%Y-%m-%d")
    while len(rows) < a.target and attempt < 600:
        attempt += 1
        try:
            data = fetch_batch()
        except Exception as e:  # retry s backoffom
            stat["api_err"] += 1
            print("api", e)
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
            if CYR.search(title + ctx):  # validator REJECT-uje cirilicu
                stat["cyr"] += 1
                continue
            if any(re.search(pat, ctx) for pat in DENY):
                stat["deny"] += 1
                continue
            seen.add(title)
            kid = f"amj-kn-{kn_max + len(rows) + 1:04d}"
            rows.append({
                "id": kid, "version": "0.3.0", "language": "bs",
                "task": "bosnian-knowledge", "difficulty": "easy",
                "messages": [
                    {"role": "user", "content": f"Šta piše o temi „{title}“ na bosanskoj Wikipediji?"},
                    {"role": "assistant", "content": ctx},
                ],
                "metadata": {"source": "wikipedia-bs", "generator": "wiki-ingest-v0.3",
                             "license": "CC BY-SA 4.0",
                             "url": "https://bs.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")),
                             "verification_status": "auto-validated", "quality_tier": "SILVER",
                             "retrieved_at": today},
            })
            if len(rows) >= a.target:
                break
        time.sleep(0.3)
        if attempt % 20 == 0:
            print(f".. {len(rows)}/{a.target} (attempt {attempt})")

    kp = Path(a.knowledge_out)
    kp.parent.mkdir(parents=True, exist_ok=True)
    kp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    # RAG v0.3: isti oblik poruka kao v0.2 (Kontekst+Pitanje -> kontekst), iz NOVIH knowledge redova
    rag = []
    for k in rows[:a.rag_target]:
        ctx = k["messages"][1]["content"]
        q = k["messages"][0]["content"]
        rag.append({
            "id": f"amj-rg-{rg_max + len(rag) + 1:04d}", "version": "0.3.0",
            "language": "bs", "task": "rag-memory", "difficulty": "medium",
            "messages": [
                {"role": "user", "content": f"Kontekst:\n{ctx}\n\nPitanje: {q}"},
                {"role": "assistant", "content": ctx},
            ],
            "metadata": {"source": "wikipedia-bs", "generator": "wiki-ingest-v0.3",
                         "license": "CC BY-SA 4.0",
                         "verification_status": "auto-validated", "synthetic": True,
                         "quality_tier": "SILVER", "derived_from": k["id"]},
        })
    rp = Path(a.rag_out)
    rp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rag), encoding="utf-8")

    rej = stat["short"] + stat["dup"] + stat["cyr"] + stat["deny"]
    print(f"knowledge: {len(rows)} -> {kp}")
    print(f"rag: {len(rag)} -> {rp}")
    print(f"odbaceni: short={stat['short']} dup={stat['dup']} cyr={stat['cyr']} "
          f"deny={stat['deny']} api_err={stat['api_err']} stopa={rej / max(len(rows) + rej, 1):.1%}")


if __name__ == "__main__":
    main()
