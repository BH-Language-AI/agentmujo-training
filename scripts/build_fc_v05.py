#!/usr/bin/env python3
"""Template expansion v0.5 za function-calling dataset: BFCL-dizajn kategorije.

VLASTITI sadrzaj (BFCL eval podaci se NE kopiraju; sources.yaml status
design-only). Generise ~2000 NOVIH redova (deterministicki, seed=45) u
pet kategorija po BFCL dizajnu, prevedenih na nas registar od 14 alata:

  (a) SIMPLE 20% (400, easy):   jedan poziv s vise parametara
      (service_logs: service+lines u argumentima, fraza/nivo u tekstu —
      model filtrira nad rezultatom).
  (b) MULTIPLE 20% (400, medium): isti cilj, 2-3 kandidat-alata u system
      poruci, model bira tacan (npr. disk_usage vs file_list).
  (c) PARALLEL 20% (400, medium): 2-3 NEZAVISNA poziva u jednom odgovoru
      (status 3 servisa odjednom).
  (d) IRRELEVANCE 15% (300, easy): upit NE zahtijeva alat (pozdrav, opste
      pitanje, "sta je nginx") — model odgovara BEZ tool_call.
  (e) CHAINED-HARD 25% (500, hard): 3 stepa s parametrom izvedenim iz
      tool rezultata (port iz network_status -> port_check -> service_logs).

Dimenzije kojih nema u v0.1-v0.4 (single-turn kompletni / slot-filling):
vise-parametarski filter u tekstu, izbor izmedju kandidata, paralelni
pozivi, no-tool odgovori, izvedeni parametri kroz lanac.
Dedup: normalizirani user sadrzaj protiv SVIH user poruka iz v0.1-v0.4.
Izlaz: datasets/canonical/function_calling_v0.5.jsonl
Ne dira postojece fajlove ni datasets/splits/.

Usage: .venv/bin/python scripts/build_fc_v05.py
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

SEED = 45
ROOT = Path(__file__).resolve().parent.parent
VPRE = [ROOT / f"datasets/canonical/function_calling_v0.{i}.jsonl"
        for i in (1, 2, 3, 4)]
OUT = ROOT / "datasets/canonical/function_calling_v0.5.jsonl"

# Svjeze vrijednosti (nema ih u v0.2/v0.3 listama)
SERVICES = ["postfix", "dovecot", "mongod", "kafka", "consul", "etcd",
            "traefik", "haproxy", "keepalived", "rsyslog", "chrony",
            "unbound", "influxdb", "alertmanager", "node-exporter", "kubelet"]
SVC_PORT = {"postfix": 587, "dovecot": 993, "mongod": 27018, "kafka": 9092,
            "consul": 8300, "etcd": 2379, "traefik": 8443, "haproxy": 8404,
            "keepalived": 112, "rsyslog": 514, "chrony": 123,
            "unbound": 8953, "influxdb": 8086, "alertmanager": 9093,
            "node-exporter": 9100, "kubelet": 10250}
PORTS = sorted(SVC_PORT.values())
DISK_PATHS = ["/var/cache", "/srv/mail", "/var/lib/mongo", "/var/lib/kafka",
              "/srv/data", "/opt/traefik", "/var/lib/consul", "/mnt/archive"]
DIRS = ["/etc/postfix", "/etc/dovecot", "/etc/traefik", "/etc/haproxy",
        "/etc/keepalived", "/etc/rsyslog.d", "/etc/chrony", "/etc/unbound",
        "/srv/mail", "/opt/traefik"]
DIR_FILE = {"/etc/postfix": "/etc/postfix/main.cf",
            "/etc/dovecot": "/etc/dovecot/dovecot.conf",
            "/etc/traefik": "/etc/traefik/traefik.yml",
            "/etc/haproxy": "/etc/haproxy/haproxy.cfg",
            "/etc/keepalived": "/etc/keepalived/keepalived.conf",
            "/etc/rsyslog.d": "/etc/rsyslog.d/50-default.conf",
            "/etc/chrony": "/etc/chrony/chrony.conf",
            "/etc/unbound": "/etc/unbound/unbound.conf",
            "/srv/mail": "/srv/mail/README",
            "/opt/traefik": "/etc/traefik/traefik.yml"}
PHRASES = ["certificate expired", "queue full", "leader election",
           "split brain", "too many open files", "replica lag",
           "checksum mismatch", "connection reset by peer"]
LEVELS = ["samo upozorenja", "samo poruke nivoa ERROR i CRITICAL",
          "samo fatalne poruke", "sve iznad INFO nivoa",
          "samo linije sa WARN"]
LOG_LINES = [25, 75, 150, 300]
PACKAGES = ["fzf", "zoxide", "direnv", "pv", "socat", "nmap", "tcpdump",
            "atop", "mosh", "screen", "bmon", "nmon"]

CTX = ["", "Veceras na dezurstvu. ", "Pred kraj smjene. ",
       "Za vecernji izvjestaj. ", "Usput dok sam tu. ",
       "Nakon redovnog odrzavanja. "]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


META = {"author": "agentmujo-team", "quality_tier": "SILVER",
        "source": "fc-bfcl-style-v0.5",
        "verification_status": "verified"}

TOOL_DESC = {
    "service_status": "vrati status systemd servisa",
    "service_restart": "restartuj systemd servis",
    "service_logs": "vrati zadnje log linije servisa",
    "disk_usage": "vrati iskoristenost diska",
    "memory_usage": "vrati iskoristenost memorije",
    "cpu_usage": "vrati opterecenje CPU-a",
    "process_list": "lista pokrenutih procesa",
    "network_status": "osnovni status mreze i interfejsa",
    "port_check": "provjeri koji proces slusa na portu",
    "terminal": "low-level fallback za komande bez high-level alata",
    "package_query": "provjeri instalaciju i verziju paketa",
    "package_install": "instaliraj paket",
    "file_list": "lista sadrzaja direktorija",
    "file_read": "procitaj tekstualni fajl",
}


def tool_resp(tool, a, extra=None):
    extra = extra or {}
    if tool == "service_status":
        return json.dumps({"service": a["service"], "status": "active"},
                          ensure_ascii=False)
    if tool == "service_restart":
        return json.dumps({"service": a["service"], "action": "restart",
                           "result": "ok"}, ensure_ascii=False)
    if tool == "service_logs":
        return json.dumps({"service": a["service"],
                           "lines": a.get("lines", 50),
                           "tail": ["... log linija ..."]}, ensure_ascii=False)
    if tool == "disk_usage":
        return json.dumps({"path": a.get("path", "/"), "used_pct": 71,
                           "avail": "9G"}, ensure_ascii=False)
    if tool == "memory_usage":
        return json.dumps({"mem_pct": 44, "available": "9G"},
                          ensure_ascii=False)
    if tool == "cpu_usage":
        return json.dumps({"cpu_pct": 27}, ensure_ascii=False)
    if tool == "process_list":
        return json.dumps({"top": [{"pid": 2345, "name": "traefik"},
                                   {"pid": 678, "name": "consul"}]},
                          ensure_ascii=False)
    if tool == "network_status":
        return json.dumps({"interfaces": {"up": ["eth0"]},
                           "open_ports": extra.get("open_ports", [])},
                          ensure_ascii=False)
    if tool == "port_check":
        return json.dumps({"port": a["port"],
                           "process": extra.get("process", "unknown")},
                          ensure_ascii=False)
    if tool == "terminal":
        return json.dumps({"result": "ok", "output": "... izlaz komande ..."},
                          ensure_ascii=False)
    if tool == "package_query":
        return json.dumps({"package": a["package"], "installed": True,
                           "version": "2.0.1"}, ensure_ascii=False)
    if tool == "package_install":
        return json.dumps({"package": a["package"], "result": "ok"},
                          ensure_ascii=False)
    if tool == "file_list":
        return json.dumps({"path": a["path"],
                           "entries": ["main.cf", "app.log"]},
                          ensure_ascii=False)
    if tool == "file_read":
        return json.dumps({"path": a["path"],
                           "preview": "... sadrzaj fajla ..."},
                          ensure_ascii=False)
    raise ValueError(tool)


def final_text(tool, a):
    if tool == "service_status":
        return f"Servis {a['service']} je aktivan."
    if tool == "service_restart":
        return f"{a['service']} je restartovan."
    if tool == "service_logs":
        return (f"Ovo je zadnjih {a.get('lines', 50)} linija loga "
                f"za {a['service']}.")
    if tool == "disk_usage":
        return f"Zauzece na {a.get('path', '/')} je 71% (slobodno 9G)."
    if tool == "memory_usage":
        return "Memorija je na 44% (slobodno 9G)."
    if tool == "cpu_usage":
        return "Opterecenje procesora je 27%."
    if tool == "process_list":
        return "Procesi su izlistani po trazenom kriteriju."
    if tool == "network_status":
        return "Mrezni interfejsi su uredni."
    if tool == "port_check":
        return f"Provjera porta {a['port']} je zavrsena."
    if tool == "terminal":
        return "Komanda je izvrsena, izlaz je iznad."
    if tool == "package_query":
        return f"Paket {a['package']} je instaliran (verzija 2.0.1)."
    if tool == "package_install":
        return f"Paket {a['package']} je instaliran."
    if tool == "file_list":
        return f"Sadrzaj direktorija {a['path']} je izlistan."
    if tool == "file_read":
        return f"Prikazan je sadrzaj fajla {a['path']}."
    raise ValueError(tool)


# ---------------------------------------------------------- (a) SIMPLE (400)
SIMPLE_T = [
    "Za {service} mi izvuci zadnjih {lines} linija i podvuci gdje se javlja '{phrase}'.",
    "Treba mi isjecak od {lines} linija za {service}, pa odvoji zapise sa '{phrase}'.",
    "Baci pogled na log od {service} ({lines} linija unazad) i pronadji '{phrase}'.",
    "Log za {service}, zadnjih {lines} linija, ali me zanimaju {level}.",
    "Pregledaj {lines} svjezih linija za {service} i prebroj one sa '{phrase}'.",
    "Iz {lines} linija loga {service} izdvoji sve sto spada pod {level}.",
    "Sta se u zadnje vrijeme desava sa {service}? Daj {lines} linija uz oznaku '{phrase}'.",
    "Daj mi {lines} linija unazad za {service} i filtriraj po '{phrase}'.",
    "U logu {service} me zanimaju {level} kroz zadnjih {lines} linija.",
    "Svjezi log za {service} ({lines} linija), u potrazi sam za tragovima '{phrase}'.",
    "Procitaj unazad {lines} linija za {service} (zadnja dva sata), fokus na '{phrase}'.",
    "Pretresi rep loga {service} ({lines} linija) i javi nalazis li '{phrase}'.",
    "Zadnjih {lines} linija od {service}, ali izdvoji {level}.",
    "Ima li '{phrase}' medju zadnjih {lines} linija loga za {service}?",
]


def simple_cands():
    out = []
    for t in SIMPLE_T:
        for s in SERVICES:
            for n in LOG_LINES:
                for ph in PHRASES:
                    for lv in LEVELS:
                        try:
                            u = t.format(service=s, lines=n, phrase=ph,
                                         level=lv)
                        except (KeyError, IndexError):
                            continue
                        for ctx in CTX[:2]:
                            out.append((ctx + u, {"service": s, "lines": n}))
    return out


# -------------------------------------------------------- (b) MULTIPLE (400)
def sys_msg(cands):
    parts = "; ".join(f"{c} — {TOOL_DESC[c]}" for c in cands)
    return (f"Na raspolaganju su ti alati: {parts}. "
            f"Odaberi tacno jedan alat koji rjesava zahtjev.")


def multiple_cands(rng):
    fams = []  # (user_tpl_fn, correct, distractors, quota)
    disk_u = ["Koliko je zauzeto na {v}?",
              "Je li {v} pri vrhu kapaciteta?",
              "Koliko je ostalo slobodno na {v}?",
              "Daj mi popunjenost za {v}.",
              "Provjeri zauzece diska na {v}."]
    list_u = ["Sta se nalazi u {v}?",
              "Izlistaj mi sadrzaj {v}.",
              "Sta drzi {v} unutra?",
              "Prikazi sta ima u {v}."]
    fams.append((disk_u, "disk_usage", ["file_list"], DISK_PATHS, 40))
    fams.append((list_u, "file_list", ["disk_usage"], DIRS, 40))
    pq_u = ["Je li {v} instaliran na sistemu?",
            "Koja verzija {v} je gore?",
            "Vidi je li {v} prisutan."]
    pi_u = ["Dodaj {v} na masinu.",
            "Postavi {v}, treba za posao.",
            "Instaliraj mi {v}."]
    fams.append((pq_u, "package_query", ["package_install"], PACKAGES, 30))
    fams.append((pi_u, "package_install", ["package_query", "terminal"], PACKAGES, 30))
    st_u = ["Je li {v} ziv?",
            "Radi li {v} uredno?",
            "Javi stanje servisa {v}."]
    lg_u = ["Sta pise u logu {v}?",
            "Ima li gresaka u logu {v}?",
            "Daj mi rep loga za {v}."]
    fams.append((st_u, "service_status", ["service_logs"], SERVICES, 40))
    fams.append((lg_u, "service_logs", ["service_status"], SERVICES, 40))
    proc_u = ["Ko trosi najvise CPU-a na masini?",
              "Koji procesi gutaju memoriju?",
              "Daj mi najvece potrosace resursa.",
              "Koji procesi najvise opterecuju masinu?",
              "Prikazi mi najvece potrosace CPU-a i memorije.",
              "Izlistaj procese koji najvise trose."]
    res_u = ["Koliko je procesor opterecen?",
             "Kakva je iskoristenost RAM-a?",
             "Je li masina preopterecena?"]
    res_cpu = ["Koliko je procesor opterecen?",
               "Je li procesor preopterecen?",
               "Kakvo je opterecenje CPU-a?"]
    res_mem = ["Kakva je iskoristenost RAM-a?",
               "Koliko je memorije slobodno?",
               "Je li RAM pri vrhu?"]
    fams.append((proc_u, "process_list", ["cpu_usage", "memory_usage"], [None], 30))
    fams.append((res_cpu, "cpu_usage", ["process_list"], [None], 15))
    fams.append((res_mem, "memory_usage", ["process_list"], [None], 15))
    port_u = ["Ko drzi port {v}?",
              "Sta slusa na {v}?",
              "Je li port {v} zauzet?"]
    net_u = ["Kakvi su mrezni interfejsi?",
             "Je li mreza na serveru uredna?",
             "Daj mi pregled mreze.",
             "Ima li mrezne konektivnosti?",
             "Jesu li svi interfejsi dignuti?",
             "Provjeri mrezno stanje servera."]
    fams.append((port_u, "port_check", ["network_status"], PORTS, 30))
    fams.append((net_u, "network_status", ["port_check"], [None], 30))
    read_u = ["Otvori {v} i prikazi mi.",
              "Sta pise u {v}?",
              "Procitaj mi {v}."]
    fl_u = ["Sta ima u {v} od fajlova?",
            "Izlistaj {v} za pregled.",
            "Prikazi sadrzaj {v}."]
    fams.append((read_u, "file_read", ["file_list", "terminal"],
                 list(DIR_FILE.values()), 30))
    fams.append((fl_u, "file_list", ["file_read"], DIRS, 30))
    return fams


# -------------------------------------------------------- (c) PARALLEL (400)
P_STATUS_T = ["Kakvo je stanje {a}, {b} i {c} jutros?",
              "Jesu li {a}, {b} i {c} dignuti?",
              "Provjeri odjednom {a}, {b} i {c}.",
              "Daj status za {a}, {b} i {c}.",
              "Treba mi stanje tri servisa: {a}, {b}, {c}.",
              "Javi jesu li zivi {a}, {b} i {c}."]
P_RES_T = ["Daj mi stanje CPU-a, memorije i top {limit} procesa po {sort}.",
           "Treba mi CPU, memorija i {limit} najvecih po {sort}.",
           "Snimi CPU, RAM i {limit} procesa sortiranih po {sort}."]
P_DISK_T = ["Provjeri zauzece na {a}, {b} i {c}.",
            "Koliko su puni {a}, {b} i {c}?",
            "Daj popunjenost za {a}, {b} i {c} odjednom."]
P_PORT_T = ["Ko slusa na {a} i {b}?",
            "Provjeri odjednom portove {a} i {b}.",
            "Daj vlasnike za {a} i {b}."]

SORT_LAB = {"cpu": "CPU-u", "memory": "memoriji"}


# ----------------------------------------------------- (d) IRRELEVANCE (300)
IR_GREET_U = ["Zdravo!", "Dobro jutro.", "Dobar dan.", "Evo me opet.",
              "Pozdrav.", "Hej, jesi tu?", "Dobro vece.",
              "Zdravo, kako si?", "Cao.", "Selam.",
              "Jutro.", "Evo me nazad."]
IR_GREET_A = ["Zdravo! Kako mogu pomoci oko servera?",
              "Dobar dan! Reci samo sta treba provjeriti.",
              "Pozdrav! Tu sam za pitanja oko odrzavanja."]
IR_CONCEPT = [
    ("Sta je {v}?", "{V} je sistemski servis. Ako te zanima stanje na ovom serveru, reci pa cu provjeriti."),
    ("Cemu sluzi {v}?", "{V} sluzi za upravljanje paketima i alatima. Pitaj ako trebas nesto konkretno provjeriti."),
    ("Sta znaci '{v}' u logovima?", "Poruka '{v}' obicno ukazuje na problem koji vrijedi istraziti. Daj mi servis pa cu pogledati log."),
    ("Koja je razlika izmedju {a} i {b}?", "{A} pokazuje ukupno zauzece, a {B} izlistava pojedinacne stavke. Reci sta te zanima pa cu provjeriti."),
    ("Na kojem portu radi {v}?", "To zavisi od konfiguracije na ovom serveru. Reci da provjerim pa cu pogledati."),
    (" Da li je {v} siguran servis?", "{V} je standardna komponenta; sigurnost zavisi od konfiguracije. Mogu provjeriti status ako zelis."),
]
IR_CAP_U = ["Koje alate imas na raspolaganju?",
            "Sta sve mozes provjeriti na serveru?",
            "Mozes li restartovati servis?",
            "Da li mozes instalirati paket?",
            "Koje provjere mozes odraditi?",
            "Sta sve znas o ovom serveru?",
            "Mozes li pogledati logove?",
            "Da li mozes provjeriti disk?"]
IR_CAP_A = ["Na raspolaganju imam provjere statusa, logova, diskova, mreze i paketa. Reci sta treba.",
            "Mogu provjeriti servise, logove, resurse, mrezu i pakete. Samo reci koji.",
            "Mogu restartovati servis ili instalirati paket kad mi kazes koji tacno."]
IR_OFF = ["Napisi mi pjesmu o serverima.",
          "Kakvo je vrijeme u Sarajevu?",
          "Ko je pobijedio sinoc?",
          "Daj mi recept za burek.",
          "Sta se desava na berzi?",
          "Preporuci mi dobar film za veceras.",
          "Koji je najbolji fudbalski klub?",
          "Daj mi savjet za putovanje.",
          "Sta kuhati za nedjeljni rucak?",
          "Preporuci mi knjigu za odmor.",
          "Kako ide kurs eura?",
          "Kad pocinje ramazan?"]
IR_OFF_A = ["To je izvan mog posla oko servera, ali pitaj slobodno nesto vezano za odrzavanje.",
            "Nazalost ne mogu pomoci s tim. Tu sam za pitanja oko servera i servisa.",
            "To nije nesto sto mogu provjeriti alatima. Ako treba nesto oko servera, reci."]
IR_THANKS = ["Hvala, to je sve.", "Pozdrav, gasim smjenu.",
             "Hvala na pomoci.", "To bi bilo to za veceras.",
             "Hvala puno.", "Odlicno, hvala."]
IR_THANKS_A = ["Nema na cemu! Javi ako jos nesto zatreba.",
               "Laku noc! Tu sam ako nesto iskrsne."]
IR_STMT = ["Serveri su danas stabilni.", "Javio sam ekipi da je sve uredno.",
           "Smjena prosla mirno.", "Nema alarma za veceras.",
           "Sve je mirno na monitoringu.", "Nema novosti sa servera."]
IR_STMT_A = ["Drago mi je da je mirno. Javi ako nesto zatreba.",
             "Primljeno. Tu sam ako nesto iskrsne."]


# --------------------------------------------------- (e) CHAINED-HARD (500)
CHAIN_T = [
    "{Service} ne odgovara. Kreni od mreze, vidi ko slusa na njegovom portu pa daj log.",
    "Klijenti ne dolaze do {service}. Prvo mrezni status, pa vlasnik porta, pa log servisa.",
    "Sumnjam na prekid prema {service}. Provjeri mrezu, port pa izvadi {lines} linija loga.",
    "Dijagnostika za {service}: status mreze, slusalac na portu pa {lines} linija loga.",
    "Port servisa {service} cuti. Kreni od mreze, preko porta do loga.",
    "Ispitaj put do {service}: mreza, provjera porta pa svjezi log od {lines} linija.",
    "Nakon promjene firewalla {service} nedostupan. Mreza, port pa log.",
    "{Service} se ne javlja izvana. Prvo interfejsi, pa ko drzi port, pa sta pise u logu.",
    "Za {service} treba puna trijaza: mrezni status, vlasnik porta i {lines} linija loga.",
    "Gubi se promet ka {service}. Provjeri mrezu, identifikuj slusaoca pa daj log.",
]


def main():
    rng = random.Random(SEED)
    seen = set()
    for fp in VPRE:
        for line in fp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                for m in json.loads(line).get("messages", []):
                    if m.get("role") == "user":
                        seen.add(norm(m.get("content", "")))
    nxt = 0
    for fp in VPRE:
        for line in fp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                nxt = max(nxt, int(json.loads(line)["id"].rsplit("-", 1)[1]))
    nxt += 1

    out_rows = []
    cats = {}

    def take(cands, q, fam):
        rng.shuffle(cands)
        got = []
        for u, calls in cands:
            if len(got) >= q:
                break
            if norm(u) in seen:
                continue
            seen.add(norm(u))
            got.append((u, calls))
        assert len(got) == q, f"{fam}: {len(got)}/{q}"
        return got

    # ---- (a) SIMPLE: user + assistant(tool_call)
    for u, args in take(simple_cands(), 400, "simple"):
        out_rows.append({"difficulty": "easy", "cat": "simple", "messages": [
            {"role": "user", "content": u},
            {"role": "assistant", "content": "Provjeravam navedeno.",
             "tool_calls": [{"name": "service_logs", "arguments": args}]}]})
    cats["simple"] = 400

    # ---- (b) MULTIPLE: system(kandidati) + user + assistant(tacan poziv)
    mcands = []
    for tpls, correct, distract, vals, q in multiple_cands(rng):
        for t in tpls:
            for v in vals:
                for ctx in CTX:
                    if correct == "service_logs" and "{v}" in t:
                        args = {"service": v, "lines": 50}
                    elif correct in ("service_status",):
                        args = {"service": v}
                    elif correct in ("package_query", "package_install"):
                        args = {"package": v}
                    elif correct in ("disk_usage", "file_list"):
                        args = {"path": v}
                    elif correct == "file_read":
                        args = {"path": v}
                    elif correct == "port_check":
                        args = {"port": v}
                    elif correct == "process_list":
                        args = {"limit": 10, "sort_by": "cpu"}
                    elif correct in ("network_status", "cpu_usage",
                                     "memory_usage"):
                        args = {}
                    else:
                        raise ValueError(correct)
                    u = ctx + (t.format(v=v) if v is not None else t)
                    mcands.append((u, correct, distract, args,
                                   f"mult:{correct}"))
    rng.shuffle(mcands)
    got = []
    need = {"mdisk": 40, "mlist": 40, "mpq": 30, "mpi": 30, "mst": 40,
            "mlog": 40, "mproc": 30, "mres": 30, "mport": 30, "mnet": 30,
            "mread": 30, "mfl": 30}
    key_of = {"disk_usage": "mdisk", "file_list": "mfl", "package_query": "mpq",
              "package_install": "mpi", "service_status": "mst",
              "service_logs": "mlog", "process_list": "mproc",
              "cpu_usage": "mres", "memory_usage": "mres",
              "port_check": "mport", "network_status": "mnet",
              "file_read": "mread"}
    # file_list se javlja i kao correct u dvije familije (disk par + read par);
    # razdvoji po distractoru
    for u, correct, distract, args, fam in mcands:
        if len(got) >= 400:
            break
        k = key_of[correct]
        if correct == "file_list":
            k = "mlist" if distract == ["disk_usage"] else "mfl"
        if need[k] <= 0 or norm(u) in seen:
            continue
        seen.add(norm(u))
        need[k] -= 1
        cands = [correct] + distract
        msgs = [{"role": "system", "content": sys_msg(cands)},
                {"role": "user", "content": u},
                {"role": "assistant", "content": "Biram odgovarajuci alat.",
                 "tool_calls": [{"name": correct, "arguments": args}]}]
        out_rows.append({"difficulty": "medium", "cat": "multiple",
                         "messages": msgs})
        got.append(u)
    assert len(got) == 400, f"multiple: {len(got)}/400 {need}"
    cats["multiple"] = 400

    # ---- (c) PARALLEL: user + assistant(2-3 poziva) + toolovi + final
    ppools = {}
    pstat_pool = []
    for trio in set(tuple(sorted(rng.sample(SERVICES, 3))) for _ in range(300)):
        a, b, c = trio
        for t in rng.sample(P_STATUS_T, 2):
            u = t.format(a=a, b=b, c=c)
            calls = [("service_status", {"service": x}) for x in (a, b, c)]
            pstat_pool.append((u, calls))
    ppools["pstat"] = (pstat_pool, 150)
    pres_pool = []
    for ctx in CTX:
        for lim in (5, 10, 15):
            for sb in ("cpu", "memory"):
                for t in P_RES_T:
                    u = ctx + t.format(limit=lim, sort=SORT_LAB[sb])
                    pres_pool.append((u, [("cpu_usage", {}),
                                          ("memory_usage", {}),
                                          ("process_list",
                                           {"limit": lim, "sort_by": sb})]))
    ppools["pres"] = (pres_pool, 100)
    pdisk_pool = []
    for trio in set(tuple(sorted(rng.sample(DISK_PATHS, 3)))
                    for _ in range(200)):
        a, b, c = trio
        for t in P_DISK_T:
            u = t.format(a=a, b=b, c=c)
            pdisk_pool.append((u, [("disk_usage", {"path": x})
                                   for x in (a, b, c)]))
    ppools["pdisk"] = (pdisk_pool, 75)
    pport_pool = []
    for pair in set(tuple(sorted(rng.sample(PORTS, 2))) for _ in range(200)):
        a, b = pair
        for t in P_PORT_T:
            u = t.format(a=a, b=b)
            pport_pool.append((u, [("port_check", {"port": x})
                                   for x in (a, b)]))
    ppools["pport"] = (pport_pool, 75)
    for kind, (pool, q) in ppools.items():
        for u, calls in take(pool, q, f"parallel:{kind}"):
            msgs = [{"role": "user", "content": u},
                    {"role": "assistant",
                     "content": "Radim sve provjere odjednom.",
                     "tool_calls": [{"name": n, "arguments": a}
                                    for n, a in calls]}]
            for n, a in calls:
                msgs.append({"role": "tool", "content": tool_resp(n, a)})
            msgs.append({"role": "assistant",
                         "content": "Gotovo: " + " ".join(
                             final_text(n, a) for n, a in calls)})
            out_rows.append({"difficulty": "medium", "cat": "parallel",
                             "messages": msgs})
    cats["parallel"] = 400

    # ---- (d) IRRELEVANCE: user + assistant(tekst, BEZ tool_calls)
    icands = []
    for t in IR_GREET_U:
        for ctx in CTX:
            icands.append((ctx + t, rng.choice(IR_GREET_A), "greet"))
    for t, a in IR_CONCEPT:
        for v in SERVICES + PACKAGES[:6] + PHRASES[:4]:
            if "{a}" in t:
                for w in DISK_PATHS[:2]:
                    u = t.format(v=v, V=v.capitalize(), a="disk_usage",
                                 A="Disk_usage", b="file_list", B="File_list")
                    icands.append((u, a, "concept"))
            else:
                try:
                    u = t.format(v=v, V=v.capitalize())
                except (KeyError, IndexError):
                    continue
                icands.append((u, a.format(v=v, V=v.capitalize()), "concept"))
    for t in IR_CAP_U:
        for ctx in CTX:
            icands.append((ctx + t, rng.choice(IR_CAP_A), "cap"))
    for t in IR_OFF:
        for ctx in CTX:
            icands.append((ctx + t, rng.choice(IR_OFF_A), "off"))
    for t in IR_THANKS:
        for ctx in CTX:
            icands.append((ctx + t, rng.choice(IR_THANKS_A), "thanks"))
    for t in IR_STMT:
        for ctx in CTX:
            icands.append((ctx + t, rng.choice(IR_STMT_A), "stmt"))
    iq = {"greet": 50, "concept": 90, "cap": 40, "off": 60, "thanks": 30,
          "stmt": 30}
    rng.shuffle(icands)
    n_irr = 0
    for u, a, k in icands:
        if n_irr >= 300:
            break
        if iq[k] <= 0 or norm(u) in seen:
            continue
        seen.add(norm(u))
        iq[k] -= 1
        n_irr += 1
        out_rows.append({"difficulty": "easy", "cat": "irrelevance",
                         "messages": [{"role": "user", "content": u},
                                      {"role": "assistant", "content": a}]})
    assert n_irr == 300, f"irrelevance: {n_irr}/300 {iq}"
    cats["irrelevance"] = 300

    # ---- (e) CHAINED-HARD: mreza -> port(iz nalaza) -> log servisa
    hcands = []
    for t in CHAIN_T:
        for s in SERVICES:
            p = SVC_PORT[s]
            for n in (50, 100, 200):
                for ctx in CTX[:2]:
                    u = ctx + t.format(service=s, Service=s.capitalize(),
                                       lines=n, port=p)
                    hcands.append((u, s, p, n))
    for u, (s, p, n) in take([(u, (s, p, n)) for (u, s, p, n) in hcands],
                           500, "chained"):
        extra_net = {"open_ports": sorted({p, 22, 80})}
        msgs = [
            {"role": "user", "content": u},
            {"role": "assistant", "content": "Krecem od mreze pa idem po nalazu.",
             "tool_calls": [{"name": "network_status", "arguments": {}}]},
            {"role": "tool", "content": tool_resp("network_status", {},
                                                  extra_net)},
            {"role": "assistant",
             "content": (f"U mreznom nalazu vidim otvoren port {p}, "
                         f"provjeravam ko ga drzi."),
             "tool_calls": [{"name": "port_check", "arguments": {"port": p}}]},
            {"role": "tool", "content": tool_resp("port_check", {"port": p},
                                                  {"process": s})},
            {"role": "assistant",
             "content": (f"Port {p} drzi {s}, vadim njegov log."),
             "tool_calls": [{"name": "service_logs",
                             "arguments": {"service": s, "lines": n}}]},
            {"role": "tool", "content": tool_resp("service_logs",
                                                  {"service": s, "lines": n})},
            {"role": "assistant",
             "content": (f"Zakljucak: mreza uredna, port {p} drzi {s}. "
                         f"Ovo je zadnjih {n} linija loga za {s}.")}]
        out_rows.append({"difficulty": "hard", "cat": "chained",
                         "thinking": True, "messages": msgs})
    cats["chained"] = 500

    assert len(out_rows) == 2000, len(out_rows)

    # tvrdnja: nijedan irrelevance red nema tool_calls
    for r in out_rows:
        if r["cat"] == "irrelevance":
            for m in r["messages"]:
                assert "tool_calls" not in m, r

    rng.shuffle(out_rows)
    with OUT.open("w", encoding="utf-8") as f:
        for k, r in enumerate(out_rows):
            f.write(json.dumps({
                "id": f"amj-fc-{nxt + k:04d}",
                "version": "0.5.0",
                "language": "bs-ijekavica",
                "task": "function-calling",
                "difficulty": r["difficulty"],
                "enable_thinking": bool(r.get("thinking", False)),
                "messages": r["messages"],
                "metadata": META,
            }, ensure_ascii=False) + "\n")

    diff = {}
    tools = {}
    for r in out_rows:
        diff[r["difficulty"]] = diff.get(r["difficulty"], 0) + 1
        for m in r["messages"]:
            for tc in m.get("tool_calls", []) or []:
                tools[tc["name"]] = tools.get(tc["name"], 0) + 1
    print(f"redova: {len(out_rows)}")
    print(f"kategorije: {json.dumps(cats, ensure_ascii=False)}")
    print(f"difficulty: {diff}")
    print(f"alati: {json.dumps(tools, indent=1, ensure_ascii=False)}")
    print(f"prvi id: amj-fc-{nxt:04d}, zadnji: amj-fc-{nxt + len(out_rows) - 1:04d}")


if __name__ == "__main__":
    main()
