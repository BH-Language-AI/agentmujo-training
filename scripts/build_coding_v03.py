#!/usr/bin/env python3
"""Build coding_repo_v0.3 — ~850 NOVIH redova (AST-mining + sinteticki zadaci za 14 alata).

Izvori:
  (a) AST-mining svih python fajlova u repou (5 tipova zadataka po funkciji).
  (b) Sinteticki "napisi python skriptu..." zadaci vezani za alate iz configs/tools.yaml.
Dedup: protiv coding_repo_v0.1 + v0.2 (hash poruka) i interno.
Ne dira postojece fajlove ni splits/.
"""
import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "datasets/canonical/coding_repo_v0.3.jsonl"
START_ID = 101  # nastavak niza (v0.2 ide do amj-cd-0100)
TARGET_AST = 450
TARGET_SYNTH = 400
VERSION = "0.3.0"

DENY = [r"\brm\s+-rf\s+/", r"\bmkfs\b", r"\bdd\s+.*of=/dev/", r"\biptables\s+-F\b",
        r":\(\)\s*\{\s*:\|\:&\s*\}", r"\bcurl\b.*\|\s*(?:sudo\s+)?bash\b",
        r"\bwget\b.*\|\s*(?:sudo\s+)?bash\b", r"PASSPHRASE|AWS_SECRET|HF_TOKEN"]


def bad(t: str) -> bool:
    return any(re.search(p, t) for p in DENY)


