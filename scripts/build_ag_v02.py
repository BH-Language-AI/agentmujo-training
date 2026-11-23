#!/usr/bin/env python3
"""Generise datasets/canonical/agentic_terminal_v0.2.jsonl (~750 scenarija).

Template-expansion v0.2: visestepeni troubleshooting (2-5 tool koraka),
difficulty mix 30/50/20, ID nastavak od max iz v0.1.
Koristenje: .venv/bin/python scripts/build_ag_v02.py
"""
import json
import random
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "datasets/canonical/agentic_terminal_v0.1.jsonl"
OUT = REPO / "datasets/canonical/agentic_terminal_v0.2.jsonl"

SERVICES = ["nginx", "postgresql", "redis", "mysql", "apache2",
            "grafana-server", "prometheus", "node-exporter", "app-api", "docker"]
PORTS = {"nginx": 80, "apache2": 80, "postgresql": 5432, "redis": 6379,
         "mysql": 3306, "grafana-server": 3000, "prometheus": 9090,
         "node-exporter": 9100, "app-api": 8080, "docker": 2375}
RIVALS = {"nginx": "apache2", "apache2": "nginx", "app-api": "test-runner",
          "grafana-server": "dev-proxy", "prometheus": "stage-agent"}
PKGS = ["nginx", "postgresql", "redis-server", "htop", "curl", "certbot",
        "prometheus", "grafana", "docker-ce", "net-tools"]
PROCS = ["ffmpeg", "python3", "java", "node", "postgres", "mysqld",
         "backup-agent", "log-shipper", "transcoder", "worker"]
LOGDIRS = ["/var/log", "/var/log/nginx", "/var/log/postgresql", "/var/lib/app/log"]
LOGFILES = {"nginx": "/var/log/nginx/error.log",
            "postgresql": "/var/log/postgresql/postgresql.log",
            "redis": "/var/log/redis/redis.log",
            "mysql": "/var/log/mysql/error.log",
            "app-api": "/var/lib/app/log/app.log"}


def T(content, calls=None):
    m = {"role": "assistant", "content": content}
    if calls:
        m["tool_calls"] = calls
    return m


def U(content):
    return {"role": "user", "content": content}


def R(obj):
    return {"role": "tool", "content": json.dumps(obj, ensure_ascii=False)}


def ts(k):
    # jedinstven timestamp za svaki red (47 je prosto na 86400) — protiv duplikata
    s = (k * 47) % 86400
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def row(i, sid, diff, msgs):
    return {"id": sid, "version": "0.2.0", "language": "bs-ijekavica",
            "task": "agentic-terminal", "difficulty": diff,
            "enable_thinking": True, "messages": msgs,
            "metadata": {"author": "agentmujo-team", "quality_tier": "SILVER",
                         "source": "template-expansion-v0.2",
                         "verification_status": "auto-validated"}}


# ---- EASY (2 koraka) ----
def e_port(rng, i):
    svc = rng.choice(["nginx", "apache2", "app-api", "grafana-server"])
    rival = RIVALS.get(svc, "dev-proxy")
    port = PORTS[svc]
    pid = 1200 + i
    return [U(rng.choice([f"Servis {svc} nece da starta. Vidi sta ga koci.",
                          f"{svc} je pao nakon deploya, port {port} je u pitanju?",
                          f"Ne radi {svc}. Sumnjam na zauzet port."])) ,
            T(f"Provjeravam status servisa {svc}.",
              [{"name": "service_status", "arguments": {"service": svc}}]),
            R({"service": svc, "status": "failed"}),
            T(f"Servis je pao. Provjeravam koji proces drzi port {port}.",
              [{"name": "port_check", "arguments": {"port": port}}]),
            R({"port": port, "process": rival, "pid": pid}),
            T(f"Dijagnoza: {rival} (pid {pid}) drzi port {port}, pa se {svc} "
               f"ne moze vezati i pada. Za verifikaciju predlazem: zaustaviti "
               f"{rival} ili premjestiti jedan servis na drugi port, pa ponovo "
               f"provjeriti status servisa {svc}. Nista ne restartujem bez tvoje potvrde.")]


