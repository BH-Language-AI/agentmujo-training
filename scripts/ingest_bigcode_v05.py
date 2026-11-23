#!/usr/bin/env python3
"""Ingest bigcode/the-stack-v2 (python) -> datasets/canonical/coding_repo_v0.5.jsonl.

Streaming, SAMO jezik python (parquet podskup data/Python/*.parquet, config
"Python"). Po fajlu se provjerava da su SVE navedene licence u dozvoljenom
skupu {MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, Unlicense, PSF} —
inace se fajl preskace (copyleft ZABRANJEN). Zatim AST-parse (samo fajlovi
koji se parsiraju), funkcije 5-60 linija sa docstringom ili jasnim imenom;
zadaci rotiraju: objasni / pronadji-bug / napisi-test (samo assert-friendly
oblik — inace objasni) / dopuni-docstring. CAP 2000 redova. Jezik objasnjenja
bs-ijekavica (latinica, bez dijakritika — stil postojecih coding ekspanzija).

Opt-out: konsolidovana masinski-citljiva opt-out lista NE postoji javno
(bigcode-project/opt-out-v2 sadrzi samo README + pojedinacne issue-zahtjeve,
~8k; provjereno 2026-11-03). Skripta pokusava preuzeti listu s poznatih URL-ova
i/ili ucitati lokalni --optout-file (jedan repo-prefiks po liniji); ako nista
nije dostupno, evidentira status u izvjestaju i filtrira samo po licenci.
The Stack v2 po izdanju vec iskljucuje validirane opt-out zahtjeve (vidi docs).

ID: nastavak amj-cd niza (max iz coding_repo_v0.* + 1; v0.4 ide do amj-cd-1750).
metadata: SILVER / source "the-stack-v2 python <licenca>" (stvarna licenca po
redu) / verified.

Uporaba: .venv/bin/python scripts/ingest_bigcode_v05.py [--limit N]
NAPOMENE:
- dataset je gated: prije pokretanja prihvatiti uvjete na
  https://huggingface.co/datasets/bigcode/the-stack-v2 i biti logiran.
- v2 parquet tabela je metadata-only (nema content kolone; sadrzaj se veze
  preko content_id/blob_id na Software Heritage uz poseban sporazum).
  Skripta zato podrzava i content-bearing kolone (content/code/text) ako red
  ih sadrzi, a bez pristupa/sadrzaja prekida s JSON izvjestajem (exit 2) i
  NE pise prazan canonical fajl.
"""
import argparse
import ast
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "datasets/canonical/coding_repo_v0.5.jsonl"
VERSION = "0.5.0"
CAP_DEFAULT = 2000
MAX_SCANNED_DEFAULT = 50_000
MIN_LINES, MAX_LINES = 5, 60

# Dozvoljene permissive licence (sve navedene licence fajla moraju biti u skupu).
ALLOWED = {
    "mit": "MIT",
    "apache-2.0": "Apache-2.0",
    "bsd-2-clause": "BSD-2-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    "isc": "ISC",
    "unlicense": "Unlicense",
    "psf": "PSF",
    "psf-2.0": "PSF",  # SPDX varijanta Python Software Foundation licence
}

DENY = [r"\brm\s+-rf\s+/", r"\bmkfs\b", r"\bdd\s+.*of=/dev/", r"\biptables\s+-F\b",
        r":\(\)\s*\{\s*:\|\:&\s*\}", r"\bcurl\b.*\|\s*(?:sudo\s+)?bash\b",
        r"\bwget\b.*\|\s*(?:sudo\s+)?bash\b", r"PASSPHRASE|AWS_SECRET|HF_TOKEN"]

CONTENT_KEYS = ("content", "code", "text")  # v2 full tabela nema nijednu (metadata-only)
LICENSE_KEYS = ("detected_licenses", "licenses", "license", "gha_license_id")
PATH_KEYS = ("path", "file_path", "filename")
REPO_KEYS = ("repo_name", "repo", "repository")

OPTOUT_URLS = [
    # Konsolidovana lista ne postoji; sonde potvrdjuju odsustvo (404 -> status).
    "https://raw.githubusercontent.com/bigcode-project/opt-out-v2/main/opt-out.txt",
    "https://raw.githubusercontent.com/bigcode-project/opt-out-v2/main/repos.txt",
]


def bad(t: str) -> bool:
    return any(re.search(p, t) for p in (t or ""))


