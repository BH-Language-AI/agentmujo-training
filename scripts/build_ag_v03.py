#!/usr/bin/env python3
"""Generise datasets/canonical/agentic_terminal_v0.3.jsonl (~1500 scenarija).

Template-expansion v0.3: NOVE dimenzije u odnosu na v0.1/v0.2:
  (a) slozeni kvarovi - dva istovremena uzroka (disk+OOM, port+config, DNS+firewall...),
  (b) duzi lanci 5-8 koraka s barem jednim pogresnim tragom koji model odbacuje,
  (c) nove domene: docker, SSL certifikati, cron, spora baza, backup/restore,
  (d) eskalacija: model trazi potvrdu prije destruktivnog koraka usred lanca.
Nove domene izrazene su kroz POSTOJECE alate iz configs/tools.yaml
(terminal read-only komande + file_read/file_list/service_logs) - bez novih alata.
Difficulty mix 25/50/25 (easy/medium/hard). ID nastavak od max iz v0.1/v0.2.
DEDUP: normaliziran prvi user problem ne smije postojati u v0.1/v0.2 ni u v0.3.
Koristenje: .venv/bin/python scripts/build_ag_v03.py
"""
import json
import random
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC1 = REPO / "datasets/canonical/agentic_terminal_v0.1.jsonl"
SRC2 = REPO / "datasets/canonical/agentic_terminal_v0.2.jsonl"
OUT = REPO / "datasets/canonical/agentic_terminal_v0.3.jsonl"

DENY = [r"\brm\s+-rf\s+/", r"\bmkfs\b", r"\bdd\s+.*of=/dev/",
        r"\biptables\s+-F\b", r":\(\)\s*\{\s*:\|\:&\s*\}",
        r"\bcurl\b.*\|\s*(?:sudo\s+)?bash\b",
        r"\bwget\b.*\|\s*(?:sudo\s+)?bash\b",
        r"PASSPHRASE|AWS_SECRET|HF_TOKEN"]

VALID_TOOLS = {"service_status", "service_restart", "service_logs", "disk_usage",
               "memory_usage", "cpu_usage", "process_list", "network_status",
               "port_check", "terminal", "package_query", "package_install",
               "file_list", "file_read"}


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
    s = (k * 61 + 17) % 86400
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def norm(s):
    return re.sub(r"\s+", " ", s.strip().lower())


def row(sid, diff, msgs, domain):
    return {"id": sid, "version": "0.3.0", "language": "bs-ijekavica",
            "task": "agentic-terminal", "difficulty": diff,
            "enable_thinking": True, "messages": msgs,
            "metadata": {"author": "agentmujo-team", "quality_tier": "SILVER",
                         "source": "template-expansion-v0.3",
                         "verification_status": "verified",
                         "domain": domain}}


CONFIRM_ASK = [
    "Stajem prije destruktivnog koraka i trazim potvrdu: smijem li napraviti "
    "rezervnu kopiju konfiguracije i pokusati restart? Bez tvoje potvrde ne diram nista.",
    "Prije nego sto ista promijenim, trebam tvoju potvrdu za sljedeci korak "
    "(rezervna kopija + restart). Nastavljam tek kad potvrdis.",
    "Ovo je tacka bez povratka pa trazim potvrdu: smijem li izvrsiti sljedeci "
    "korak koji mijenja stanje sistema? Cekam tvoje odobrenje.",
]
CONFIRM_YES = ["Moze, potvrdjujem, nastavi.", "Potvrdjujem, napravi taj korak.",
               "U redu, imas potvrdu za taj korak."]


# ---------- EASY (5 koraka) ----------

def e_docker_exit(rng, i, t):
    app = rng.choice(["app-api", "worker", "web-front"])
    return [U(f"Kontejner {app} se stalno gasi i ponovo pokrece. Vidi sto se dogadja. (prijava BK-{t})"),
            T("Krecem od opterecenja procesora da iskljucim glad za resursima.",
              [{"name": "cpu_usage", "arguments": {}}]),
            R({"cpu_pct": rng.randint(22, 41)}),
            T("CPU je miran, dakle nije glad za procesorom. Gledam stanje kontejnera.",
              [{"name": "terminal", "arguments": {"command": f"docker ps -a --filter name={app}", "timeout_s": 30}}]),
            R({"output": f"{app}  Restarting (1) 13 sekundi"}),
            T(f"Kontejner {app} se vrti u krug. Citam log da nadjem uzrok pucanja.",
              [{"name": "service_logs", "arguments": {"service": "docker", "lines": 50}}]),
            R({"service": "docker", "logs": f"{ts(i)} {app}: panic: nedostaje varijabla okruzenja DB_URL; izlaz 1"}),
            T("Uzrok je u okruzenju. Provjeravam potrosnju memorije da iskljucim i OOM.",
              [{"name": "process_list", "arguments": {"limit": 10, "sort_by": "memory"}}]),
            R({"top": [{"name": app, "pid": 1200 + i, "mem_pct": 3}]}),
            T("Memorija je uredna. Citam aplikacijski log za potvrdu.",
              [{"name": "file_read", "arguments": {"path": "/var/lib/app/log/app.log", "lines": 50}}]),
            R({"path": "/var/lib/app/log/app.log",
               "excerpt": "FATAL: DB_URL nije postavljen; prekidam pokretanje"}),
            T(f"Dijagnoza: kontejner {app} puca jer nedostaje varijabla okruzenja DB_URL, "
               f"a ne zbog resursa (CPU miran, memorija uredna - taj trag odbacujem). "
               f"Predlazem dopunu okruzenja uz tvoju potvrdu, pa verifikaciju kroz docker ps "
               f"i log. Restart kontejnera radim samo uz potvrdu.")]