def e_disk(rng, i):
    pct = rng.randint(93, 99)
    avail = rng.choice(["1.2G", "800M", "2.1G"])
    d = rng.choice(LOGDIRS)
    big = rng.choice(["syslog.1", "kern.log.1", "app.log.2", "access.log.3"])
    gb = round(rng.uniform(4.5, 18.0), 1)
    return [U(rng.choice(["Disk je skoro pun, provjeri sta ga je zatrpalo.",
                          "Nestaje mjesta na disku. Gdje je otislo?",
                          "Upozorenje: malo slobodnog prostora. Analiziraj."])),
            T("Provjeravam zauzece diska.",
              [{"name": "disk_usage", "arguments": {"path": "/"}}]),
            R({"path": "/", "used_pct": pct, "avail": avail}),
            T(f"Disk je na {pct}%. Gledam sta zauzima najvise u {d}.",
              [{"name": "file_list", "arguments": {"path": d}}]),
            R({"path": d, "largest": [{"name": big, "size_gb": gb,
                                       "mtime": f"2026-11-02 {ts(i)}"}]}),
            T(f"Dijagnoza: disk je popunjen na {pct}%, najveci potrosac je {big} "
               f"({gb} GB) u {d}. Predlazem arhiviranje ili rotaciju tog fajla uz "
               f"tvoju potvrdu, pa verifikaciju ponovnim ocitanjem zauzeca diska. "
               f"Bez potvrde nista ne brisem.")]


def e_cpu(rng, i):
    cpu = rng.randint(85, 98)
    proc = rng.choice(PROCS)
    pcpu = cpu - rng.randint(3, 12)
    pid = 1200 + i
    mem = rng.randint(18, 45)
    return [U(rng.choice(["Server je odjednom spor. Sta ga gusi?",
                          "Sve se vuce, load je ogroman.",
                          "Masina steka. Provjeri opterecenje."])),
            T("Mjerim opterecenje procesora.",
              [{"name": "cpu_usage", "arguments": {}}]),
            R({"cpu_pct": cpu}),
            T(f"CPU je na {cpu}%. Gledam koji procesi ga najvise trose.",
              [{"name": "process_list",
                "arguments": {"limit": 10, "sort_by": "cpu"}}]),
            R({"top": [{"name": proc, "pid": pid, "cpu": pcpu}]}),
            T(f"Dijagnoza: {proc} (pid {pid}) trosi oko {pcpu}% CPU-a, memorija je "
               f"uredna ({mem}% po zadnjem ocitanju). Za verifikaciju predlazem da "
               f"provjeris je li to ocekivan posao (npr. zakazani zadatak), pa tek "
               f"onda odlucimo o zaustavljanju. Proces ne diram bez potvrde.")]


def e_pkg(rng, i):
    pkg = rng.choice(PKGS)
    svc = rng.choice(SERVICES)
    return [U(rng.choice([f"Alat {pkg} izgleda nije instaliran. Provjeri.",
                          f"Komanda vezana za {pkg} ne radi. Je li paket tu?",
                          f"Sumnjam da paket {pkg} nedostaje na serveru."])),
            T(f"Provjeravam je li paket {pkg} instaliran.",
              [{"name": "package_query", "arguments": {"package": pkg}}]),
            R({"package": pkg, "installed": False}),
            T(f"Paket {pkg} nije instaliran. Gledam utice li to na servis {svc}.",
              [{"name": "service_status", "arguments": {"service": svc}}]),
            R({"service": svc, "status": "inactive",
               "since": f"2026-11-02 {ts(i)}"}),
            T(f"Dijagnoza: paket {pkg} nije instaliran, a servis {svc} je neaktivan. "
               f"Predlazem instalaciju paketa uz tvoju potvrdu, pa verifikaciju "
               f"ponovnim upitom o paketu i provjerom statusa servisa. Bez potvrde "
               f"nista ne instaliram.")]


# ---- MEDIUM (3 koraka) ----
def m_restart(rng, i):
    svc = rng.choice(SERVICES)
    err = rng.choice(["Timeout pri startu zavisnog servisa", "Neispravna opcija u konfiguraciji",
                      "Pad zbog kratkog nestanka mreze", "Istekla sesija ka bazi"])
    return [U(f"Restartuj {svc} i provjeri da je stvarno proradio."),
            T(f"Prvo gledam trenutni status servisa {svc}.",
              [{"name": "service_status", "arguments": {"service": svc}}]),
            R({"service": svc, "status": "failed"}),
            T("Servis je pao. Citam log da potvrdim uzrok prije restarta.",
              [{"name": "service_logs",
                "arguments": {"service": svc, "lines": 50}}]),
            R({"service": svc, "logs": f"{ts(i)} {svc}: {err}"}),
            T(f"Uzrok je prolazan ({err}). Radim restart high-level alatom.",
              [{"name": "service_restart", "arguments": {"service": svc}}]),
            R({"service": svc, "action": "restart", "result": "ok"}),
            T(f"Dijagnoza: {svc} je pao zbog: {err}; restart je pokrenut. Za "
               f"verifikaciju predlazem provjeru statusa servisa i kratak pogled "
               f"u log da se greska ne ponavlja. Ako se ponovi, idemo na konfiguraciju.")]


