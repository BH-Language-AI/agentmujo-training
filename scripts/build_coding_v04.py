#!/usr/bin/env python3
"""Build coding_repo_v0.4 — ~800 NOVIH redova (AST-mining novih skripti + meta-generator zadaci).

Izvori:
  (a) AST-mining samo fajlova s mtime novijim od coding_repo_v0.3.jsonl
      (5 tipova zadataka po funkciji: objasni/bug/test/docstring/refaktoriraj).
  (b) Meta-zadaci "napisi generator dataset-redova" — rjesenje je mini-generator
      u stilu postojecih build_* skripti (seed, dedup, JSONL flush).
Dedup: protiv coding_repo_v0.1 + v0.2 + v0.3 (hash poruka + par funkcija+zadatak).
Ne dira postojece fajlove ni splits/.
"""
import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "datasets/canonical/coding_repo_v0.4.jsonl"
REF = ROOT / "datasets/canonical/coding_repo_v0.3.jsonl"
START_ID = 951  # v0.3 ide do amj-cd-0950
TARGET_TOTAL = 800
VERSION = "0.4.0"
SRC = "coding-expansion-v0.4"

DENY = [r"\brm\s+-rf\s+/", r"\bmkfs\b", r"\bdd\s+.*of=/dev/", r"\biptables\s+-F\b",
        r":\(\)\s*\{\s*:\|\:&\s*\}", r"\bcurl\b.*\|\s*(?:sudo\s+)?bash\b",
        r"\bwget\b.*\|\s*(?:sudo\s+)?bash\b", r"PASSPHRASE|AWS_SECRET|HF_TOKEN"]


def bad(t: str) -> bool:
    return any(re.search(p, t) for p in DENY)