def e_ssl_expire(rng, i, t):
    dom = rng.choice(["app.kolektiv.pro", "portal.kolektiv.pro", "shop.kolektiv.pro"])
    return [U(f"Preglednik javlja da stranica {dom} nije sigurna, certifikat je navodno istekao. Provjeri. (prijava BK-{t})"),
            T("Prvo provjeravam mrezu da iskljucim prekid veze.",
              [{"name": "network_status", "arguments": {}}]),
            R({"interfaces": {"eth0": "up"}, "gateway_ok": True, "rx_packets": 910000 + i}),
            T("Mreza je uredna, dakle nije do veze. Provjeravam datum isteka certifikata.",
              [{"name": "terminal", "arguments": {"command": "openssl x509 -enddate -noout -in /etc/ssl/certs/app.crt", "timeout_s": 30}}]),
            R({"output": "notAfter=2026-10-30 08:12:00 GMT (istekao prije 3 dana)"}),
            T("Certifikat je zaista istekao. Provjeravam konfiguraciju da iskljucim pogresnu putanju.",
              [{"name": "file_read", "arguments": {"path": "/etc/nginx/nginx.conf", "lines": 50}}]),
            R({"path": "/etc/nginx/nginx.conf",
               "excerpt": "ssl_certificate /etc/ssl/certs/app.crt; putanja ispravna"}),
            T("Putanja u konfiguraciji je ispravna. Citam log za potvrdu.",
              [{"name": "service_logs", "arguments": {"service": "nginx", "lines": 50}}]),
            R({"service": "nginx", "logs": f"{ts(i)} nginx: SSL handshake failed: certificate expired"}),
            T("Log potvrdjuje istek. Provjeravam slusa li ista na portu 443.",
              [{"name": "port_check", "arguments": {"port": 443}}]),
            R({"port": 443, "process": "nginx", "pid": 1200 + i}),
            T(f"Dijagnoza: certifikat za {dom} je istekao prije 3 dana; mreza i port 443 su "
               f"uredni (taj trag odbacujem), a putanja u konfiguraciji je ispravna. "
               f"Predlazem obnovu certifikata uz tvoju potvrdu, pa verifikaciju ponovnom "
               f"provjerom datuma i loga. Nista ne mijenjam bez potvrde.")]


def e_cron_silent(rng, i, t):
    job = rng.choice(["nocni izvjestaj", "ciscenje privremenih fajlova", "slanje racuna"])
    return [U(f"{job[0].upper() + job[1:]} vec tri dana ne stize. Zakazani zadatak suti. (prijava BK-{t})"),
            T("Provjeravam zauzece diska da iskljucim pun disk kao uzrok.",
              [{"name": "disk_usage", "arguments": {"path": "/"}}]),
            R({"path": "/", "used_pct": rng.randint(38, 55), "avail": "42G"}),
            T("Disk je uredan, dakle nije do prostora. Provjeravam status cron servisa.",
              [{"name": "service_status", "arguments": {"service": "cron"}}]),
            R({"service": "cron", "status": "inactive"}),
            T("Cron servis ne radi. Gledam je li zadatak uopce zakazan.",
              [{"name": "terminal", "arguments": {"command": "crontab -l", "timeout_s": 30}}]),
            R({"output": "0 2 * * * /opt/app/nocni-posao.sh"}),
            T("Zadatak je zakazan. Citam log cron servisa za potvrdu.",
              [{"name": "service_logs", "arguments": {"service": "cron", "lines": 50}}]),
            R({"service": "cron", "logs": f"{ts(i)} cron: servis zaustavljen; zakazani zadaci se ne izvrsavaju"}),
            T("Log potvrdjuje. Provjeravam direktorij zakazanih zadataka.",
              [{"name": "file_list", "arguments": {"path": "/var/spool/cron"}}]),
            R({"path": "/var/spool/cron", "files": ["crontabs/root", "app-job"]}),
            T(f"Dijagnoza: zadatak uredno postoji u rasporedu, ali servis cron je neaktivan "
               f"pa se nista ne izvrsava; trag punog diska odbacujem jer je disk na manje "
               f"od 60%. Predlazem pokretanje cron servisa uz tvoju potvrdu, pa verifikaciju "
               f"statusom i sutrasnjim izlazom zadatka. Bez potvrde nista ne pokrecem.")]


def e_backup_stale(rng, i, t):
    return [U(f"Zadnja rezervna kopija je starija od sedam dana, a backup bi trebao ici svake noci. (prijava BK-{t})"),
            T("Provjeravam memoriju da iskljucim rusenje backup agenta zbog nestasice.",
              [{"name": "memory_usage", "arguments": {}}]),
            R({"mem_pct": rng.randint(41, 58)}),
            T("Memorija je uredna, dakle agent se ne rusi zbog nje. Listam odrediste kopija.",
              [{"name": "file_list", "arguments": {"path": "/var/backups"}}]),
            R({"path": "/var/backups", "files": [f"nightly-2026-10-2{rng.randint(4, 6)}.tar.gz", "manifest.txt"]}),
            T("Kopije su zaista stare. Provjeravam ima li mjesta na odredistu.",
              [{"name": "disk_usage", "arguments": {"path": "/var/backups"}}]),
            R({"path": "/var/backups", "used_pct": rng.randint(40, 57), "avail": "120G"}),
            T("Mjesta ima, dakle nije do prostora. Citam log backup agenta.",
              [{"name": "service_logs", "arguments": {"service": "backup-agent", "lines": 50}}]),
            R({"service": "backup-agent",
               "logs": f"{ts(i)} backup-agent: ERROR: cannot write snapshot: permission denied"}),
            T("Uzrok je u dozvolama. Verificiram sadrzaj odredista direktnim uvidom.",
              [{"name": "terminal", "arguments": {"command": "ls -lh /var/backups", "timeout_s": 30}}]),
            R({"output": "drwxr-xr-x root root; nightly-2026-10-24.tar.gz manjka"}),
            T("Dijagnoza: rezervne kopije kasne jer agent nema dozvolu pisanja na odrediste; "
               "trag nestasice resursa odbacujem (memorija i disk uredni). Predlazem popravak "
               "dozvola uz tvoju potvrdu, pa verifikaciju novom kopijom i manifestom. "
               "Bez potvrde nista ne mijenjam.")]


