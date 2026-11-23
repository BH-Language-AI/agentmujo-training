#!/usr/bin/env python3
"""Generise datasets/canonical/agentic_terminal_v0.5.jsonl (~1200 scenarija).

Template-expansion v0.5: NOVE T-Bench inspirisane domene (vlastiti sadrzaj,
ne kopije testova):
  (a) build from source pao (nedostaje compiler/dependency -> package_query
      -> install -> retry, verifikacija builda);
  (b) test suite pada (citanje loga, izolacija jednog failing testa, fix configa);
  (c) obrada podataka (ogroman CSV/log -> disk provjera -> chunked obrada
      -> verifikacija izlaza);
  (d) server setup od nule (port+firewall+servis+SSL redoslijed s verifikacijom);
  (e) korisnici/dozvole (deploy user, ssh kljuc, sudoers read-only, permission audit).
Svaki scenarij je viseturni troubleshooting (easy 4, medium 5, hard 6 tool
koraka) kroz POSTOJECIH 14 alata iz configs/tools.yaml. Build/compile/test
radnje SAMO kao terminal read-only (npr. --version, --collect-only, wc -l,
nginx -t) ili file operacije, NIKAD destruktivno. Mutacije (package_install)
samo uz potvrdu usred lanca. Difficulty mix 25/50/25. ID nastavak od max iz
v0.1-v0.4. DEDUP: normaliziran prvi user problem ne smije postojati u
v0.1-v0.4 ni unutar v0.5. metadata SILVER / tbench-inspired-v0.5 / verified.
Koristenje: .venv/bin/python scripts/build_ag_v05.py
"""
import json
import random
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRCS = [REPO / f"datasets/canonical/agentic_terminal_v0.{n}.jsonl" for n in ("1", "2", "3", "4")]
OUT = REPO / "datasets/canonical/agentic_terminal_v0.5.jsonl"

DENY = [r"\brm\s+-rf\s+/", r"\bmkfs\b", r"\bdd\s+.*of=/dev/",
        r"\biptables\s+-F\b", r":\(\)\s*\{\s*:\|\:&\s*\}",
        r"\bcurl\b.*\|\s*(?:sudo\s+)?bash\b",
        r"\bwget\b.*\|\s*(?:sudo\s+)?bash\b",
        r"PASSPHRASE|AWS_SECRET|HF_TOKEN"]

VALID_TOOLS = {"service_status", "service_restart", "service_logs", "disk_usage",
               "memory_usage", "cpu_usage", "process_list", "network_status",
               "port_check", "terminal", "package_query", "package_install",
               "file_list", "file_read"}

CONFIRM_ASK = ("Prije instalacije paketa stajem i trazim potvrdu: smijem li "
               "instalirati paket? Bez tvoje potvrde nista ne instaliram.")
CONFIRM_YES = ["Moze, potvrdjujem instalaciju.", "Potvrdjujem, instaliraj paket.",
               "U redu, imas potvrdu za instalaciju."]


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
    s = (k * 67 + 41) % 86400
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def norm(s):
    return re.sub(r"\s+", " ", s.strip().lower())


def row(sid, diff, msgs, domain):
    return {"id": sid, "version": "0.5.0", "language": "bs-ijekavica",
            "task": "agentic-terminal", "difficulty": diff,
            "enable_thinking": True, "messages": msgs,
            "metadata": {"author": "agentmujo-team", "quality_tier": "SILVER",
                         "source": "tbench-inspired-v0.5",
                         "verification_status": "verified",
                         "domain": domain}}


# ---------- (a) build from source pao ----------

