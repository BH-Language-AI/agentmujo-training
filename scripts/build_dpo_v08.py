"""Build datasets/canonical/dpo_v0.8.jsonl — ~2000 DPO parova deriviranih iz FC v0.3.

Metoda kao v0.7 (rotacija 4 rejected tipa) + 2 nova tipa za v0.3 visekoracne redove:
  (a) pogresan alat za isti cilj, (b) izmisljen parametar,
  (c) odgovor bez tool poziva, (d) rizicno bez potvrde,
  (e) skraceni lanac — rejected preskace verifikacijski (zadnji) korak iz chosena,
  (f) pogresan redoslijed — rejected izvrsava korake obrnutim redom.
(e)/(f) samo za redove sa >=2 tool poziva; jednokoracni rotiraju a-d.
ID: nastavak na max amj-dpo-* (dinamicki). metadata: SILVER/dpo-auto-derived-v0.8/verified.
Deterministicki (seed 808). Ne dira postojece fajlove ni splits/.
"""

from __future__ import annotations

import glob
import json
import random
from pathlib import Path

RNG = random.Random(808)
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "datasets" / "canonical" / "dpo_v0.8.jsonl"
VERSION = "0.8.0"
N_WANT = 2000

FC_FILES = [ROOT / "datasets" / "canonical" / "function_calling_v0.3.jsonl"]


def tc(func: str, **params: object) -> str:
    inner = "".join(f"<parameter={k}>\n{v}\n</parameter>" for k, v in params.items())
    return f"<tool_call>\n<function={func}>\n{inner}</function>\n</tool_call>"


def row(n: int, prompt: str, chosen: str, rejected: str, difficulty: str) -> dict:
    rid = f"amj-dpo-{n:04d}"
    assert chosen.strip() and rejected.strip() and chosen != rejected
    return {
        "id": rid, "version": VERSION, "language": "bs-ijekavica",
        "task": "preference-dpo", "difficulty": difficulty,
        "messages": [{"role": "user", "content": prompt},
                     {"role": "assistant", "content": chosen}],
        "prompt": prompt, "chosen": chosen, "rejected": rejected,
        "metadata": {"source": "dpo-auto-derived-v0.8", "quality_tier": "SILVER",
                     "verification_status": "verified"},
    }


WRONG_TOOL = {
    "service_status": ("service_logs", lambda a: {"service": a["service"], "lines": 30}),
    "service_restart": ("service_status", lambda a: {"service": a["service"]}),
    "service_logs": ("service_status", lambda a: {"service": a["service"]}),
    "disk_usage": ("memory_usage", lambda a: {}),
    "memory_usage": ("disk_usage", lambda a: {"path": "/"}),
    "cpu_usage": ("memory_usage", lambda a: {}),
    "process_list": ("cpu_usage", lambda a: {}),
    "network_status": ("port_check", lambda a: {"port": 80}),
    "port_check": ("network_status", lambda a: {}),
    "package_query": ("file_list", lambda a: {"path": "/usr/bin"}),
    "package_install": ("package_query", lambda a: {"package": a["package"]}),
    "file_list": ("disk_usage", lambda a: {"path": a["path"]}),
    "file_read": ("file_list", lambda a: {"path": a["path"].rsplit("/", 1)[0] or "/"}),
}
TERMINAL_EQUIV = {
    "service_status": lambda a: f"systemctl is-active {a['service']}",
    "service_restart": lambda a: f"systemctl restart {a['service']}",
    "service_logs": lambda a: f"journalctl -u {a['service']} -n {a.get('lines', 50)}",
    "disk_usage": lambda a: f"df -h {a.get('path', '/')}",
    "memory_usage": lambda a: "free -h",
    "cpu_usage": lambda a: "uptime",
    "process_list": lambda a: f"ps aux --sort=-%cpu | head -n {a.get('limit', 10)}",
    "network_status": lambda a: "ip -brief addr",
    "port_check": lambda a: f"ss -tlnp | grep {a['port']}",
    "package_query": lambda a: f"dpkg -l {a['package']}",
    "package_install": lambda a: f"apt-get install -y {a['package']}",
    "file_list": lambda a: f"ls -la {a['path']}",
    "file_read": lambda a: f"cat {a['path']}",
    "terminal": lambda a: a["command"],
}
A_LEADS = ["Evo provjeravam, krecem od ovoga:",
           "Moze, odmah gledam:",
           "Uredu, provjeravam na najbrzi nacin:"]


def terminal_for_term_cmd(cmd: str) -> tuple[str, dict]:
    c = cmd.lower()
    if any(k in c for k in ("ss ", "ss-", "ip ", "ping", "curl", "wget", "nmcli")):
        return "port_check", {"port": 80}
    if any(k in c for k in ("df", "du ", "du-", "lsblk", "mount")):
        return "memory_usage", {}
    if any(k in c for k in ("ps ", "ps-", "uptime", "top", "htop", "free")):
        return "cpu_usage", {}
    return "service_status", {"service": "nginx"}


