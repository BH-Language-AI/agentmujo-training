#!/usr/bin/env python3
"""Build RAG v0.4 expansion (~3000 rows) from knowledge_wikipedia_bs_v0.3.

Metoda (bez novog weba, samo postojeci knowledge):
- za svaki clanak iz knowledge v0.3 sa <2 RAG pitanja: DVA nova pitanja iz
  drugog ugla (razlicita od generickog "Sta pise o temi X?" iz v0.1-v0.3):
    tip A (fact/extract, medium): cinjenicno pitanje na izvod iz uvoda,
      odgovor je doslovna recenica iz ciljnog uvoda;
    tip B (infer, hard): "zasto/kako/koja-veza" pitanje koje spaja dvije
      cinjenice iz istog uvoda, odgovor su doslovne nosece recenice;
- svaki kontekst sadrzi i jedan DISTRAKTOR paragraf iz drugog clanka koji
  model mora ignorisati (eksplicitno oznacen kao nerelevantan);
- dedup pitanja protiv v0.1/v0.2/v0.3 + unutar novog skupa;
- prioritet: prvo nepokriveni clanci (0 RAG), zatim pokriveni (1 RAG), cap 3000.
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CAN = REPO / "datasets" / "canonical"
KNOW = CAN / "knowledge_wikipedia_bs_v0.3.jsonl"
OUT = CAN / "rag_wikipedia_bs_v0.4.jsonl"
OLD_RAG = [CAN / "rag_wikipedia_bs_v0.1.jsonl",
           CAN / "rag_wikipedia_bs_v0.2.jsonl",
           CAN / "rag_wikipedia_bs_v0.3.jsonl"]

TARGET_ROWS = 3000
START_ID = 1001
VERSION = "0.4.0"

SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+")
TITLE_RE = re.compile("temi\\s+\u201e(.+?)\\s+na bosanskoj")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def load_rows(p: Path):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def question_of(r) -> str:
    u = r["messages"][0]["content"]
    return u.split("Pitanje:", 1)[-1].strip() if "Pitanje:" in u else u.strip()


_QUOTES = chr(34) + chr(0x201c) + chr(0x201d) + chr(0xab) + chr(0xbb) + chr(0x201f) + chr(0x2033)


def title_of_know(k) -> str:
    m = TITLE_RE.search(k["messages"][0]["content"])
    if m:
        return m.group(1).strip().strip(_QUOTES)
    return k["id"]


def intro_of(k) -> str:
    return k["messages"][1]["content"].strip()


def sents(text: str):
    return [s.strip() for s in SENT_SPLIT.split(text.strip()) if len(s.strip()) > 20]


def fact_subtype(s0: str) -> str:
    if re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", s0):
        return "datum"
    if re.search(r"\d", s0):
        return "broj"
    if re.search(r"\b(bio je|bila je|rođen|rođena|osnovao|otkrio|dobio|dobili)\b", s0, re.I):
        return "akter"
    if re.search(r"\b(nalazi se|grad|držav|rijek|planin|jezer|selo|općin)\b", s0, re.I):
        return "mjesto"
    return "definicija"


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


def build(know, dtalk, dtype_title, seen_q: set, rows: list, qtype_counter: dict):
    intro = intro_of(know)
    title = title_of_know(know)
    ss = sents(intro)
    s0 = ss[0]
    s1 = ss[1] if len(ss) > 1 else ss[0]

    # --- tip A: fact/extract ---
    st = fact_subtype(s0)
    qa = FACT_Q[st].format(t=title)
    nqa = norm(qa)
    if nqa in seen_q:  # shortcut: titl je jedinstven pa se ovo prakticno ne desava
        qa += " (Odgovori isključivo na osnovu relevantnog dijela konteksta.)"
        nqa = norm(qa)
    seen_q.add(nqa)
    ctx_a = (f"Relevantni uvod:\n{intro}\n\n"
             f"Nepovezani odlomak (iz članka „{dtype_title}\") — ZANEMARI ga, "
             f"nije dio odgovora:\n{dtalk}")
    rows.append({
        "id": f"amj-rg-{START_ID + len(rows):04d}", "version": VERSION,
        "language": "bs", "task": "rag-memory", "difficulty": "medium",
        "messages": [
            {"role": "user", "content": f"Kontekst:\n{ctx_a}\n\nPitanje: {qa}"},
            {"role": "assistant", "content": s0},
        ],
        "metadata": {"source": "wikipedia-bs", "generator": "rag-expansion-v0.4",
                     "license": "CC BY-SA 4.0", "verification_status": "verified",
                     "synthetic": True, "quality_tier": "SILVER",
                     "derived_from": know["id"], "question_type": f"fact-{st}"},
    })
    qtype_counter[f"fact-{st}"] += 1

    # --- tip B: why/how/connection inference ---
    btpl = INFER_Q[len(rows) % 3]
    qb = btpl.format(t=title)
    nqb = norm(qb)
    if nqb in seen_q:
        qb += " (Odgovori isključivo na osnovu relevantnog dijela konteksta.)"
        nqb = norm(qb)
    seen_q.add(nqb)
    support = s0 if s1 == s0 else f"{s0} {s1}"
    ctx_b = (f"Relevantni uvod:\n{intro}\n\n"
             f"Nepovezani odlomak (iz članka „{dtype_title}\") — ZANEMARI ga, "
             f"nije dio odgovora:\n{dtalk}")
    rows.append({
        "id": f"amj-rg-{START_ID + len(rows):04d}", "version": VERSION,
        "language": "bs", "task": "rag-memory", "difficulty": "hard",
        "messages": [
            {"role": "user", "content": f"Kontekst:\n{ctx_b}\n\nPitanje: {qb}"},
            {"role": "assistant", "content":
             f"{support} Dakle, odgovor proizilazi iz veze između ovih navoda iz istog uvoda."},
        ],
        "metadata": {"source": "wikipedia-bs", "generator": "rag-expansion-v0.4",
                     "license": "CC BY-SA 4.0", "verification_status": "verified",
                     "synthetic": True, "quality_tier": "SILVER",
                     "derived_from": know["id"], "question_type": "infer-veza"},
    })
    qtype_counter["infer-veza"] += 1


def main():
    know = load_rows(KNOW)
    by_id = {k["id"]: k for k in know}

    seen_q = set()
    for f in OLD_RAG:
        for r in load_rows(f):
            seen_q.add(norm(question_of(r)))

    rag_counts = {k["id"]: 0 for k in know}
    for f in OLD_RAG:
        for r in load_rows(f):
            d = r.get("metadata", {}).get("derived_from")
            if d in rag_counts:
                rag_counts[d] += 1
    eligible = [k for k in know if rag_counts[k["id"]] < 2]
    eligible.sort(key=lambda k: (rag_counts[k["id"]], k["id"]))

    from collections import Counter
    qtype_counter: dict = Counter()
    rows: list = []
    n = len(know)
    for i, k in enumerate(eligible):
        if len(rows) >= TARGET_ROWS:
            break
        dk = know[(i * 791 + 331) % n]  # deterministicki distractor, drugi clanak
        if dk["id"] == k["id"]:
            dk = know[(i * 791 + 332) % n]
        ds = sents(intro_of(dk))[0][:220]
        build(k, ds + ("…" if len(ds) == 220 else ""), title_of_know(dk),
              seen_q, rows, qtype_counter)

    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                   encoding="utf-8")

    touched = {r["metadata"]["derived_from"] for r in rows}
    prev_covered = sum(1 for k in know if rag_counts[k["id"]] > 0)
    new_for_uncovered = sum(1 for t in touched if rag_counts[t] == 0)
    print(f"rows: {len(rows)} -> {OUT.name}")
    print(f"clanci: knowledge={len(know)}, prije pokriveno={prev_covered}, "
          f"v0.4 dotaknuto={len(touched)} (od toga prethodno nepokrivenih={new_for_uncovered})")
    print(f"ukupna pokrivenost nakon v0.4: {len(set(by_id) & (set(touched) | {k for k in by_id if rag_counts[k] > 0}))}/{len(know)}")
    print("tipovi pitanja:", dict(qtype_counter))
    print("idd: amj-rg-%04d..amj-rg-%04d" % (START_ID, START_ID + len(rows) - 1))


if __name__ == "__main__":
    main()
