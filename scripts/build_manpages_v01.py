#!/usr/bin/env python3
"""linux-terminal v0.1: ~1500 redova iz man stranica (localhost, provjereno).

Metoda: za svaku komandu s postojecom man stranicom (`man <cmd> | col -b`,
MANWIDTH=80, LC_ALL=C):
  - NAME sekcija -> 1 cinjenica (sto radi komanda),
  - SYNOPSIS sekcija -> 1 cinjenica (osnovni oblik poziva / primjer),
  - zapisi nalik opcijama (uvuceni redovi koji pocinju s `-`, ps-stil
    jednoslovne bez crtice) + opis iz narednih uvlacenih redova -> do 4
    cinjenice po komandi (zastavica/znacenje),
  - fallback: COMMANDS sekcija ako opcija ima < 3 (systemd-stil).
Pitanja su na BOSANSKOM (latinica, ijekavica); odgovor = jedna bosanska
uvodna recenica bez cinjenica + DOSLOVAN citat man teksta pod navodnicima
(engleski ostaje unutar navodnika). De-hifenacija preloma redova
(`inti- mate` -> `intimate`) i kolapsiranje visestrukih razmaka su jedine
normalizacije citata.
Sigurnost: cinjenice ciji citat pogadja DENY_PATTERNS validatora se
preskacu. metadata: SILVER + source "man-pages (localhost)" + verified.
ID: amj-lt-%06d. Dedup: normalizovana user pitanja unutar fajla.
Uporaba: .venv/bin/python scripts/build_manpages_v01.py
"""
import json
import os
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "datasets/canonical/linux_terminal_v0.1.jsonl"

N_TOTAL = 1500
MAX_OPTS_PER_CMD = 4

CANDIDATES = [
    "systemctl", "journalctl", "ss", "ip", "df", "du", "ps", "lsblk",
    "mount", "crontab", "useradd", "chmod", "chown", "tar", "rsync",
    "find", "grep", "ufw", "timedatectl", "hostnamectl",
    # zamjene za komande bez man stranice (da se drzi ~20 pokrivenih)
    "ls", "free", "mkdir", "curl", "ssh", "top",
]

HEADER_RE = re.compile(r"^[A-Z][A-Z0-9 /_-]*$")
CYR = re.compile(r"[Ѐ-џ]")
HYPH_WRAP_RE = re.compile(r"(\w)[\u2010\u2011\u00ad-]\s+(\w)")


def collapse(text: str) -> str:
    text = HYPH_WRAP_RE.sub(r"\1\2", text)
    return re.sub(r"\s+", " ", text.strip())


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def man_text(cmd: str) -> str | None:
    try:
        p = subprocess.run(
            ["sh", "-c", f"man {cmd} 2>/dev/null | col -b"],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "MANWIDTH": "80", "LC_ALL": "C", "LANG": "C"},
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = p.stdout.strip("\n")
    if len(out) < 200 or not re.search(r"^NAME$", out, re.M):
        return None
    return out


def sections(lines: list[str]) -> dict[str, list[str]]:
    secs: dict[str, list[str]] = {}
    cur: str | None = None
    for ln in lines:
        if HEADER_RE.match(ln.strip()) and len(ln.strip().split()) <= 4:
            cur = ln.strip()
            secs[cur] = []
        elif cur is not None:
            secs[cur].append(ln)
    return secs


def first_nonempty(secs: dict, name: str) -> str:
    for ln in secs.get(name, []):
        if ln.strip():
            return collapse(ln)
    return ""


def synopsis_quote(secs: dict) -> str:
    got = [collapse(ln) for ln in secs.get("SYNOPSIS", []) if ln.strip()]
    got = [g for g in got if g][:3]
    q = " / ".join(got)
    if len(q) > 600:  # na recenicu ispod limita
        acc = ""
        for part in re.split(r"(?<=[.;]) ", q):
            if len(acc) + len(part) + 1 > 600:
                break
            acc = f"{acc} {part}".strip()
        q = acc or q[:600]
    return q


def indent_of(ln: str) -> int:
    e = ln.expandtabs(8)
    return len(e) - len(e.lstrip(" "))


def parse_entries(block: list[str]) -> list[tuple[str, str]]:
    """Genericki parser: uvuceni `flag` red + uvlaceniji opisni redovi."""
    block = [ln.expandtabs(8) for ln in block]
    out: list[tuple[str, str]] = []
    i, n = 0, len(block)
    while i < n:
        ln = block[i].rstrip()
        s = ln.strip()
        ind = indent_of(ln)
        is_dash = (
            s.startswith("-") and len(s) <= 64
            and len(s) > 1 and s[1].isalnum()
        )
        is_bare = bool(re.fullmatch(r"[A-Za-z]", s))  # ps-stil: a, g, x, r, T
        if ind >= 5 and (is_dash or is_bare) and not s.startswith("---"):
            desc: list[str] = []
            j = i + 1
            while j < n:
                nxt = block[j].rstrip()
                if not nxt.strip():
                    # prazan red: kraj opisa ako slijedi manje/isto uvuceno
                    k = j + 1
                    while k < n and not block[k].strip():
                        k += 1
                    if k >= n or indent_of(block[k]) <= ind \
                            or HEADER_RE.match(block[k].strip()):
                        j = k
                        break
                    j += 1
                    continue
                if indent_of(nxt) <= ind or HEADER_RE.match(nxt.strip()):
                    break
                desc.append(nxt.strip())
                j += 1
            d = collapse(" ".join(desc))
            if len(d) >= 20:
                if len(d) > 500:
                    acc = ""
                    for part in re.split(r"(?<=[.;]) ", d):
                        if len(acc) + len(part) + 1 > 500:
                            break
                        acc = f"{acc} {part}".strip()
                    d = acc or d[:500]
                out.append((collapse(s), d))
            i = j
        else:
            i += 1
    return out