def rej_a(first_name: str, first_args: dict, k: int) -> str:
    lead = RNG.choice(A_LEADS)
    if first_name == "terminal":
        wn, wa = terminal_for_term_cmd(first_args.get("command", ""))
        return f"{lead}\n\n{tc(wn, **wa)}"
    if k % 2 == 0:
        wn, fn = WRONG_TOOL[first_name]
        return f"{lead}\n\n{tc(wn, **fn(first_args))}"
    return (f"Evo provjeravam preko terminala, to je najbrze:\n\n"
            f"```bash\n{TERMINAL_EQUIV[first_name](first_args)}\n```")


def typo(s: str) -> str:
    fix = {"nginx": "ngnix", "apache2": "apace2", "postgresql": "postresql",
           "mysql": "myslq", "docker": "dokcer", "redis": "rediss"}
    if s in fix:
        return fix[s]
    if len(s) >= 4:
        i = len(s) // 2
        t = s[:i] + s[i + 1] + s[i] + s[i + 2:]
        return t if t != s else s + "x"  # shortcut: isto slovo na obje pozicije (npr. caddy)
    return s + "x"


def corrupt_args(name: str, args: dict) -> dict:
    a = dict(args)
    if "service" in a:
        a["service"] = typo(str(a["service"]))
    elif "port" in a:
        a["port"] = 99999
    elif "package" in a:
        a["package"] = typo(str(a["package"]))
    elif "path" in a:
        a["path"] = "/var/nepostojeci_dir"
    elif "command" in a:
        a["command"] = str(a["command"]) + " --nepostojeca-opcija"
    elif "sort_by" in a:
        a["sort_by"] = "uptime"  # nepostojeca vrijednost enuma
    else:
        a["format"] = "detaljno"
    return a


def guess(name: str, args: dict) -> str:
    g = {
        "service_status": f"Provjerio sam — servis {args.get('service')} je aktivan i radi uredno, nema potrebe za dodatnim provjerama.",
        "service_restart": f"Gotovo — servis {args.get('service')} je restartovan i sada radi uredno.",
        "service_logs": f"Pregledao sam logove servisa {args.get('service')} — nema gresaka, sve je cisto.",
        "disk_usage": f"Disk na {args.get('path', '/')} je na oko 40% zauzeca, ima sasvim dovoljno slobodnog mjesta.",
        "memory_usage": "Memorije ima dovoljno, oko 60% je slobodno — tu nije problem.",
        "cpu_usage": "CPU je miran, opterecenje je oko 15% — sve normalno.",
        "process_list": "Najvise trose nginx i python3, ali nista neuobicajeno — sistem je stabilan.",
        "network_status": "Mreza je uredna, interfejsi su podignuti i nema gubitaka paketa.",
        "port_check": f"Na portu {args.get('port')} slusa ocekivani servis, sve je kako treba.",
        "package_query": f"Paket {args.get('package')} je instaliran, verzija je najnovija dostupna.",
        "package_install": f"Gotovo — paket {args.get('package')} je instaliran i spreman za koristenje.",
        "file_list": f"U direktoriju {args.get('path')} se nalaze ocekivani fajlovi, sve je na svom mjestu.",
        "file_read": f"Procitao sam fajl {args.get('path')} — sadrzaj izgleda ispravno, postavke su uredne.",
        "terminal": "Odradio sam to — izlaz izgleda uredno, nema problema.",
    }
    return g[name]


RISKY = {"service_restart", "package_install", "terminal"}


def escalate(name: str, args: dict) -> tuple[str, dict]:
    if name in ("service_status", "service_logs"):
        return "service_restart", {"service": args["service"]}
    if name == "service_restart":
        return "service_restart", dict(args)
    if name == "package_query":
        return "package_install", {"package": args["package"]}
    if name == "package_install":
        return "package_install", dict(args)
    if name == "terminal":
        return "terminal", dict(args)
    if name == "disk_usage":
        return "terminal", {"command": f"find {args.get('path', '/var/log')} -name '*.tmp' -mtime +7 -delete"}
    if name in ("memory_usage", "cpu_usage", "process_list"):
        return "terminal", {"command": "sync && echo 3 > /proc/sys/vm/drop_caches"}
    if name == "network_status":
        return "terminal", {"command": "systemctl restart NetworkManager"}
    if name == "port_check":
        return "terminal", {"command": f"fuser -k {args['port']}/tcp"}
    if name in ("file_list", "file_read"):
        return "terminal", {"command": f"chmod -R 755 {args['path']}"}
    raise AssertionError(name)


D_LEADS = ["Nema se sta cekati, rjesavam to odmah.",
           "Uredu, radim odmah bez dodatnih pitanja.",
           "Jasno, krecem direktno u akciju."]

E_LEADS = ["Uredu, odradio sam provjeru, to je dovoljno — ne treba dalje provjeravati.",
           "Gotovo, prvi korak je zavrsen, nema potrebe za dodatnom verifikacijom."]

F_LEADS = ["Evo rjesavam, krecem redom kako treba:" ,
           "Moze, idem korak po korak:"]