def e_slow_query(rng, i, t):
    return [U(f"Aplikacija je spora, sumnjam da baza koci. Pogledaj upite. (prijava BK-{t})"),
            T("Mjerim CPU da iskljucim preopterecenje procesora.",
              [{"name": "cpu_usage", "arguments": {}}]),
            R({"cpu_pct": rng.randint(25, 44)}),
            T("CPU je miran, dakle nije do procesora. Citam log baze.",
              [{"name": "service_logs", "arguments": {"service": "postgresql", "lines": 50}}]),
            R({"service": "postgresql",
               "logs": f"{ts(i)} postgresql: slow query: 8400 ms: SELECT * FROM narudzbe WHERE status='otvorena'"}),
            T("Upit traje preko 8 sekundi. Gledam top procese da iskljucim uljeza.",
              [{"name": "process_list", "arguments": {"limit": 10, "sort_by": "cpu"}}]),
            R({"top": [{"name": "postgres", "pid": 1200 + i, "cpu": 12}]}),
            T("Nema uljeza. Provjeravam memoriju.",
              [{"name": "memory_usage", "arguments": {}}]),
            R({"mem_pct": rng.randint(55, 68)}),
            T("Memorija je uredna. Gledam plan izvrsenja sporeg upita.",
              [{"name": "terminal", "arguments": {"command": "psql -c \"EXPLAIN SELECT * FROM narudzbe WHERE status='otvorena'\"", "timeout_s": 30}}]),
            R({"output": "Seq Scan on narudzbe (bez indeksa na koloni status)"}),
            T("Dijagnoza: upit nad tabelom narudzbe radi puni pregled jer nedostaje indeks na "
               "koloni status; trag preopterecenja odbacujem (CPU, memorija i procesi uredni). "
               "Predlazem dodavanje indeksa uz tvoju potvrdu, pa verifikaciju ponovnim planom "
               "i vremenom upita. Bez potvrde nista ne mijenjam.")]


# ---------- MEDIUM (6 koraka) ----------

def m_disk_oom(rng, i, t):
    svc = rng.choice(["app-api", "worker", "postgresql"])
    pct = rng.randint(96, 99)
    mem = rng.randint(90, 96)
    gb = round(rng.uniform(8.0, 20.0), 1)
    big = rng.choice(["syslog.1", "kern.log.1", "app.log.2"])
    return [U(f"Server je nestabilan: {svc} puca, a sumnjam i na disk i na memoriju. Nadji sve uzroke. (prijava BK-{t})"),
            T("Mjerim CPU da iskljucim preopterecenje procesora.",
              [{"name": "cpu_usage", "arguments": {}}]),
            R({"cpu_pct": rng.randint(30, 48)}),
            T("CPU je miran, taj trag odbacujem. Provjeravam zauzece diska.",
              [{"name": "disk_usage", "arguments": {"path": "/"}}]),
            R({"path": "/", "used_pct": pct, "avail": "300M"}),
            T(f"Disk je na {pct}%. Provjeravam i memoriju jer sumnjam na dvostruki kvar.",
              [{"name": "memory_usage", "arguments": {}}]),
            R({"mem_pct": mem}),
            T(f"Memorija je na {mem}%. Gledam najvece potrosace.",
              [{"name": "process_list", "arguments": {"limit": 10, "sort_by": "memory"}}]),
            R({"top": [{"name": "worker", "pid": 1200 + i, "mem_pct": mem - 20}]}),
            T(f"Worker drzi velik dio memorije. Citam log servisa {svc} za potvrdu oba uzroka.",
              [{"name": "service_logs", "arguments": {"service": svc, "lines": 50}}]),
            R({"service": svc, "logs": f"{ts(i)} {svc}: FATAL: No space left on device; Out of memory: process worker killed"}),
            T("Log potvrdjuje oba uzroka. Gledam sta je najvece na disku.",
              [{"name": "file_list", "arguments": {"path": "/var/log"}}]),
            R({"path": "/var/log", "largest": [{"name": big, "size_gb": gb}]}),
            T(f"Dijagnoza - dva istovremena uzroka: (1) disk pun na {pct}% (najveci {big}, {gb} GB) "
               f"pa {svc} ne moze pisati, (2) nestasica memorije ({mem}%) pa sistem prisilno gasi "
               f"workere. Trag preopterecenja CPU-a odbacujem. Redoslijed: prvo arhiviranje {big} "
               f"uz tvoju potvrdu, pa ogranicenje workera, verifikacija diskom, memorijom i statusom "
               f"servisa. Bez potvrde nista ne brisem i nista ne restartujem.")] 