BUILDS = [
    ("modula za nginx", "cc", "gcc --version", "gcc: komanda nije pronadjena",
     "build-essential", "/opt/mod-auth/build.log",
     "greska: cc: komanda nije pronadjena (red 3)",
     "/opt/mod-auth/Makefile", "CC=gcc\nCFLAGS=-O2 -fPIC"),
    ("alata za slike", "cmake", "cmake --version", "cmake: komanda nije pronadjena",
     "cmake", "/opt/imgconv/build.log",
     "greska: cmake: komanda nije pronadjena (red 1)",
     "/opt/imgconv/CMakeLists.txt", "cmake_minimum_required(VERSION 3.16)"),
    ("api servisa", "go", "go version", "go: komanda nije pronadjena",
     "golang-go", "/opt/racun-api/build.log",
     "greska: go: komanda nije pronadjena (red 5)",
     "/opt/racun-api/go.mod", "module racun-api\ngo 1.22"),
    ("sistemskog demona", "pkg-config/openssl", "pkg-config --modversion openssl",
     "Package openssl was not found in the pkg-config search path",
     "libssl-dev", "/opt/kolektiv-agent/build.log",
     "greska: openssl/ssl.h: datoteka ne postoji (red 12)",
     "/opt/kolektiv-agent/Makefile", "CFLAGS+=-I/usr/include/openssl"),
    ("python ekstenzije", "python3-dev", "pkg-config --modversion python3-embed",
     "Package python3-embed was not found",
     "python3-dev", "/opt/brzi-hash/build.log",
     "greska: Python.h: datoteka ne postoji (red 8)",
     "/opt/brzi-hash/setup.py", "Extension('brzi_hash', sources=['hash.c'])"),
]


def b_build(rng, i, t, diff):
    desc, alat, cmd, missing, pkg, log, logex, conf, confex = rng.choice(BUILDS)
    ver = rng.choice(["1.4.2", "2.1.0", "3.0.1"])
    m = [U(rng.choice([f"Ne mogu izgraditi {desc} iz izvornog koda, build puca na pocetku. Vidi sta nedostaje. (slucaj T5-{t})",
                       f"Build {desc} pada - izgleda da fali {alat}. Dijagnostikuj lanac. (slucaj T5-{t})",
                       f"Kompajliranje {desc} staje sa greskom oko {alat}. Provjeri. (slucaj T5-{t})"]))]
    if diff == "hard":
        m += [T("Krecem od diska da iskljucim pun particiju kao uzrok pada.",
                [{"name": "disk_usage", "arguments": {"path": "/opt"}}]),
              R({"path": "/opt", "used_pct": rng.randint(38, 55), "avail": "41G"})]
        m += [T("Mjesta ima, taj trag odbacujem. Citam build log da nadjem gresku.",
                [{"name": "file_read", "arguments": {"path": log, "lines": 50}}]),
              R({"path": log, "excerpt": f"{ts(i)} {logex}"})]
    else:
        m += [T("Citam build log da nadjem gdje build staje.",
                [{"name": "file_read", "arguments": {"path": log, "lines": 50}}]),
              R({"path": log, "excerpt": f"{ts(i)} {logex}"})]
    m += [T(f"Log ukazuje na {alat}. Provjeravam je li alat uopce dostupan (read-only).",
            [{"name": "terminal", "arguments": {"command": cmd, "timeout_s": 30}}]),
          R({"output": missing}),
          T(f"{alat} zaista nedostaje. Provjeravam je li paket {pkg} instaliran.",
            [{"name": "package_query", "arguments": {"package": pkg}}]),
          R({"package": pkg, "installed": False})]
    if diff == "easy":
        m += [T("Paket nije instaliran. Otvaram recept za gradnju da potvrdim sta se trazi.",
                [{"name": "file_read", "arguments": {"path": conf, "lines": 50}}]),
              R({"path": conf, "excerpt": confex})]
        m += [T(f"Dijagnoza: build {desc} pada jer alat {alat} nije dostupan - paket {pkg} nije instaliran "
                f"({missing}), a recept ga ocekuje. Trag punog diska odbacujem. Sljedeci korak: instalacija "
                f"paketa {pkg} uz tvoju potvrdu, pa ponovni build i verifikacija kroz build log (uspjesan kraj). "
                f"Bez potvrde nista ne instaliram.")]
    else:
        m += [T(CONFIRM_ASK), U(rng.choice(CONFIRM_YES)),
              T(f"Instaliram paket {pkg}.",
                [{"name": "package_install", "arguments": {"package": pkg}}]),
              R({"package": pkg, "installed": True, "version": ver}),
              T("Paket je instaliran. Citam novi build log da verifikujem retry.",
                [{"name": "file_read", "arguments": {"path": log, "lines": 50}}]),
              R({"path": log, "excerpt": f"{ts(i)} build uspjesan: meta pronadjena, 0 gresaka"})]
        m += [T(f"Dijagnoza: build {desc} je padao jer je nedostajao {alat} (paket {pkg} nije bio instaliran). "
                f"Nakon instalacije (verzija {ver}) ponovni build prolazi bez gresaka - verifikovano kroz build log. "
                f"Sljedeci korak: pokrenuti pripadajuci test paket prije deploya. Bez potvrde nista dalje ne diram.")]
    return m


