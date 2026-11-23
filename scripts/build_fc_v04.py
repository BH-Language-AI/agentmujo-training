#!/usr/bin/env python3
"""Template expansion v0.4 za function-calling dataset: slot-filling kroz vise turnova.

Generise ~1500 NOVIH redova (deterministicki, seed=44). Svi redovi v0.1/v0.2/v0.3
su single-turn (kompletan zahtjev -> tool poziv); v0.4 pokriva NOVU dimenziju:
nepotpun zahtjev -> model NE pogadja parametre nego POSTAVLJA ciljano pitanje
-> user dopunjava -> tool poziv s kompletnim parametrima.

2-turn (1000): U1 nepotpun, A1 pitanje, U2 dopuna, A2 tool_call + tool + final.
3-turn (500): dva slot-a / korekcija nevazece vrijednosti / disambiguacija +
  potvrda prije destruktivnog poziva.
Difficulty: easy 450 / medium 750 / hard 300 (30/50/20).
Dedup: normalizirani U1 sadrzaj protiv SVIH user poruka iz v0.1/v0.2/v0.3.
Izlaz: datasets/canonical/function_calling_v0.4.jsonl
Ne dira postojece fajlove ni datasets/splits/.

Usage: .venv/bin/python scripts/build_fc_v04.py
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

SEED = 44
ROOT = Path(__file__).resolve().parent.parent
V01 = ROOT / "datasets/canonical/function_calling_v0.1.jsonl"
V02 = ROOT / "datasets/canonical/function_calling_v0.2.jsonl"
V03 = ROOT / "datasets/canonical/function_calling_v0.3.jsonl"
OUT = ROOT / "datasets/canonical/function_calling_v0.4.jsonl"

SERVICES = ["nginx", "apache2", "postgresql", "mysql", "redis", "docker",
            "ssh", "cron", "fail2ban", "ufw", "ollama", "named",
            "gunicorn", "celery", "prometheus", "grafana-server",
            "memcached", "rabbitmq-server", "elasticsearch", "vault"]
PACKAGES = ["ripgrep", "bat", "htop", "curl", "git", "tmux", "jq", "ncdu",
            "certbot", "glances", "httpie", "restic"]
DIRS = ["/var/log", "/etc/nginx", "/etc/celery", "/etc/prometheus",
        "/srv/backups", "/etc/grafana", "/opt/minio", "/etc/fail2ban"]
DIR_FILE = {"/var/log": "/var/log/syslog", "/etc/nginx": "/etc/nginx/nginx.conf",
            "/etc/celery": "/etc/celery/worker.conf",
            "/etc/prometheus": "/etc/prometheus/prometheus.yml",
            "/srv/backups": "/opt/app/config.yaml",
            "/etc/grafana": "/etc/grafana/grafana.ini",
            "/etc/minio": "/etc/minio/config",
            "/etc/fail2ban": "/etc/fail2ban/jail.local",
            "/opt/minio": "/etc/minio/config"}
PORTS = [22, 80, 443, 3000, 5432, 6379, 8080, 8000, 11434, 3306, 9090, 9200]
LINES = [20, 50, 100]

# dvosmislene oznake -> kandidati (model mora razjasniti, ne pogadjati)
AMBIG = {"web servis": ["nginx", "apache2"],
         "baza": ["postgresql", "mysql"],
         "kes": ["redis", "memcached"],
         "monitoring": ["prometheus", "grafana-server"]}

CTX = ["", "Jutros na dezurstvu. ", "Prije predaje smjene. ",
       "Za zapisnik. ", "Usput. ", "Kad stignes. ",
       "Prije nocnog deploya. ", "Monitoring je nesto dojavio. "]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


# ------------------------------------------------------- U1 nepotpuni zahtjevi
SVC_U1 = ["Restartuj servis.", "Provjeri status servisa.", "Prikazi log servisa.",
          "Ugasi pa digni servis.", "Je li servis ziv?", "Daj mi stanje servisa.",
          "Treba restart servisa.", "Servis nesto steka, provjeri ga.",
          "Osvjezi servis restartom.", "Log servisa mi treba.",
          "Vidi je li servis pao.", "Daj dijagnostiku servisa.",
          "Servis ne prima promet, vidi sta je.", "Ponovo digni servis.",
          "Provjeri onaj servis od jutros.", "Treba mi servis dignut.",
          "Vidi status onog servisa.", "Servis je zapeo, pogledaj.",
          "Daj brzi pregled servisa.", "Provjeri da servis radi.",
          "Servis se cudno ponasa.", "Treba mi restart onog servisa.",
          "Javi stanje servisa.", "Baci pogled na servis.",
          "Vidi onaj servis sto zeza.", "Stanje servisa mi treba.",
          "Provjeri servisnu sluzbu.", "Daj info o servisu.",
          "Vidi radi li servis.", "Treba mi uvid u servis.",
          "Servis provjera.", "Pogledaj servis."]
PORT_U1 = ["Ko drzi port?", "Provjeri port.", "Je li port zauzet?",
           "Sta slusa na portu?", "Vidi ko je na portu.",
           "Treba mi vlasnik porta.", "Port je mozda zauzet, provjeri.",
           "Koji proces drzi port?", "Provjeri zauzetost porta.",
           "Javi ko slusa na portu.", "Vidi sta je na portu.",
           "Identifikuj slusaoca na portu.", "Provjeri ko slusa port.",
           "Daj proces iza porta."]
PORT_INV_U1 = ["Provjeri mi port.", "Vidi port.", "Ko je na portu?",
               "Daj vlasnika porta.", "Port provjera.", "Treba mi port.",
               "Vidi zauzetost porta.", "Ko slusa port?",
               "Provjeri slusaoca porta.", "Daj stanje porta.",
               "Vidi ko drzi port.", "Port me zanima, provjeri."]
FILE_U1 = ["Izlistaj direktorij.", "Sta ima u direktoriju?", "Otvori fajl.",
           "Procitaj config fajl.", "Daj sadrzaj fajla.", "Listaj folder.",
           "Prikazi mi onaj config.", "Treba mi sadrzaj fajla.",
           "Baci pogled u direktorij.", "Otvori log fajl.",
           "Daj listing direktorija.", "Iscitaj fajl.",
           "Pogledaj sta ima u folderu.", "Daj mi fajl na uvid."]
PKG_U1 = ["Je li paket instaliran?", "Provjeri paket.", "Instaliraj paket.",
          "Treba mi paket, vidi je li tu.", "Dodaj paket na masinu.",
          "Koja verzija paketa je gore?", "Vidi ima li paketa.",
          "Namjesti paket na sistem.", "Fali nam paket, provjeri.",
          "Ubaci paket.", "Postavi alat.", "Daj info o paketu.",
          "Provjeri status paketa.", "Treba mi alat, vidi je li tu."]
LINES_U1 = ["Prikazi log za {service}.", "Daj mi log od {service}.",
            "Treba mi log servisa {service}.", "Izvadi log za {service}.",
            "Sta pise u logu {service}?", "Prelistaj log {service}.",
            "Daj svjezi log {service}.", "Provjeri log za {service}.",
            "Izlistaj procese.", "Daj mi procese.", "Koji procesi trose najvise?",
            "Prikazi top procese.", "Listaj procese po potrosnji.",
            "Treba mi lista procesa.", "Vidi procese na masini.",
            "Daj potrosace resursa.", "Snimi procese.",
            "Vidi najvece potrosace.", "Daj pregled procesa.",
            "Ko trosi CPU?", "Ko trosi memoriju?"]
DISAMBIG_U1 = ["Restartuj {label}.", "Provjeri {label}.", "Daj status {label}.",
               "Restartuj {label} radi osvjezenja.", "Prikazi log {label}.",
               "Je li {label} ziv?", "{label} nesto steka, provjeri.",
               "Osvjezi {label}.", "Digni ponovo {label}.",
               "Treba mi stanje {label}.", "Vidi {label}.",
               "{label} ne odgovara, intervenisi."]
# potvrda prije destruktivnog: U1 kompletan ali model MORA traziti potvrdu
CONFIRM_U1 = {"service_restart": ["Restartuj {service}.", "Uradi restart {service}.",
                                  "Ponovo digni {service}.", "Treba restartovati {service}.",
                                  "Daj {service} jedan restart.", "Resetuj {service} kroz restart.",
                                  "Restartuj {service} cistoce radi.", "Osvjezi {service} restartom.",
                                  "Izvrsi restart nad {service}.", "Digni ponovo {service} servis."],
              "package_install": ["Instaliraj {package}.", "Dodaj {package} na masinu.",
                                  "Ubaci paket {package}.", "Postavi {package} na sistem.",
                                  "Treba nam {package}, postavi ga.", "Instaliraj alat {package}.",
                                  "Namjesti {package}.", "Stavi {package} gore."]}
TWOSLOT_U1 = ["Prikazi log.", "Treba mi log.", "Daj mi log servisa.",
              "Izvadi zadnje linije loga.", "Treba mi isjecak iz loga.",
              "Pokazi sta se desavalo.", "Daj rep loga.", "Prelistaj log.",
              "Treba mi svjezi log.", "Izvuci log.", "Daj zadnje zapise iz loga.",
              "Pogledaj log.", "Treba mi uvid u log.", "Snimi isjecak loga.",
              "Daj log unazad sat vremena.", "Izvadi log servisa.",
              "Daj mi zadnje log zapise.", "Treba mi rep loga."]
FCHAIN_U1 = ["Treba mi config.", "Otvori config fajl.", "Daj mi konfiguraciju.",
             "Procitaj config.", "Treba mi uvid u config.", "Prikazi konfiguraciju.",
             "Vidi config.", "Treba mi sadrzaj configa.", "Otvori postavke.",
             "Daj mi config na uvid.", "Iscitaj konfiguraciju.", "Nadji config."]
DCONF_U1 = ["Restartuj {label}.", "Restartuj {label} radi osvjezenja.",
            "Digni ponovo {label}.", "{label} zaglavio, restartuj ga.",
            "Osvjezi {label} jednim restartom.", "{label} ne prima promet, restartuj.",
            "Uradi restart {label}.", "Resetuj {label} kroz restart.",
            "Treba restartovati {label}.", "{label} se rusi, restartuj ga."]

# ------------------------------------------------------- A1 ciljana pitanja
Q_SERVICE = ["Koji servis je u pitanju?", "Za koji servis tacno?",
             "Koji servis mislis?", "Navedi ime servisa.",
             "O kojem servisu se radi?", "Koji servis da provjerim?"]
Q_PORT = ["Koji port da provjerim?", "O kojem portu se radi?",
          "Navedi broj porta.", "Koji port te zanima?"]
Q_PATH = ["Koji direktorij tacno?", "Navedi putanju.", "Koji fajl mislis?",
          "O kojoj putanji se radi?", "Koju putanju da otvorim?"]
Q_PKG = ["Koji paket je u pitanju?", "Navedi ime paketa.",
         "O kojem paketu se radi?", "Koji paket mislis?"]
Q_LINES = ["Koliko linija da izvucem?", "Koliko linija unazad?",
           "Navedi broj linija.", "Koliko zapisa te zanima?"]
Q_LIMIT = ["Koliko procesa da izlistam?", "Koliko prvih da prikazem?",
           "Navedi broj procesa.", "Po cemu da sortiram, CPU ili memorija?"]
Q_DISAMBIG = "Koji tacno mislis, {a} ili {b}?"
Q_CONFIRM_R = "Ovo ce restartovati servis {v}. Potvrdjujes?"
Q_CONFIRM_I = "Ovo ce instalirati paket {v}. Potvrdjujes?"
Q_CORR_PORT = ("Port {bad} nije validan (opseg je 1-65535). Koji port tacno mislis?")
Q_CORR_LINES = ("Broj linija {bad} nije validan (opseg 1-500). Koliko linija da izvucem?")
Q_CORR_SVC = ("Servis '{bad}' ne postoji na sistemu. Koji servis tacno mislis?")

# ------------------------------------------------------- U2/U3 dopune
U2_SVC = ["{v}.", "{v} je u pitanju.", "Mislim na {v}.", "Radi se o {v}.",
          "{v}, molim.", "U pitanju je {v}."]
U2_PORT = ["{v}.", "Port {v}.", "Mislim na port {v}.", "U pitanju je {v}."]
U2_PATH = ["{v}.", "Putanja {v}.", "Mislim na {v}.", "Otvori {v}."]
U2_PKG = ["{v}.", "Paket {v}.", "Mislim na {v}.", "U pitanju je {v}."]
U2_LINES = ["{v}.", "{v} linija.", "Daj {v}.", "Mislim na {v}."]
U2_CONFIRM = ["Da.", "Potvrdjujem.", "Moze.", "Izvrsi.", "Da, izvrsi.",
              "Slobodno.", "Da, potvrdjujem.", "Moze, odradi to."]
U3_LINES = U2_LINES
BAD_PORTS = ["999999", "0", "-5", "osamdeset"]
BAD_LINES = ["0", "-10", "5000", "puno"]
BAD_SVC = ["taj tamo", "onaj", "servis123", "ne znam ime"]

META = {"author": "agentmujo-team", "quality_tier": "SILVER",
        "source": "fc-slotfilling-v0.4",
        "verification_status": "verified"}


def tool_resp(tool, a):
    if tool == "service_status":
        return json.dumps({"service": a["service"], "status": "active"}, ensure_ascii=False)
    if tool == "service_restart":
        return json.dumps({"service": a["service"], "action": "restart", "result": "ok"}, ensure_ascii=False)
    if tool == "service_logs":
        return json.dumps({"service": a["service"], "lines": a.get("lines", 50),
                           "tail": ["... log linija ..."]}, ensure_ascii=False)
    if tool == "port_check":
        return json.dumps({"port": a["port"], "process": "unknown"}, ensure_ascii=False)
    if tool == "package_query":
        return json.dumps({"package": a["package"], "installed": True, "version": "2.0.1"},
                          ensure_ascii=False)
    if tool == "package_install":
        return json.dumps({"package": a["package"], "result": "ok"}, ensure_ascii=False)
    if tool == "file_list":
        return json.dumps({"path": a["path"], "entries": ["worker.conf", "app.log"]},
                          ensure_ascii=False)
    if tool == "file_read":
        return json.dumps({"path": a["path"], "preview": "... sadrzaj fajla ..."},
                          ensure_ascii=False)
    if tool == "process_list":
        return json.dumps({"top": [{"pid": 2345, "name": "celery"},
                                   {"pid": 678, "name": "gunicorn"}]}, ensure_ascii=False)
    raise ValueError(tool)


def final_text(tool, a):
    if tool == "service_status":
        return f"Servis {a['service']} je aktivan."
    if tool == "service_restart":
        return f"{a['service']} je restartovan."
    if tool == "service_logs":
        return f"Ovo je zadnjih {a.get('lines', 50)} linija loga za {a['service']}."
    if tool == "port_check":
        return f"Provjera porta {a['port']} je zavrsena."
    if tool == "package_query":
        return f"Paket {a['package']} je instaliran (verzija 2.0.1)."
    if tool == "package_install":
        return f"Paket {a['package']} je instaliran."
    if tool == "file_list":
        return f"Sadrzaj direktorija {a['path']} je izlistan."
    if tool == "file_read":
        return f"Prikazan je sadrzaj fajla {a['path']}."
    if tool == "process_list":
        return "Procesi su izlistani po trazenom kriteriju."
    raise ValueError(tool)


def row_2turn(diff, u1, q, u2, tool, args, think=False):
    msgs = [{"role": "user", "content": u1},
            {"role": "assistant", "content": q},
            {"role": "user", "content": u2},
            {"role": "assistant", "content": "Hvala, sad imam sve pa provjeravam.",
             "tool_calls": [{"name": tool, "arguments": args}]},
            {"role": "tool", "content": tool_resp(tool, args)},
            {"role": "assistant", "content": f"Gotovo: {final_text(tool, args)}"}]
    return {"difficulty": diff, "thinking": think, "messages": msgs}


def row_3turn(diff, u1, q1, u2, q2, u3, tool, args, think=False):
    msgs = [{"role": "user", "content": u1},
            {"role": "assistant", "content": q1},
            {"role": "user", "content": u2},
            {"role": "assistant", "content": q2},
            {"role": "user", "content": u3},
            {"role": "assistant", "content": "Hvala, sad imam sve pa provjeravam.",
             "tool_calls": [{"name": tool, "arguments": args}]},
            {"role": "tool", "content": tool_resp(tool, args)},
            {"role": "assistant", "content": f"Gotovo: {final_text(tool, args)}"}]
    return {"difficulty": diff, "thinking": think, "messages": msgs}


def main():
    rng = random.Random(SEED)
    seen = set()
    for fp in (V01, V02, V03):
        for line in fp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                for m in json.loads(line).get("messages", []):
                    if m.get("role") == "user":
                        seen.add(norm(m.get("content", "")))
    ids = []
    for fp in (V01, V02, V03):
        for line in fp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                ids.append(int(json.loads(line)["id"].rsplit("-", 1)[1]))
    nxt = max(ids) + 1

    out_rows = []

    def take(u1cands, q, fam):
        rng.shuffle(u1cands)
        got = []
        for u1 in u1cands:
            if len(got) >= q:
                break
            if norm(u1) in seen:
                continue
            seen.add(norm(u1))
            got.append(u1)
        assert len(got) == q, f"{fam}: {len(got)}/{q}"
        return got

    def pick(tpls, v):
        return rng.choice(tpls).format(v=v)

    # ---- EASY 2-turn (450): jedno nedostajuce required polje
    for u1 in take([c + t for c in CTX for t in SVC_U1], 60, "svc:status"):
        s = rng.choice(SERVICES)
        out_rows.append(row_2turn("easy", u1, rng.choice(Q_SERVICE),
                                  pick(U2_SVC, s), "service_status", {"service": s}))
    for u1 in take([c + t for c in CTX for t in SVC_U1], 60, "svc:restart"):
        s = rng.choice(SERVICES)
        out_rows.append(row_2turn("easy", u1, rng.choice(Q_SERVICE),
                                  pick(U2_SVC, s), "service_restart", {"service": s}))
    for u1 in take([c + t for c in CTX for t in SVC_U1], 60, "svc:logs"):
        s = rng.choice(SERVICES)
        out_rows.append(row_2turn("easy", u1, rng.choice(Q_SERVICE),
                                  pick(U2_SVC, s), "service_logs",
                                  {"service": s, "lines": 50}))
    for u1 in take([c + t for c in CTX for t in PORT_U1], 90, "port"):
        p = rng.choice(PORTS)
        out_rows.append(row_2turn("easy", u1, rng.choice(Q_PORT),
                                  pick(U2_PORT, p), "port_check", {"port": p}))
    for u1 in take([c + t for c in CTX for t in FILE_U1], 45, "file:list"):
        d = rng.choice(DIRS)
        out_rows.append(row_2turn("easy", u1, rng.choice(Q_PATH),
                                  pick(U2_PATH, d), "file_list", {"path": d}))
    for u1 in take([c + t for c in CTX for t in FILE_U1], 45, "file:read"):
        d = rng.choice(DIRS)
        f = DIR_FILE[d]
        out_rows.append(row_2turn("easy", u1, rng.choice(Q_PATH),
                                  pick(U2_PATH, f), "file_read", {"path": f}))
    for u1 in take([c + t for c in CTX for t in PKG_U1], 45, "pkg:query"):
        p = rng.choice(PACKAGES)
        out_rows.append(row_2turn("easy", u1, rng.choice(Q_PKG),
                                  pick(U2_PKG, p), "package_query", {"package": p}))
    for u1 in take([c + t for c in CTX for t in PKG_U1], 45, "pkg:install"):
        p = rng.choice(PACKAGES)
        out_rows.append(row_2turn("easy", u1, rng.choice(Q_PKG),
                                  pick(U2_PKG, p), "package_install", {"package": p}))

    # ---- MEDIUM 2-turn (550): opciona polja, dvosmislenost, potvrda
    log_u1 = [c + t.format(service=s) for c in CTX for t in LINES_U1[:8]
              for s in SERVICES]
    for u1 in take(log_u1, 80, "lines:logs"):
        m = re.search(r"(nginx|apache2|postgresql|mysql|redis|docker|ssh|cron|"
                      r"fail2ban|ufw|ollama|named|gunicorn|celery|prometheus|"
                      r"grafana-server|memcached|rabbitmq-server|elasticsearch|vault)",
                      u1)
        s = m.group(1)
        n = rng.choice(LINES)
        out_rows.append(row_2turn("medium", u1, rng.choice(Q_LINES),
                                  pick(U2_LINES, n), "service_logs",
                                  {"service": s, "lines": n}))
    proc_u1 = [c + t for c in CTX for t in LINES_U1[8:]]
    for u1 in take(proc_u1, 70, "lines:proc"):
        lim = rng.choice([5, 10, 15, 20])
        sb = rng.choice(["cpu", "memory"])
        out_rows.append(row_2turn("medium", u1, rng.choice(Q_LIMIT),
                                  pick(U2_LINES, lim), "process_list",
                                  {"limit": lim, "sort_by": sb}))
    dis_u1 = [c + t.format(label=lab) for c in CTX for t in DISAMBIG_U1
              for lab in AMBIG]
    for u1 in take(dis_u1, 200, "disambig"):
        lab = next(lb for lb in AMBIG if lb in u1.lower())
        a, b = AMBIG[lab]
        s = rng.choice([a, b])
        out_rows.append(row_2turn("medium", u1,
                                  Q_DISAMBIG.format(a=a, b=b),
                                  pick(U2_SVC, s), "service_status", {"service": s}))
    conf_cands = ([c + t.format(service=s) for c in CTX
                   for t in CONFIRM_U1["service_restart"] for s in SERVICES] +
                  [c + t.format(package=p) for c in CTX
                   for t in CONFIRM_U1["package_install"] for p in PACKAGES])
    conf_rows = take(conf_cands, 200, "confirm")
    for u1 in conf_rows:
        m = re.search(r"(nginx|apache2|postgresql|mysql|redis|docker|ssh|cron|"
                      r"fail2ban|ufw|ollama|named|gunicorn|celery|prometheus|"
                      r"grafana-server|memcached|rabbitmq-server|elasticsearch|vault)",
                      u1)
        if m:
            s = m.group(1)
            out_rows.append(row_2turn("medium", u1, Q_CONFIRM_R.format(v=s),
                                      rng.choice(U2_CONFIRM), "service_restart",
                                      {"service": s}))
        else:
            m2 = re.search(r"(ripgrep|bat|htop|curl|git|tmux|jq|ncdu|certbot|"
                           r"glances|httpie|restic)", u1)
            p = m2.group(1)
            out_rows.append(row_2turn("medium", u1, Q_CONFIRM_I.format(v=p),
                                      rng.choice(U2_CONFIRM), "package_install",
                                      {"package": p}))

    # ---- MEDIUM 3-turn (200): dva slot-a redom
    for u1 in take([c + t for c in CTX for t in TWOSLOT_U1], 120, "twoslot"):
        s = rng.choice(SERVICES)
        n = rng.choice(LINES)
        out_rows.append(row_3turn("medium", u1, rng.choice(Q_SERVICE),
                                  pick(U2_SVC, s), rng.choice(Q_LINES),
                                  pick(U3_LINES, n), "service_logs",
                                  {"service": s, "lines": n}))
    for u1 in take([c + t for c in CTX for t in FCHAIN_U1], 80, "fchain"):
        d = rng.choice(DIRS)
        f = DIR_FILE[d]
        out_rows.append(row_3turn("medium", u1, "Koji direktorij tacno?",
                                  pick(U2_PATH, d), "Koji fajl iz tog direktorija?",
                                  pick(U2_PATH, f), "file_read", {"path": f}))

    # ---- HARD 3-turn (300): nevazeca vrijednost + korekcija; disambig + potvrda
    inv_port = take([c + t for c in CTX for t in PORT_INV_U1], 50, "invalid:port")
    for u1 in inv_port:
            bad = rng.choice(BAD_PORTS)
            p = rng.choice(PORTS)
            args = {"port": p}
            msgs = [{"role": "user", "content": u1},
                    {"role": "assistant", "content": rng.choice(Q_PORT)},
                    {"role": "user", "content": bad},
                    {"role": "assistant",
                     "content": Q_CORR_PORT.format(bad=bad)},
                    {"role": "user", "content": pick(U2_PORT, p)},
                    {"role": "assistant", "content": "Hvala, sad imam sve pa provjeravam.",
                     "tool_calls": [{"name": "port_check", "arguments": args}]},
                    {"role": "tool", "content": tool_resp("port_check", args)},
                    {"role": "assistant",
                     "content": f"Gotovo: {final_text('port_check', args)}"}]
            out_rows.append({"difficulty": "hard", "thinking": True, "messages": msgs})

    inv_lines_u1 = [c + t.format(service=s) for c in CTX for t in LINES_U1[:8]
                    for s in SERVICES]
    for u1 in take(inv_lines_u1, 50, "invalid:lines"):
        s = re.search(r"(nginx|apache2|postgresql|mysql|redis|docker|ssh|cron|"
                      r"fail2ban|ufw|ollama|named|gunicorn|celery|prometheus|"
                      r"grafana-server|memcached|rabbitmq-server|elasticsearch|vault)",
                      u1).group(1)
        bad = rng.choice(BAD_LINES)
        n = rng.choice(LINES)
        args = {"service": s, "lines": n}
        msgs = [{"role": "user", "content": u1},
                {"role": "assistant", "content": rng.choice(Q_LINES)},
                {"role": "user", "content": bad},
                {"role": "assistant", "content": Q_CORR_LINES.format(bad=bad)},
                {"role": "user", "content": pick(U2_LINES, n)},
                {"role": "assistant", "content": "Hvala, sad imam sve pa provjeravam.",
                 "tool_calls": [{"name": "service_logs", "arguments": args}]},
                {"role": "tool", "content": tool_resp("service_logs", args)},
                {"role": "assistant",
                 "content": f"Gotovo: {final_text('service_logs', args)}"}]
        out_rows.append({"difficulty": "hard", "thinking": True, "messages": msgs})

    for u1 in take([c + t for c in CTX for t in SVC_U1], 50, "invalid:svc"):
            bad = rng.choice(BAD_SVC)
            s = rng.choice(SERVICES)
            args = {"service": s}
            msgs = [{"role": "user", "content": u1},
                    {"role": "assistant", "content": rng.choice(Q_SERVICE)},
                    {"role": "user", "content": bad},
                    {"role": "assistant", "content": Q_CORR_SVC.format(bad=bad)},
                    {"role": "user", "content": pick(U2_SVC, s)},
                    {"role": "assistant", "content": "Hvala, sad imam sve pa provjeravam.",
                     "tool_calls": [{"name": "service_status", "arguments": args}]},
                    {"role": "tool", "content": tool_resp("service_status", args)},
                    {"role": "assistant",
                     "content": f"Gotovo: {final_text('service_status', args)}"}]
            out_rows.append({"difficulty": "hard", "thinking": True, "messages": msgs})

    dconf_u1 = [c + t.format(label=lab) for c in CTX for t in DCONF_U1
                for lab in AMBIG]
    for u1 in take(dconf_u1, 150, "dconfirm"):
        lab = next(lb for lb in AMBIG if lb in u1.lower())
        a, b = AMBIG[lab]
        s = rng.choice([a, b])
        out_rows.append(row_3turn("hard", u1, Q_DISAMBIG.format(a=a, b=b),
                                  pick(U2_SVC, s), Q_CONFIRM_R.format(v=s),
                                  rng.choice(U2_CONFIRM), "service_restart",
                                  {"service": s}, think=True))

    assert len(out_rows) == 1500, len(out_rows)

    rng.shuffle(out_rows)
    with OUT.open("w", encoding="utf-8") as f:
        for k, r in enumerate(out_rows):
            f.write(json.dumps({
                "id": f"amj-fc-{nxt + k:04d}",
                "version": "0.4.0",
                "language": "bs-ijekavica",
                "task": "function-calling",
                "difficulty": r["difficulty"],
                "enable_thinking": bool(r.get("thinking", False)),
                "messages": r["messages"],
                "metadata": META,
            }, ensure_ascii=False) + "\n")

    diff = {}
    tools = {}
    turns = {}
    for r in out_rows:
        diff[r["difficulty"]] = diff.get(r["difficulty"], 0) + 1
        n_user = sum(1 for m in r["messages"] if m["role"] == "user")
        turns[n_user] = turns.get(n_user, 0) + 1
        for m in r["messages"]:
            for tc in m.get("tool_calls", []) or []:
                tools[tc["name"]] = tools.get(tc["name"], 0) + 1
    print(f"redova: {len(out_rows)}")
    print(f"difficulty: {diff}")
    print(f"user-turnovi: {turns}")
    print(f"alati: {json.dumps(tools, indent=1, ensure_ascii=False)}")
    print(f"prvi id: amj-fc-{nxt:04d}, zadnji: amj-fc-{nxt + len(out_rows) - 1:04d}")


if __name__ == "__main__":
    main()
