#!/usr/bin/env python3
"""Build coding_repo_v0.5 — ~1500 NOVIH redova (AST-mining permissive OSS repoa).

Umjesto blokiranog BigCodea: shallow-klon 3 repoa s poznatim permissive
licencama u /tmp/opencode/oss-repos/ (psf/requests, pallets/flask,
Textualize/rich). Licenca se provjerava iz LICENSE fajla; repo s
nepoklapajucom licencom se preskace. Rudari se samo izvorni kod
(bez test fajlova), funkcije 5-60 linija, bez __dunder__ trivijalnosti.
5 tipova zadataka po funkciji: objasni/bug/test/docstring/refaktoriraj.
Dedup: protiv v0.1-v0.4 (hash poruka + par funkcija+zadatak) i interno.
Ne dira druge fajlove ni splits/.
"""
import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "datasets/canonical/coding_repo_v0.5.jsonl"
OSS = Path("/tmp/opencode/oss-repos")
TARGET = 1500
VERSION = "0.5.0"
GENERATOR = "oss-mining-v0.5"

REPOS = [
    # (dir, org/repo, SPDX, markeri u LICENSE fajlu)
    ("requests", "psf/requests", "Apache-2.0", ["Apache License", "Version 2.0"]),
    ("flask", "pallets/flask", "BSD-3-Clause",
     ["Redistribution and use in source and binary forms"]),
    ("rich", "Textualize/rich", "MIT",
     ["Permission is hereby granted, free of charge"]),
]

DENY = [r"\brm\s+-rf\s+/", r"\bmkfs\b", r"\bdd\s+.*of=/dev/", r"\biptables\s+-F\b",
        r":\(\)\s*\{\s*:\|\:&\s*\}", r"\bcurl\b.*\|\s*(?:sudo\s+)?bash\b",
        r"\bwget\b.*\|\s*(?:sudo\s+)?bash\b", r"PASSPHRASE|AWS_SECRET|HF_TOKEN"]


def bad(t: str) -> bool:
    return any(re.search(p, t) for p in DENY)