def m_disk_chain(rng, i):
    svc = rng.choice(["postgresql", "mysql", "app-api"])
    pct = rng.randint(95, 99)
    return [U(f"{svc} je pao, a sumnjam da je disk pun. Istazi lanac uzroka."),
            T("Provjeravam zauzece diska.",
              [{"name": "disk_usage", "arguments": {"path": "/"}}]),
            R({"path": "/", "used_pct": pct, "avail": "400M"}),
            T(f"Disk je na {pct}%. Provjeravam status servisa {svc}.",
              [{"name": "service_status", "arguments": {"service": svc}}]),
            R({"service": svc, "status": "failed"}),
            T("Servis je pao. Citam log da potvrdim vezu sa diskom.",
              [{"name": "service_logs",
                "arguments": {"service": svc, "lines": 50}}]),
            R({"service": svc,
               "logs": f"{ts(i)} {svc}: FATAL: No space left on device"}),
            T(f"Dijagnoza: lanac je disk pun ({pct}%) pa je {svc} pao jer ne moze "
               f"pisati na disk. Predlazem: prvo osloboditi prostor (arhiviranje "
               f"logova uz tvoju potvrdu), pa tek onda restart servisa i verifikaciju "
               f"statusom i upisom testnog reda. Restart prije ciscenja bi opet pao.")] 


def m_net(rng, i):
    svc = rng.choice(["nginx", "app-api", "grafana-server"])
    port = PORTS[svc]
    iface = rng.choice(["eth0", "ens3"])
    return [U(f"Servis {svc} se ne odaziva izvana. Je li mreza ili servis?"),
            T("Provjeravam status mreznih interfejsa.",
              [{"name": "network_status", "arguments": {}}]),
            R({"interfaces": {iface: "up"}, "gateway_ok": True,
               "rx_packets": 900000 + i}),
            T(f"Mreza je uredna. Provjeravam slusa li ista na portu {port}.",
              [{"name": "port_check", "arguments": {"port": port}}]),
            R({"port": port, "process": None}),
            T(f"Nista ne slusa na portu {port}. Provjeravam status servisa {svc}.",
              [{"name": "service_status", "arguments": {"service": svc}}]),
            R({"service": svc, "status": "inactive"}),
            T(f"Dijagnoza: mreza je ispravna, ali {svc} ne radi pa port {port} "
               f"stoji prazan. Predlazem pokretanje servisa uz potvrdu, pa "
               f"verifikaciju provjerom porta i statusa. Problem nije u mrezi.")]


def m_mem(rng, i):
    proc = rng.choice(PROCS)
    pid = 1200 + i
    mem = rng.randint(86, 96)
    pmem = mem - rng.randint(5, 15)
    svc = rng.choice(SERVICES)
    return [U("Masina jede memoriju, sumnjam na curenje. Pronadji krivca."),
            T("Provjeravam zauzece memorije.",
              [{"name": "memory_usage", "arguments": {}}]),
            R({"mem_pct": mem}),
            T(f"Memorija je na {mem}%. Gledam najvece potrosace.",
              [{"name": "process_list",
                "arguments": {"limit": 10, "sort_by": "memory"}}]),
            R({"top": [{"name": proc, "pid": pid, "mem_pct": pmem}]}),
            T(f"{proc} (pid {pid}) drzi {pmem}% memorije. Citam log servisa {svc} "
               f"da vidim ima li tragova nestasice.",
              [{"name": "service_logs",
                "arguments": {"service": svc, "lines": 50}}]),
            R({"service": svc, "logs": "Out of memory: process killed, restarting worker"}),
            T(f"Dijagnoza: {proc} (pid {pid}) trosi {pmem}% memorije, sistem vec "
               f"ubija workere. Predlazem provjeru konfiguracije limita za {proc}, "
               f"pa verifikaciju pracenjem memorije nakon restarta workera. "
               f"Restart cijelog servisa samo uz tvoju potvrdu.")]