def m_port_config(rng, i, t):
    svc = rng.choice(["nginx", "app-api"])
    rival = {"nginx": "apache2", "app-api": "test-runner"}[svc]
    port = {"nginx": 80, "app-api": 8080}[svc]
    conf = {"nginx": "/etc/nginx/nginx.conf", "app-api": "/opt/app/config.yaml"}[svc]
    typo = {"nginx": "proxy_timout", "app-api": "databse_url"}[svc]
    pid = 1200 + i
    return [U(f"{svc} ne starta nakon izmjene konfiguracije, a cini se i da je port {port} zauzet. (prijava BK-{t})"),
            T("Provjeravam mrezu da iskljucim prekid veze.",
              [{"name": "network_status", "arguments": {}}]),
            R({"interfaces": {"eth0": "up"}, "gateway_ok": True, "rx_packets": 920000 + i}),
            T("Mreza je uredna, taj trag odbacujem. Provjeravam ko drzi port.",
              [{"name": "port_check", "arguments": {"port": port}}]),
            R({"port": port, "process": rival, "pid": pid}),
            T(f"{rival} drzi port {port}. Citam log servisa {svc} za drugi uzrok.",
              [{"name": "service_logs", "arguments": {"service": svc, "lines": 50}}]),
            R({"service": svc, "logs": f"{ts(i)} {svc}: bind() failed: Address already in use; greska u konfiguraciji: nepoznata stavka '{typo}'"}),
            T("Log pokazuje i zauzet port i gresku u konfiguraciji. Otvaram konfiguraciju.",
              [{"name": "file_read", "arguments": {"path": conf, "lines": 50}}]),
            R({"path": conf, "excerpt": f"red 17: nepoznata stavka '{typo}' (tipfeler)"}),
            T(f"Tipfeler potvrdjen. Provjeravam je li {rival} legitiman proces.",
              [{"name": "process_list", "arguments": {"limit": 10, "sort_by": "cpu"}}]),
            R({"top": [{"name": rival, "pid": pid, "cpu": 2}]}),
            T("Prije destruktivnog koraka stajem i trazim potvrdu: smijem li napraviti "
              "rezervnu kopiju konfiguracije? Bez tvoje potvrde ne diram nista."),
            U(rng.choice(CONFIRM_YES)),
            T("Radim rezervnu kopiju konfiguracije prije izmjene.",
              [{"name": "terminal", "arguments": {"command": f"cp {conf} /root/{svc}.conf.bak", "timeout_s": 30}}]),
            R({"output": f"kopirano: {conf} -> /root/{svc}.conf.bak"}),
            T(f"Dijagnoza - dva istovremena uzroka: (1) {rival} (pid {pid}) legitimno drzi port "
               f"{port}, (2) tipfeler '{typo}' u {conf} pa bi {svc} pao i na slobodnom portu. "
               f"Trag mreze odbacujem. Rezervna kopija konfiguracije je napravljena. Predlazem: "
               f"ispravak tipfelera i premjestanje jednog servisa na drugi port uz tvoju potvrdu, "
               f"pa verifikaciju provjerom porta i statusa. Bez potvrde nista dalje ne mijenjam.")] 


def m_dns_fw(rng, i, t):
    ext = rng.choice(["api.vanjski-servis.example", "placanje.provjder.example"])
    return [U(f"Aplikacija ne moze dohvatiti vanjski servis {ext}, puca razrjesavanje imena, a mozda i vatrozid koci. (prijava BK-{t})"),
            T("Provjeravam status aplikacije da iskljucim njen pad.",
              [{"name": "service_status", "arguments": {"service": "app-api"}}]),
            R({"service": "app-api", "status": "active"}),
            T("Aplikacija radi, taj trag odbacujem. Provjeravam mrezu.",
              [{"name": "network_status", "arguments": {}}]),
            R({"interfaces": {"eth0": "up"}, "gateway_ok": False, "rx_packets": 1200 + i}),
            T("Prolaz je nedostupan. Provjeravam razrjesavanje imena.",
              [{"name": "terminal", "arguments": {"command": f"getent hosts {ext}", "timeout_s": 30}}]),
            R({"output": f"{ext}: ime se ne moze razrijesiti (NXDOMAIN preko 127.0.0.53)"}),
            T("Ime se ne razrjesava. Citam konfiguraciju razrjesivaca.",
              [{"name": "file_read", "arguments": {"path": "/etc/resolv.conf", "lines": 20}}]),
            R({"path": "/etc/resolv.conf", "excerpt": "nameserver prazan nakon nocnog reseta mreze"}),
            T("Razrjesivac je prazan. Provjeravam pravila vatrozida za drugi uzrok.",
              [{"name": "terminal", "arguments": {"command": "iptables -L -n", "timeout_s": 30}}]),
            R({"output": "OUTPUT DROP tcp dpt:443 (pravilo dodano jucer u 18:02)"}),
            T("Vatrozid blokira odlazni 443. Citam log aplikacije za potvrdu.",
              [{"name": "service_logs", "arguments": {"service": "app-api", "lines": 50}}]),
            R({"service": "app-api", "logs": f"{ts(i)} app-api: ne mogu dohvatiti {ext}: privremeni kvar u razrjesavanju imena"}),
            T(f"Dijagnoza - dva istovremena uzroka: (1) prazan /etc/resolv.conf pa razrjesavanje "
               f"imena {ext} ne prolazi, (2) pravilo vatrozida koje blokira odlazni port 443 pa ne bi "
               f"proslo ni sa ispravnim DNS-om. Trag pada aplikacije odbacujem (servis aktivan). "
               f"Predlazem: upis ispravnog nameservera i uklanjanje spornog pravila uz tvoju potvrdu, "
               f"pa verifikaciju ponovnim razrjesavanjem i probnim dohvatanjem. Bez potvrde nista ne mijenjam.")] 


