"""Build datasets/canonical/dpo_v0.9.jsonl — ~1500 DPO parova iz agentic tragova.

Metoda: iz svakog agentic scenarija (terminal v0.1..v0.4) sa >=3 tool koraka:
  prompt = prvi user problem,
  chosen = originalni dobar trag (vjeran: svi tool pozivi + rezultati + zakljucak,
           skracen: viseturna konverzacija svedena na jednu assistant poruku),
  rejected = programska mutacija, 4 tipa rotirana ravnomjerno:
    (a) preskocena dijagnostika (odmah zadnja akcija, bez provjera),
    (b) ignorisan tool rezultat (prvi rezultat + nastavak po starom planu),
    (c) destruktivna akcija bez potvrde usred lanca,
    (d) odustajanje na prvom neuspjehu ("ne mogu pomoci").
ID: nastavak na max amj-dpo-* (dinamicki). metadata: SILVER/dpo-agentic-derived-v0.9/verified.
Deterministicki (seed 909). Ne dira postojece fajlove ni splits/.
"""

from __future__ import annotations

import glob
import json
import random
from pathlib import Path

RNG = random.Random(909)
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "datasets" / "canonical" / "dpo_v0.9.jsonl"
VERSION = "0.9.0"
N_WANT = 1500

AG_FILES = [ROOT / "datasets" / "canonical" / f"agentic_terminal_v0.{i}.jsonl"
            for i in (1, 2, 3, 4)]


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
        "metadata": {"source": "dpo-agentic-derived-v0.9", "quality_tier": "SILVER",
                     "verification_status": "verified"},
    }


def steps_of(r: dict) -> tuple[list[tuple[str, list[dict], list[str]]], str]:
    """(koraci, zakljucak): korak = (tekst, tool_calls, tool_rezultati)."""
    steps, i, msgs = [], 0, r["messages"]
    while i < len(msgs):
        m = msgs[i]
        if m["role"] == "assistant" and m.get("tool_calls"):
            res = []
            j = i + 1
            while j < len(msgs) and msgs[j]["role"] == "tool":
                res.append(str(msgs[j].get("content", "")))
                j += 1
            steps.append((m.get("content", "").strip(), m["tool_calls"], res))
            i = j
        else:
            i += 1
    tail = next((m.get("content", "").strip() for m in reversed(msgs)
                 if m["role"] == "assistant" and not m.get("tool_calls")), "")
    return steps, tail


def short(s: str, n: int = 300) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[:n] + "..."


def chosen_of(steps: list, tail: str) -> str:
    parts = []
    for text, tcs, res in steps:
        parts.append(text + "\n\n" + "\n\n".join(tc(t["name"], **t["arguments"]) for t in tcs))
        parts += [f"Rezultat: {short(x)}" for x in res]
    if tail:
        parts.append(tail)
    return "\n\n".join(p for p in parts if p)


def destructive_for(steps: list) -> tuple[str, dict]:
    for _, tcs, _ in steps:
        for t in tcs:
            a = t["arguments"]
            if "service" in a:
                return "service_restart", {"service": a["service"]}
            if "package" in a:
                return "package_install", {"package": a["package"]}
            if "port" in a:
                return "terminal", {"command": f"fuser -k {a['port']}/tcp"}
            if "path" in a:
                return "terminal", {"command": f"chmod -R 777 {a['path']}"}
    return "service_restart", {"service": "nginx"}  # shortcut: agentic tragovi uvijek imaju cilj; fallback se ne ocekuje


A_LEADS = ["Nema se sta provjeravati, idem odmah na rjesenje:",
           "Ne gubim vrijeme na dijagnostiku, radim direktno:"]
B_LEADS = ["Ne obazirem se na rezultat, nastavljam po starom planu:",
           "Rezultat me ne zanima previse, idem dalje kako sam naumio:"]
C_LEADS = ["Ne cekam potvrdu, radim odmah usred provjere:",
           "Nema pitanja, cistim/restartujem odmah:"]
D_TAILS = ["Prvi korak nije dao idealan rezultat pa odustajem. Ne mogu pomoci s ovim, potrazi nekog drugog.",
           "Zapelo je na prvom koraku i ne vidim dalje. Ne mogu pomoci — morat ces sam."]


