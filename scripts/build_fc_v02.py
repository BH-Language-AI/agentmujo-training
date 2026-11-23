#!/usr/bin/env python3
"""Template expansion v0.2 za function-calling dataset.

Generise ~1600 novih redova (deterministicki, seed=42) pokrivajuci svih
14 alata iz configs/tools.yaml. Izlaz: datasets/canonical/function_calling_v0.2.jsonl
Ne dira v0.1 ni datasets/splits/.

Usage: .venv/bin/python scripts/build_fc_v02.py
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

SEED = 42
ROOT = Path(__file__).resolve().parent.parent
V01 = ROOT / "datasets/canonical/function_calling_v0.1.jsonl"
OUT = ROOT / "datasets/canonical/function_calling_v0.2.jsonl"

SERVICES = ["nginx", "apache2", "postgresql", "docker", "ssh", "redis",
            "cron", "fail2ban", "ufw", "ollama", "tailscaled", "snapd",
            "named", "mysql"]
PORTS = [22, 80, 443, 3000, 5432, 6379, 8080, 8000, 11434, 53, 3306, 9090]
PORT_SVC = {22: "ssh", 80: "nginx", 443: "nginx", 3000: "node",
            5432: "postgresql", 6379: "redis", 8080: "nginx", 8000: "gunicorn",
            11434: "ollama", 53: "named", 3306: "mysql", 9090: "prometheus"}
DISK_PATHS = ["/", "/var", "/home", "/tmp", "/opt", "/boot", "/var/log", "/data"]
LOG_LINES = [10, 20, 25, 30, 50, 100, 200]
PROC_LIMITS = [5, 10, 15, 20, 50]
PROC_SORTS = ["cpu", "memory", "pid", "name"]
PACKAGES = ["nginx", "htop", "curl", "git", "tmux", "jq", "ncdu", "mtr",
            "postgresql-client", "redis-tools", "certbot", "glances"]
TERMINAL_CMDS = ["uptime", "free -h", "df -h /", "ss -tlnp", "ip -brief addr",
                 "lsblk -o NAME,SIZE,MOUNTPOINT",
                 "journalctl -p err -n 20 --no-pager",
                 "systemctl list-units --type=service --state=failed --no-pager",
                 "cat /proc/loadavg", "ps aux --sort=-%cpu | head -n 15",
                 "du -sh /var/log", "uname -a", "who",
                 "ls -la /etc/nginx"]
DIRS = ["/var/log", "/etc/nginx", "/home", "/tmp", "/opt", "/var/www",
        "/etc/ssh", "/data", "/etc/postgresql", "/var/backups"]
FILES = ["/etc/nginx/nginx.conf", "/etc/hosts", "/var/log/syslog",
         "/etc/ssh/sshd_config", "/etc/fstab", "/var/log/nginx/error.log",
         "/proc/loadavg", "/etc/postgresql/15/main/postgresql.conf",
         "/etc/crontab", "/etc/resolv.conf"]
DIR_FILE = {"/var/log": "/var/log/syslog", "/etc/nginx": "/etc/nginx/nginx.conf",
            "/home": "/etc/hosts", "/tmp": "/etc/fstab",
            "/opt": "/etc/hosts", "/var/www": "/etc/nginx/nginx.conf",
            "/etc/ssh": "/etc/ssh/sshd_config", "/data": "/etc/fstab",
            "/etc/postgresql": "/etc/postgresql/15/main/postgresql.conf",
            "/var/backups": "/etc/crontab"}
DISK_DIR = {"/": "/var/log", "/var": "/var/log", "/home": "/home",
            "/tmp": "/tmp", "/opt": "/opt", "/boot": "/etc/nginx",
            "/var/log": "/var/log", "/data": "/data"}

TOOLS_ORDER = ["service_status", "service_restart", "service_logs",
               "disk_usage", "memory_usage", "cpu_usage", "process_list",
               "network_status", "port_check", "terminal", "package_query",
               "package_install", "file_list", "file_read"]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


# ---------------------------------------------------------------- user tekstovi
EASY_U = {
 "service_status": ["Kakav je status {service} servisa?",
    "Je li {service} aktivan?", "Radi li {service} servis?",
    "Provjeri status {service} servisa.", "Da li je {service} pokrenut?",
    "Javi mi status {service}.", "Je li {service} gore?",
    "Status servisa {service}?"],
 "service_restart": ["Restartuj {service} servis.", "Restartuj {service}.",
    "Uradi restart {service} servisa.", "Treba mi restart {service}.",
    "Možeš li restartovati {service}?", "Molim te restartuj {service}.",
    "Ponovo pokreni {service}.", "Resetuj {service} restartom."],
 "service_logs": ["Prikaži zadnjih {lines} linija loga za {service}.",
    "Daj mi log {service} servisa, zadnjih {lines} linija.",
    "Šta piše u logu {service}? Daj zadnjih {lines} linija.",
    "Izvadi {lines} linija iz loga {service}.",
    "Treba mi {lines} linija loga za {service}."],
 "disk_usage": ["Koliko je zauzet {path}?", "Provjeri zauzeće diska na {path}.",
    "Ima li mjesta na {path}?", "Koliko prostora ima na {path}?",
    "Prikaži zauzeće za {path}.", "Je li {path} pun?",
    "Daj mi stanje diska na {path}.", "Provjeri slobodan prostor na {path}."],
 "memory_usage": ["Kakvo je stanje memorije na serveru?",
    "Koliko memorije je slobodno?", "Je li memorija pri kraju?",
    "Provjeri iskorištenost memorije.", "Koliko RAM-a je zauzeto?",
    "Daj mi stanje memorije.", "Kakva je potrošnja memorije?",
    "Provjeri ima li dovoljno slobodne memorije.",
    "Koliko je memorije ostalo?", "Je li memorija kritično zauzeta?"],
 "cpu_usage": ["Koliko je CPU opterećen?",
    "Kakvo je opterećenje procesora?", "Je li procesor preopterećen?",
    "Provjeri zauzeće CPU-a.", "Daj mi stanje procesora.",
    "Koliko je procesor zauzet?", "Kakva je potrošnja CPU-a?",
    "Provjeri opterećenje sistema.", "Je li load visok?",
    "Kakav je load average na serveru?"],
 "process_list": ["Izlistaj {limit} procesa sortiranih po {sort}.",
    "Daj mi {limit} procesa sortiranih po {sort}.",
    "Prikaži {limit} procesa (sortirano po {sort}).",
    "Listaj procese, prvih {limit}, sortiraj po {sort}."],
 "network_status": ["Je li mreža na serveru uredna?",
    "Provjeri mrežni status.", "Daj mi mrežni status.",
    "Kakvo je stanje mreže?", "Jesu li mrežni interfejsi aktivni?",
    "Provjeri mrežne interfejse.", "Ima li mrežne konektivnosti?",
    "Je li server dostupan preko mreže?", "Prikaži status mreže.",
    "Kakvi su mrežni interfejsi?"],
 "port_check": ["Ko sluša na portu {port}?", "Šta sluša na portu {port}?",
    "Provjeri port {port}.", "Je li port {port} zauzet?",
    "Koji proces drži port {port}?", "Da li nešto sluša na portu {port}?"],
 "terminal": ["Izvrši `{command}` preko terminala.",
    "Pokreni komandu `{command}`.", "Šta daje komanda `{command}`?",
    "Od radi `{command}` u terminalu.".replace("Od radi", "Odradi"),
    "Možeš li pokrenuti `{command}`?"],
 "package_query": ["Je li paket {package} instaliran?",
    "Provjeri paket {package}.", "Koja verzija {package} je instalirana?",
    "Da li imamo {package}?", "Vidi je li {package} dostupan na sistemu.",
    "Provjeri instalaciju paketa {package}."],
 "package_install": ["Instaliraj paket {package}.",
    "Treba mi {package}, instaliraj ga.", "Dodaj paket {package}.",
    "Instaliraj {package} alat.", "Možeš li instalirati {package}?",
    "Postavi {package} na server."],
 "file_list": ["Izlistaj sadržaj {path}.", "Šta ima u {path}?",
    "Prikaži fajlove u {path}.", "Listaj direktorij {path}.",
    "Koji fajlovi su u {path}?", "Daj mi sadržaj direktorija {path}."],
 "file_read": ["Pročitaj fajl {path}.", "Prikaži sadržaj {path}.",
    "Šta piše u {path}?", "Otvori {path} i prikaži prvih {lines} linija.",
    "Daj mi prvih {lines} linija iz {path}."],
}

EASY_CTX = ["", "Prije nastavka rada. ", "Usput dok si tu. ",
            "Za redovni izvještaj. ", "Na brzinu. ", "Za evidenciju. "]
MED_CTX = ["Server je usporen. ", "Prije deploya nove verzije. ",
           "Nakon restarta servera. ", "Korisnici prijavljuju problem. ",
           "Radim večernju provjeru. ", "Sumnjam na anomaliju. ",
           "Prije backup prozora. ", "Load je neuobičajen. "]

HARD_U = {
 "service_status": ["{Service} ne odgovara. Provjeri status {service} pa pogledaj i zadnjih {lines} linija loga.",
    "{Service} se ruši. Daj mi status i zadnjih {lines} linija loga.",
    "Sumnjam da je {service} pao. Provjeri status pa potvrdi logom ({lines} linija).",
    "Aplikacija iza {service} ne radi. Prvo status {service}, pa {lines} linija loga.",
    "Nakon nadogradnje {service} ne starta. Provjeri status i log ({lines} linija).",
    "Monitoring javlja {service} down. Provjeri status pa izvadi {lines} linija loga."],
 "service_restart": ["{Service} je zaglavio. Provjeri status {service} pa ga restartuj.",
    "{Service} ne prima konekcije. Prvo status, pa restart {service}.",
    "Izmijenio sam konfiguraciju {service}. Provjeri status pa restartuj da primijeni izmjene.",
    "{Service} troši previše resursa. Provjeri status pa ga restartuj.",
    "Log {service} je pun grešaka. Provjeri status pa restartuj {service}.",
    "Deploy je gotov. Provjeri status {service} pa uradi restart."],
 "service_logs": ["{Service} prijavljuje greške. Provjeri status {service} pa izvadi {lines} linija loga.",
    "Nešto ne štima sa {service}. Prvo status, pa {lines} linija loga.",
    "{Service} se restartovao sam. Provjeri status pa pogledaj {lines} linija loga.",
    "Korisnici se žale na {service}. Status pa {lines} linija loga, molim.",
    "Nakon restarta {service} opet pada. Provjeri status i {lines} linija loga.",
    "Provjeri je li {service} aktivan i šta kaže zadnjih {lines} linija loga."],
 "disk_usage": ["Disk na {path} je pri kraju. Provjeri zauzeće {path} pa izlistaj {dir} da vidim šta troši.",
    "Nestaje prostora na {path}. Daj zauzeće {path} i sadržaj {dir}.",
    "Backup ne staje na {path}. Provjeri zauzeće pa pogledaj šta je u {dir}.",
    "Upozorenje za disk {path}. Provjeri stanje pa izlistaj {dir}.",
    "Logovi pune {path}. Koliko je zauzet {path} i šta ima u {dir}?",
    "Prije čišćenja provjeri zauzeće {path} i sadržaj {dir}."],
 "memory_usage": ["Server je spor. Provjeri memoriju pa izlistaj top {limit} potrošača po memoriji.",
    "Sumnjam na curenje memorije. Daj stanje memorije i prvih {limit} procesa po memoriji.",
    "Aplikacija puca bez greške. Provjeri memoriju pa top {limit} po memoriji.",
    "OOM killer se javljao. Kakva je memorija i koji procesi ({limit}) je najviše troše?",
    "Prije pokretanja novog servisa provjeri memoriju i top {limit} potrošača.",
    "Memorija raste danima. Daj stanje memorije i prvih {limit} po potrošnji."],
 "cpu_usage": ["Load je visok. Provjeri CPU pa izlistaj top {limit} potrošača po CPU-u.",
    "Server ne odgovara. Kakav je CPU i koji procesi ({limit}) ga najviše troše?",
    "Ventilatori bruje. Provjeri opterećenje CPU-a i top {limit} procesa.",
    "Monitoring javlja visok load. Daj CPU stanje i prvih {limit} po CPU-u.",
    "Nešto guta procesor. Provjeri CPU pa top {limit} potrošača.",
    "Prije stress testa provjeri CPU i izlistaj {limit} najvećih potrošača."],
 "process_list": ["Sistem je trom. Provjeri memoriju pa izlistaj {limit} procesa po {sort_by}.",
    "Nešto ne štima. Daj stanje CPU-a pa {limit} procesa sortiranih po {sort_by}.",
    "Sumnjam na zagušenje. Provjeri memoriju i izlistaj {limit} procesa po {sort_by}.",
    "Server se vuče. Kakav je CPU i koji su top {limit} po {sort_by}?",
    "Prije restarta servisa snimi stanje: memorija plus {limit} procesa po {sort_by}.",
    "Za izvještaj trebam memoriju i {limit} procesa sortiranih po {sort_by}."],
 "network_status": ["Ne mogu pristupiti serveru. Provjeri mrežu pa vidi ko sluša na portu {port}.",
    "Konekcije pucaju. Daj mrežni status i provjeri port {port}.",
    "Sumnjam na prekid mreže. Provjeri interfejse pa port {port}.",
    "Servis iza porta {port} nedostupan. Prvo mreža, pa provjera porta {port}.",
    "VPN ne radi. Provjeri mrežni status i ko sluša na portu {port}.",
    "Latency je visok. Daj stanje mreže i provjeri port {port}."],
 "port_check": ["Port {port} je zauzet. Provjeri ko sluša na {port} pa daj status {service}.",
    "{Service} se ne može vezati za port {port}. Ko sluša na {port} i kakav je status {service}?",
    "Konflikt na portu {port}. Provjeri proces na {port} pa status {service}.",
    "Nešto drži port {port}. Identifikuj proces pa provjeri status {service}.",
    "Prije podizanja {service} provjeri port {port} i status {service}.",
    "Dvije aplikacije ciljaju port {port}. Ko sluša i radi li {service}?"],
 "terminal": ["Server prijavljuje failed servise ({topic}). Izlistaj ih pa daj zadnje greške iz journala.",
    "Sumnjam na problem s diskom ({topic}). Provjeri zauzeće pa najveće potrošače u /var/log.",
    "Mreža je sumnjiva ({topic}). Prikaži socket listenere pa stanje interfejsa.",
    "Load je visok ({topic}). Daj load average pa top potrošače CPU-a.",
    "Provjeri ima li mjesta za deploy ({topic}): stanje diska pa sadržaj ciljanog direktorija.",
    "Dijagnostika prije restarta ({topic}): uptime, failed servisi i zadnje greške."],
 "package_query": ["Treba mi {package}. Provjeri je li instaliran pa ga instaliraj ako fali.",
    "Deploy traži {package}. Prvo provjeri instalaciju pa instaliraj {package}.",
    "Skripta puca jer nema {package}. Provjeri paket pa ga instaliraj.",
    "Novi alat {package} nam treba. Vidi je li tu, ako nije instaliraj ga.",
    "Prije builda provjeri {package} i instaliraj ako nedostaje.",
    "Kolega kaže da fali {package}. Provjeri pa instaliraj."],
 "package_install": ["Za monitoring treba {package}. Provjeri je li tu pa instaliraj {package}.",
    "Nedostaje {package} na serveru. Prvo provjera, pa instalacija {package}.",
    "Setup zahtijeva {package}. Vidi status paketa pa ga instaliraj.",
    "Stigao zahtjev za {package}. Provjeri instalaciju pa instaliraj.",
    "Prije migracije osiguraj {package}: provjeri pa instaliraj.",
    "Novi član tima treba {package}. Provjeri i instaliraj."],
 "file_list": ["Tražim veliki log. Izlistaj {dir} pa pročitaj {file}.",
    "Konfiguracija ne valja. Listaj {dir} pa otvori {file}.",
    "Provjeri šta ima u {dir} pa mi prikaži {file}.",
    "Sumnjam na pun direktorij {dir}. Izlistaj ga pa pročitaj {file}.",
    "Prije izmjena pogledaj sadržaj {dir} i trenutni {file}.",
    "Audit traži pregled: izlistaj {dir} pa prikaži {file}."],
 "file_read": ["Provjeri konfiguraciju. Izlistaj {dir} pa pročitaj {file}.",
    "Nešto ne radi. Pogledaj šta ima u {dir} pa otvori {file}.",
    "Trebam sadržaj {file}. Prvo izlistaj {dir} pa ga pročitaj.",
    "Validiraj postavke: listaj {dir}, čitaj {file}.",
    "Prije restarta provjeri {file}. Prvo izlistaj {dir} pa ga otvori.",
    "Debugiram servis. Izlistaj {dir} pa prikaži {file}."],
}

EASY_ARGSETS = {
 "service_status": [{"service": s} for s in SERVICES],
 "service_restart": [{"service": s} for s in SERVICES],
 "service_logs": [{"service": s, "lines": n} for s in SERVICES for n in LOG_LINES],
 "disk_usage": [{"path": p} for p in DISK_PATHS],
 "memory_usage": [{}],
 "cpu_usage": [{}],
 "process_list": [{"limit": l, "sort_by": s} for l in PROC_LIMITS for s in PROC_SORTS],
 "network_status": [{}],
 "port_check": [{"port": p} for p in PORTS],
 "terminal": [{"command": c} for c in TERMINAL_CMDS],
 "package_query": [{"package": p} for p in PACKAGES],
 "package_install": [{"package": p} for p in PACKAGES],
 "file_list": [{"path": d} for d in DIRS],
 "file_read": [{"path": f} for f in FILES] + [{"path": f, "lines": n} for f in FILES for n in (20, 50, 100)],
}

EASY_ASST = ["Provjeravam.", "Odmah provjeravam.", "Evo provjere.",
             "Provjeravam stanje.", "Idem provjeriti."]
MED_ASST = ["Krećem od provjere.", "Prvo provjeravam navedeno.",
            "Provjeravam pa javljam nalaz.", "Idem korak po korak."]


def fmt_args(tool, a):
    if tool == "process_list":
        lab = {"cpu": "CPU-u", "memory": "memoriji", "pid": "PID-u",
               "name": "imenu"}[a["sort_by"]]
        return {"limit": a["limit"], "sort": lab}
    if tool == "file_read" and "lines" not in a:
        return dict(a, lines=50)
    return dict(a)


def tool_resp(tool, a):
    if tool == "service_status":
        return json.dumps({"service": a["service"], "status": "active"}, ensure_ascii=False)
    if tool == "service_restart":
        return json.dumps({"service": a["service"], "action": "restart", "result": "ok"}, ensure_ascii=False)
    if tool == "service_logs":
        return json.dumps({"service": a["service"], "lines": a.get("lines", 50),
                           "tail": ["... log linija ..."]}, ensure_ascii=False)
    if tool == "disk_usage":
        return json.dumps({"path": a.get("path", "/"), "used_pct": 63, "avail": "17G"}, ensure_ascii=False)
    if tool == "memory_usage":
        return json.dumps({"mem_pct": 38, "available": "12G"}, ensure_ascii=False)
    if tool == "cpu_usage":
        return json.dumps({"cpu_pct": 21}, ensure_ascii=False)
    if tool == "process_list":
        return json.dumps({"top": [{"pid": 1234, "name": "python3"},
                                   {"pid": 567, "name": "nginx"}]}, ensure_ascii=False)
    if tool == "network_status":
        return json.dumps({"interfaces": {"up": ["eth0"]}}, ensure_ascii=False)
    if tool == "port_check":
        proc = {"22": "sshd", "80": "nginx", "443": "nginx",
                "5432": "postgres", "6379": "redis"}.get(str(a["port"]))
        return json.dumps({"port": a["port"], "process": proc}, ensure_ascii=False)
    if tool == "terminal":
        return json.dumps({"result": "ok", "output": "... izlaz komande ..."}, ensure_ascii=False)
    if tool == "package_query":
        return json.dumps({"package": a["package"], "installed": True,
                           "version": "1.2.3"}, ensure_ascii=False)
    if tool == "package_install":
        return json.dumps({"package": a["package"], "result": "ok"}, ensure_ascii=False)
    if tool == "file_list":
        return json.dumps({"path": a["path"], "entries": ["app.conf", "error.log"]}, ensure_ascii=False)
    if tool == "file_read":
        return json.dumps({"path": a["path"], "preview": "... sadržaj fajla ..."}, ensure_ascii=False)
    raise ValueError(tool)


def final_text(tool, a):
    if tool == "service_status":
        return f"Servis {a['service']} je aktivan."
    if tool == "service_restart":
        return f"{a['service']} je restartovan. Provjeri status ako želiš potvrdu."
    if tool == "service_logs":
        return f"Ovo je zadnjih {a.get('lines', 50)} linija loga za {a['service']}."
    if tool == "disk_usage":
        return f"Zauzeće na {a.get('path', '/')} je 63% (slobodno 17G)."
    if tool == "memory_usage":
        return "Memorija je na 38% (slobodno 12G), uredno."
    if tool == "cpu_usage":
        return "Opterećenje procesora je 21%, uredno."
    if tool == "process_list":
        return "Procesi su izlistani sortirano po traženom kriteriju."
    if tool == "network_status":
        return "Mrežni interfejsi su aktivni."
    if tool == "port_check":
        return f"Provjera porta {a['port']} je gotova, rezultat je iznad."
    if tool == "terminal":
        return "Komanda je izvršena, izlaz je iznad."
    if tool == "package_query":
        return f"Paket {a['package']} je instaliran (verzija 1.2.3)."
    if tool == "package_install":
        return f"Paket {a['package']} je instaliran."
    if tool == "file_list":
        return f"Sadržaj direktorija {a['path']} je izlistan."
    if tool == "file_read":
        return f"Prikazan je sadržaj fajla {a['path']}."
    raise ValueError(tool)


def hard_calls(tool, a, rng):
    """Vrati (call1, resp1, call2, resp2) za hard uzorke."""
    if tool == "service_status":
        c1 = ("service_status", {"service": a["service"]})
        c2 = ("service_logs", {"service": a["service"], "lines": a["lines"]})
    elif tool == "service_restart":
        c1 = ("service_status", {"service": a["service"]})
        c2 = ("service_restart", {"service": a["service"]})
    elif tool == "service_logs":
        c1 = ("service_status", {"service": a["service"]})
        c2 = ("service_logs", {"service": a["service"], "lines": a["lines"]})
    elif tool == "disk_usage":
        c1 = ("disk_usage", {"path": a["path"]})
        c2 = ("file_list", {"path": DISK_DIR[a["path"]]})
    elif tool == "memory_usage":
        c1 = ("memory_usage", {})
        c2 = ("process_list", {"limit": a["limit"], "sort_by": "memory"})
    elif tool == "cpu_usage":
        c1 = ("cpu_usage", {})
        c2 = ("process_list", {"limit": a["limit"], "sort_by": "cpu"})
    elif tool == "process_list":
        c1 = ("memory_usage", {}) if a["sort_by"] in ("memory", "name") else ("cpu_usage", {})
        c2 = ("process_list", {"limit": a["limit"], "sort_by": a["sort_by"]})
    elif tool == "network_status":
        c1 = ("network_status", {})
        c2 = ("port_check", {"port": a["port"]})
    elif tool == "port_check":
        c1 = ("port_check", {"port": a["port"]})
        c2 = ("service_status", {"service": PORT_SVC[a["port"]]})
    elif tool == "terminal":
        c1 = ("terminal", {"command": a["cmd1"]})
        c2 = ("terminal", {"command": a["cmd2"]})
    elif tool in ("package_query", "package_install"):
        c1 = ("package_query", {"package": a["package"]})
        c2 = ("package_install", {"package": a["package"]})
    elif tool in ("file_list", "file_read"):
        c1 = ("file_list", {"path": a["dir"]})
        c2 = ("file_read", {"path": a["file"]})
    else:
        raise ValueError(tool)
    return c1, c2


HARD_ARGSETS = {
 "service_status": [{"service": s, "lines": n, "Service": s.capitalize()} for s in SERVICES for n in (30, 50, 100)],
 "service_restart": [{"service": s, "Service": s.capitalize()} for s in SERVICES],
 "service_logs": [{"service": s, "lines": n, "Service": s.capitalize()} for s in SERVICES for n in (30, 50, 100)],
 "disk_usage": [{"path": p, "dir": DISK_DIR[p]} for p in DISK_PATHS],
 "memory_usage": [{"limit": n} for n in (5, 10, 15, 20)],
 "cpu_usage": [{"limit": n} for n in (5, 10, 15, 20)],
 "process_list": [{"limit": n, "sort_by": s} for n in (5, 10, 20) for s in PROC_SORTS],
 "network_status": [{"port": p} for p in PORTS],
 "port_check": [{"port": p, "service": PORT_SVC[p], "Service": PORT_SVC[p].capitalize()} for p in PORTS],
 "terminal": [{"topic": "failed servisi", "cmd1": "systemctl list-units --type=service --state=failed --no-pager",
               "cmd2": "journalctl -p err -n 20 --no-pager"},
              {"topic": "zauzeće diska", "cmd1": "df -h /", "cmd2": "du -sh /var/log/* 2>/dev/null | sort -rh | head -n 10"},
              {"topic": "socketi i interfejsi", "cmd1": "ss -tlnp", "cmd2": "ip -brief addr"},
              {"topic": "visok load", "cmd1": "cat /proc/loadavg", "cmd2": "ps aux --sort=-%cpu | head -n 15"},
              {"topic": "prostor za deploy", "cmd1": "df -h /data", "cmd2": "ls -la /data"},
              {"topic": "stanje pred restart", "cmd1": "uptime", "cmd2": "systemctl list-units --type=service --state=failed --no-pager"}],
 "package_query": [{"package": p} for p in PACKAGES],
 "package_install": [{"package": p} for p in PACKAGES],
 "file_list": [{"dir": d, "file": DIR_FILE[d]} for d in DIRS],
 "file_read": [{"dir": d, "file": DIR_FILE[d]} for d in DIRS],
}

META = {"author": "agentmujo-team", "quality_tier": "SILVER",
        "source": "template-expansion-v0.2",
        "verification_status": "auto-validated"}


def build_easy(tool, rng):
    rows = []
    for t in EASY_U[tool]:
        for a in EASY_ARGSETS[tool]:
            for ctx in EASY_CTX:
                try:
                    u = ctx + t.format(**fmt_args(tool, a))
                except (KeyError, IndexError):
                    continue
                rows.append((u, a))
    return rows


def build_medium(tool, rng):
    rows = []
    for t in EASY_U[tool]:
        for a in EASY_ARGSETS[tool]:
            for ctx in MED_CTX:
                try:
                    u = ctx + t.format(**fmt_args(tool, a))
                except (KeyError, IndexError):
                    continue
                rows.append((u, a))
    return rows


def build_hard(tool, rng):
    rows = []
    for t in HARD_U[tool]:
        for a in HARD_ARGSETS[tool]:
            try:
                u = t.format(**a)
            except (KeyError, IndexError):
                continue
            rows.append((u, a))
    return rows


def main():
    rng = random.Random(SEED)
    seen = set()
    for line in V01.read_text(encoding="utf-8").splitlines():
        if line.strip():
            obj = json.loads(line)
            for m in obj.get("messages", []):
                if m.get("role") == "user":
                    seen.add(norm(m.get("content", "")))
    ids = [int(json.loads(l)["id"].rsplit("-", 1)[1])
           for l in V01.read_text(encoding="utf-8").splitlines() if l.strip()]
    nxt = max(ids) + 1

    out_rows = []
    easy_n = med_n = hard_n = 0
    tool_counts: dict[str, int] = {}
    diff_counts = {"easy": 0, "medium": 0, "hard": 0}

    for i, tool in enumerate(TOOLS_ORDER):
        qe, qm, qh = (58 if i < 2 else 57), 40, (18 if i < 2 else 17)

        # EASY: user + assistant(tool_call)
        cands = build_easy(tool, rng)
        rng.shuffle(cands)
        got = 0
        for u, a in cands:
            if got >= qe:
                break
            if norm(u) in seen:
                continue
            seen.add(norm(u))
            asst = rng.choice(EASY_ASST) if tool in ("memory_usage", "cpu_usage", "network_status") \
                else f"Provjeravam {tool}."
            if tool == "service_status":
                asst = f"Provjeravam status {a['service']} servisa."
            elif tool == "service_restart":
                asst = f"Restartujem {a['service']} servis."
            elif tool == "service_logs":
                asst = f"Pribavljam log {a['service']} servisa."
            elif tool == "disk_usage":
                asst = f"Provjeravam zauzeće {a.get('path', '/')}."
            elif tool == "memory_usage":
                asst = "Provjeravam iskorištenost memorije."
            elif tool == "cpu_usage":
                asst = "Provjeravam opterećenje procesora."
            elif tool == "process_list":
                asst = "Listam procese po traženom kriteriju."
            elif tool == "network_status":
                asst = "Provjeravam status mreže."
            elif tool == "port_check":
                asst = f"Provjeravam koji proces sluša na portu {a['port']}."
            elif tool == "terminal":
                asst = "Izvršavam komandu preko terminala."
            elif tool == "package_query":
                asst = f"Provjeravam paket {a['package']}."
            elif tool == "package_install":
                asst = f"Instaliram paket {a['package']}."
            elif tool == "file_list":
                asst = f"Listam sadržaj {a['path']}."
            elif tool == "file_read":
                asst = f"Čitam fajl {a['path']}."
            args = {k: v for k, v in a.items() if k not in ("Service",)}
            if tool == "file_read" and "lines" not in args:
                pass  # lines ima default, path je dovoljan
            out_rows.append({"tool": tool, "difficulty": "easy",
                             "messages": [
                                 {"role": "user", "content": u},
                                 {"role": "assistant", "content": asst,
                                  "tool_calls": [{"name": tool, "arguments": args}]}]})
            got += 1
        assert got == qe, f"{tool} easy: {got}/{qe}"

        # MEDIUM: user + assistant(call) + tool + assistant(final)
        cands = build_medium(tool, rng)
        rng.shuffle(cands)
        got = 0
        for u, a in cands:
            if got >= qm:
                break
            if norm(u) in seen:
                continue
            seen.add(norm(u))
            args = {k: v for k, v in a.items() if k not in ("Service",)}
            out_rows.append({"tool": tool, "difficulty": "medium",
                             "messages": [
                                 {"role": "user", "content": u},
                                 {"role": "assistant", "content": rng.choice(MED_ASST),
                                  "tool_calls": [{"name": tool, "arguments": args}]},
                                 {"role": "tool", "content": tool_resp(tool, args)},
                                 {"role": "assistant", "content": final_text(tool, args)}]})
            got += 1
        assert got == qm, f"{tool} medium: {got}/{qm}"

        # HARD: 2 tool poziva (H1 jedan odgovor / H2 iz konteksta, naizmjenicno)
        cands = build_hard(tool, rng)
        rng.shuffle(cands)
        got = 0
        for u, a in cands:
            if got >= qh:
                break
            if norm(u) in seen:
                continue
            seen.add(norm(u))
            (n1, a1), (n2, a2) = hard_calls(tool, a, rng)
            if got % 2 == 0:  # H1: oba poziva u jednom odgovoru
                msgs = [
                    {"role": "user", "content": u},
                    {"role": "assistant", "content": "Krećem od prve provjere pa odmah radim i drugu, da ne gubimo vrijeme.",
                     "tool_calls": [{"name": n1, "arguments": a1},
                                   {"name": n2, "arguments": a2}]},
                    {"role": "tool", "content": tool_resp(n1, a1)},
                    {"role": "tool", "content": tool_resp(n2, a2)},
                    {"role": "assistant", "content": f"Gotovo: {final_text(n1, a1)} {final_text(n2, a2)}"}]
            else:  # H2: drugi poziv s parametrom iz konteksta prvog
                msgs = [
                    {"role": "user", "content": u},
                    {"role": "assistant", "content": "Prvo provjeravam početno stanje pa na osnovu nalaza idem dalje.",
                     "tool_calls": [{"name": n1, "arguments": a1}]},
                    {"role": "tool", "content": tool_resp(n1, a1)},
                    {"role": "assistant", "content": "Na osnovu gornjeg nalaza radim sljedeći korak.",
                     "tool_calls": [{"name": n2, "arguments": a2}]},
                    {"role": "tool", "content": tool_resp(n2, a2)},
                    {"role": "assistant", "content": f"Zaključak: {final_text(n1, a1)} {final_text(n2, a2)}"}]
            out_rows.append({"tool": tool, "difficulty": "hard", "messages": msgs,
                             "thinking": True})
            got += 1
        assert got == qh, f"{tool} hard: {got}/{qh}"

    rng.shuffle(out_rows)
    with OUT.open("w", encoding="utf-8") as f:
        for k, r in enumerate(out_rows):
            f.write(json.dumps({
                "id": f"amj-fc-{nxt + k:04d}",
                "version": "0.2.0",
                "language": "bs-ijekavica",
                "task": "function-calling",
                "difficulty": r["difficulty"],
                "enable_thinking": bool(r.get("thinking", False)),
                "messages": r["messages"],
                "metadata": META,
            }, ensure_ascii=False) + "\n")

    # distribucije
    for r in out_rows:
        diff_counts[r["difficulty"]] += 1
        for m in r["messages"]:
            for tc in m.get("tool_calls", []) or []:
                tool_counts[tc["name"]] = tool_counts.get(tc["name"], 0) + 1
    print(f"redova: {len(out_rows)}")
    print(f"difficulty: {diff_counts}")
    print(f"alati: {json.dumps(tool_counts, indent=1, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