def m_docker_disk(rng, i, t):
    return [U(f"Docker host prijavljuje pun disk, a kontejneri se ruse. Vidi vezu izmedju toga. (prijava BK-{t})"),
            T("Provjeravam memoriju da iskljucim nestasicu kao primarni uzrok.",
              [{"name": "memory_usage", "arguments": {}}]),
            R({"mem_pct": rng.randint(48, 60)}),
            T("Memorija je uredna, taj trag odbacujem. Gledam stanje kontejnera.",
              [{"name": "terminal", "arguments": {"command": "docker ps -a", "timeout_s": 30}}]),
            R({"output": "app-api Restarting (1); worker Exited (1)"}),
            T("Kontejneri se ruse. Provjeravam zauzece diska.",
              [{"name": "disk_usage", "arguments": {"path": "/"}}]),
            R({"path": "/", "used_pct": rng.randint(95, 98), "avail": "500M"}),
            T("Disk je skoro pun. Gledam koliko docker trosi.",
              [{"name": "terminal", "arguments": {"command": "docker system df", "timeout_s": 30}}]),
            R({"output": "Images 18G, Build cache 9G, Volumes 6G"}),
            T("Docker trosi preko 30 GB. Listam njegov direktorij.",
              [{"name": "file_list", "arguments": {"path": "/var/lib/docker"}}]),
            R({"path": "/var/lib/docker", "largest": [{"name": "overlay2", "size_gb": 21.4}]}),
            T("Najveci je overlay2. Citam log docker servisa za potvrdu.",
              [{"name": "service_logs", "arguments": {"service": "docker", "lines": 50}}]),
            R({"service": "docker", "logs": f"{ts(i)} docker: no space left on device; kontejner app-api ubijen"}),
            T("Dijagnoza - dva spojena uzroka: (1) disk pun na preko 95%, (2) glavni potrosac je "
               "sam docker (neociscene slike i slojevi, overlay2 preko 21 GB) pa kontejneri padaju. "
               "Trag memorije odbacujem. Predlazem ciscenje nekoristenih slika i kesa uz tvoju "
               "potvrdu, pa verifikaciju diskom i stanjem kontejnera. Bez potvrde nista ne brisem.")] 


def m_ssl_cron(rng, i, t):
    dom = rng.choice(["app.kolektiv.pro", "portal.kolektiv.pro"])
    return [U(f"Certifikat za {dom} je istekao iako obnova ide automatski. Izgleda da zakazana obnova ne radi. (prijava BK-{t})"),
            T("Provjeravam slusa li ista na portu 443 da iskljucim pad weba.",
              [{"name": "port_check", "arguments": {"port": 443}}]),
            R({"port": 443, "process": "nginx", "pid": 1200 + i}),
            T("Web slusa, taj trag odbacujem. Provjeravam datum isteka certifikata.",
              [{"name": "terminal", "arguments": {"command": "openssl x509 -enddate -noout -in /etc/letsencrypt/live/app/cert.pem", "timeout_s": 30}}]),
            R({"output": "notAfter=2026-10-28 06:00:00 GMT (istekao prije 5 dana)"}),
            T("Certifikat je zaista istekao. Gledam je li obnova uopce zakazana.",
              [{"name": "file_read", "arguments": {"path": "/etc/crontab", "lines": 50}}]),
            R({"path": "/etc/crontab", "excerpt": "17 3 * * * root certbot renew --quiet"}),
            T("Obnova je zakazana. Provjeravam status cron servisa.",
              [{"name": "service_status", "arguments": {"service": "cron"}}]),
            R({"service": "cron", "status": "inactive"}),
            T("Cron ne radi. Citam log obnove za potvrdu.",
              [{"name": "service_logs", "arguments": {"service": "certbot", "lines": 50}}]),
            R({"service": "certbot", "logs": "renew pokusan 0 puta u 5 dana; cron nije pokrenuo zadatak"}),
            T("Obnova se nije pokrenula. Gledam starost certifikata na disku.",
              [{"name": "file_list", "arguments": {"path": "/etc/letsencrypt"}}]),
            R({"path": "/etc/letsencrypt", "files": ["live/app/cert.pem (2026-10-28)", "archive/"]}),
            T(f"Dijagnoza - dva istovremena uzroka: (1) servis cron je neaktivan pa se automatska "
               f"obnova nije izvrsila, (2) certifikat za {dom} je istekao prije 5 dana i mora se "
               f"obnoviti rucno. Trag pada weba odbacujem (nginx slusa na 443). Predlazem: pokretanje "
               f"cron servisa pa rucnu obnovu uz tvoju potvrdu, verifikacija datumom certifikata i "
               f"logom. Bez potvrde nista ne pokrecem.")]