def rejected_of(typ: str, steps: list) -> str:
    first_text, first_tcs, first_res = steps[0]
    last_tcs = steps[-1][1]
    res_echo = f"\n\nRezultat: {short(first_res[0])}" if first_res else ""
    if typ == "a":  # preskocena dijagnostika: samo zadnja akcija
        return (f"{RNG.choice(A_LEADS)}\n\n"
                + "\n\n".join(tc(t["name"], **t["arguments"]) for t in last_tcs)
                + "\n\nGotovo, to je to.")
    if typ == "b":  # ignorisan rezultat: prvi poziv + rezultat, pa stari plan bez prilagodbe
        return (f"{first_text}\n\n{tc(first_tcs[0]['name'], **first_tcs[0]['arguments'])}"
                f"{res_echo}\n\n{RNG.choice(B_LEADS)}\n\n"
                + "\n\n".join(tc(t["name"], **t["arguments"]) for t in last_tcs)
                + "\n\nGotovo, rijeseno bez dalje provjere.")
    if typ == "c":  # destruktivno bez potvrde usred lanca
        dn, da = destructive_for(steps)
        return (f"{first_text}\n\n{tc(first_tcs[0]['name'], **first_tcs[0]['arguments'])}"
                f"{res_echo}\n\n{RNG.choice(C_LEADS)}\n\n{tc(dn, **da)}")
    # (d) odustajanje na prvom neuspjehu
    return (f"{first_text}\n\n{tc(first_tcs[0]['name'], **first_tcs[0]['arguments'])}"
            f"{res_echo}\n\n{RNG.choice(D_TAILS)}")


def main() -> None:
    pool = []
    for f in AG_FILES:
        pool += [(json.loads(l), f.name) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    cand = []
    for r, src in pool:
        steps, _ = steps_of(r)
        if sum(len(t) for _, t, _ in steps) >= 3:
            cand.append((r, src, steps))
    seen, uniq = set(), []
    for r, src, steps in cand:  # dedup po promptu, prvi red pobijedjuje
        p = r["messages"][0]["content"]
        if p not in seen:
            seen.add(p)
            uniq.append((r, src, steps))
    old_prompts = set()
    for f in glob.glob(str(ROOT / "datasets" / "canonical" / "dpo_*.jsonl")):
        for l in open(f, encoding="utf-8"):
            if l.strip():
                old_prompts.add(json.loads(l).get("prompt"))
    uniq = [(r, s, st) for r, s, st in uniq if r["messages"][0]["content"] not in old_prompts]
    assert len(uniq) >= N_WANT, f"premalo kandidata: {len(uniq)}"
    RNG.shuffle(uniq)
    plan = [(uniq[i], "abcd"[i % 4]) for i in range(N_WANT)]  # tocno 375 po tipu
    RNG.shuffle(plan)

    max_id = 0
    for f in glob.glob(str(ROOT / "datasets" / "canonical" / "dpo_*.jsonl")):
        for l in open(f, encoding="utf-8"):
            if l.strip():
                max_id = max(max_id, int(json.loads(l)["id"].rsplit("-", 1)[1]))
    start = max_id + 1

    rows, counts, srcs = [], {"a": 0, "b": 0, "c": 0, "d": 0}, {}
    for (r, src, steps), typ in plan:
        prompt = r["messages"][0]["content"]
        _, tail = steps_of(r)
        rows.append(row(start + len(rows), prompt, chosen_of(steps, tail),
                        rejected_of(typ, steps), r.get("difficulty", "medium")))
        counts[typ] += 1
        srcs[src] = srcs.get(src, 0) + 1

    OUT.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows),
                   encoding="utf-8")

    from agentmujo_training.datasets import validate_file
    from agentmujo_training.tools import ToolRegistry
    reg = ToolRegistry.from_yaml(str(ROOT / "configs" / "tools.yaml"))
    rep = validate_file(str(OUT), set(reg.names()), reg.validate_call)
    assert rep["accepted"] == N_WANT, rep["errors"][:5]
    assert len({x["prompt"] for x in rows}) == N_WANT
    assert all(x["chosen"] != x["rejected"] for x in rows)
    print(f"upisano: {OUT} ({len(rows)} redova, id {start:04d}..{start + len(rows) - 1:04d})")
    print("po tipu rejected:", counts)
    print("po izvoru:", srcs)
    print("validate:", {k: v for k, v in rep.items() if k != "errors"})


if __name__ == "__main__":
    main()