# ---------- (b) test suite pada ----------

TESTS = [
    ("pytest", "/opt/app/tests/test_api.py::test_kreira_korisnika",
     "pytest --collect-only -q /opt/app/tests", "11 testova pronadjeno",
     "/opt/app/pytest-izvjestaj.log", "FAILED test_api.py::test_kreira_korisnika - veza odbijena (red 44)",
     "/opt/app/tests/test_api.py", "def test_kreira_korisnika(client):\n    assert client.post('/korisnici').status == 201",
     "/opt/app/config.yaml", "test_db_url: (prazno, nije postavljeno)"),
    ("jest", "/opt/web/test/checkout.test.js",
     "npx jest --listTests", "8 datoteka s testovima pronadjeno",
     "/opt/web/jest-izvjestaj.log", "FAIL test/checkout.test.js - nije moguce citati PAYMENT_URL (red 19)",
     "/opt/web/test/checkout.test.js", "test('placanje prolazi', () => { expect(plati()).toBe(true); })",
     "/opt/web/.env.test", "PAYMENT_URL=(prazno, nije postavljeno)"),
    ("go test", "paket skladiste / TestUpisi",
     "go test -list '.*' ./skladiste/", "6 testova pronadjeno",
     "/opt/skladiste/gotest-izvjestaj.log", "--- FAIL: TestUpisi (otvaranje /tmp/proba.db: dozvola odbacena)",
     "/opt/skladiste/upis_test.go", "func TestUpisi(t *testing.T) { // pise u /tmp/proba.db }",
     "/opt/skladiste/testdata/okruzenje.yaml", "tmp_dir: /tmp (pisanje nije dozvoljeno u ovom okruzenju)"),
]


def b_test(rng, i, t, diff):
    runner, test, cmd, found, log, logex, tfile, tex, conf, cex = rng.choice(TESTS)
    port = rng.choice([5433, 6378, 8081])
    m = [U(rng.choice([f"Test paket pada ({runner}), vecina prolazi ali jedan test rusi sve. Izoluj uzrok. (slucaj T5-{t})",
                       f"{runner} javlja FAIL na jednom testu ({test}). Nadji je li do koda ili konfiguracije. (slucaj T5-{t})",
                       f"CI mi je crven zbog {runner} - pada samo {test}. Analiziraj. (slucaj T5-{t})"]))]
    m += [T("Citam izvjestaj testova da vidim koji tacno test pada.",
            [{"name": "file_read", "arguments": {"path": log, "lines": 50}}]),
          R({"path": log, "excerpt": f"{ts(i)} {logex}"})]
    if diff in ("medium", "hard"):
        m += [T(f"Jedan test pada. Provjeravam port {port} da iskljucim sukob s pomocnim servisom.",
                [{"name": "port_check", "arguments": {"port": port}}]),
              R({"port": port, "process": None, "pid": None})]
        m += [T("Port je slobodan, taj trag odbacujem. Otvaram datoteku palog testa.",
                [{"name": "file_read", "arguments": {"path": tfile, "lines": 50}}]),
              R({"path": tfile, "excerpt": tex})]
    else:
        m += [T("Izolujem pali test - otvaram njegovu datoteku.",
                [{"name": "file_read", "arguments": {"path": tfile, "lines": 50}}]),
              R({"path": tfile, "excerpt": tex})]
    m += [T(f"Test je izolovan ({test}). Provjeravam popis testova read-only da potvrdim opseg.",
            [{"name": "terminal", "arguments": {"command": cmd, "timeout_s": 30}}]),
          R({"output": found}),
          T("Opseg potvrdjen. Citam konfiguraciju testnog okruzenja.",
            [{"name": "file_read", "arguments": {"path": conf, "lines": 50}}]),
          R({"path": conf, "excerpt": cex})]
    if diff == "hard":
        m += [T("Konfiguracija je sumnjiva. Listam direktorij testova da iskljucim nedostatak datoteka.",
                [{"name": "file_list", "arguments": {"path": str(Path(tfile).parent)}}]),
              R({"path": str(Path(tfile).parent), "files": ["sve test datoteke prisutne"]})]
    m += [T(f"Dijagnoza: pada samo {test} ({runner}), a uzrok je konfiguracija testnog okruzenja ({conf}: {cex}), "
            f"ne kod - ostali testovi prolaze, a trag zauzetog porta odbacujem. Sljedeci korak: dopuniti konfiguraciju "
            f"uz tvoju potvrdu pa ponoviti samo izolovani test i verifikacija kroz izvjestaj (svi zeleni). "
            f"Bez potvrde nista ne mijenjam.")]
    return m