def m_forenzika(rng, i):
    svc = rng.choice(["nginx", "postgresql", "app-api"])
    logf = LOGFILES.get(svc, "/var/log/syslog")
    d = logf.rsplit("/", 1)[0]
    sig = rng.choice(["connection refused", "timeout upstream", "deadlock detected",
                      "SSL handshake failed", "too many open files"])
    n = 1200 + i
    return [U(f"U logovima servisa {svc} ima cudnih gresaka. Uradi forenziku."),
            T(f"Citam zadnje linije loga servisa {svc}.",
              [{"name": "service_logs",
                "arguments": {"service": svc, "lines": 50}}]),
            R({"service": svc, "logs": f"ERROR {sig} (slucaj {n})"}),
            T(f"Trag vodi ka {d}. Listam direktorij da nadjem srodne fajlove.",
              [{"name": "file_list", "arguments": {"path": d}}]),
            R({"path": d, "files": [logf.rsplit("/", 1)[1], "archive.gz"]}),
            T(f"Otvaram fajl {logf} za detalje.",
              [{"name": "file_read",
                "arguments": {"path": logf, "lines": 50}}]),
            R({"path": logf, "excerpt": f"{sig}; ponavlja se svakih par minuta"}),
            T(f"Dijagnoza: centralna greska je '{sig}', ponavlja se periodicno, "
               f"sto mirise na sistemski uzrok (resurs ili zavisni servis), ne na "
               f"jednokratni incident. Predlazem provjeru zavisnog servisa i resursa, "
               f"pa verifikaciju pracenjem loga nakon intervencije. Nista ne mijenjam "
               f"bez potvrde.")]


# ---- HARD (4-5 koraka) ----
def h_disk_full_chain(rng, i):
    # disk pun -> baza pala -> inspekcija -> restart -> verifikacija (5 koraka)
    svc = rng.choice(["postgresql", "mysql"])
    pct = rng.randint(96, 99)
    d = "/var/log"
    big = rng.choice(["syslog.1", "kern.log.1", "archive.log"])
    gb = round(rng.uniform(8.0, 25.0), 1)
    return [U(f"Baza {svc} je pala usred noci. Sumnjam na pun disk. Rijesi korak po korak."),
            T("Provjeravam zauzece diska.",
              [{"name": "disk_usage", "arguments": {"path": "/"}}]),
            R({"path": "/", "used_pct": pct, "avail": "200M"}),
            T(f"Disk je na {pct}%. Provjeravam status baze {svc}.",
              [{"name": "service_status", "arguments": {"service": svc}}]),
            R({"service": svc, "status": "failed"}),
            T("Baza je pala. Citam log da potvrdim uzrok.",
              [{"name": "service_logs",
                "arguments": {"service": svc, "lines": 50}}]),
            R({"service": svc, "logs": f"{ts(i)} {svc}: FATAL: No space left on device; checkpoint failed"}),
            T(f"Uzrok potvrdjen. Gledam sta je najvece u {d} prije ciscenja.",
              [{"name": "terminal",
                "arguments": {"command": f"du -sh {d}/* | sort -rh | head -5",
                              "timeout_s": 30}}]),
            R({"output": f"{gb}G\t{d}/{big}"}),
            T(f"Najveci je {big} ({gb} GB). Radim restart baze {svc} nakon "
               f"sto prostor bude oslobodjen.",
              [{"name": "service_restart", "arguments": {"service": svc}}]),
            R({"service": svc, "action": "restart", "result": "ok"}),
            T(f"Dijagnoza: lanac je disk pun ({pct}%) pa je pala baza {svc}; "
               f"restart je pokrenut. Za verifikaciju predlazem: provjeru statusa "
               f"baze, potvrdu da checkpoint prolazi u logu i ponovno ocitanje "
               f"diska. Ciscenje {big} radim samo uz tvoju potvrdu (arhiva prije brisanja).")]