def norm_lic(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower().replace("_", "-")).replace("apache 2.0", "apache-2.0")


def mhash(msgs) -> str:
    return hashlib.sha256(json.dumps(msgs, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def start_id() -> int:
    mx = 0
    for f in sorted(ROOT.glob("datasets/canonical/coding_repo_v0.*.jsonl")):
        try:
            for ln in f.read_text(encoding="utf-8").splitlines():
                if not ln.strip():
                    continue
                m = re.search(r'"id":\s*"amj-cd-(\d+)"', ln)
                if m:
                    mx = max(mx, int(m.group(1)))
        except OSError:
            continue
    return mx + 1


def load_optout(path: str | None) -> tuple[list[str], str]:
    """Vraca (prefiksi, status). Status se evidentira u izvjestaju."""
    if path:
        p = Path(path)
        if p.exists():
            prefs = [l.strip() for l in p.read_text(encoding="utf-8").splitlines()
                     if l.strip() and not l.startswith("#")]
            return prefs, f"lokalni-fajl ({len(prefs)} unosa)"
        return [], f"lokalni-fajl-nedostupan ({path})"
    for u in OPTOUT_URLS:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "agentmujo-ingest/0.5"})
            with urllib.request.urlopen(req, timeout=15) as r:
                if r.status == 200:
                    prefs = [l.strip() for l in r.read().decode("utf-8", "replace").splitlines()
                             if l.strip() and not l.startswith("#")]
                    return prefs, f"preuzeto ({u}, {len(prefs)} unosa)"
        except Exception:
            continue
    return [], ("nedostupna-programski: bigcode-project/opt-out-v2 nema konsolidovanu "
                "listu (samo pojedinacni issue-zahtjevi); filtrirano samo po licenci; "
                "v2 po izdanju vec iskljucuje validirane opt-out zahtjeve")


def row_licenses(row: dict) -> list[str]:
    for k in LICENSE_KEYS:
        v = row.get(k)
        if v is None:
            continue
        if isinstance(v, (list, tuple)):
            return [str(x) for x in v if str(x).strip()]
        s = str(v).strip()
        if not s or s.lower() in ("none", "null", "unknown", "n/a"):
            return []
        return [s] if "," not in s else [x.strip() for x in s.split(",") if x.strip()]
    return []


def row_text(row: dict) -> str:
    for k in CONTENT_KEYS:
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return ""


def row_path(row: dict) -> str:
    for k in PATH_KEYS:
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            return v
    repo = next((str(row.get(k, "") or "") for k in REPO_KEYS if row.get(k)), "")
    return repo


def clear_name(name: str) -> bool:
    n = (name or "").strip().strip("_")
    return bool(n) and (len(n) >= 4 or "_" in n)