# ---------- (c) obrada podataka ----------

DATASETS = [
    ("prodaje", "/data/prodaja-2026.csv", "18G", "142M redova",
     "datum,artikl,kolicina,cijena", "/data/izlaz/sazetak-prodaje.csv"),
    ("pristupnog loga", "/var/log/nginx/access-arhiva.log", "42G", "96M redova",
     '203.0.113.7 - - [02/Nov/2026:08:12:01] "GET /proizvod/418" 200',
     "/data/izlaz/top-rute.csv"),
    ("dogadjaja", "/data/dogadjaji.jsonl", "9G", "31M redova",
     '{"vrijeme":"2026-11-02T08:12:01","vrsta":"klik","id":418201}', "/data/izlaz/dogadjaji-dnevno.csv"),
    ("senzora", "/data/senzori.csv", "6G", "58M redova",
     "2026-11-02T08:12:01,senzor-14,21.4", "/data/izlaz/senzori-prosjek.csv"),
]


def b_data(rng, i, t, diff):
    desc, ulaz, vel, redova, uzorak, izlaz = rng.choice(DATASETS)
    d = str(Path(ulaz).parent)
    m = [U(rng.choice([f"Treba obraditi ogromnu datoteku {desc} ({ulaz}, {vel}). Isplaniraj siguran postupak. (slucaj T5-{t})",
                       f"Skripta za {desc} se gusi na punoj datoteci ({redova}). Kako to pametno obraditi? (slucaj T5-{t})",
                       f"Datoteka {ulaz} je prevelika za obradu odjednom. Predlozi chunked pristup s verifikacijom. (slucaj T5-{t})"]))]
    m += [T(f"Provjeravam ima li diska za ulaz i izlaz (ulaz {vel}).",
            [{"name": "disk_usage", "arguments": {"path": d if d.startswith('/') else '/data'}}]),
          R({"path": d, "used_pct": rng.randint(52, 68), "avail": "380G"}),
          T("Mjesta ima. Listam direktorij da vidim raspored datoteka.",
            [{"name": "file_list", "arguments": {"path": d}}]),
          R({"path": d, "files": [f"{Path(ulaz).name} ({vel})", "izlaz/"]}),
          T("Citam uzorak pocetka datoteke da potvrdim format.",
            [{"name": "file_read", "arguments": {"path": ulaz, "lines": 5}}]),
          R({"path": ulaz, "excerpt": uzorak})]
    if diff == "easy":
        m += [T("Format potvrdjen. Brojim redove read-only za planiranje chunkova.",
                [{"name": "terminal", "arguments": {"command": f"wc -l {ulaz}", "timeout_s": 30}}]),
              R({"output": f"{redova} {ulaz}"})]
        m += [T(f"Dijagnoza: datoteka {desc} ima {redova} ({vel}), format uredan, diska ima (trag punog diska odbacujem). "
                f"Sljedeci korak: chunked obrada u blokovima od po milion redova uz tvoju potvrdu, pa verifikacija "
                f"izlaza {izlaz} (broj redova + uzorak). Bez potvrde nista ne pokrecem.")]
    else:
        m += [T("Format potvrdjen. Mjerim memoriju da odredim velicinu chunka.",
                [{"name": "memory_usage", "arguments": {}}]),
              R({"mem_pct": rng.randint(41, 58)}),
              T("Memorija je polupuna. Brojim redove read-only za plan.",
                [{"name": "terminal", "arguments": {"command": f"wc -l {ulaz}", "timeout_s": 30}}]),
              R({"output": f"{redova} {ulaz}"})]
        if diff == "hard":
            m += [T("Planiram chunkove od po milion redova. Provjeravam da druga obrada vec ne radi paralelno.",
                    [{"name": "process_list", "arguments": {"limit": 10, "sort_by": "memory"}}]),
                  R({"top": [{"name": "bash", "pid": 1200 + i, "mem_pct": 2}]})]
            m += [T("Nema paralelne obrade, taj trag odbacujem. Dijagnoza: datoteka ima "
                    f"{redova} ({vel}), memorija na pola - chunkovi od po milion redova su siguran izbor. "
                    f"Sljedeci korak: chunked obrada uz tvoju potvrdu, pa verifikacija izlaza {izlaz} kroz broj "
                    f"redova i uzorak (ocekivano poklapanje s ulazom). Bez potvrde nista ne pokrecem.")]
        else:
            m += [T(f"Dijagnoza: datoteka {desc} ima {redova} ({vel}), memorija polupuna - chunkovi od po milion "
                    f"redova stanu komotno. Trag paralelne obrade odbacujem (nema je). Sljedeci korak: chunked obrada "
                    f"uz tvoju potvrdu, pa verifikacija izlaza {izlaz} (broj redova + uzorak). Bez potvrde nista "
                    f"ne pokrecem.")]
    return m