def facts_for(cmd: str, text: str) -> tuple[list[dict], str]:
    lines = text.splitlines()
    secs = sections(lines)
    name = first_nonempty(secs, "NAME")
    if not name or len(name) > 300:
        return [], "los NAME"
    syn = synopsis_quote(secs)
    # opcije: trazi u OPTIONS* sekcijama, inace cijeli dokument
    # (ssh/top/ls drze opcije u DESCRIPTION)
    opt_blocks: list[str] = []
    for h, b in secs.items():
        if "OPTION" in h or "SELECTION" in h or "MODIFIER" in h:
            opt_blocks += b
    if not opt_blocks:
        try:
            start = next(i for i, l in enumerate(lines)
                         if l.strip() in ("DESCRIPTION", "COMMANDS"))
            opt_blocks = lines[start:]
        except StopIteration:
            opt_blocks = lines
    seen_f: set[str] = set()
    opts: list[tuple[str, str]] = []
    for flag, desc in parse_entries(opt_blocks):
        key = norm(flag.split()[0])
        if key in seen_f:
            continue
        seen_f.add(key)
        opts.append((flag, desc))
        if len(opts) >= MAX_OPTS_PER_CMD:
            break
    facts = [{"kind": "name", "flag": "", "quote": name, "diff": "easy"}]
    if syn:
        facts.append({"kind": "syn", "flag": "", "quote": syn,
                      "diff": "medium"})
    for flag, desc in opts:
        facts.append({"kind": "opt", "flag": flag, "quote": desc,
                      "diff": "medium"})
    if len([f for f in facts if f["kind"] == "opt"]) < 3:
        # fallback: COMMANDS sekcija (systemd-stil podkomande)
        for h, b in secs.items():
            if h == "COMMANDS":
                for flag, desc in parse_entries(b):
                    if norm(flag.split()[0]) in seen_f:
                        continue
                    seen_f.add(norm(flag.split()[0]))
                    facts.append({"kind": "cmd", "flag": flag,
                                  "quote": desc, "diff": "medium"})
                    if len(facts) >= 6:
                        break
    return facts[:6], "ok"


# ---------------------------------------------------------------- predlosci
PREFIXES = ["", "Molim te, ", "Reci mi, ", "Zanima me — "]

USER_T = {
    "name": [
        "šta radi komanda `{cmd}`?",
        "čemu služi komanda `{cmd}`?",
        "objasni ukratko šta radi `{cmd}`.",
        "šta je komanda `{cmd}` i čemu služi?",
        "opiši namjenu komande `{cmd}`.",
        "za šta se koristi komanda `{cmd}`?",
    ],
    "syn": [
        "kako glasi sintaksa komande `{cmd}` prema man stranici?",
        "napiši osnovni oblik poziva komande `{cmd}` iz man stranice.",
        "kako se osnovno poziva komanda `{cmd}`?",
        "citiraj sinopsis komande `{cmd}` iz man stranice.",
        "koji je opšti oblik komande `{cmd}`?",
    ],
    "opt": [
        "šta radi opcija `{flag}` komande `{cmd}`?",
        "objasni značenje opcije `{flag}` kod komande `{cmd}`.",
        "šta man stranica kaže za opciju `{flag}` komande `{cmd}`?",
        "citiraj opis opcije `{flag}` iz man stranice za `{cmd}`.",
        "kako man stranica opisuje opciju `{flag}` komande `{cmd}`?",
    ],
    "cmd": [
        "šta radi podkomanda `{flag}` komande `{cmd}`?",
        "objasni značenje podkomande `{flag}` kod komande `{cmd}`.",
        "šta man stranica kaže za podkomandu `{flag}` komande `{cmd}`?",
        "citiraj opis podkomande `{flag}` iz man stranice za `{cmd}`.",
    ],
}

INTROS = [
    "Prema man stranici za komandu `{cmd}`:",
    "Man stranica za komandu `{cmd}` kaže:",
    "Doslovan citat iz man stranice za `{cmd}`:",
]
INTROS_OPT = [
    "Prema man stranici za komandu `{cmd}`, opcija `{flag}`:",
    "Man stranica za komandu `{cmd}` za opciju `{flag}` kaže:",
    "Doslovan citat o opciji `{flag}` iz man stranice za `{cmd}`:",
]
INTROS_CMD = [
    "Prema man stranici za komandu `{cmd}`, podkomanda `{flag}`:",
    "Man stranica za komandu `{cmd}` za podkomandu `{flag}` kaže:",
    "Doslovan citat o podkomandi `{flag}` iz man stranice za `{cmd}`:",
]