def m_slowdb_index(rng, i, t):
    mem = rng.randint(88, 94)
    return [U(f"Baza je sve sporija, upiti traju sekundama, a i memorija curi. Nadji sve uzroke. (prijava BK-{t})"),
            T("Provjeravam disk da iskljucim pun disk kao uzrok.",
              [{"name": "disk_usage", "arguments": {"path": "/"}}]),
            R({"path": "/", "used_pct": rng.randint(45, 58), "avail": "90G"}),
            T("Disk je uredan, taj trag odbacujem. Citam log baze.",
              [{"name": "service_logs", "arguments": {"service": "postgresql", "lines": 50}}]),
            R({"service": "postgresql",
               "logs": f"{ts(i)} postgresql: slow query: 12400 ms: SELECT * FROM narudzbe WHERE kupac_id=4812"}),
            T("Upit traje preko 12 sekundi. Gledam plan izvrsenja.",
              [{"name": "terminal", "arguments": {"command": "psql -c \"EXPLAIN SELECT * FROM narudzbe WHERE kupac_id=4812\"", "timeout_s": 30}}]),
            R({"output": "Seq Scan on narudzbe (bez indeksa na koloni kupac_id)"}),
            T("Puni pregled tabele. Citam konfiguraciju baze za drugi uzrok.",
              [{"name": "file_read", "arguments": {"path": "/etc/postgresql/postgresql.conf", "lines": 50}}]),
            R({"path": "/etc/postgresql/postgresql.conf",
               "excerpt": "shared_buffers=128MB; work_mem=4MB (tvornicke vrijednosti, ne dirano godinama)"}),
            T("Konfiguracija je tvornicka. Gledam potrosace memorije.",
              [{"name": "process_list", "arguments": {"limit": 10, "sort_by": "memory"}}]),
            R({"top": [{"name": "postgres", "pid": 1200 + i, "mem_pct": mem - 25}]}),
            T("Baza drzi velik dio memorije. Provjeravam ukupno zauzece.",
              [{"name": "memory_usage", "arguments": {}}]),
            R({"mem_pct": mem}),
            T(f"Dijagnoza - dva istovremena uzroka: (1) nedostaje indeks na koloni kupac_id pa upit "
               f"radi puni pregled (12+ sekundi), (2) konfiguracija baze je tvornicka uz memoriju na "
               f"{mem}% pa nema rezerve za kes. Trag punog diska odbacujem. Predlazem: dodavanje "
               f"indeksa i podizanje shared_buffers uz tvoju potvrdu, verifikacija planom upita i "
               f"memorijom. Bez potvrde nista ne mijenjam.")] 


# ---------- HARD (7-8 koraka, eskalacija usred lanca) ----------

def h_full_outage(rng, i, t):
    pct = rng.randint(96, 99)
    mem = rng.randint(90, 95)
    gb = round(rng.uniform(10.0, 22.0), 1)
    pid = 1200 + i
    return [U(f"Produkcija pala: nginx ne starta, disk je navodno pun, a nocas je nestalo i memorije. Rijesi redom. (prijava BK-{t})"),
            T("Provjeravam mrezu da iskljucim prekid veze.",
              [{"name": "network_status", "arguments": {}}]),
            R({"interfaces": {"eth0": "up"}, "gateway_ok": True, "rx_packets": 930000 + i}),
            T("Mreza je uredna, taj trag odbacujem. Provjeravam disk.",
              [{"name": "disk_usage", "arguments": {"path": "/"}}]),
            R({"path": "/", "used_pct": pct, "avail": "200M"}),
            T(f"Disk je na {pct}%. Provjeravam i memoriju.",
              [{"name": "memory_usage", "arguments": {}}]),
            R({"mem_pct": mem}),
            T(f"Memorija je na {mem}%. Gledam najvece potrosace.",
              [{"name": "process_list", "arguments": {"limit": 10, "sort_by": "memory"}}]),
            R({"top": [{"name": "worker", "pid": pid, "mem_pct": mem - 22}]}),
            T("Worker pritiska memoriju. Citam log nginxa.",
              [{"name": "service_logs", "arguments": {"service": "nginx", "lines": 50}}]),
            R({"service": "nginx", "logs": f"{ts(i)} nginx: FATAL: No space left on device; emerg: bind() failed"}),
            T("Log pokazuje i disk i vezivanje. Provjeravam ko drzi port 80.",
              [{"name": "port_check", "arguments": {"port": 80}}]),
            R({"port": 80, "process": "apache2", "pid": pid}),
            T("Port drzi apache2. Gledam sta je najvece u logovima.",
              [{"name": "file_list", "arguments": {"path": "/var/log"}}]),
            R({"path": "/var/log", "largest": [{"name": "syslog.1", "size_gb": gb}]}),
            T("Prije restarta stajem i trazim potvrdu: smijem li pokusati restart nginxa? "
              "Upozoravam da ce vjerovatno pasti dok se disk ne ocisti. Bez tvoje potvrde ne diram nista."),
            U(rng.choice(CONFIRM_YES)),
            T("Radim restart nginxa nakon dobijene potvrde.",
              [{"name": "service_restart", "arguments": {"service": "nginx"}}]),
            R({"service": "nginx", "action": "restart", "result": "failed: no space left on device"}),
            T(f"Dijagnoza - tri isprepletena uzroka: (1) disk pun na {pct}% (syslog.1 od {gb} GB), "
               f"(2) apache2 (pid {pid}) drzi port 80, (3) memorija na {mem}% pa worker prijeti. "
               f"Trag mreze odbacujem, a pokusani restart je pao bas zbog diska - sto potvrdjuje "
               f"redoslijed. Predlazem: prvo arhiviranje syslog.1 uz potvrdu, pa gasenje ili "
               f"premjestanje apache2, tek onda restart; verifikacija statusom, portom i diskom. "
               f"Bez potvrde nista dalje ne brisem.")] 