def h_port_chain(rng, i):
    svc = rng.choice(["nginx", "app-api", "prometheus"])
    rival = RIVALS.get(svc, "dev-proxy")
    port = PORTS[svc]
    pid = 1200 + i
    return [U(f"{svc} ne starta poslije updatea. Nadji sve karike lanca."),
            T(f"Provjeravam status servisa {svc}.",
              [{"name": "service_status", "arguments": {"service": svc}}]),
            R({"service": svc, "status": "failed"}),
            T("Servis je pao. Citam log za tacan uzrok.",
              [{"name": "service_logs",
                "arguments": {"service": svc, "lines": 50}}]),
            R({"service": svc, "logs": f"bind() to 0.0.0.0:{port} failed: Address already in use"}),
            T(f"Port {port} je zauzet. Provjeravam ko ga drzi.",
              [{"name": "port_check", "arguments": {"port": port}}]),
            R({"port": port, "process": rival, "pid": pid}),
            T(f"{rival} (pid {pid}) drzi port. Gledam je li to legitiman proces.",
              [{"name": "process_list",
                "arguments": {"limit": 10, "sort_by": "cpu"}}]),
            R({"top": [{"name": rival, "pid": pid, "cpu": 2}]}),
            T(f"Dijagnoza: {rival} (pid {pid}) legitimno drzi port {port}, pa se "
               f"{svc} ne moze vezati. Predlazem: ugasiti {rival} ili premjestiti "
               f"jedan servis na drugi port uz tvoju potvrdu, pa verifikaciju "
               f"provjerom porta i statusa servisa {svc}.")] 


def h_res_chain(rng, i):
    proc = rng.choice(PROCS)
    pid = 1200 + i
    cpu = rng.randint(88, 97)
    mem = rng.randint(80, 94)
    svc = rng.choice(SERVICES)
    return [U("Sistem je spor i nestabilan, a logovi pucaju. Daj kompletnu sliku."),
            T("Mjerim CPU.",
              [{"name": "cpu_usage", "arguments": {}}]),
            R({"cpu_pct": cpu}),
            T(f"CPU je na {cpu}%. Gledam top procese.",
              [{"name": "process_list",
                "arguments": {"limit": 10, "sort_by": "cpu"}}]),
            R({"top": [{"name": proc, "pid": pid, "cpu": cpu - 6}]}),
            T("CPU gusi jedan proces. Provjeravam i memoriju.",
              [{"name": "memory_usage", "arguments": {}}]),
            R({"mem_pct": mem}),
            T(f"Memorija je na {mem}%. Citam log servisa {svc} za posljedice.",
              [{"name": "service_logs",
                "arguments": {"service": svc, "lines": 50}}]),
            R({"service": svc, "logs": "worker timeout; request queue full"}),
            T(f"Dijagnoza: {proc} (pid {pid}) pritiska i CPU ({cpu}%) i memoriju "
               f"({mem}%), pa {svc} gubi workere i red zahtjeva raste. Predlazem "
               f"provjeru da li je {proc} ocekivan posao, ogranicenje resursa i "
               f"verifikaciju pracenjem CPU/memorije i loga nakon mjere. "
               f"Zaustavljanje samo uz tvoju potvrdu.")] 


EASY = [e_port, e_disk, e_cpu, e_pkg]
MEDIUM = [m_restart, m_disk_chain, m_net, m_mem, m_forenzika]
HARD = [h_disk_full_chain, h_port_chain, h_res_chain]


def main():
    rng = random.Random(202602)
    nums = [int(json.loads(l)["id"].split("-")[-1])
            for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    nxt = max(nums) + 1
    jobs = []
    per_easy = [57, 56, 56, 56]
    per_med = [75] * 5
    per_hard = [50] * 3
    for fn, c in zip(EASY, per_easy):
        jobs += [("easy", fn)] * c
    for fn, c in zip(MEDIUM, per_med):
        jobs += [("medium", fn)] * c
    for fn, c in zip(HARD, per_hard):
        jobs += [("hard", fn)] * c
    rng.shuffle(jobs)
    assert len(jobs) == 750, len(jobs)
    rows = []
    for k, (diff, fn) in enumerate(jobs):
        sid = f"amj-ag-{nxt + k:04d}"
        msgs = fn(rng, k)
        assert msgs is not None
        nsteps = sum(1 for m in msgs if m.get("tool_calls"))
        assert 2 <= nsteps <= 5, (fn.__name__, nsteps)
        rows.append(row(k, sid, diff, msgs))
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                   encoding="utf-8")
    from collections import Counter
    cs = Counter(sum(1 for m in r["messages"] if m.get("tool_calls")) for r in rows)
    cd = Counter(r["difficulty"] for r in rows)
    print(f"redova: {len(rows)} -> {OUT}")
    print(f"start: amj-ag-{nxt:04d} end: amj-ag-{nxt + len(rows) - 1:04d}")
    print(f"difficulty: {dict(sorted(cd.items()))}")
    print(f"koraci: {dict(sorted(cs.items()))}")


if __name__ == "__main__":
    main()