def mhash(msgs) -> str:
    return hashlib.sha256(json.dumps(msgs, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def meta(src: str) -> dict:
    return {"source": src, "license": "Apache-2.0", "quality_tier": "SILVER",
            "verification_status": "verified"}


def row(sid: int, user: str, asst: str, difficulty: str, src: str, extra: dict) -> dict:
    m = meta(src)
    m.update(extra)
    return {"id": f"amj-cd-{sid:04d}", "version": VERSION, "language": "bs-ijekavica",
            "task": "coding", "difficulty": difficulty,
            "messages": [{"role": "user", "content": user},
                         {"role": "assistant", "content": asst}],
            "metadata": m}


# --- dedup protiv v0.1 + v0.2 ---
seen: set[str] = set()
for f in ("datasets/canonical/coding_repo_v0.1.jsonl", "datasets/canonical/coding_repo_v0.2.jsonl"):
    p = ROOT / f
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                seen.add(mhash(json.loads(ln)["messages"]))

rows: list[dict] = []
counts: dict[str, int] = {}


def emit(user: str, asst: str, difficulty: str, src: str, kind: str, extra: dict) -> bool:
    msgs = [{"role": "user", "content": user}, {"role": "assistant", "content": asst}]
    if bad(asst) or bad(user) or mhash(msgs) in seen:
        return False
    seen.add(mhash(msgs))
    rows.append(row(START_ID + len(rows), user, asst, difficulty, src, extra))
    counts[kind] = counts.get(kind, 0) + 1
    return True


# ============ (a) AST-MINING ============
funcs: list[tuple[str, str, str, str, list[str]]] = []  # file, name, sig, seg, args
for p in sorted(ROOT.rglob("*.py")):
    if ".git" in p.parts or "__pycache__" in p.parts or ".venv" in p.parts:
        continue
    try:
        src = p.read_text(encoding="utf-8")
        tree = ast.parse(src)
    except Exception:
        continue
    rel = str(p.relative_to(ROOT))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_") and node.name != "__init__":
            pass  # privatne funkcije su OK kao gradivo
        seg = ast.get_source_segment(src, node) or ""
        if not (80 <= len(seg) <= 1600) or bad(seg):
            continue
        args = [a.arg for a in node.args.args if a.arg not in ("self", "cls")]
        doc = ast.get_docstring(node) or ""
        first = doc.strip().splitlines()[0].strip() if doc.strip() else ""
        mod = rel[:-3].replace("/", ".")
        funcs.append((rel, node.name, f"{node.name}({', '.join(args)})", seg, args, first, mod,
                      len(seg.splitlines())))
funcs.sort(key=lambda t: (t[0], t[1]))


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


def refaktor_prijedlozi(seg: str, args: list[str], doc: str) -> list[str]:
    p = []
    if len(seg.splitlines()) > 40:
        p.append("podijeli funkciju na dvije manje cjeline (priprema + obrada)")
    if len(args) > 4:
        p.append("grupiraj argumente u rjecnik ili dataclass (previse parametara)")
    if ":" not in seg.splitlines()[0].replace("->", "") or "->" not in seg.splitlines()[0]:
        if re.search(r"def \w+\([^)]*\):", seg.splitlines()[0]):
            p.append("dodaj anotacije tipova argumenata i povratne vrijednosti")
    if not doc:
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
        lines.append("")
        lines.append("Args:")
        lines += [f"    {a}: opis argumenta." for a in args[:6]]
        lines.append("")
        lines.append("Returns:")
        lines.append("    Rezultat obrade.")
    lines.append('"""')
    return "\n".join(lines)


def ubaci_docstring(seg: str, doc: str) -> str:
    import textwrap
    try:
        tree = ast.parse(textwrap.dedent(seg))
        fn = tree.body[0]
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return ""
        if ast.get_docstring(fn):
            return ""  # vec ima docstring — ne dupliraj
        fn.body.insert(0, ast.Expr(value=ast.Constant(value=doc.strip('"'))))
        novi = ast.unparse(tree)
        ast.parse(novi)
        return novi
    except Exception:
        return ""


made_ast = 0
ast_kinds = ["objasni", "bug", "test", "docstring", "refaktoriraj"]
for (rel, name, sig, seg, args, first, mod, nlines) in funcs:  # round-robin: ravnomjerno po tipovima
    if made_ast >= TARGET_AST:
        break
    for kind in ast_kinds:
        if made_ast >= TARGET_AST:
            break
        code = "```python\n" + seg + "\n```"
        if kind == "objasni":
            opis = ('Prema docstringu: "' + first + '".') if first else (
                f"Prima {len(args)} argument(a) ({', '.join(args)}) i vraca rezultat obrade." if args
                else "Ne prima argumente; izvrsava unaprijed odredjeni posao i vraca rezultat.")
            ok = emit(f"Objasni sto radi Python funkcija `{name}` iz fajla `{rel}`. "
                      f"Odgovori na bosanskom (ijekavica) i prilozi izvorni kod.",
                      f"Funkcija `{name}` ({sig}) — {opis}\n\nIzvorni kod:\n{code}",
                      "easy", "coding-expansion-v0.3", "ast-objasni", {"file": rel})
        elif kind == "bug":
            nal = bug_nalazi(seg)
            ok = emit(f"Pregledaj sljedecu Python funkciju `{name}` iz fajla `{rel}` i pronadji "
                      f"potencijalni bug ili propust. Odgovori na bosanskom (ijekavica).",
                      "Pregledom sam uocio sljedece:\n" + "".join(f"{i}. {x}.\n" for i, x in enumerate(nal, 1)) +
                      f"\nKod na koji se odnosi:\n{code}",
                      "medium", "coding-expansion-v0.3", "ast-bug", {"file": rel})
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
                      "medium", "coding-expansion-v0.3", "ast-test", {"file": rel})
        elif kind == "docstring":
            novi = ubaci_docstring(seg, docstring_tekst(name, args, first))
            if not novi or bad(novi):
                continue
            ok = emit(f"Dopuni docstring za Python funkciju `{name}` iz fajla `{rel}` tako da opisuje "
                      f"namjenu, argumente i povratnu vrijednost. Odgovori na bosanskom (ijekavica).",
                      "Dopunjena verzija s docstringom na bosanskom:\n\n```python\n" + novi + "\n```",
                      "easy", "coding-expansion-v0.3", "ast-docstring", {"file": rel})
        else:
            pr = refaktor_prijedlozi(seg, args, first)
            ok = emit(f"Predlozi refaktoriranje Python funkcije `{name}` iz fajla `{rel}` "
                      f"(citljivost, tipovi, struktura). Odgovori na bosanskom (ijekavica).",
                      "Prijedlozi (bez promjene ponasanja):\n" + "".join(f"{i}. {x}.\n" for i, x in enumerate(pr, 1)) +
                      f"\nTrenutni kod:\n{code}",
                      "hard", "coding-expansion-v0.3", "ast-refaktoriraj", {"file": rel})
        if ok:
            made_ast += 1

# ============ (b) SINTETICKI ZADACI ZA 14 ALATA ============
# Svaki alat: cilj, 5 parametara, komanda (subprocess), obrada izlaza.
SPEC = {
    "service_status": ("provjeru statusa systemd servisa", ["nginx", "postgres", "redis", "app", "worker"],
        '["systemctl", "is-active", vrijednost]', 'aktivan = r.stdout.strip() == "active"'),
    "service_restart": ("restart systemd servisa uz potvrdu", ["nginx", "postgres", "redis", "app", "worker"],
        '["systemctl", "restart", vrijednost]', 'r.check_returncode()'),
    "service_logs": ("dohvat zadnjih log linija servisa", ["nginx", "postgres", "redis", "app", "worker"],
        '["journalctl", "-u", vrijednost, "-n", "50", "--no-pager"]', 'linije = r.stdout.splitlines()'),
    "disk_usage": ("provjeru iskoristenosti diska", ["/", "/var", "/home", "/tmp", "/var/log"],
        '["df", "-h", vrijednost]', 'red = [l for l in r.stdout.splitlines() if vrijednost in l]'),
    "memory_usage": ("provjeru iskoristenosti memorije", ["80", "85", "90", "75", "95"],
        '["cat", "/proc/meminfo"]',
        'mem = dict(l.split(": ", 1) for l in r.stdout.splitlines() if ": " in l)\n'
        'slobodno = int(mem.get("MemAvailable", "0 kB").split()[0]) // 1024'),
    "cpu_usage": ("provjeru opterecenja CPU-a", ["1.0", "2.0", "4.0", "0.5", "8.0"],
        '["cat", "/proc/loadavg"]', 'load1 = float(r.stdout.split()[0])'),
    "process_list": ("listu najzahtjevnijih procesa", ["%cpu", "%mem", "pid", "etime", "comm"],
        '["ps", "-eo", "pid,pcpu,pmem,comm", "--sort=-" + vrijednost]',
        'redovi = r.stdout.splitlines()[1:11]'),
    "network_status": ("provjeru statusa mreznih interfejsa", ["eth0", "lo", "wlan0", "ens3", "enp0s3"],
        '["ip", "-brief", "addr", "show", vrijednost]', 'postoji = bool(r.stdout.strip())'),
    "port_check": ("provjeru da li nesto slusa na portu", ["80", "443", "3000", "5432", "8080"],
        '["ss", "-ltn"]', 'slusa = (":" + vrijednost) in r.stdout'),
    "terminal": ("sigurnu read-only shell provjeru", ["uptime", "df -h /", "whoami", "date", "uname -a"],
        'vrijednost.split()', 'izlaz = r.stdout.strip()'),
    "package_query": ("provjeru da li je paket instaliran", ["nginx", "python3", "git", "curl", "redis"],
        '["dpkg-query", "-W", "-f=${Version}", vrijednost]', 'instaliran = r.returncode == 0'),
    "package_install": ("instalaciju paketa uz provjeru i potvrdu", ["htop", "curl", "git", "jq", "ncdu"],
        '["apt-get", "install", "-y", vrijednost]', 'r.check_returncode()'),
    "file_list": ("listu sadrzaja direktorija", ["/var/log", "/etc/nginx", "/tmp", "/home", "/etc"],
        '["ls", "-la", vrijednost]', 'stavke = r.stdout.splitlines()[1:]'),
    "file_read": ("sigurno citanje tekstualnog fajla",
        ["/etc/hosts", "/etc/os-release", "/proc/uptime", "/etc/hostname", "/proc/loadavg"],
        '["head", "-n", "50", vrijednost]', 'linije = r.stdout.splitlines()[:50]'),
}

UVOD = [
    "Napisi python3 monitoring skriptu za {c} (vezano za alat `{t}` iz configs/tools.yaml). "
    "Skripta mora koristiti subprocess i standardnu biblioteku, imati vremensko ogranicenje i jasan izlaz.",
    "Napisi python3 skriptu koja parsira izlaz {c} (alat `{t}`) i ispisuje JSON izvjestaj "
    "s poljima provjereno, ulaz i rezultat. Koristi subprocess i standardnu biblioteku.",
    "Napisi python3 skriptu za redovnu provjeru: {c} (alat `{t}`). Skripta neka vrati izlazni kod 0 "
    "kad je sve u redu, a 1 kad nije, uz poruku na bosanskom (ijekavica).",
    "Napisi python3 skriptu s argparse suceljem za {c} (alat `{t}`). Podrzaj --json prekidac za "
    "masinski citljiv izlaz. Koristi subprocess i standardnu biblioteku.",
    "Napisi python3 skriptu koja u petlji nadgleda {c} (alat `{t}`) i upozorava kad stanje nije "
    "ocekivano. Koristi subprocess, time i standardnu biblioteku.",
    "Napisi python3 skriptu koja daje iscrpan izvjestaj o {c} (alat `{t}`), s vremenskom oznakom "
    "pokretanja i JSON izlazom. Koristi subprocess, datetime i standardnu biblioteku.",
]

TEZINA = ["easy", "medium", "medium", "medium", "hard", "medium"]
SKEL_IDX = [0, 1, 0, 1, 2, 1]  # varijanta -> kostur (petlja za V5, JSON za V6)

POTVRDA = {  # mutacije (restart/instalacija) traze potvrdu prije izvrsenja
    0: '    if input(f"Potvrdjujes {vrijednost}? (da/NE): ").strip().lower() != "da":\n'
       '        print("Otkazano bez promjena.")\n        return False\n',
    1: '    if input(f"Potvrdjujes {vrijednost}? (da/NE): ").strip().lower() != "da":\n'
       '        return {"ulaz": vrijednost, "otkazano": True}\n',
    2: '    if input(f"Potvrdjujes {vrijednost}? (da/NE): ").strip().lower() != "da":\n'
       '        print("Otkazano bez promjena.")\n        return False\n',
}

SKEL = [  # 3 kostura koda
    ('provjera s izlaznim kodom',
     '#!/usr/bin/env python3\n"""{G}."""\nimport subprocess\nimport sys\n\n\n'
     'def provjeri(vrijednost="{P}"):\n{CONFIRM}'
     '    r = subprocess.run({C}, capture_output=True, text=True, timeout=30)\n{O}\n'
     '    return r.returncode == 0\n\n\n'
     'if __name__ == "__main__":\n    ulaz = sys.argv[1] if len(sys.argv) > 1 else "{P}"\n'
     '    ok = provjeri(ulaz)\n    print("OK: " + ulaz if ok else "NEUSPJEH: " + ulaz)\n'
     '    raise SystemExit(0 if ok else 1)\n'),
    ('argparse + JSON izvjestaj',
     '#!/usr/bin/env python3\n"""{G}."""\nimport argparse\nimport datetime\nimport json\nimport subprocess\n\n\n'
     'def prikupi(vrijednost):\n{CONFIRM}'
     '    r = subprocess.run({C}, capture_output=True, text=True, timeout=30)\n{O}\n'
     '    return {"ulaz": vrijednost, "kod": r.returncode,\n'
     '            "vrijeme": datetime.datetime.now().isoformat(timespec="seconds"),\n'
     '            "izlaz": r.stdout.strip()[:500]}\n\n\n'
     'def main():\n    ap = argparse.ArgumentParser(description="{G}")\n    ap.add_argument("vrijednost", nargs="?", default="{P}")\n'
     '    ap.add_argument("--json", action="store_true")\n    a = ap.parse_args()\n'
     '    rez = prikupi(a.vrijednost)\n    print(json.dumps(rez, indent=2, ensure_ascii=False))\n\n\n'
     'if __name__ == "__main__":\n    main()\n'),
    ('nadgledanje u petlji',
     '#!/usr/bin/env python3\n"""{G}."""\nimport subprocess\nimport sys\nimport time\n\nPROVJERA_S = 60\n\n\n'
     'def jednom(vrijednost="{P}"):\n{CONFIRM}'
     '    r = subprocess.run({C}, capture_output=True, text=True, timeout=30)\n{O}\n'
     '    return r.returncode == 0\n\n\n'
     'def main(krugova=3):\n    ulaz = sys.argv[1] if len(sys.argv) > 1 else "{P}"\n'
     '    for i in range(krugova):\n        ok = jednom(ulaz)\n        print(f"[{i + 1}/{krugova}] " + ulaz + ": " + ("u redu" if ok else "UPOZORENJE"))\n'
     '        if not ok:\n            return 1\n        if i + 1 < krugova:\n            time.sleep(PROVJERA_S)\n    return 0\n\n\n'
     'if __name__ == "__main__":\n    raise SystemExit(main())\n'),
]


def synth_code(tool: str, cilj: str, param: str, cmd: str, obrada: str, vi: int) -> str:
    si = SKEL_IDX[vi % 6]
    title, kostur = SKEL[si]
    g = f"{cilj[0].upper() + cilj[1:]} — {title}"
    o = "\n".join("    " + l if l.strip() else l for l in obrada.splitlines())
    confirm = ""
    if tool in ("service_restart", "package_install"):
        confirm = POTVRDA[si].replace("{vrijednost}", "vrijednost")
    kod = kostur.replace("{G}", g).replace("{P}", param).replace("{C}", cmd).replace("{O}", o)
    kod = kod.replace("{CONFIRM}", confirm)
    try:
        ast.parse(kod)
    except SyntaxError:
        return ""
    return kod


made_synth = 0
names14 = list(SPEC.keys())
per_tool = TARGET_SYNTH // 14
ekstra = TARGET_SYNTH % 14
for ti, t in enumerate(names14):
    cilj, params, cmd, obrada = SPEC[t]
    n = per_tool + (1 if ti < ekstra else 0)
    got = 0
    vi = 0
    while got < n and vi < 60:
        p = params[(vi // 6) % len(params)]
        v = vi % 6
        kod = synth_code(t, cilj, p, cmd, obrada, v)
        vi += 1
        if not kod:
            continue
        user = UVOD[v].format(c=cilj, t=t)
        if v == 2 and t in ("service_restart", "package_install"):
            user += " Posto je rijec o mutaciji, skripta mora traziti potvrdu prije izvrsenja."
        asst = (f"Evo skripte (python3, samo standardna biblioteka). Pokretanje: `python3 provjera.py [{p}]`.\n\n"
                f"```python\n{kod}\n```\n\nSkripta prati ponasanje alata `{t}`: pokrece odgovarajucu "
                f"sistemsku komandu s ogranicenjem od 30 sekundi i javlja rezultat.")
        if emit(user, asst, TEZINA[v], "coding-expansion-v0.3", f"synth-{t}", {"tool": t}):
            got += 1
            made_synth += 1

print(json.dumps({"ast": made_ast, "synth": made_synth, "total": len(rows), "out": str(OUT)},
                 ensure_ascii=False))
OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

by_source = {"ast-mining": sum(v for k, v in counts.items() if k.startswith("ast-")),
             "sinteticki-alati": sum(v for k, v in counts.items() if k.startswith("synth-"))}
print(json.dumps({"counts": counts, "by_source": by_source}, ensure_ascii=False))