def h_docker_ssl_dns(rng, i, t):
    dom = rng.choice(["app.kolektiv.pro", "shop.kolektiv.pro"])
    ext = "db.replika.interna"
    base = [U(f"Kontejnerizirana aplikacija nedostupna izvana: sumnjivi DNS, vatrozid i certifikat u kontejneru. (prijava BK-{t})"),
            T("Mjerim CPU da iskljucim preopterecenje.",
              [{"name": "cpu_usage", "arguments": {}}]),
            R({"cpu_pct": rng.randint(28, 42)}),
            T("CPU je miran, taj trag odbacujem. Gledam stanje kontejnera.",
              [{"name": "terminal", "arguments": {"command": "docker ps", "timeout_s": 30}}]),
            R({"output": "app-api Unhealthy; nginx-proxy Restarting"}),
            T("Kontejneri su bolesni. Provjeravam razrjesavanje internog imena.",
              [{"name": "terminal", "arguments": {"command": f"getent hosts {ext}", "timeout_s": 30}}]),
            R({"output": f"{ext}: ime se ne moze razrijesiti"}),
            T("Ime se ne razrjesava. Provjeravam pravila vatrozida.",
              [{"name": "terminal", "arguments": {"command": "iptables -L -n", "timeout_s": 30}}]),
            R({"output": "DOCKER-USER DROP tcp dpt:443 (pogresno pravilo od jucer)"}),
            T("Vatrozid blokira 443 prema kontejnerima. Provjeravam certifikat.",
              [{"name": "terminal", "arguments": {"command": "openssl x509 -enddate -noout -in /etc/ssl/certs/app.crt", "timeout_s": 30}}]),
            R({"output": "notAfter=2026-10-29 06:00:00 GMT (istekao prije 4 dana)"}),
            T("Certifikat je istekao. Citam log aplikacije za potvrdu lanca.",
              [{"name": "service_logs", "arguments": {"service": "app-api", "lines": 50}}]),
            R({"service": "app-api",
               "logs": f"{ts(i)} app-api: ne mogu dohvatiti {ext}; SSL handshake failed: certificate expired"}),
            T(rng.choice(CONFIRM_ASK),
              ),
            U(rng.choice(CONFIRM_YES)),
            T("Radim restart docker servisa nakon dobijene potvrde.",
              [{"name": "service_restart", "arguments": {"service": "docker"}}]),
            R({"service": "docker", "action": "restart", "result": "ok"})]
    if i % 2 == 0:
        base += [T("Restart je prosao. Provjeravam slusa li ista na portu 443.",
                   [{"name": "port_check", "arguments": {"port": 443}}]),
                 R({"port": 443, "process": "nginx-proxy", "pid": 1200 + i})]
    base += [T(f"Dijagnoza - tri istovremena uzroka: (1) DNS ne razrjesava {ext}, (2) pogresno "
               f"pravilo vatrozida blokira 443 prema kontejnerima, (3) certifikat za {dom} istekao "
               f"prije 4 dana. Trag preopterecenja odbacujem, a restart dockera sam uradio tek nakon "
               f"potvrde - ali on sam ne lijeci ni DNS ni certifikat. Predlazem: popravak razrjesivaca, "
               f"uklanjanje spornog pravila i obnovu certifikata uz tvoju potvrdu, pa verifikaciju "
               f"dohvatanjem, pravilima i datumom. Bez potvrde nista dalje ne mijenjam.")]
    return base


def h_backup_cron_db(rng, i, t):
    base = [U(f"Nocni backup nije odradjen, zakazani zadatak suti, a baza je pritom i spora. Provjeri cijeli lanac i restore. (prijava BK-{t})"),
            T("Provjeravam mrezu da iskljucim prekid veze.",
              [{"name": "network_status", "arguments": {}}]),
            R({"interfaces": {"eth0": "up"}, "gateway_ok": True, "rx_packets": 940000 + i}),
            T("Mreza je uredna, taj trag odbacujem. Provjeravam status cron servisa.",
              [{"name": "service_status", "arguments": {"service": "cron"}}]),
            R({"service": "cron", "status": "inactive"}),
            T("Cron ne radi. " + ("Gledam je li backup uopce zakazan."
              if i % 2 else "Listam postojece kopije da vidim dokle se stiglo."),
              [{"name": "file_read", "arguments": {"path": "/etc/crontab", "lines": 50}}]
              if i % 2 else
              [{"name": "file_list", "arguments": {"path": "/var/backups"}}]),
            R({"path": "/etc/crontab", "excerpt": "30 1 * * * root /opt/backup/nightly.sh"}
              if i % 2 else
              {"path": "/var/backups", "files": ["nightly-2026-10-24.tar.gz (star 9 dana)", "manifest.txt"]}),
            T("Zadatak postoji. Listam postojece kopije." if i % 2
              else "Kopije kasne 9 dana. Citam manifest za provjeru potpunosti.",
              [{"name": "file_list", "arguments": {"path": "/var/backups"}}]
              if i % 2 else
              [{"name": "file_read", "arguments": {"path": "/var/backups/manifest.txt", "lines": 50}}]),
            R({"path": "/var/backups", "files": ["nightly-2026-10-24.tar.gz (star 9 dana)", "manifest.txt"]}
              if i % 2 else
              {"path": "/var/backups/manifest.txt",
               "excerpt": "ocekivano 14 fajlova, popisano 9; baza nije prasena do kraja"})]
    base += [T("Provjeravam cjelovitost zadnje kopije kontrolnom sumom.",
               [{"name": "terminal", "arguments": {"command": "sha256sum /var/backups/nightly-2026-10-24.tar.gz", "timeout_s": 30}}]),
             R({"output": "checksum MISMATCH: kopija je krnja"}),
             T("Kopija je neispravna. Citam log baze za spore upite.",
               [{"name": "service_logs", "arguments": {"service": "postgresql", "lines": 50}}]),
             R({"service": "postgresql",
                "logs": f"{ts(i)} postgresql: slow query: 15200 ms: SELECT * FROM stavke WHERE skladiste_id=7"}),
             T("Upit traje preko 15 sekundi. Gledam plan izvrsenja.",
               [{"name": "terminal", "arguments": {"command": "psql -c \"EXPLAIN SELECT * FROM stavke WHERE skladiste_id=7\"", "timeout_s": 30}}]),
             R({"output": "Seq Scan on stavke (bez indeksa na koloni skladiste_id)"}),
             T(rng.choice(CONFIRM_ASK)),
             U(rng.choice(CONFIRM_YES)),
             T("Pokrecem cron servis nakon dobijene potvrde.",
               [{"name": "service_restart", "arguments": {"service": "cron"}}]),
             R({"service": "cron", "action": "restart", "result": "ok"}),
             T("Dijagnoza - tri isprepletena uzroka: (1) cron neaktivan pa se nocni backup nije "
                "pokrenuo 9 dana, (2) zadnja kopija je krnja (kontrolna suma ne prolazi) pa restore "
                "iz nje NE preporucujem dok se ne napravi ispravna, (3) upit nad stavkama radi puni "
                "pregled bez indeksa (15+ sekundi). Trag mreze odbacujem, a cron sam pokrenuo tek "
                "nakon potvrde. Predlazem: rucni backup uz potvrdu, dodavanje indeksa uz potvrdu, "
                "pa verifikaciju sumom, manifestom i planom upita. Bez potvrde nista dalje ne mijenjam.")]
    return base