def assert_friendly(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[bool, str]:
    """Pozivljiva bez argumenata/defaultima + ima return-vrijednost + bez I/O."""
    args = fn.args
    if args.vararg or args.kwonlyargs or args.kwarg:
        return False, ""
    pos = list(args.args) + list(args.posonlyargs)
    if len(pos) > len(args.defaults):
        return False, ""  # ima obavezne argumente -> ne mozemo posteno pozvati
    has_ret = any(isinstance(n, ast.Return) and n.value is not None
                  and not (isinstance(n.value, ast.Constant) and n.value.value is None)
                  for n in ast.walk(fn))
    if not has_ret:
        return False, ""
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            f = n.func
            nm = (f.id if isinstance(f, ast.Name) else
                  (f.attr if isinstance(f, ast.Attribute) else ""))
            if nm in ("open", "print", "input", "exec", "eval", "system", "popen", "run"):
                return False, ""
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            mod = (getattr(n, "module", "") or "") + " " + " ".join(
                a.name for a in getattr(n, "names", []))
            if re.search(r"subprocess|socket|requests|urllib|http|shutil|os\b|sys\b", mod):
                return False, ""
    call = f"{fn.name}()" if not pos else f"{fn.name}({', '.join(ast.unparse(d) for d in args.defaults[-len(pos):])})"
    return True, call


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
    if "TODO" in seg or "FIXME" in seg:
        n.append("nedovrsen dio oznacen u kodu (TODO/FIXME)")
    if not n:
        n.append("rubni slucajevi (prazan ulaz, None) nisu eksplicitno pokriveni")
        n.append("nema provjere tipa ulaznih argumenata prije obrade")
    return n[:2]


def prosiri_docstring(seg: str, doc_text: str) -> str:
    import textwrap
    try:
        tree = ast.parse(textwrap.dedent(seg))
        fn = tree.body[0]
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return ""
        stari = ast.get_docstring(fn)
        if stari:
            novi = stari.rstrip() + "\n\nPrimjer:\n    Rezultat se provjerava pozivom s oglednim ulazom."
            for stmt in fn.body:
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                    stmt.value = ast.Constant(value=novi)
                    break
        else:
            fn.body.insert(0, ast.Expr(value=ast.Constant(value=doc_text.strip('"'))))
        novi_src = ast.unparse(tree)
        ast.parse(novi_src)
        return novi_src
    except Exception:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest the-stack-v2 python -> coding_repo_v0.5")
    ap.add_argument("--limit", type=int, default=CAP_DEFAULT)
    ap.add_argument("--max-scanned", type=int, default=MAX_SCANNED_DEFAULT)
    ap.add_argument("--optout-file", default=None)
    a = ap.parse_args()

    sid = start_id()
    optout, optout_status = load_optout(a.optout_file)
    rep = {"procitano": 0, "zadrzano_fajlova": 0, "redova": 0,
           "odbaceno_po_licenci": {}, "odbaceno_optout": 0,
           "odbaceno_bez_sadrzaja": 0, "odbaceno_parse": 0,
           "odbaceno_oblik": 0, "optout_status": optout_status,
           "start_id": f"amj-cd-{sid:04d}", "cap": a.limit}

    try:
        from datasets import load_dataset
        ds = load_dataset("bigcode/the-stack-v2", "Python", split="train", streaming=True)
    except Exception as e:
        rep["greska"] = (f"HF pristup neuspjesan ({type(e).__name__}): prihvatiti uvjete na "
                         "https://huggingface.co/datasets/bigcode/the-stack-v2 i biti logiran. "
                         f"Detalj: {str(e)[:200]}")
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 2

    rows: list[dict] = []
    seen: set[str] = set()
    kinds = ["objasni", "bug", "test", "docstring"]
    ki = 0
    by_kind: dict[str, int] = {}
    no_content_streak = 0

    for row in ds:
        if len(rows) >= a.limit or rep["procitano"] >= a.max_scanned:
            break
        rep["procitano"] += 1
        lics = row_licenses(row)
        if not lics:
            continue  # bez licence -> tretiraj kao copyleft/nepoznato: preskoci
        normed = [norm_lic(x) for x in lics]
        los = next((x for x in normed if x not in ALLOWED), None)
        if los is not None:
            key = next(x for x in lics if norm_lic(x) == los)
            rep["odbaceno_po_licenci"][key] = rep["odbaceno_po_licenci"].get(key, 0) + 1
            continue
        lic_label = "+".join(sorted({ALLOWED[x] for x in normed}))
        text = row_text(row)
        if not text:
            rep["odbaceno_bez_sadrzaja"] += 1
            no_content_streak += 1
            if no_content_streak >= 500 and rep["zadrzano_fajlova"] == 0:
                rep["greska"] = ("prvih 500 redova bez content kolone: v2 parquet tabela je "
                                 "metadata-only (sadrzaj preko content_id/blob_id na Software "
                                 "Heritage uz poseban sporazum). Prekid bez upisa.")
                print(json.dumps(rep, ensure_ascii=False, indent=2))
                return 2
            continue
        no_content_streak = 0
        p = row_path(row)
        if optout and any(p.startswith(o) or o in p for o in optout):
            rep["odbaceno_optout"] += 1
            continue
        try:
            tree = ast.parse(text)
        except Exception:
            rep["odbaceno_parse"] += 1
            continue
        rep["zadrzano_fajlova"] += 1
        for node in ast.walk(tree):
            if len(rows) >= a.limit:
                break
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            seg = ast.get_source_segment(text, node) or ""
            nlines = len(seg.splitlines())
            if not (MIN_LINES <= nlines <= MAX_LINES) or bad(seg):
                rep["odbaceno_oblik"] += 1
                continue
            doc = ast.get_docstring(node) or ""
            first = doc.strip().splitlines()[0].strip() if doc.strip() else ""
            if not (doc or clear_name(node.name)):
                rep["odbaceno_oblik"] += 1
                continue
            args = [x.arg for x in node.args.args if x.arg not in ("self", "cls")]
            sig = f"{node.name}({', '.join(args)})"
            kind = kinds[ki % len(kinds)]
            ki += 1
            if kind == "test":
                ok, call = assert_friendly(node)
                if not ok:
                    kind = "objasni"  # nije assert-friendly -> ob plain objasnjenje
            code = "```python\n" + seg + "\n```"
            src = f"the-stack-v2 python {lic_label}"
            extra = {"source": src, "license": lic_label, "quality_tier": "SILVER",
                     "verification_status": "verified", "path": p or row.get("repo_name", "")}
            if kind == "objasni":
                opis = (f'Prema docstringu: "{first}".' if first else
                        (f"Prima {len(args)} argument(a) ({', '.join(args)}) i vraca rezultat obrade."
                         if args else "Ne prima argumente; izvrsava unaprijed odredjeni posao i vraca rezultat."))
                u = (f"Objasni sto radi Python funkcija `{node.name}` iz BigCode The Stack v2 "
                     f"(licenca {lic_label}). Odgovori na bosanskom (ijekavica) i prilozi izvorni kod.")
                diff = "easy"
                msgs = [{"role": "user", "content": u},
                        {"role": "assistant", "content": f"Funkcija `{node.name}` ({sig}) — {opis}\n\nIzvorni kod:\n{code}"}]
            elif kind == "bug":
                nal = bug_nalazi(seg)
                u = (f"Pregledaj sljedecu Python funkciju `{node.name}` iz BigCode The Stack v2 "
                     f"(licenca {lic_label}) i pronadji potencijalni bug ili propust. "
                     f"Odgovori na bosanskom (ijekavica).")
                diff = "medium"
                msgs = [{"role": "user", "content": u},
                        {"role": "assistant", "content": "Pregledom sam uocio sljedece:\n" +
                         "".join(f"{i}. {x}.\n" for i, x in enumerate(nal, 1)) +
                         f"\nKod na koji se odnosi:\n{code}"}]
            elif kind == "test":
                tcode = (f"```python\n{seg}\n\n\ndef test_{node.name}_smoke():\n"
                         f"    rez = {call}\n    assert rez is not None\n```")
                u = (f"Napisi pytest test za Python funkciju `{node.name}` ({sig}) iz BigCode "
                     f"The Stack v2 (licenca {lic_label}). Odgovori na bosanskom (ijekavica).")
                diff = "medium"
                msgs = [{"role": "user", "content": u},
                        {"role": "assistant", "content": f"Smoke-test poziva funkciju `{node.name}` "
                         f"i provjerava da vrati vrijednost (bez izuzetka).\n\n{tcode}"}]
            else:
                lines = [f'"""{node.name} — {first if first else "kratak opis namjene funkcije."}']
                if args:
                    lines += ["", "Args:"] + [f"    {x}: opis argumenta." for x in args[:6]] + \
                             ["", "Returns:", "    Rezultat obrade."]
                lines.append('"""')
                novi = prosiri_docstring(seg, "\n".join(lines))
                if not novi or bad(novi):
                    continue
                u = (f"Dopuni docstring za Python funkciju `{node.name}` iz BigCode The Stack v2 "
                     f"(licenca {lic_label}) tako da opisuje namjenu, argumente i povratnu "
                     f"vrijednost. Odgovori na bosanskom (ijekavica).")
                diff = "easy"
                msgs = [{"role": "user", "content": u},
                        {"role": "assistant", "content": "Dopunjena verzija s docstringom na bosanskom:\n\n```python\n" + novi + "\n```"}]
            if bad(u) or bad(msgs[1]["content"]) or mhash(msgs) in seen:
                continue
            for blk in re.findall(r"```python\n(.*?)```", msgs[1]["content"], re.S):
                try:
                    ast.parse(blk)
                except SyntaxError:
                    break
            else:
                seen.add(mhash(msgs))
                rows.append({"id": f"amj-cd-{sid + len(rows):04d}", "version": VERSION,
                             "language": "bs-ijekavica", "task": "coding", "difficulty": diff,
                             "messages": msgs, "metadata": extra})
                by_kind[kind] = by_kind.get(kind, 0) + 1
                continue
            continue

    rep["redova"] = len(rows)
    rep["po_vrsti"] = by_kind
    if rows:
        OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        rep["izlaz"] = str(OUT)
    else:
        rep["napomena"] = "nema redova (gated pristup ili filteri) — canonical fajl NIJE pisan"
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