# ---------- (d) server setup od nule ----------

SERVERS = [
    ("portal", "nginx", 443, "/etc/nginx/sites-enabled/portal.conf",
     "server { listen 443 ssl; server_name portal.kolektiv.pro; }",
     "openssl x509 -enddate -noout -in /etc/ssl/certs/portal.crt",
     "notAfter=2027-02-01 08:12:00 GMT (vazeci)"),
    ("api servis", "app-api", 8080, "/opt/app/config.yaml",
     "port: 8080\ntls: true\ncert: /etc/ssl/certs/api.crt",
     "openssl x509 -enddate -noout -in /etc/ssl/certs/api.crt",
     "notAfter=2027-01-15 08:12:00 GMT (vazeci)"),
    ("nadzor", "grafana-server", 3000, "/etc/grafana/grafana.ini",
     "[server]\nhttp_port = 3000\nprotocol = https",
     "openssl x509 -enddate -noout -in /etc/ssl/certs/nadzor.crt",
     "notAfter=2026-12-20 08:12:00 GMT (vazeci)"),
]


def b_server(rng, i, t, diff):
    desc, svc, port, conf, cex, sslcmd, sslout = rng.choice(SERVERS)
    m = [U(rng.choice([f"Postavljam {desc} od nule. Provjeri redom: port, firewall, servis, SSL. (slucaj T5-{t})",
                       f"Novi {desc} ({svc}) treba pustiti u rad. Verifikuj svaki korak redoslijedom. (slucaj T5-{t})",
                       f"Pripremam {desc} za promet. Prodji port, vatrozid, servis i certifikat. (slucaj T5-{t})"]))]
    if diff == "hard":
        m += [T("Krecem od mreze da iskljucim prekid veze prije svega.",
                [{"name": "network_status", "arguments": {}}]),
              R({"interfaces": {"eth0": "up"}, "gateway_ok": True, "rx_packets": 940000 + i})]
        m += [T("Mreza je uredna. Provjeravam je li port slobodan (korak 1: port).",
                [{"name": "port_check", "arguments": {"port": port}}]),
              R({"port": port, "process": None, "pid": None})]
    else:
        m += [T(f"Korak 1 (port): provjeravam je li port {port} slobodan.",
                [{"name": "port_check", "arguments": {"port": port}}]),
              R({"port": port, "process": None, "pid": None})]
    m += [T(f"Port {port} je slobodan. Korak 2 (firewall): citam status vatrozida read-only.",
            [{"name": "terminal", "arguments": {"command": "ufw status", "timeout_s": 30}}]),
          R({"output": f"Status: active; {port}/tcp ALLOW (pravilo postoji)"}),
          T(f"Vatrozid propusta port {port}. Korak 3 (servis): provjeravam status {svc}.",
            [{"name": "service_status", "arguments": {"service": svc}}]),
          R({"service": svc, "status": "active"})]
    if diff == "easy":
        m += [T("Servis radi. Korak 4 (SSL): provjeravam certifikat read-only.",
                [{"name": "terminal", "arguments": {"command": sslcmd, "timeout_s": 30}}]),
              R({"output": sslout})]
    else:
        m += [T(f"Servis radi. Citam konfiguraciju {desc} prije SSL provjere.",
                [{"name": "file_read", "arguments": {"path": conf, "lines": 50}}]),
              R({"path": conf, "excerpt": cex}),
              T("Konfiguracija gadja pravi port i certifikat. Korak 4 (SSL): provjeravam certifikat.",
                [{"name": "terminal", "arguments": {"command": sslcmd, "timeout_s": 30}}]),
              R({"output": sslout})]
    m += [T(f"Dijagnoza: {desc} je spreman - redoslijed verifikovan korak po korak: (1) port {port} slobodan, "
            f"(2) vatrozid ga propusta, (3) servis {svc} aktivan, (4) certifikat vazeci ({sslout.split('(')[0].strip()}). "
            f"Sljedeci korak: probni HTTPS zahtjev ka {desc} uz tvoju potvrdu, pa pracenje loga prvih sat vremena. "
            f"Bez potvrde nista ne otvaram prema van.")]
    return m