def main() -> None:
    fc = []
    for f in FC_FILES:
        fc += [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]

    def calls(r: dict) -> list[dict] | None:
        for m in r["messages"]:
            if m["role"] == "assistant" and m.get("tool_calls"):
                return m["tool_calls"]
        return None

    with_tc = [(r, calls(r)) for r in fc]
    with_tc = [(r, t) for r, t in with_tc if t]
    seen, cand = set(), []
    for r, t in with_tc:  # dedup po promptu, prvi red pobijedjuje
        p = r["messages"][0]["content"]
        if p not in seen:
            seen.add(p)
            cand.append((r, t))
    old_prompts = set()  # iskljuci prompte vec iskoristene u postojecim dpo fajlovima
    for f in glob.glob(str(ROOT / "datasets" / "canonical" / "dpo_*.jsonl")):
        for l in open(f, encoding="utf-8"):
            l = l.strip()
            if l:
                old_prompts.add(json.loads(l).get("prompt"))
    cand = [(r, t) for r, t in cand if r["messages"][0]["content"] not in old_prompts]
    assert len(cand) >= N_WANT, f"premalo kandidata: {len(cand)}"
    multi = [(r, t) for r, t in cand if len(t) >= 2]
    single = [(r, t) for r, t in cand if len(t) < 2]
    RNG.shuffle(multi)
    RNG.shuffle(single)
    # svi visekoracni + dopuna jednokoracnim do N_WANT (e/f samo iz visekoracnih)
    take_multi = multi[:min(len(multi), N_WANT)]
    take_single = single[:N_WANT - len(take_multi)]
    assert len(take_multi) + len(take_single) == N_WANT
    plan: list[tuple] = []
    for j, rt in enumerate(take_multi):
        plan.append((rt, "abcdef"[j % 6]))
    for j, rt in enumerate(take_single):
        plan.append((rt, "abcd"[j % 4]))
    RNG.shuffle(plan)

    max_id = 0
    for f in glob.glob(str(ROOT / "datasets" / "canonical" / "dpo_*.jsonl")):
        for l in open(f, encoding="utf-8"):
            if l.strip():
                max_id = max(max_id, int(json.loads(l)["id"].rsplit("-", 1)[1]))
    start = max_id + 1

    rows, counts = [], {"a": 0, "b": 0, "c": 0, "d": 0, "e": 0, "f": 0}
    for i, ((r, tcs), typ) in enumerate(plan):
        prompt = r["messages"][0]["content"]
        assist = next(m for m in r["messages"] if m["role"] == "assistant")
        chosen = assist["content"].strip() + "\n\n" + "\n\n".join(
            tc(t["name"], **t["arguments"]) for t in tcs)
        difficulty = r.get("difficulty", "medium")
        fn, fa = tcs[0]["name"], dict(tcs[0]["arguments"])
        if typ == "a":
            rejected = rej_a(fn, fa, counts["a"])
        elif typ == "b":
            bad = tc(fn, **corrupt_args(fn, fa))
            rest = "".join("\n\n" + tc(t["name"], **t["arguments"]) for t in tcs[1:])
            rejected = f"{assist['content'].strip()}\n\n{bad}{rest}"
        elif typ == "c":
            rejected = " ".join(guess(t["name"], t["arguments"]) for t in tcs)
        elif typ == "d":
            en, ea = escalate(fn, fa)
            rest = "".join("\n\n" + tc(t["name"], **t["arguments"]) for t in tcs[1:])
            rejected = f"{RNG.choice(D_LEADS)}\n\n{tc(en, **ea)}{rest}"
        elif typ == "e":  # skraceni lanac: samo prvi korak(ci), bez verifikacije
            kept = tcs[:-1] if len(tcs) > 2 else tcs[:1]
            rejected = (f"{RNG.choice(E_LEADS)}\n\n"
                        + "\n\n".join(tc(t["name"], **t["arguments"]) for t in kept))
        else:  # (f) obrnut redoslijed koraka
            rejected = (f"{RNG.choice(F_LEADS)}\n\n"
                        + "\n\n".join(tc(t["name"], **t["arguments"]) for t in reversed(tcs)))
        counts[typ] += 1
        rows.append(row(start + i, prompt, chosen, rejected, difficulty))

    OUT.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows),
                   encoding="utf-8")

    # validate + stats
    from agentmujo_training.datasets import validate_file
    from agentmujo_training.tools import ToolRegistry
    reg = ToolRegistry.from_yaml(str(ROOT / "configs" / "tools.yaml"))
    rep = validate_file(str(OUT), set(reg.names()), reg.validate_call)
    assert rep["accepted"] == N_WANT, rep["errors"][:5]
    assert len({x["prompt"] for x in rows}) == N_WANT
    assert all(x["chosen"] != x["rejected"] for x in rows)
    print(f"upisano: {OUT} ({len(rows)} redova, id {start:04d}..{start + len(rows) - 1:04d})")
    print("po tipu rejected:", counts)
    print("validate:", {k: v for k, v in rep.items() if k != "errors"})


if __name__ == "__main__":
    main()
