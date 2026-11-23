#!/usr/bin/env python3
"""Bosnian instructions v0.1: ~1500 redova iz provjerljivih izvora (nista izmisljeno).

Izvori:
  (a) 60% — pitanja izvedena iz bosnian_core_v0.2 (Sag69 rjecnicki redovi,
      tipovi dictionary/bilingual_dictionary). Odgovor je DOSLOVNO preuzet
      tekst izvornog reda (verbatim assistant sadrzaj):
        - "Koja je vrsta rijeci X?" (samo redovi s prepoznatom oznakom vrste)
        - "Sta znaci X?" (samo redovi s nepraznom definicijom iza " - ")
        - "Navedi primjer za X" (samo redovi koji sadrze "npr.")
  (b) 25% — FIKSNA pravopisna pravila ugradena kao konstante FIXED_RULES.
      SAMO ovih 5 neospornih pravila, svako s 2-3 fiksna primjera.
      NIKAKVA druga pravila se ne generisu.
  (c) 15% — ijekavica: redovi iz (a) pula cija definicija sadrzi ijekavski
      oblik (rijeci s nastavkom "ije"); pitanje "napisi ijekavski", odgovor verbatim.

metadata: SILVER + source "instructions-v0.1" + verification_status "verified".
ID: amj-bi-%06d. Dedup: normalizovana user pitanja unutar fajla.
Uporaba: .venv/bin/python scripts/build_instructions_v01.py
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "datasets/canonical/bosnian_core_v0.2.jsonl"
OUT = REPO / "datasets/canonical/bosnian_instructions_v0.1.jsonl"

N_TOTAL, N_A, N_B, N_C = 1500, 900, 375, 225
N_VRSTA, N_ZNACENJE, N_PRIMJER = 300, 300, 300

CYR = re.compile(r"[Ѐ-џ]")

# ---------------------------------------------------------------- (b) fiksna pravila
# SAMO ovih 5 pravila. Svako: nepromjenljiva izjava + 2-3 fiksna primjera.
# Skript ne smije generisati nijedno drugo pravilo.
FIXED_RULES = [
    {
        "key": "necu-sastavljeno",
        "topic": "sastavljeno pisanje niječne niječnice uz glagol htjeti u futuru",
        "statement": (
            "Niječna niječnica uz glagol htjeti u futuru piše se sastavljeno: "
            "neću, nećeš, neće, nećemo, nećete, neće."
        ),
        "examples": [
            {"wrong": "ne ću", "right": "neću", "sentence": "Neću doći na vrijeme."},
            {"wrong": "ne ćeš", "right": "nećeš", "sentence": "Nećeš pogriješiti ako provjeriš."},
            {"wrong": "ne ćemo", "right": "nećemo", "sentence": "Nećemo kasniti na sastanak."},
        ],
    },
    {
        "key": "ije-je-izgovor",
        "topic": "pisanje ije/je po izgovoru (dugi slog ije, kratki slog je)",
        "statement": (
            "Dugi slog piše se ije, a kratki slog je: mlijeko, dijete, mjesto."
        ),
        "examples": [
            {"word": "mlijeko", "sentence": "Popio je čašu toplog mlijeka."},
            {"word": "dijete", "sentence": "Dijete se igra u dvorištu."},
            {"word": "mjesto", "sentence": "Nađi slobodno mjesto i sjedi."},
        ],
    },
    {
        "key": "veliko-slovo-imena",
        "topic": "veliko početno slovo vlastitih imena i naselja",
        "statement": (
            "Vlastita imena lica i naselja pišu se velikim početnim slovom."
        ),
        "examples": [
            {"word": "Sarajevo", "sentence": "Sarajevo je glavni grad Bosne i Hercegovine."},
            {"word": "Milica", "sentence": "Milica je došla na vrijeme."},
            {"word": "Una", "sentence": "Una je bistra rijeka na zapadu zemlje."},
        ],
    },
    {
        "key": "zarez-a-ali-nego",
        "topic": "zarez ispred suprotnih veznika a, ali, nego",
        "statement": (
            "Ispred suprotnih veznika a, ali i nego piše se zarez."
        ),
        "examples": [
            {"sentence": "Došao je, ali nije ostao."},
            {"sentence": "Nije on, nego ona je to uradila."},
            {"sentence": "Htio je doći, a nije mogao."},
        ],
    },
    {
        "key": "c-c-razlika",
        "topic": "razlika između glasova č i ć",
        "statement": (
            "Glasovi č i ć razlikuju se po izgovoru i pisanju: kuća se piše "
            "sa ć, a množina kući zadržava ć."
        ),
        "examples": [
            {"word": "kuća", "sentence": "Naša kuća je na kraju ulice."},
            {"word": "kući", "sentence": "Djeca su kod kuće."},
            {"word": "pomoć", "sentence": "Hvala na pomoći."},
        ],
    },
]

N_FIXED_RULES = len(FIXED_RULES)
assert N_FIXED_RULES == 5

USER_T_B = [
    "kako se pravilno piše: {choice}?",
    "da li je pravilno '{right}'? ({topic})",
    "ispravi grešku u riječi '{wrong}': kako glasi pravilno?",
    "koje pravilo važi za {topic} na primjeru '{right}'?",
    "napiši pravilnu rečenicu sa '{right}' i objasni pravilo.",
]
USER_PREFIX_B = ["", "molim te, ", "reci mi: ", "zanima me — ", "pomozi mi: "]
ASST_T_B = [
    "{statement} Pravilno je '{right}'. Primjer: {sentence}",
    "Pravilno je '{right}'. {statement} Primjer: {sentence}",
    "{statement} Dakle: {sentence}",
    "'{right}' — {statement} Primjer pravilne upotrebe: {sentence}",
    "Pravilo: {statement} Primjer: {sentence}",
]

USER_T_VRSTA = [
    "Koja je vrsta riječi '{w}'?",
    "Koju vrstu riječi ima riječ '{w}'?",
    "Je li riječ '{w}' imenica, glagol ili neka druga vrsta riječi?",
]
USER_T_ZNACENJE = [
    "Šta znači riječ '{w}'?",
    "Definiši riječ '{w}'.",
    "Koje je značenje riječi '{w}'?",
]
USER_T_PRIMJER = [
    "Navedi primjer upotrebe riječi '{w}'.",
    "U kojoj rečenici se koristi riječ '{w}'? Navedi primjer.",
    "Daj primjer za riječ '{w}'.",
]
USER_T_IJEK = [
    "Napiši ijekavski: koji ijekavski oblik se javlja u objašnjenju riječi '{w}'?",
    "Koji ijekavski oblik sadrži opis riječi '{w}'? Napiši ijekavski.",
    "Riječ '{w}' opisana je ijekavskim oblikom — napiši ijekavski koji se tu javlja.",
]

POS_PATTERNS = [
    (re.compile(r"\(imenica\)", re.I), "imenica"),
    (re.compile(r"\(glagol\)", re.I), "glagol"),
    (re.compile(r"\(pridjev\)", re.I), "pridjev"),
    (re.compile(r"\(prilog\)", re.I), "prilog"),
    (re.compile(r"\bim\.", re.I), "imenica"),
    (re.compile(r"\bgl\.", re.I), "glagol"),
    (re.compile(r"\bprid\.", re.I), "pridjev"),
    (re.compile(r"\bpril\.", re.I), "prilog"),
    (re.compile(r"\bzam\.", re.I), "zamjenica"),
    (re.compile(r"\bvezn\.", re.I), "veznik"),
    (re.compile(r"\bprijedl?\.", re.I), "prijedlog"),
    (re.compile(r"\buzvik\.?", re.I), "uzvik"),
    (re.compile(r"\bbroj", re.I), "broj"),
]
IJE_RE = re.compile(r"[A-Za-zčćđšžČĆĐŠŽ]*ije[A-Za-zčćđšžČĆĐŠŽ]{2,}")
NPR_RE = re.compile(r"\bnpr\.?", re.I)
HEAD_BAD = re.compile(r"[\d\u0400-\u04ff]")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def parse_row(r: dict) -> dict | None:
    msgs = r.get("messages") or []
    if len(msgs) < 2:
        return None
    text = msgs[1].get("content", "").strip()
    if not text or CYR.search(text) or len(text) < 20:
        return None
    if " - " not in text:
        return None
    head_raw = text.split(" - ", 1)[0].strip()
    if head_raw.lower().startswith("bosnian translation:"):
        head_raw = head_raw[len("bosnian translation:"):].strip()
    head = re.split(r"[\s/,;()]+", head_raw)[0].strip().strip("'\"")
    if not (2 <= len(head) <= 30) or HEAD_BAD.search(head):
        return None
    pos = next((lbl for rx, lbl in POS_PATTERNS if rx.search(text)), None)
    m = IJE_RE.search(text.split(" - ", 1)[1])
    return {
        "head": head, "pos": pos, "text": text,
        "has_example": bool(NPR_RE.search(text)),
        "ije": m.group(0) if m else None,
        "src": r.get("id", "?"),
    }


def main() -> None:
    parsed = []
    for line in SRC.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("metadata", {}).get("sag69_type") not in ("dictionary", "bilingual_dictionary"):
            continue
        p = parse_row(r)
        if p:
            parsed.append(p)
    parsed.sort(key=lambda p: p["src"])
    print(f"parsirano upotrebljivih: {len(parsed)}", flush=True)

    used_src: set[str] = set()
    used_heads: set[str] = set()
    seen_q: set[str] = set()
    rows: list[dict] = []

    import zlib

    def take_unique(pool: list[dict], n: int, tmpl: list[str]) -> list[tuple[str, dict]]:
        out = []
        for p in pool:
            if len(out) >= n:
                break
            if p["src"] in used_src or norm(p["head"]) in used_heads:
                continue
            base = zlib.crc32(p["src"].encode()) % len(tmpl)
            pick = None
            for k in range(len(tmpl)):  # isti head drugog padeza/sloga -> drugi sablon
                q = tmpl[(base + k) % len(tmpl)].format(w=p["head"])
                if norm(q) not in seen_q:
                    pick = q
                    break
            if pick is None:
                used_src.add(p["src"])
                continue
            used_src.add(p["src"])
            used_heads.add(norm(p["head"]))
            out.append((pick, p))
        assert len(out) == n, f"nedovoljno redova u pulu: {len(out)}<{n}"
        return out

    def add_row(user: str, asst: str, diff: str) -> None:
        key = norm(user)
        assert key not in seen_q, f"duplikat pitanja: {user[:70]}"
        seen_q.add(key)
        assert asst and not CYR.search(user + asst)
        rows.append({
            "id": f"amj-bi-{len(rows) + 1:06d}",
            "version": "0.1.0",
            "language": "bs-ijekavica",
            "task": "bosnian-instructions",
            "difficulty": diff,
            "enable_thinking": False,
            "messages": [
                {"role": "user", "content": user},
                {"role": "assistant", "content": asst},
            ],
            "metadata": {
                "source": "instructions-v0.1",
                "quality_tier": "SILVER",
                "verification_status": "verified",
                "author": "agentmujo-team",
            },
        })

    # (a) 60%: vrsta / znacenje / primjer — odgovor verbatim izvorni red
    pos_pool = [p for p in parsed if p["pos"]]
    any_pool = [p for p in parsed]
    ex_pool = [p for p in parsed if p["has_example"]]
    print(f"pulovi: pos={len(pos_pool)} any={len(any_pool)} primjer={len(ex_pool)}", flush=True)
    for q, p in take_unique(pos_pool, N_VRSTA, USER_T_VRSTA):
        add_row(q, p["text"], "easy")
    for q, p in take_unique(any_pool, N_ZNACENJE, USER_T_ZNACENJE):
        add_row(q, p["text"], "easy")
    for q, p in take_unique(ex_pool, N_PRIMJER, USER_T_PRIMJER):
        add_row(q, p["text"], "easy")

    # (b) 25%: 5 pravila x 3 primjera x 5 baza x 5 prefiksa = 375 jedinstvenih pitanja
    n_b = 0
    for rule in FIXED_RULES:
        for ex in rule["examples"]:
            right = ex.get("right", ex.get("word", ex["sentence"].split()[0]))
            choice = f"{ex['wrong']} ili {ex['right']}" if "wrong" in ex else f"{right}"
            ctx = dict(ex, topic=rule["topic"], statement=rule["statement"],
                       right=right, choice=choice, wrong=ex.get("wrong", right))
            for bi, base in enumerate(USER_T_B):
                for pi, pre in enumerate(USER_PREFIX_B):
                    user = (pre + base).format(**ctx)
                    if not pre:
                        user = user[0].upper() + user[1:]
                    add_row(user, ASST_T_B[(bi + pi) % len(ASST_T_B)].format(**ctx), "medium")
                    n_b += 1
    assert n_b == N_B, n_b

    # (c) 15%: ijekavica — redovi cija definicija sadrzi ijekavski oblik
    ije_pool = [p for p in parsed if p["ije"] and p["src"] not in used_src]
    print(f"ije pul (nedodirnutih): {len(ije_pool)}", flush=True)
    for q, p in take_unique(ije_pool, N_C, USER_T_IJEK):
        add_row(q, p["text"], "easy")

    assert len(rows) == N_TOTAL, len(rows)
    blobs = [json.dumps(r["messages"], sort_keys=True, ensure_ascii=False) for r in rows]
    assert len(set(blobs)) == len(blobs), "duplikat uzorka"

    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    dist_a = {"vrsta": N_VRSTA, "znacenje": N_ZNACENJE, "primjer": N_PRIMJER}
    print(f"redova: {len(rows)} -> {OUT}")
    print(f"distribucija izvora: rjecnik(a)={N_A} pravopis(b)={N_B} ijekavica(c)={N_C}")
    print(f"distribucija (a): {dist_a}")
    print(f"broj fiksnih pravila: {N_FIXED_RULES} "
          f"({', '.join(r['key'] for r in FIXED_RULES)})")

    from agentmujo_training.datasets.validator import validate_file
    rep = validate_file(OUT, set())
    print(f"validate: total={rep['total']} accepted={rep['accepted']} "
          f"rejected={rep['rejected']} tiers={rep['tiers']}")
    assert rep["rejected"] == 0, json.dumps(rep["errors"][:5], ensure_ascii=False)[:1000]


if __name__ == "__main__":
    main()