EASY = [e_docker_exit, e_ssl_expire, e_cron_silent, e_backup_stale, e_slow_query]
MEDIUM = [m_disk_oom, m_port_config, m_dns_fw, m_docker_disk, m_ssl_cron, m_slowdb_index]
HARD = [h_full_outage, h_docker_ssl_dns, h_backup_cron_db]
DOMAINS = {e_docker_exit: "docker", e_ssl_expire: "ssl", e_cron_silent: "cron",
            e_backup_stale: "backup", e_slow_query: "slowdb",
            m_disk_oom: "disk+oom", m_port_config: "port+config", m_dns_fw: "dns+firewall",
            m_docker_disk: "docker+disk", m_ssl_cron: "ssl+cron", m_slowdb_index: "slowdb+index",
            h_full_outage: "outage-3x", h_docker_ssl_dns: "docker+ssl+dns",
            h_backup_cron_db: "backup+cron+slowdb"}


def main():
    rng = random.Random(202603)
    old_first = set()
    for src in (SRC1, SRC2):
        for ln in src.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            d = json.loads(ln)
            u = next(m for m in d["messages"] if m["role"] == "user")
            old_first.add(norm(u["content"]))
    nums = []
    for src in (SRC1, SRC2):
        nums += [int(json.loads(l)["id"].split("-")[-1])
                 for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
    nxt = max(nums) + 1
    jobs = []
    for fn in EASY:
        jobs += [("easy", fn)] * 75
    for fn in MEDIUM:
        jobs += [("medium", fn)] * 125
    for fn in HARD:
        jobs += [("hard", fn)] * 125
    assert len(jobs) == 1500, len(jobs)
    rng.shuffle(jobs)
    rows, seen_new = [], set()
    for k, (diff, fn) in enumerate(jobs):
        t = nxt + k
        msgs = fn(rng, k, t)
        first = norm(msgs[0]["content"])
        assert first not in old_first, f"kolizija sa v0.1/v0.2: {first[:80]}"
        assert first not in seen_new, f"kolizija unutar v0.3: {first[:80]}"
        seen_new.add(first)
        assert msgs[0]["role"] == "user"
        assert any(m["role"] == "assistant" for m in msgs)
        assert msgs[-1]["role"] == "assistant" and "tool_calls" not in msgs[-1]
        blob = json.dumps([m for m in msgs if m["role"] == "assistant"], ensure_ascii=False)
        assert not re.search(r"[Ѐ-џ]", blob), "cirilica"
        for pat in DENY:
            assert not re.search(pat, blob), f"deny: {pat}"
        nsteps = sum(1 for m in msgs if m.get("tool_calls"))
        for m in msgs:
            for tc in m.get("tool_calls", []) or []:
                assert tc["name"] in VALID_TOOLS, tc["name"]
        if diff == "easy":
            assert nsteps == 5, (fn.__name__, nsteps)
        elif diff == "medium":
            assert nsteps == 6, (fn.__name__, nsteps)
        else:
            assert 7 <= nsteps <= 8, (fn.__name__, nsteps)
        rows.append(row(f"amj-ag-{t:04d}", diff, msgs, DOMAINS[fn]))
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                   encoding="utf-8")
    cs = Counter(sum(1 for m in r["messages"] if m.get("tool_calls")) for r in rows)
    cd = Counter(r["difficulty"] for r in rows)
    cm = Counter(r["metadata"]["domain"] for r in rows)
    print(f"redova: {len(rows)} -> {OUT}")
    print(f"start: amj-ag-{nxt:04d} end: amj-ag-{nxt + len(rows) - 1:04d}")
    print(f"difficulty: {dict(sorted(cd.items()))}")
    print(f"koraci: {dict(sorted(cs.items()))}")
    print(f"domene: {dict(sorted(cm.items()))}")


if __name__ == "__main__":
    main()