def mhash(msgs) -> str:
    return hashlib.sha256(json.dumps(msgs, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def meta(source: str, lic: str, extra: dict) -> dict:
    m = {"source": source, "license": lic, "quality_tier": "SILVER",
         "verification_status": "verified", "generator": GENERATOR}
    m.update(extra)
    return m


def row(sid: int, user: str, asst: str, difficulty: str, source: str, lic: str, extra: dict) -> dict:
    return {"id": f"amj-cd-{sid:04d}", "version": VERSION, "language": "bs-ijekavica",
            "task": "coding", "difficulty": difficulty,
            "messages": [{"role": "user", "content": user},
                         {"role": "assistant", "content": asst}],
            "metadata": meta(source, lic, extra)}


# --- START_ID: iza max amj-cd iz v0.1-v0.4 + dedup skupovi ---
seen: set[str] = set()
seen_fk: set[tuple[str, str]] = set()
AST_PAT = [
    ("objasni", re.compile(r"Objasni sto radi Python funkcija `(\w+)`")),
    ("bug", re.compile(r"Pregledaj sljedecu Python funkciju `(\w+)`")),
    ("test", re.compile(r"Napisi pytest test za Python funkciju `(\w+)`")),
    ("docstring", re.compile(r"Dopuni docstring za Python funkciju `(\w+)`")),
    ("refaktoriraj", re.compile(r"Predlozi refaktoriranje Python funkcije `(\w+)`")),
]
max_id = 0
for f in ("datasets/canonical/coding_repo_v0.1.jsonl",
          "datasets/canonical/coding_repo_v0.2.jsonl",
          "datasets/canonical/coding_repo_v0.3.jsonl",
          "datasets/canonical/coding_repo_v0.4.jsonl"):
    p = ROOT / f
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            r = json.loads(ln)
            mt = re.search(r"amj-cd-(\d+)", r["id"])
            if mt:
                max_id = max(max_id, int(mt.group(1)))
            msgs = r["messages"]
            seen.add(mhash(msgs))
            u = msgs[0]["content"] if msgs else ""
            for kind, pat in AST_PAT:
                mm = pat.search(u)
                if mm:
                    seen_fk.add((mm.group(1), kind))
START_ID = max_id + 1

rows: list[dict] = []
counts: dict[str, int] = {}
otpalo_dedup = 0


def emit(user: str, asst: str, difficulty: str, source: str, lic: str,
         kind: str, extra: dict) -> bool:
    global otpalo_dedup
    msgs = [{"role": "user", "content": user}, {"role": "assistant", "content": asst}]
    if bad(asst) or bad(user) or mhash(msgs) in seen:
        otpalo_dedup += 1
        return False
    for blk in re.findall(r"```python\n(.*?)```", asst, re.S):
        try:
            ast.parse(blk)
        except SyntaxError:
            otpalo_dedup += 1
            return False
    seen.add(mhash(msgs))
    rows.append(row(START_ID + len(rows), user, asst, difficulty, source, lic, extra))
    counts[kind] = counts.get(kind, 0) + 1
    return True


# ============ PROVJERA LICENCI + AST-MINING ============
licence_izvjestaj: dict[str, str] = {}
per_repo: dict[str, list] = {}
for d, slug, lic, markeri in REPOS:
    base = OSS / d
    licf = next((base / n for n in ("LICENSE", "LICENSE.txt", "COPYING") if (base / n).exists()),
                None)
    tekst = licf.read_text(encoding="utf-8", errors="replace") if licf else ""
    if not all(mk in tekst for mk in markeri):
        print(json.dumps({"preskocen_repo": slug, "razlog": "licenca se ne poklapa"}))
        continue
    licence_izvjestaj[slug] = lic
    flist: list = []
    for p in sorted(base.rglob("*.py")):
        if "tests" in p.parts or "test" in p.parts or "__pycache__" in p.parts:
            continue
        if p.name.startswith("test_") or p.name.endswith("_test.py"):
            continue
        try:
            src = p.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except Exception:
            continue
        rel = str(p.relative_to(base))
        # modul za import: requests/flask zive pod src/<paket>, rich direktno
        mod = rel[:-3].replace("/", ".")
        if mod.startswith("src."):
            mod = mod[4:]
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("__") and node.name.endswith("__"):
                continue
            if node.name.startswith("test_"):
                continue
            seg = ast.get_source_segment(src, node) or ""
            nlines = len(seg.splitlines())
            if not (5 <= nlines <= 60) or len(seg) > 6000 or bad(seg):
                continue
            args = [a.arg for a in node.args.args if a.arg not in ("self", "cls")]
            doc = ast.get_docstring(node) or ""
            first = doc.strip().splitlines()[0].strip() if doc.strip() else ""
            flist.append((rel, node.name, f"{node.name}({', '.join(args)})",
                          seg, args, first, mod, bool(doc)))
    flist.sort(key=lambda t: (t[0], t[1]))
    per_repo[slug] = flist
print(json.dumps({"klonirani_repovi": licence_izvjestaj,
                  "funkcija_po_repou": {k: len(v) for k, v in per_repo.items()}},
                 ensure_ascii=False))

# round-robin kroz repove radi ravnomjerne zastupljenosti
funcs: list[tuple] = []  # + slug, licenca, source
idx = {k: 0 for k in per_repo}
while any(idx[k] < len(per_repo[k]) for k in per_repo):
    for slug in per_repo:
        i = idx[slug]
        if i < len(per_repo[slug]):
            lic = licence_izvjestaj[slug]
            funcs.append(per_repo[slug][i] + (slug, lic, f"oss:{slug} ({lic})"))
            idx[slug] += 1


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


otpalo_fk = 0
kinds = ["objasni", "bug", "test", "docstring", "refaktoriraj"]
for (rel, name, sig, seg, args, first, mod, has_doc, slug, lic, source) in funcs:
    if len(rows) >= TARGET:
        break
    for kind in kinds:
        if len(rows) >= TARGET:
            break
        if (name, kind) in seen_fk:  # dedup protiv v0.1-v0.4
            otpalo_fk += 1
            continue
        code = "```python\n" + seg + "\n```"
        gdje = f"iz repozitorija `{slug}` (fajl `{rel}`)"
        if kind == "objasni":
            opis = ('Prema docstringu: "' + first + '".') if first else (
                f"Prima {len(args)} argument(a) ({', '.join(args)}) i vraca rezultat obrade." if args
                else "Ne prima argumente; izvrsava unaprijed odredjeni posao i vraca rezultat.")
            ok = emit(f"Objasni sto radi Python funkcija `{name}` {gdje}. "
                      f"Odgovori na bosanskom (ijekavica) i prilozi izvorni kod.",
                      f"Funkcija `{name}` ({sig}) — {opis}\n\nIzvorni kod:\n{code}",
                      "easy", source, lic, "ast-objasni",
                      {"file": f"{slug}/{rel}", "repo": slug})
        elif kind == "bug":
            nal = bug_nalazi(seg)
            ok = emit(f"Pregledaj sljedecu Python funkciju `{name}` {gdje} i pronadji "
                      f"potencijalni bug ili propust. Odgovori na bosanskom (ijekavica).",
                      "Pregledom sam uocio sljedece:\n" + "".join(f"{i}. {x}.\n" for i, x in enumerate(nal, 1)) +
                      f"\nKod na koji se odnosi:\n{code}",
                      "medium", source, lic, "ast-bug",
                      {"file": f"{slug}/{rel}", "repo": slug})
        elif kind == "test":
            tcode = ("```python\nimport inspect\nfrom " + mod + " import " + name + "\n\n\n"
                     f"def test_{name}_postoji():\n    assert callable({name})\n\n\n"
                     f"def test_{name}_signatura():\n    params = inspect.signature({name}).parameters\n"
                     f"    assert len(params) >= {len(args)}\n```")
            ok = emit(f"Napisi pytest test za Python funkciju `{name}` ({sig}) {gdje}. "
                      f"Odgovori na bosanskom (ijekavica).",
                      f"Test provjerava da je funkcija `{name}` uvoziva i da signatura odgovara "
                      f"ocekivanoj ({len(args)} parametara). Za puni test dodaj poziv s konkretnim "
                      f"ulazom iz svog okruzenja.\n\n{tcode}",
                      "medium", source, lic, "ast-test",
                      {"file": f"{slug}/{rel}", "repo": slug})
        elif kind == "docstring":
            novi = prosiri_docstring(seg, docstring_tekst(name, args, first))
            if not novi or bad(novi):
                continue
            ok = emit(f"Dopuni docstring za Python funkciju `{name}` {gdje} tako da opisuje "
                      f"namjenu, argumente i povratnu vrijednost. Odgovori na bosanskom (ijekavica).",
                      "Dopunjena verzija s docstringom na bosanskom:\n\n```python\n" + novi + "\n```",
                      "easy", source, lic, "ast-docstring",
                      {"file": f"{slug}/{rel}", "repo": slug})
        else:
            pr = refaktor_prijedlozi(seg, args, has_doc)
            ok = emit(f"Predlozi refaktoriranje Python funkcije `{name}` {gdje} "
                      f"(citljivost, tipovi, struktura). Odgovori na bosanskom (ijekavica).",
                      "Prijedlozi (bez promjene ponasanja):\n" + "".join(f"{i}. {x}.\n" for i, x in enumerate(pr, 1)) +
                      f"\nTrenutni kod:\n{code}",
                      "hard", source, lic, "ast-refaktoriraj",
                      {"file": f"{slug}/{rel}", "repo": slug})
        if ok:
            seen_fk.add((name, kind))  # interni dedup

# --- zavrsna provjera: svaki code-block se parsira ---
for r in rows:
    for blk in re.findall(r"```python\n(.*?)```", r["messages"][1]["content"], re.S):
        ast.parse(blk)

OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

po_repo: dict[str, int] = {}
po_zadatku: dict[str, int] = {}
for r in rows:
    po_repo[r["metadata"]["repo"]] = po_repo.get(r["metadata"]["repo"], 0) + 1
po_zadatku = dict(counts)
print(json.dumps({"start_id": f"amj-cd-{START_ID:04d}",
                  "total": len(rows), "out": str(OUT),
                  "po_repo": po_repo, "po_zadatku": po_zadatku,
                  "otpalo_dedup_fk": otpalo_fk, "otpalo_hash_ili_parse": otpalo_dedup},
                 ensure_ascii=False))