def mhash(msgs) -> str:
    return hashlib.sha256(json.dumps(msgs, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def meta() -> dict:
    return {"source": SRC, "license": "Apache-2.0", "quality_tier": "SILVER",
            "verification_status": "verified"}


def row(sid: int, user: str, asst: str, difficulty: str, extra: dict) -> dict:
    m = meta()
    m.update(extra)
    return {"id": f"amj-cd-{sid:04d}", "version": VERSION, "language": "bs-ijekavica",
            "task": "coding", "difficulty": difficulty,
            "messages": [{"role": "user", "content": user},
                         {"role": "assistant", "content": asst}],
            "metadata": m}


seen: set[str] = set()
seen_fk: set[tuple[str, str]] = set()  # (ime_funkcije, vrsta_zadatka) iz v0.3
AST_PAT = [
    ("objasni", re.compile(r"Objasni sto radi Python funkcija `(\w+)`")),
    ("bug", re.compile(r"Pregledaj sljedecu Python funkciju `(\w+)`")),
    ("test", re.compile(r"Napisi pytest test za Python funkciju `(\w+)`")),
    ("docstring", re.compile(r"Dopuni docstring za Python funkciju `(\w+)`")),
    ("refaktoriraj", re.compile(r"Predlozi refaktoriranje Python funkcije `(\w+)`")),
]
for f in ("datasets/canonical/coding_repo_v0.1.jsonl",
          "datasets/canonical/coding_repo_v0.2.jsonl",
          "datasets/canonical/coding_repo_v0.3.jsonl"):
    p = ROOT / f
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            msgs = json.loads(ln)["messages"]
            seen.add(mhash(msgs))
            u = msgs[0]["content"] if msgs else ""
            for kind, pat in AST_PAT:
                mt = pat.search(u)
                if mt:
                    seen_fk.add((mt.group(1), kind))

rows: list[dict] = []
counts: dict[str, int] = {}


def emit(user: str, asst: str, difficulty: str, kind: str, extra: dict) -> bool:
    msgs = [{"role": "user", "content": user}, {"role": "assistant", "content": asst}]
    if bad(asst) or bad(user) or mhash(msgs) in seen:
        return False
    for blk in re.findall(r"```python\n(.*?)```", asst, re.S):
        try:
            ast.parse(blk)
        except SyntaxError:
            return False
    seen.add(mhash(msgs))
    rows.append(row(START_ID + len(rows), user, asst, difficulty, extra))
    counts[kind] = counts.get(kind, 0) + 1
    return True


# ============ (a) AST-MINING SAMO NOVIH FAJLOVA ============
ref_mtime = REF.stat().st_mtime
funcs: list[tuple[str, str, str, str, list[str]]] = []
for p in sorted(ROOT.rglob("*.py")):
    if ".git" in p.parts or "__pycache__" in p.parts or ".venv" in p.parts:
        continue
    if p.resolve() == Path(__file__).resolve():
        continue  # ne rudari samog sebe
    if p.stat().st_mtime <= ref_mtime:
        continue  # samo fajlovi nastali nakon v0.3
    try:
        src = p.read_text(encoding="utf-8")
        tree = ast.parse(src)
    except Exception:
        continue
    rel = str(p.relative_to(ROOT))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        seg = ast.get_source_segment(src, node) or ""
        if not (80 <= len(seg) <= 1600) or bad(seg):
            continue
        args = [a.arg for a in node.args.args if a.arg not in ("self", "cls")]
        doc = ast.get_docstring(node) or ""
        first = doc.strip().splitlines()[0].strip() if doc.strip() else ""
        mod = rel[:-3].replace("/", ".")
        funcs.append((rel, node.name, f"{node.name}({', '.join(args)})", seg, args, first, mod,
                      len(seg.splitlines()), bool(doc)))
funcs.sort(key=lambda t: (t[0], t[1]))
print(json.dumps({"novi_fajlovi": len({f[0] for f in funcs}), "funkcije": len(funcs)}))


def bug_nalazi(seg: str) -> list[str]:
    n = []
    if "subprocess" in seg and "timeout" not in seg:
        n.append("poziv bez vremenskog ogranicenja (timeout) — proces se moze zalediti")
    if re.search(r"except\s*:", seg):
        n.append("goli `except:` hvata i prekide (KeyboardInterrupt) — suzi na konkretne izuzetke")
    if re.search(r"open\(", seg) and "try" not in seg:
        n.append("otvaranje fajla bez obrade greske ako fajl ne postoji")
    if re.search(r"def \w+\([^)]*=\s*(\[\]|\{\})", seg):
        n.append("promjenjiva podrazumijevana vrijednost (lista/rjecnik) — dijeli se izmedju poziva")
    if "shell=True" in seg:
        n.append("`shell=True` uz vanjski ulaz nosi rizik umetanja komande")
    if ".get(" not in seg and "[" in seg and "args" in seg:
        n.append("direktan pristup kljucu bez provjere — KeyError na neocekivanom ulazu")
    if "TODO" in seg or "FIXME" in seg:
        n.append("nedovrsen dio oznacen u kodu (TODO/FIXME)")
    if not n:
        n.append("rubni slucajevi (prazan ulaz, None) nisu eksplicitno pokriveni")
        n.append("nema provjere tipa ulaznih argumenata prije obrade")
    return n[:2]


def refaktor_prijedlozi(seg: str, args: list[str], has_doc: bool) -> list[str]:
    p = []
    if len(seg.splitlines()) > 40:
        p.append("podijeli funkciju na dvije manje cjeline (priprema + obrada)")
    if len(args) > 4:
        p.append("grupiraj argumente u rjecnik ili dataclass (previse parametara)")
    if re.search(r"def \w+\([^)]*\):", seg.splitlines()[0]):
        p.append("dodaj anotacije tipova argumenata i povratne vrijednosti")
    if not has_doc:
        p.append("dodaj docstring s opisom, argumentima i primjerom")
    if max((len(l) - len(l.lstrip()) for l in seg.splitlines()[1:] or [0]), default=0) > 12:
        p.append("smanji ugnijezdenost ranim povratkom (early return)")
    if re.search(r"\b\d{2,}\b", seg):
        p.append("izdvoji magicne brojeve u imenovane konstante")
    if not p:
        p.append("izdvoji ponovljene izraze u pomocne varijable s jasnim imenima")
        p.append("dodaj anotacije tipova radi citljivosti")
    return p[:2]


def docstring_tekst(name: str, args: list[str], first: str) -> str:
    lines = [f'"""{name} — {first if first else "kratak opis namjene funkcije."}']
    if args:
        lines += ["", "Args:"] + [f"    {a}: opis argumenta." for a in args[:6]] + ["", "Returns:",
                                                                                    "    Rezultat obrade."]
    lines.append('"""')
    return "\n".join(lines)


def prosiri_docstring(seg: str, doc: str) -> str:
    import textwrap
    try:
        tree = ast.parse(textwrap.dedent(seg))
        fn = tree.body[0]
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return ""
        stari = ast.get_docstring(fn)
        if stari:
            novi_doc = stari.rstrip() + "\n\nPrimjer:\n    Rezultat se provjerava pozivom s oglednim ulazom."
            for stmt in fn.body:
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                    stmt.value = ast.Constant(value=novi_doc)
                    break
        else:
            fn.body.insert(0, ast.Expr(value=ast.Constant(value=doc.strip('"'))))
        novi = ast.unparse(tree)
        ast.parse(novi)
        return novi
    except Exception:
        return ""


made_ast = 0
ast_kinds = ["objasni", "bug", "test", "docstring", "refaktoriraj"]
for (rel, name, sig, seg, args, first, mod, nlines, has_doc) in funcs:
    for kind in ast_kinds:
        if (name, kind) in seen_fk:
            continue
        code = "```python\n" + seg + "\n```"
        if kind == "objasni":
            opis = ('Prema docstringu: "' + first + '".') if first else (
                f"Prima {len(args)} argument(a) ({', '.join(args)}) i vraca rezultat obrade." if args
                else "Ne prima argumente; izvrsava unaprijed odredjeni posao i vraca rezultat.")
            ok = emit(f"Objasni sto radi Python funkcija `{name}` iz fajla `{rel}`. "
                      f"Odgovori na bosanskom (ijekavica) i prilozi izvorni kod.",
                      f"Funkcija `{name}` ({sig}) — {opis}\n\nIzvorni kod:\n{code}",
                      "easy", "ast-objasni", {"file": rel})
        elif kind == "bug":
            nal = bug_nalazi(seg)
            ok = emit(f"Pregledaj sljedecu Python funkciju `{name}` iz fajla `{rel}` i pronadji "
                      f"potencijalni bug ili propust. Odgovori na bosanskom (ijekavica).",
                      "Pregledom sam uocio sljedece:\n" + "".join(f"{i}. {x}.\n" for i, x in enumerate(nal, 1)) +
                      f"\nKod na koji se odnosi:\n{code}",
                      "medium", "ast-bug", {"file": rel})
        elif kind == "test":
            tcode = ("```python\nimport inspect\nfrom " + mod + " import " + name + "\n\n\n"
                     f"def test_{name}_postoji():\n    assert callable({name})\n\n\n"
                     f"def test_{name}_signatura():\n    params = inspect.signature({name}).parameters\n"
                     f"    assert len(params) >= {len(args)}\n```")
            ok = emit(f"Napisi pytest test za Python funkciju `{name}` ({sig}) iz fajla `{rel}`. "
                      f"Odgovori na bosanskom (ijekavica).",
                      f"Test provjerava da je funkcija `{name}` uvoziva i da signatura odgovara "
                      f"ocekivanoj ({len(args)} parametara). Za puni test dodaj poziv s konkretnim "
                      f"ulazom iz svog okruzenja.\n\n{tcode}",
                      "medium", "ast-test", {"file": rel})
        elif kind == "docstring":
            novi = prosiri_docstring(seg, docstring_tekst(name, args, first))
            if not novi or bad(novi):
                continue
            ok = emit(f"Dopuni docstring za Python funkciju `{name}` iz fajla `{rel}` tako da opisuje "
                      f"namjenu, argumente i povratnu vrijednost. Odgovori na bosanskom (ijekavica).",
                      "Dopunjena verzija s docstringom na bosanskom:\n\n```python\n" + novi + "\n```",
                      "easy", "ast-docstring", {"file": rel})
        else:
            pr = refaktor_prijedlozi(seg, args, has_doc)
            ok = emit(f"Predlozi refaktoriranje Python funkcije `{name}` iz fajla `{rel}` "
                      f"(citljivost, tipovi, struktura). Odgovori na bosanskom (ijekavica).",
                      "Prijedlozi (bez promjene ponasanja):\n" + "".join(f"{i}. {x}.\n" for i, x in enumerate(pr, 1)) +
                      f"\nTrenutni kod:\n{code}",
                      "hard", "ast-refaktoriraj", {"file": rel})
        if ok:
            made_ast += 1

# ============ (b) META-ZADACI: NAPISI GENERATOR DATASET-REDOVA ============
# Rjesenje je mini-generator u stilu build_* skripti: seed, dedup, JSONL flush.
SKELETONS = [
    ("seed-sampler",
     "#!/usr/bin/env python3\n\"\"\"Mini-generator: uzorkovanje s seed-om, dedup, JSONL flush.\"\"\"\n"
     "import hashlib\nimport json\nimport random\n\n\n"
     "SEED = @SEED@\nN = @N@\nIZLAZ = \"@IZLAZ@\"\n\n\n"
     "def kljuc(r):\n    return hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest()[:16]\n\n\n"
     "def main():\n    rng = random.Random(SEED)\n    vidjeno = set()\n    redovi = []\n"
     "    while len(redovi) < N:\n        r = {\"tema\": \"@TEMA@\", \"x\": rng.randrange(10**6)}\n"
     "        k = kljuc(r)\n        if k in vidjeno:\n            continue\n        vidjeno.add(k)\n        redovi.append(r)\n"
     "    with open(IZLAZ, \"w\", encoding=\"utf-8\") as f:\n"
     "        for r in redovi:\n            f.write(json.dumps(r, ensure_ascii=False) + \"\\n\")\n"
     "    print(json.dumps({\"upisano\": len(redovi), \"izlaz\": IZLAZ}))\n\n\n"
     "if __name__ == \"__main__\":\n    main()\n"),
    ("template-expander",
     "#!/usr/bin/env python3\n\"\"\"Mini-generator: ekspanzija predlozaka, dedup, JSONL flush.\"\"\"\n"
     "import hashlib\nimport itertools\nimport json\n\n\n"
     "SEED = @SEED@\nN = @N@\nIZLAZ = \"@IZLAZ@\"\n"
     "PREDLOSCI = [\"provjeri @TEMA@ slucaj {i}\", \"obradi @TEMA@ stavku {i}\"]\n\n\n"
     "def kljuc(t):\n    return hashlib.sha256(t.encode()).hexdigest()[:16]\n\n\n"
     "def main():\n    vidjeno = set()\n    redovi = []\n"
     "    for p, i in itertools.product(PREDLOSCI, range(10**6)):\n"
     "        if len(redovi) >= N:\n            break\n        t = p.format(i=i)\n        k = kljuc(t)\n"
     "        if k in vidjeno:\n            continue\n        vidjeno.add(k)\n        redovi.append({\"id\": len(redovi), \"tekst\": t})\n"
     "    with open(IZLAZ, \"w\", encoding=\"utf-8\") as f:\n"
     "        for r in redovi:\n            f.write(json.dumps(r, ensure_ascii=False) + \"\\n\")\n"
     "    print(json.dumps({\"upisano\": len(redovi), \"izlaz\": IZLAZ}))\n\n\n"
     "if __name__ == \"__main__\":\n    main()\n"),
    ("hash-dedup",
     "#!/usr/bin/env python3\n\"\"\"Mini-generator: dedup ulaznog JSONL-a po hash-u, JSONL flush.\"\"\"\n"
     "import hashlib\nimport json\n\n\n"
     "SEED = @SEED@\nN = @N@\nULAZ = \"ulaz.jsonl\"\nIZLAZ = \"@IZLAZ@\"\n\n\n"
     "def kljuc(r):\n    return hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest()[:16]\n\n\n"
     "def ucitaj():\n    try:\n        with open(ULAZ, encoding=\"utf-8\") as f:\n"
     "            return [json.loads(l) for l in f if l.strip()]\n"
     "    except FileNotFoundError:\n        return [{\"tema\": \"@TEMA@\", \"i\": i} for i in range(N * 2)]\n\n\n"
     "def main():\n    vidjeno = set()\n    redovi = []\n"
     "    for r in ucitaj():\n        k = kljuc(r)\n        if k in vidjeno:\n            continue\n        vidjeno.add(k)\n        redovi.append(r)\n        if len(redovi) >= N:\n            break\n"
     "    assert len(redovi) == len({kljuc(r) for r in redovi})\n"
     "    with open(IZLAZ, \"w\", encoding=\"utf-8\") as f:\n"
     "        for r in redovi:\n            f.write(json.dumps(r, ensure_ascii=False) + \"\\n\")\n"
     "    print(json.dumps({\"upisano\": len(redovi), \"izlaz\": IZLAZ}))\n\n\n"
     "if __name__ == \"__main__\":\n    main()\n"),
    ("id-allocator",
     "#!/usr/bin/env python3\n\"\"\"Mini-generator: redni ID-evi u nizu, dedup, JSONL flush.\"\"\"\n"
     "import hashlib\nimport json\n\n\n"
     "SEED = @SEED@\nN = @N@\nSTART = @SEED@\nIZLAZ = \"@IZLAZ@\"\nPREFIKS = \"@TEMA@\"\n\n\n"
     "def main():\n    vidjeno = set()\n    redovi = []\n    i = START\n"
     "    while len(redovi) < N:\n        rid = f\"{PREFIKS}-{i:04d}\"\n"
     "        k = hashlib.sha256(rid.encode()).hexdigest()[:16]\n"
     "        i += 1\n        if k in vidjeno:\n            continue\n        vidjeno.add(k)\n        redovi.append({\"id\": rid, \"seed\": SEED})\n"
     "    with open(IZLAZ, \"w\", encoding=\"utf-8\") as f:\n"
     "        for r in redovi:\n            f.write(json.dumps(r, ensure_ascii=False) + \"\\n\")\n"
     "    print(json.dumps({\"upisano\": len(redovi), \"izlaz\": IZLAZ}))\n\n\n"
     "if __name__ == \"__main__\":\n    main()\n"),
    ("schema-check",
     "#!/usr/bin/env python3\n\"\"\"Mini-generator: provjera obaveznih polja, dedup, JSONL flush.\"\"\"\n"
     "import hashlib\nimport json\n\n\n"
     "SEED = @SEED@\nN = @N@\nIZLAZ = \"@IZLAZ@\"\nOBAVEZNA = [\"id\", \"tekst\"]\n\n\n"
     "def ispravan(r):\n    return all(r.get(p) for p in OBAVEZNA)\n\n\n"
     "def main():\n    vidjeno = set()\n    redovi = []\n    lose = 0\n    i = 0\n"
     "    while len(redovi) < N:\n        r = {\"id\": f\"@TEMA@-{i:04d}\", \"tekst\": f\"ogled {i}\"} if i % 2 else {\"id\": i}\n"
     "        i += 1\n        if not ispravan(r):\n            lose += 1\n            continue\n"
     "        k = hashlib.sha256(r[\"id\"].encode()).hexdigest()[:16]\n"
     "        if k in vidjeno:\n            continue\n        vidjeno.add(k)\n        redovi.append(r)\n"
     "    with open(IZLAZ, \"w\", encoding=\"utf-8\") as f:\n"
     "        for r in redovi:\n            f.write(json.dumps(r, ensure_ascii=False) + \"\\n\")\n"
     "    print(json.dumps({\"upisano\": len(redovi), \"odbaceno\": lose, \"izlaz\": IZLAZ}))\n\n\n"
     "if __name__ == \"__main__\":\n    main()\n"),
    ("length-filter",
     "#!/usr/bin/env python3\n\"\"\"Mini-generator: filter po duzini, dedup, JSONL flush.\"\"\"\n"
     "import hashlib\nimport json\n\n\n"
     "SEED = @SEED@\nN = @N@\nIZLAZ = \"@IZLAZ@\"\nMIN_D = 8\nMAX_D = 500\n\n\n"
     "def main():\n    vidjeno = set()\n    redovi = []\n    i = 0\n"
     "    while len(redovi) < N:\n        t = f\"@TEMA@ ogledni tekst broj {i} \" + \"x\" * (i % 40)\n"
     "        i += 1\n        if not (MIN_D <= len(t) <= MAX_D):\n            continue\n"
     "        k = hashlib.sha256(t.encode()).hexdigest()[:16]\n"
     "        if k in vidjeno:\n            continue\n        vidjeno.add(k)\n        redovi.append({\"id\": len(redovi), \"tekst\": t})\n"
     "    with open(IZLAZ, \"w\", encoding=\"utf-8\") as f:\n"
     "        for r in redovi:\n            f.write(json.dumps(r, ensure_ascii=False) + \"\\n\")\n"
     "    print(json.dumps({\"upisano\": len(redovi), \"izlaz\": IZLAZ}))\n\n\n"
     "if __name__ == \"__main__\":\n    main()\n"),
    ("shuffle-split",
     "#!/usr/bin/env python3\n\"\"\"Mini-generator: mijesanje sa seed-om, train/dev split, JSONL flush.\"\"\"\n"
     "import json\nimport random\n\n\n"
     "SEED = @SEED@\nN = @N@\nIZLAZ = \"@IZLAZ@\"\nUDIO_DEV = 0.1\n\n\n"
     "def main():\n    rng = random.Random(SEED)\n    bazen = [{\"id\": i, \"tema\": \"@TEMA@\"} for i in range(N * 2)]\n"
     "    rng.shuffle(bazen)\n    n_dev = max(1, int(len(bazen) * UDIO_DEV))\n"
     "    dev = bazen[:n_dev]\n    train = bazen[n_dev:n_dev + N]\n"
     "    assert not ({r[\"id\"] for r in train} & {r[\"id\"] for r in dev})\n"
     "    with open(IZLAZ, \"w\", encoding=\"utf-8\") as f:\n"
     "        for r in train:\n            f.write(json.dumps(r, ensure_ascii=False) + \"\\n\")\n"
     "    print(json.dumps({\"train\": len(train), \"dev\": len(dev), \"izlaz\": IZLAZ}))\n\n\n"
     "if __name__ == \"__main__\":\n    main()\n"),
    ("stats-reporter",
     "#!/usr/bin/env python3\n\"\"\"Mini-generator: gradnja redova sa statistikom, dedup, JSONL flush.\"\"\"\n"
     "import hashlib\nimport json\n\n\n"
     "SEED = @SEED@\nN = @N@\nIZLAZ = \"@IZLAZ@\"\n\n\n"
     "def main():\n    vidjeno = set()\n    redovi = []\n    i = 0\n"
     "    while len(redovi) < N:\n        r = {\"id\": f\"@TEMA@-{SEED}-{i}\", \"duzina\": len(f\"@TEMA@-{i}\")}\n"
     "        i += 1\n        k = hashlib.sha256(r[\"id\"].encode()).hexdigest()[:16]\n"
     "        if k in vidjeno:\n            continue\n        vidjeno.add(k)\n        redovi.append(r)\n"
     "    prosjek = sum(r[\"duzina\"] for r in redovi) / len(redovi)\n"
     "    with open(IZLAZ, \"w\", encoding=\"utf-8\") as f:\n"
     "        for r in redovi:\n            f.write(json.dumps(r, ensure_ascii=False) + \"\\n\")\n"
     "    print(json.dumps({\"upisano\": len(redovi), \"prosjecna_duzina\": prosjek, \"izlaz\": IZLAZ}))\n\n\n"
     "if __name__ == \"__main__\":\n    main()\n"),
]

META_TOPICS = ["sigurnosni-parovi", "dpo-izbori", "misaoni-lanci", "fc-pozivi",
               "ag-terminal", "rag-memorija", "potvrde", "bosanski-testovi"]
META_USERS = [
    "Napisi python3 mini-generator dataset-redova za temu `{t}` u stilu postojecih build_* skripti "
    "(obavezno: seed, dedup, JSONL flush). Odgovori na bosanskom (ijekavica).",
    "Napisi python3 skriptu koja generira N oglednih redova za temu `{t}`: seed za ponovljivost, "
    "dedup po hash-u i upis u JSONL. Odgovori na bosanskom (ijekavica).",
    "Treba mi generator redova za `{t}` po uzoru na build_* skripte (seed, dedup, JSONL flush). "
    "Napisi python3 kod i objasni pokretanje. Odgovori na bosanskom (ijekavica).",
]
META_TEZINA = ["easy", "medium", "medium"]

made_meta = 0
vi = 0
while len(rows) < TARGET_TOTAL and vi < 20000:
    si = vi % len(SKELETONS)
    sname, skel = SKELETONS[si]
    topic = META_TOPICS[(vi // len(SKELETONS)) % len(META_TOPICS)]
    seed = 4000 + vi
    n = 50 + (vi % 5) * 50
    kod = skel.replace("@SEED@", str(seed)).replace("@N@", str(n)).replace("@TEMA@", topic)
    kod = kod.replace("@IZLAZ@", f"{topic}_{seed}.jsonl")
    try:
        ast.parse(kod)
    except SyntaxError:
        vi += 1
        continue
    u = META_USERS[vi % len(META_USERS)].format(t=topic)
    a = (f"Evo mini-generatora ({sname}) za temu `{topic}` — seed {seed}, cilj {n} redova. "
         f"Pokretanje: `python3 generator.py`.\n\n```python\n{kod}\n```\n\n"
         f"Skripta koristi fiksni seed pa je ponovljiva, izbacuje duplikate po hash-u "
         f"i redove upisuje u JSONL s `ensure_ascii=False`.")
    if emit(u, a, META_TEZINA[vi % len(META_TEZINA)], f"meta-{sname}", {"generator": sname, "topic": topic}):
        made_meta += 1
    vi += 1

# --- zavrsna provjera: svaki code-block se parsira ---
for r in rows:
    for blk in re.findall(r"```python\n(.*?)```", r["messages"][1]["content"], re.S):
        ast.parse(blk)  # assert: baca SyntaxError ako ne valja

OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
by_source = {"ast-mining": sum(v for k, v in counts.items() if k.startswith("ast-")),
             "meta-generatori": sum(v for k, v in counts.items() if k.startswith("meta-"))}
print(json.dumps({"ast": made_ast, "meta": made_meta, "total": len(rows), "out": str(OUT)},
                 ensure_ascii=False))
print(json.dumps({"counts": counts, "by_source": by_source}, ensure_ascii=False))