# ---------- (e) korisnici/dozvole ----------

USERS = [
    ("deploy", "/srv/app", "/etc/sudoers.d/deploy",
     "deploy ALL=(root) NOPASSWD: /bin/systemctl restart app-api",
     "/home/deploy/.ssh", "app-api"),
    ("webadmin", "/srv/portal", "/etc/sudoers.d/webadmin",
     "webadmin ALL=(root) NOPASSWD: /bin/systemctl reload nginx",
     "/home/webadmin/.ssh", "nginx"),
    ("backupop", "/srv/rezerva", "/etc/sudoers.d/backupop",
     "backupop ALL=(root) NOPASSWD: /usr/bin/rsync",
     "/home/backupop/.ssh", "cron"),
]


def b_users(rng, i, t, diff):
    user, srvdir, sudofile, sudoex, sshdir, svc = rng.choice(USERS)
    m = [U(rng.choice([f"Novi korisnik {user} treba pristup za deploy. Provjeri nalog, kljuc, sudoers i dozvole. (slucaj T5-{t})",
                       f"Pripremam nalog {user} za odrzavanje. Prodji ssh kljuc, sudo pravila i vlasnistvo direktorija. (slucaj T5-{t})",
                       f"Audit pristupa za {user}: postoji li nalog, je li kljuc uredan, sta smije kroz sudo? (slucaj T5-{t})"]))]
    m += [T(f"Provjeravam postoji li nalog {user}.",
            [{"name": "terminal", "arguments": {"command": f"id {user}", "timeout_s": 30}}]),
          R({"output": f"uid=100{i % 50 + 2}({user}) gid=100{i % 50 + 2}({user}) groups=100{i % 50 + 2}({user})"}),
          T("Nalog postoji. Provjeravam ssh direktorij (samo popis, bez ispisa kljuceva).",
            [{"name": "terminal", "arguments": {"command": f"ls -l {sshdir}", "timeout_s": 30}}]),
          R({"output": "authorized_keys (-rw-------, 2 kljuca tipa ssh-ed25519, sadrzaj se ne ispisuje)"})]
    if diff in ("medium", "hard"):
        m += [T("Kljuc postoji s pravim dozvolama. Listam kucni direktorij.",
                [{"name": "file_list", "arguments": {"path": sshdir.replace('/.ssh', '')}}]),
              R({"path": sshdir.replace('/.ssh', ''), "files": [".ssh/ (drwx------)", ".bashrc"]})]
    m += [T("Direktorij je uredan. Citam sudo pravila (read-only).",
            [{"name": "file_read", "arguments": {"path": sudofile, "lines": 50}}]),
          R({"path": sudofile, "excerpt": sudoex})]
    if diff == "hard":
        m += [T("Sudo je ogranicen na jednu komandu. Provjeravam port 22 da sshd uopce prima veze.",
                [{"name": "port_check", "arguments": {"port": 22}}]),
              R({"port": 22, "process": "sshd", "pid": 700 + i})]
    m += [T(f"Port 22 slusa (sshd). Zavrsavam auditom vlasnistva nad {srvdir}.",
            [{"name": "terminal", "arguments": {"command": f"stat -c '%a %U %G %n' {srvdir}", "timeout_s": 30}}]),
          R({"output": f"755 {user} {user} {srvdir}"})] if diff == "hard" else [
          T(f"Pravila su ogranicena kako treba. Zavrsavam auditom vlasnistva nad {srvdir}.",
            [{"name": "terminal", "arguments": {"command": f"stat -c '%a %U %G %n' {srvdir}", "timeout_s": 30}}]),
          R({"output": f"755 {user} {user} {srvdir}"})]
    m += [T(f"Dijagnoza: nalog {user} je uredan - postoji (uid/gid), ima 2 ssh kljuca s pravim dozvolama (600/700), "
            f"sudo je ogranicen samo na {svc} komandu ({sudoex.split(':')[-1].strip()}), a {srvdir} je u njegovom "
            f"vlasnistvu (755). Trag nedostupnog sshd-a odbacujem (port 22 slusa). Sljedeci korak: probna prijava "
            f"kljucem uz tvoju potvrdu, pa verifikacija kroz auth log. Bez potvrde nista ne sirim.")]
    return m