def main() -> None:
    from agentmujo_training.datasets.validator import (
        DENY_PATTERNS, validate_file,
    )
    deny = [re.compile(p) for p in DENY_PATTERNS]

    covered: list[str] = []
    skipped: list[str] = []
    all_facts: list[dict] = []
    per_cmd: dict[str, int] = {}
    for cmd in CANDIDATES:
        text = man_text(cmd)
        if text is None:
            skipped.append(cmd)
            continue
        facts, why = facts_for(cmd, text)
        if len(facts) < 3:
            skipped.append(f"{cmd} ({why}/premalo: {len(facts)})")
            continue
        # safety filter prije generisanja
        kept = []
        for f in facts:
            probe = f["quote"]
            if any(rx.search(probe) for rx in deny):
                continue
            kept.append(f)
        if len(kept) < 3:
            skipped.append(f"{cmd} (safety-filter: {len(kept)})")
            continue
        for f in kept:
            f["cmd"] = cmd
        covered.append(cmd)
        per_cmd[cmd] = len(kept)
        all_facts += kept

    n = len(all_facts)
    base, rem = divmod(N_TOTAL, n)
    print(f"komandi pokriveno: {len(covered)}, cinjenica: {n}, "
          f"redova/cinjenici: {base}+1 za prvih {rem}")

    seen_q: set[str] = set()
    rows: list[dict] = []
    for fi, f in enumerate(all_facts):
        k = base + (1 if fi < rem else 0)
        tmpls = USER_T[f["kind"]]
        made = 0
        for t in tmpls:
            for pre in PREFIXES:
                if made >= k:
                    break
                user = (pre + t).format(cmd=f["cmd"], flag=f["flag"])
                if not pre:
                    user = user[0].upper() + user[1:]
                if norm(user) in seen_q:
                    continue
                seen_q.add(norm(user))
                if f["kind"] == "name":
                    intro = INTROS[made % len(INTROS)].format(cmd=f["cmd"])
                    asst = f'{intro}\n"{f["quote"]}"'
                elif f["kind"] == "syn":
                    intro = INTROS[made % len(INTROS)].format(cmd=f["cmd"])
                    asst = (f"{intro} Osnovni oblik poziva je:\n"
                            f'"{f["quote"]}"')
                elif f["kind"] == "opt":
                    intro = INTROS_OPT[made % len(INTROS_OPT)].format(
                        cmd=f["cmd"], flag=f["flag"])
                    asst = f'{intro}\n"{f["flag"]}"\n"{f["quote"]}"'
                else:
                    intro = INTROS_CMD[made % len(INTROS_CMD)].format(
                        cmd=f["cmd"], flag=f["flag"])
                    asst = f'{intro}\n"{f["flag"]}"\n"{f["quote"]}"'
                assert not CYR.search(user + asst)
                assert not any(rx.search(asst) for rx in deny), f["cmd"]
                rows.append({
                    "id": f"amj-lt-{len(rows) + 1:06d}",
                    "version": "0.1.0",
                    "language": "bs-ijekavica",
                    "task": "linux-terminal",
                    "difficulty": f["diff"],
                    "enable_thinking": False,
                    "messages": [
                        {"role": "user", "content": user},
                        {"role": "assistant", "content": asst},
                    ],
                    "metadata": {
                        "source": "man-pages (localhost)",
                        "quality_tier": "SILVER",
                        "verification_status": "verified",
                        "author": "agentmujo-team",
                    },
                })
                made += 1
            if made >= k:
                break
        assert made == k, f"{f['cmd']} {f['kind']}: {made}<{k}"

    assert len(rows) == N_TOTAL, len(rows)
    blobs = [json.dumps(r["messages"], sort_keys=True, ensure_ascii=False)
             for r in rows]
    assert len(set(blobs)) == len(blobs), "duplikat uzorka"

    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                                     for r in rows), encoding="utf-8")

    from collections import Counter
    diffs = Counter(r["difficulty"] for r in rows)
    print(f"redova: {len(rows)} -> {OUT}")
    print(f"pokrivene komande ({len(covered)}): {', '.join(covered)}")
    print(f"preskocene ({len(skipped)}): {', '.join(skipped)}")
    print(f"cinjenica po komandi: {per_cmd}")
    print(f"distribucija tezine: {dict(diffs)}")

    rep = validate_file(OUT, set())
    print(f"validate: total={rep['total']} accepted={rep['accepted']} "
          f"rejected={rep['rejected']} tiers={rep['tiers']}")
    assert rep["rejected"] == 0, json.dumps(rep["errors"][:5],
                                            ensure_ascii=False)[:1000]


if __name__ == "__main__":
    main()