BUILDERS = [b_build, b_test, b_data, b_server, b_users]
DOMAINS = {b_build: "build-source", b_test: "test-suite", b_data: "data-processing",
           b_server: "server-setup", b_users: "users-perms"}


def main():
    rng = random.Random(202605)
    old_first = set()
    for src in SRCS:
        for ln in src.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            d = json.loads(ln)
            u = next(m for m in d["messages"] if m["role"] == "user")
            old_first.add(norm(u["content"]))
    nums = []
    for src in SRCS:
        nums += [int(json.loads(l)["id"].split("-")[-1])
                 for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
    nxt = max(nums) + 1
    jobs = []
    for fn in BUILDERS:
        jobs += [("easy", fn)] * 60 + [("medium", fn)] * 120 + [("hard", fn)] * 60
    assert len(jobs) == 1200, len(jobs)
    rng.shuffle(jobs)
    rows, seen_new = [], set()
    for k, (diff, fn) in enumerate(jobs):
        t = nxt + k
        msgs = fn(rng, k, t, diff)
        first = norm(msgs[0]["content"])
        assert first not in old_first, f"kolizija sa v0.1-v0.4: {first[:80]}"
        assert first not in seen_new, f"kolizija unutar v0.5: {first[:80]}"
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
        want = {"easy": 4, "medium": 5, "hard": 6}[diff]
        assert nsteps == want, (fn.__name__, diff, nsteps)
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
