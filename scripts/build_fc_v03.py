#!/usr/bin/env python3
"""Template expansion v0.3 za function-calling dataset.

Generise ~3000 NOVIH redova (deterministicki, seed=43) sa dimenzijama
kojih nema u v0.2: uslovni upiti nad logovima, paketski lanci
query->install->verify, file_list+file_read lanci, network+port
kombinacije, filtriranje procesa, terminal fallback SAMO gdje high-level
alat ne postoji (uz obrazlozenje), 12 novih servisa, hard sa 3 tool
poziva. Izlaz: datasets/canonical/function_calling_v0.3.jsonl
Ne dira postojece fajlove ni datasets/splits/.

Usage: .venv/bin/python scripts/build_fc_v03.py
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

SEED = 43
ROOT = Path(__file__).resolve().parent.parent
V01 = ROOT / "datasets/canonical/function_calling_v0.1.jsonl"
V02 = ROOT / "datasets/canonical/function_calling_v0.2.jsonl"
OUT = ROOT / "datasets/canonical/function_calling_v0.3.jsonl"

# 12 novih servisa (nema ih u v0.2 SERVICES listi)
SERVICES = ["gunicorn", "celery", "celery-beat", "minio", "prometheus",
            "grafana-server", "memcached", "rabbitmq-server",
            "elasticsearch", "node-app", "vault", "loki"]
# novi portovi (nema ih u v0.2 PORTS listi) + mapiranje na servise
PORT_SVC = {25: "postfix", 110: "dovecot", 143: "dovecot", 389: "slapd",
            636: "slapd", 2049: "nfs-server", 2181: "zookeeper",
            27017: "mongod", 5601: "kibana", 8125: "statsd",
            8400: "consul", 8500: "consul", 9000: "minio",
            9200: "elasticsearch", 9300: "elasticsearch",
            11211: "memcached", 15672: "rabbitmq-server",
            2375: "docker", 6443: "kubelet"}
PORTS = sorted(PORT_SVC)
# nove putanje / direktoriji / fajlovi (nema ih u v0.2)
DISK_PATHS = ["/srv", "/var/lib", "/var/spool", "/srv/backups",
              "/var/lib/postgres", "/opt/minio", "/var/lib/redis", "/mnt"]
DIRS = ["/etc/celery", "/etc/minio", "/etc/prometheus", "/srv/backups",
        "/etc/grafana", "/opt/minio", "/var/lib/redis", "/etc/fail2ban",
        "/var/spool/cron", "/etc/rabbitmq"]
FILES = ["/etc/celery/worker.conf", "/etc/minio/config",
         "/etc/prometheus/prometheus.yml", "/etc/grafana/grafana.ini",
         "/etc/fail2ban/jail.local", "/var/log/celery/worker.log",
         "/var/log/minio/minio.log", "/etc/redis/redis.conf",
         "/etc/mysql/my.cnf", "/opt/app/config.yaml"]
DIR_FILE = {"/etc/celery": "/etc/celery/worker.conf",
            "/etc/minio": "/etc/minio/config",
            "/etc/prometheus": "/etc/prometheus/prometheus.yml",
            "/srv/backups": "/opt/app/config.yaml",
            "/etc/grafana": "/etc/grafana/grafana.ini",
            "/opt/minio": "/etc/minio/config",
            "/var/lib/redis": "/etc/redis/redis.conf",
            "/etc/fail2ban": "/etc/fail2ban/jail.local",
            "/var/spool/cron": "/var/log/celery/worker.log",
            "/etc/rabbitmq": "/etc/mysql/my.cnf"}
DISK_DIR = {"/srv": "/srv/backups", "/var/lib": "/var/lib/redis",
            "/var/spool": "/var/spool/cron", "/srv/backups": "/srv/backups",
            "/var/lib/postgres": "/var/lib/redis", "/opt/minio": "/opt/minio",
            "/var/lib/redis": "/var/lib/redis", "/mnt": "/srv/backups"}
# (a) fraze/nivoi za uslovne upite nad logovima (filtar radi model nad rezultatom)
PHRASES = ["OutOfMemory", "connection refused", "timeout",
           "Failed password", "segfault", "TLS handshake",
           "upstream timed out", "disk quota"]
LEVELS = ["samo greske", "upozorenja i greske", "samo kriticne poruke",
          "samo linije sa ERROR", "sve iz WARN navise"]
LOG_LINES = [15, 40, 60, 120, 250]
# (e) filteri procesa (model filtrira nad rezultatom process_list)
PROCS = ["nginx", "postgres", "redis-server", "celery", "gunicorn",
         "java", "python3", "node"]
THRESH = ["preko 80% CPU-a", "preko 50% memorije", "preko 500M memorije",
          "preko 2% CPU-a stalno", "sa najvecim RSS-om"]
# (b) novi paketi (nema ih u v0.2 PACKAGES listi)
PACKAGES = ["ripgrep", "bat", "eza", "dust", "procs", "httpie", "restic",
            "borgbackup", "mc", "lsof", "sysstat", "iotop"]
# (f) terminal SAMO za stvari bez high-level alata (read-only, bez DENY obrazaca)
TERMINAL_CMDS = ["timedatectl status", "hostnamectl status", "id ubuntu",
                 "getent hosts db-primary", "ls -la /etc/celery",
                 "sha256sum /etc/hosts", "stat /var/log/syslog",
                 "du -sh /srv/backups", "ls -la /srv/backups",
                 "curl -sI http://localhost:80 | head -n 10",
                 "ping -c 3 8.8.8.8", "dig +short example.com",
                 "ss -tulpn | head -n 20",
                 "lsblk -o NAME,SIZE,TYPE,MOUNTPOINT",
                 "blkid | head -n 10", "mount | grep ' / '",
                 "sysctl vm.swappiness", "cat /proc/uptime",
                 "ls -la /etc/ssl/certs | head -n 20",
                 "date -u && uptime"]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


EASY_CTX = ["", "Jutros na dezurstvu. ", "Prije predaje smjene. ",
            "Za zapisnik. ", "Usput. ", "Kad stignes. "]
MED_CTX = ["Aplikacija se cudno ponasa. ", "Prije nocnog deploya. ",
           "Nakon migracije podataka. ", "Korisnici prijavljuju spor rad. ",
           "Radim jutarnju smotru. ", "Monitoring je nesto dojavio. ",
           "Prije prosirenja klastera. ", "Disk upozorava vec danima. "]

# ------------------------------------------------------------------ EASY (1 poziv)
EASY_T = {
 "service_status": [
    "Kakvo je stanje {service} servisa jutros?",
    "Je li {service} dignut i uredan?", "Radi li {service} kako treba?",
    "Provjeri je li {service} ziv.", "Da li {service} uredno slusa?",
    "Javi stanje servisa {service}.", "Vrijedi li {service} provjeriti?",
    "Baci pogled na {service}, je li aktivan?",
    "Je li {service} u funkciji?", "Daj status za {service}.",
    "Sto kaze {service}, radi li?", "Provjeri {service} prije smjene.",
    "Treba mi status od {service}.", "Je li {service} pao?",
    "Prikazi mi stanje {service}."],
 "service_restart": [
    "Restartuj {service} servis radi osvjezenja.",
    "Uradi restart servisa {service}.", "Treba restartovati {service}.",
    "Digni ponovo {service}.", "Moze restart za {service}?",
    "Osvjezi {service} jednim restartom.", "Restartuj {service} cistoce radi.",
    "Ponovo digni {service} servis.", "Resetuj {service} kroz restart.",
    "Izvrsi restart nad {service}.", "Daj {service} jedan restart.",
    "Provjetri {service} restartom."],
 "service_logs": [  # (a) vremenski/uslovni upiti; alat prima service+lines
    "Izvadi zadnjih {lines} linija loga za {service}, zanimaju me zapisi sa '{phrase}'.",
    "Daj {lines} linija loga od {service} pa izdvoji gdje se spominje '{phrase}'.",
    "Pogledaj log servisa {service} ({lines} linija) i nadji '{phrase}'.",
    "Treba mi log za {service}, zadnjih {lines} linija, nivo: {level}.",
    "Prelistaj zadnjih {lines} linija loga {service} i izbroj koliko ima sa '{phrase}'.",
    "Iz loga {service} ({lines} linija) izdvoji {level}.",
    "Sta se zadnje desavalo sa {service}? Daj {lines} linija i oznaci '{phrase}'.",
    "Za {service} mi daj {lines} linija loga unazad i filtriraj '{phrase}'.",
    "Provjeri {level} u logu {service} kroz zadnjih {lines} linija.",
    "Daj svjezi log {service} ({lines} linija), trazim tragove '{phrase}'.",
    "Iscitaj {lines} linija loga za {service} unazad sat vremena, fokus '{phrase}'.",
    "Pregledaj rep loga {service} ({lines} linija) i javi ima li '{phrase}'.",
    "Zadnjih {lines} linija za {service}, zanimaju me {level}.",
    "Izvuci iz loga {service} ({lines} linija) sve sto lici na '{phrase}'.",
    "Daj mi {lines} linija loga servisa {service} pa naglasi {level}.",
    "Provjeri ima li '{phrase}' u zadnjih {lines} linija loga {service}."],
 "disk_usage": [
    "Koliko je puno na {path}?", "Provjeri popunjenost diska {path}.",
    "Ima li jos lufta na {path}?", "Daj popunjenost za {path}.",
    "Je li {path} pred pucanjem?", "Kakva je popunjenost na {path}?",
    "Prikazi koliko je ostalo na {path}.", "Provjeri disk {path} za izvjestaj.",
    "Koliko gigabajta je slobodno na {path}?", "Javi stanje diska {path}."],
 "memory_usage": [
    "Kakva je iskoristenost RAM-a jutros?", "Koliko RAM-a je ostalo slobodno?",
    "Je li RAM pri vrhu?", "Daj iskoristenost radne memorije.",
    "Koliko je RAM-a zauzeto trenutno?", "Prikazi stanje radne memorije.",
    "Je li ostalo dovoljno RAM-a za novi servis?", "Kakav je RAM na masini?",
    "Provjeri RAM za zapisnik.", "Koliko memorije aplikacije drze?"],
 "cpu_usage": [
    "Kakvo je stanje procesora?", "Koliko je procesor opterecen?",
    "Je li CPU na izdisaju?", "Daj trenutno opterecenje CPU-a.",
    "Kakav je CPU load?", "Provjeri procesor za zapisnik.",
    "Ima li CPU jos lufta?", "Koliko procesor trosi?",
    "Je li masina preopterecena procesorski?", "Prikazi CPU potrosnju."],
 "process_list": [  # (e) filter u tekstu; alat prima limit+sort_by
    "Nadji procese '{proc}' medju prvih {limit} po {sort}.",
    "Izdvoji '{proc}' iz liste od {limit} procesa sortiranih po {sort}.",
    "Daj {limit} procesa po {sort}, zanimaju me samo '{proc}'.",
    "Provjeri ima li '{proc}' medju top {limit} po {sort}.",
    "Izlistaj {limit} procesa po {sort} pa izdvoji '{proc}'.",
    "Koji '{proc}' procesi trose najvise? Daj {limit} po {sort}.",
    "Pregledaj prvih {limit} po {sort} i javi za '{proc}'.",
    "Ima li procesa {thresh}? Pogledaj {limit} po {sort}.",
    "Izbroj procese {thresh} medju prvih {limit} po {sort}.",
    "Daj {limit} procesa sortiranih po {sort}, oznaci one {thresh}.",
    "Provjeri potrosace {thresh}: izlistaj {limit} po {sort}.",
    "Ko trosi {thresh}? Treba mi {limit} procesa po {sort}.",
    "Snimi {limit} procesa po {sort}, fokus na one {thresh}.",
    "Za izvjestaj: {limit} procesa po {sort}, izdvoji {thresh}."],
 "network_status": [
    "Kakvi su mrezni interfejsi jutros?", "Je li mreza stabilna?",
    "Provjeri mrezne interfejse za zapisnik.", "Ima li mreza problema?",
    "Daj pregled mreze.", "Jesu li svi interfejsi dignuti?",
    "Provjeri mrezno stanje masine.", "Kakva je konektivnost servera?",
    "Javi stanje mreze ukratko.", "Da li mreza radi uredno?"],
 "port_check": [
    "Ko drzi port {port}?", "Sta slusa na {port}?",
    "Provjeri ko je na portu {port}.", "Je li {port} slobodan ili zauzet?",
    "Koji servis slusa {port}?", "Daj proces iza porta {port}.",
    "Vidi sta je na portu {port}.", "Port {port}, ko ga drzi?",
    "Provjeri zauzetost porta {port}.", "Treba mi vlasnik porta {port}.",
    "Javi ko slusa na portu {port}.", "Identifikuj slusaoca na {port}."],
 "terminal": [  # (f) fallback: nema high-level alata + zasto
    "Provjeri sistemsko vrijeme (`{command}`); za ovo nema high-level alat pa koristi terminal.",
    "Treba mi `{command}`; high-level alat za to ne postoji, odradi preko terminala.",
    "Izvrsi `{command}` jer to nijedan high-level alat ne pokriva.",
    "Daj `{command}`; posto nema viseg alata za sistemsko vrijeme/identitet, koristi terminal.",
    "Odradi `{command}` preko terminala, high-level alternativa ne postoji.",
    "Pokreni `{command}`; za ovu provjeru nema namjenski alat pa ide terminal.",
    "Treba mi izlaz iz `{command}`, a to se moze samo terminalom.",
    "Provjeri `{command}`; high-level alati to ne pokrivaju, zato terminal.",
    "Daj mi `{command}` preko terminala jer viseg alata za to nema.",
    "Odradi nisku provjeru `{command}`; namjenski alat ne postoji.",
    "Izvrsi `{command}`; terminal je jedini put posto high-level alat izostaje.",
    "Za evidenciju treba `{command}`; odradi terminalom jer alat za to nemamo."],
 "package_query": [
    "Je li {package} prisutan na sistemu?", "Vidi ima li paketa {package}.",
    "Koja verzija {package} je gore?", "Provjeri {package} za zapisnik.",
    "Da li je {package} instaliran?", "Treba mi status paketa {package}.",
    "Javi verziju paketa {package}.", "Provjeri postoji li {package}.",
    "Daj info o paketu {package}.", "Je li {package} dostupan?"],
 "package_install": [
    "Instaliraj {package} na server.", "Dodaj {package} na masinu.",
    "Treba nam {package}, postavi ga.", "Ubaci paket {package}.",
    "Moze instalacija za {package}?", "Postavi alat {package}.",
    "Namjesti {package} na sistem.", "Dodaj mi {package}, treba za posao.",
    "Instaliraj alat {package}.", "Stavi {package} gore."],
 "file_list": [
    "Sta se nalazi u {path}?", "Izlistaj {path} za pregled.",
    "Daj sadrzaj direktorija {path}.", "Pogledaj sta ima u {path}.",
    "Listaj {path}.", "Prikazi fajlove iz {path}.",
    "Treba mi listing za {path}.", "Sta drzi {path}?",
    "Baci pogled u {path}.", "Izlistaj sadrzaj {path}."],
 "file_read": [
    "Otvori fajl {path}.", "Daj sadrzaj fajla {path}.",
    "Procitaj {path}.", "Sta pise u {path}?",
    "Prikazi {path} u cijelosti.", "Treba mi {path} na uvid.",
    "Otvori {path} i prikazi.", "Daj mi {path} za pregled.",
    "Iscitaj fajl {path}.", "Pogledaj sadrzaj {path}."],
}

# ---------------------------------------------------------------- MEDIUM (2 poziva)
# (b) paketni lanac, (c) file lanac, (d) mreza+port, (a) status+uslovni log
MED_FAMS = {
 "pkg_chain": [
    "Treba mi {package} za alat. Provjeri je li tu pa ga instaliraj.",
    "Za novi posao treba {package}. Vidi instalaciju pa postavi {package}.",
    "Fali nam {package}. Prvo provjera paketa pa instalacija.",
    "Prije skripte osiguraj {package}: provjeri pa instaliraj.",
    "Kolega trazi {package}. Provjeri stanje pa ga dodaj.",
    "Deploy ocekuje {package}. Provjeri paket pa instaliraj ako ga nema.",
    "Namjesti {package}: prvo vidi je li instaliran pa ga postavi.",
    "Treba {package} na masini. Provjera pa instalacija.",
    "Za monitoring fali {package}. Provjeri i instaliraj.",
    "Ubaci {package}: provjeri prisutnost pa instaliraj."],
 "file_chain": [
    "Pogledaj sta ima u {dir} pa otvori {file}.",
    "Prvo izlistaj {dir}, pa mi prikazi {file}.",
    "Treba mi {file}. Listaj {dir} pa ga procitaj.",
    "Provjeri sadrzaj {dir} pa otvori {file} za pregled.",
    "Za audit: listing {dir} pa sadrzaj {file}.",
    "Nadji {file} kroz {dir} pa ga prikazi.",
    "Izlistaj {dir} pa iscitaj {file}.",
    "Prije izmjene vidi {dir} pa otvori {file}.",
    "Daj listing {dir} i onda sadrzaj {file}.",
    "Kreni od {dir} pa mi daj {file}."],
 "net_port": [
    "Aplikacija ne odgovara. Provjeri mrezu pa ko slusa na portu {port}.",
    "Sumnjam na mrezu. Daj status mreze pa provjeri port {port}.",
    "Servis cuti. Prvo mrezni status, pa vlasnik porta {port}.",
    "Konekcije zastaju. Provjeri interfejse pa port {port}.",
    "Nesto ne stima sa mrezom. Status mreze pa provjera porta {port}.",
    "Prije otvaranja porta {port} provjeri mrezu pa ko ga drzi.",
    "Latency skace. Daj mrezu pa vidi port {port}.",
    "Provjeri je li mreza uredna pa ko slusa {port}.",
    "Za dijagnostiku: mrezni status pa port {port}.",
    "Jutros mreza steka. Provjeri stanje pa port {port}."],
 "status_log": [
    "{Service} cudno radi. Provjeri status {service} pa {lines} linija loga sa fokusom '{phrase}'.",
    "Zalbe na {service}. Prvo status, pa {lines} linija loga ({level}).",
    "{Service} se ponasa cudno. Status pa {lines} linija loga, trazi '{phrase}'.",
    "Provjeri {service}: status pa zadnjih {lines} linija, zanimaju me {level}.",
    "Nesto smrdi oko {service}. Daj status pa {lines} linija loga sa '{phrase}'.",
    "{Service} usporio. Provjeri status pa {lines} linija loga unazad.",
    "Monitoring dojavio {service}. Status pa {lines} linija, fokus '{phrase}'.",
    "Prelistaj {service}: status pa {lines} linija loga ({level}).",
    "Sumnja na {service}. Prvo status, pa {lines} linija i izdvoji '{phrase}'.",
    "Dijagnostika za {service}: status pa {lines} linija loga."],
 "disk_file": [
    "{path} se puni. Provjeri zauzece pa izlistaj {dir}.",
    "Nestaje mjesta na {path}. Daj zauzece i sadrzaj {dir}.",
    "Prije ciscenja: zauzece {path} pa listing {dir}.",
    "Provjeri {path} pa vidi sta je u {dir}.",
    "Upozorenje za {path}. Stanje diska pa sadrzaj {dir}.",
    "Backup staje? Provjeri {path} pa izlistaj {dir}.",
    "Koliko je {path} pun i sta drzi {dir}?",
    "Za izvjestaj: zauzece {path} plus listing {dir}."],
 "res_proc": [
    "Masina steka. Provjeri memoriju pa top {limit} po memoriji.",
    "Load skocio. Daj CPU pa top {limit} po CPU-u.",
    "Nesto guta resurse. Stanje memorije pa {limit} procesa po memoriji.",
    "Spor rad. Provjeri CPU pa {limit} najvecih potrosaca.",
    "Prije restarta snimi memoriju i {limit} procesa po memoriji.",
    "Provjeri ima li curenja: memorija pa {limit} po memoriji.",
    "Ventilatori bruje. CPU stanje pa top {limit} po CPU-u.",
    "Aplikacija stuca. Memorija pa {limit} procesa po memoriji.",
    "Za zapisnik: CPU plus {limit} procesa po CPU-u.",
    "Sumnjam na zaguzenje. Daj memoriju pa {limit} po memoriji."],
 "status_restart": [
    "{Service} ne prima promet. Provjeri status {service} pa ga restartuj.",
    "Nakon izmjene configa za {service}: provjeri status pa restartuj.",
    "{Service} zaglavio. Status pa restart {service}.",
    "Deploy gotov za {service}. Provjeri status pa uradi restart.",
    "{Service} trosi previse. Vidi status pa ga restartuj.",
    "Log pun gresaka za {service}. Status pa restart.",
    "{Service} ne odgovara. Provjeri pa restartuj {service}.",
    "Osvjezi {service}: prvo status pa restart."],
 "port_svc": [
    "Nesto drzi port {port}. Ko slusa pa kakav je status {service}?",
    "Prije dizanja {service} provjeri port {port} i status {service}.",
    "Konflikt na {port}. Identifikuj proces pa provjeri {service}.",
    "Port {port} zauzet. Vidi ko slusa pa status {service}.",
    "{Service} se ne veze za {port}. Provjeri port pa status {service}.",
    "Dvije stvari ciljaju {port}. Ko slusa i radi li {service}?"],
}

# ------------------------------------------------------------------ HARD (3 poziva, param. iz prethodnih rezultata)
HARD_FAMS = {
 "pkg_verify": [  # query -> install -> query (verify)
    "Treba mi {package} za produkciju. Provjeri, instaliraj pa potvrdi verziju.",
    "Osiguraj {package}: provjera, instalacija pa zavrsna potvrda.",
    "Novi agent trazi {package}. Provjeri, postavi pa verificiraj.",
    "Za pipeline treba {package}. Prvo vidi stanje, instaliraj pa potvrdi.",
    "Pripremi {package}: provjeri prisutnost, instaliraj pa provjeri verziju.",
    "Stavi {package} gore: provjera, instalacija pa kontrolna provjera.",
    "Treba nam {package} hitno. Provjeri, instaliraj pa javi verziju.",
    "Za skriptu osiguraj {package}: status, instalacija pa verifikacija.",
    "Dodaj {package} i potvrdi da je zaista instaliran: provjeri, instaliraj, provjeri.",
    "Inicijalni setup trazi {package}. Provjera pa instalacija pa potvrda.",
    "Ubaci {package} na cistu masinu: vidi stanje, instaliraj pa verificiraj.",
    "Kolegi treba {package}. Provjeri, dodaj pa potvrdi instalaciju."],
 "disk_triage": [  # disk -> file_list -> file_read (sve izvedeno)
    "{path} je skoro pun. Provjeri zauzece, izlistaj {dir} pa otvori {file}.",
    "Nestaje prostora na {path}. Daj zauzece, listing {dir} pa sadrzaj {file}.",
    "Prije ciscenja {path}: stanje diska, sta je u {dir}, pa prikazi {file}.",
    "Upozorenje za disk {path}. Provjeri zauzece, izlistaj {dir} pa procitaj {file}.",
    "Logovi pune {path}. Koliko je pun, sta je u {dir} i sta pise u {file}?",
    "Backup ne staje na {path}. Zauzece, listing {dir} pa uvid u {file}.",
    "Rijesi guzvu na {path}: provjeri disk, izlistaj {dir} pa otvori {file}.",
    "Za audit diska {path}: zauzece, sadrzaj {dir} pa sadrzaj {file}.",
    "Ciscenje {path} ceka. Prvo zauzece, pa {dir}, pa procitaj {file}.",
    "Provjeri katastrofu na {path}: disk, {dir} pa {file}."],
 "net_triage": [  # network -> port -> service (servis izveden iz porta)
    "Servis na portu {port} cuti. Provjeri mrezu, ko slusa {port} pa status {service}.",
    "Nedostupan {service}. Prvo mreza, pa vlasnik porta {port}, pa status {service}.",
    "Klijenti ne dolaze do {service}. Mreza, port {port} pa status {service}.",
    "Sumnja na prekid prema {service}. Provjeri mrezu, port {port} pa {service}.",
    "Za dijagnostiku {service}: mrezni status, ko drzi {port}, pa status servisa.",
    "Port {port} cuti a treba {service}. Mreza pa port pa status {service}.",
    "Provjeri lanac do {service}: mreza, slusalac na {port}, pa status.",
    "Nakon promjene firewalla: mreza, port {port} pa status {service}.",
    "{service} nedostupan izvana. Kreni od mreze, preko porta {port} do statusa.",
    "Ispitaj put do {service}: status mreze, provjera {port}, pa status servisa."],
 "svc_recovery": [  # status -> logs -> restart
    "{Service} se rusi. Provjeri status {service}, izvadi {lines} linija loga pa ga restartuj.",
    "{Service} ne odgovara. Status, {lines} linija loga pa restart {service}.",
    "Spasi {service}: vidi status, {lines} linija loga pa restartuj.",
    "{Service} zaglavio nakon deploya. Status, log ({lines} linija) pa restart.",
    "Intervencija nad {service}: status, {lines} linija loga pa restart.",
    "{Service} prijavljuju korisnici. Status pa {lines} linija pa restart {service}.",
    "Oporavi {service}: provjeri status, snimi {lines} linija loga pa restartuj.",
    "{Service} curi memorija. Status, {lines} linija loga pa restart.",
    "Hitno za {service}: status, brzi log ({lines} linija) pa restart.",
    "Stabilizuj {service}: status, {lines} linija loga pa restartuj."],
 "log_escalation": [  # status -> logs(50) -> logs(200) prosireno po nalazu
    "{Service} baca greske sa '{phrase}'. Status, pa {a} linija loga, pa prosiri na {b} ako ima traga.",
    "Trag '{phrase}' u {service}. Provjeri status, uzmi {a} linija pa produbi na {b}.",
    "{Service} sumnjiv na '{phrase}'. Status pa {a} linija, pa siri zahvat od {b} linija.",
    "Goni '{phrase}' kroz {service}: status, {a} linija pa eskaliraj na {b}.",
    "{Service} i '{phrase}' u logu. Status, uzi uzorak {a} pa punih {b} linija.",
    "Provjeri '{phrase}' u {service}: status, {a} linija pa prosiri na {b}.",
    "Eskalacija za {service}: status, {a} linija loga pa {b} linija po nalazu.",
    "Za {service} treba dublji log oko '{phrase}': status, {a} pa {b} linija."],
 "proc_drill": [  # cpu/mem -> process_list -> process_list (refinirano po nalazu)
    "Masina stenje. Provjeri CPU, izlistaj {a} po CPU-u pa {b} po memoriji po nalazu.",
    "Sporost bez uzroka. Daj memoriju, {a} procesa po memoriji pa {b} po CPU-u.",
    "Trazi potrosaca. CPU stanje, top {a} po CPU-u pa provjeri i {b} po memoriji.",
    "Sumnja na curenje. Memorija, {a} po memoriji pa suzi na {b} po CPU-u.",
    "Dijagnostika loada: CPU, {a} procesa po CPU-u pa {b} po memoriji za poredjenje.",
    "Prije intervencije: memorija, {a} po memoriji pa {b} po CPU-u po nalazu.",
    "Nejasno zaguzenje. CPU, {a} po CPU-u pa jos {b} po memoriji.",
    "Snimi stanje: memorija, top {a} po memoriji pa top {b} po CPU-u."],
}

MED_ASST = ["Krecem od provjere.", "Prvo provjeravam navedeno.",
            "Provjeravam pa javljam nalaz.", "Idem korak po korak."]

META = {"author": "agentmujo-team", "quality_tier": "SILVER",
        "source": "template-expansion-v0.3",
        "verification_status": "verified"}


def tool_resp(tool, a):
    if tool == "service_status":
        return json.dumps({"service": a["service"], "status": "active"}, ensure_ascii=False)
    if tool == "service_restart":
        return json.dumps({"service": a["service"], "action": "restart", "result": "ok"}, ensure_ascii=False)
    if tool == "service_logs":
        return json.dumps({"service": a["service"], "lines": a.get("lines", 50),
                           "tail": ["... log linija ..."]}, ensure_ascii=False)
    if tool == "disk_usage":
        return json.dumps({"path": a.get("path", "/"), "used_pct": 71, "avail": "9G"}, ensure_ascii=False)
    if tool == "memory_usage":
        return json.dumps({"mem_pct": 44, "available": "9G"}, ensure_ascii=False)
    if tool == "cpu_usage":
        return json.dumps({"cpu_pct": 27}, ensure_ascii=False)
    if tool == "process_list":
        return json.dumps({"top": [{"pid": 2345, "name": "celery"},
                                   {"pid": 678, "name": "gunicorn"}]}, ensure_ascii=False)
    if tool == "network_status":
        return json.dumps({"interfaces": {"up": ["eth0"]}}, ensure_ascii=False)
    if tool == "port_check":
        return json.dumps({"port": a["port"], "process": "unknown"}, ensure_ascii=False)
    if tool == "terminal":
        return json.dumps({"result": "ok", "output": "... izlaz komande ..."}, ensure_ascii=False)
    if tool == "package_query":
        return json.dumps({"package": a["package"], "installed": True,
                           "version": "2.0.1"}, ensure_ascii=False)
    if tool == "package_install":
        return json.dumps({"package": a["package"], "result": "ok"}, ensure_ascii=False)
    if tool == "file_list":
        return json.dumps({"path": a["path"], "entries": ["worker.conf", "app.log"]}, ensure_ascii=False)
    if tool == "file_read":
        return json.dumps({"path": a["path"], "preview": "... sadrzaj fajla ..."}, ensure_ascii=False)
    raise ValueError(tool)


def final_text(tool, a):
    if tool == "service_status":
        return f"Servis {a['service']} je aktivan."
    if tool == "service_restart":
        return f"{a['service']} je restartovan."
    if tool == "service_logs":
        return f"Ovo je zadnjih {a.get('lines', 50)} linija loga za {a['service']}."
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


SORT_LAB = {"cpu": "CPU-u", "memory": "memoriji", "pid": "PID-u", "name": "imenu"}


def easy_cands(tool, rng):
    out = []
    for t in EASY_T[tool]:
        if tool in ("service_status", "service_restart"):
            for s in SERVICES:
                for ctx in EASY_CTX:
                    out.append((ctx + t.format(service=s), {"service": s}))
        elif tool == "service_logs":
            for s in SERVICES:
                for n in LOG_LINES:
                    for ph in PHRASES:
                        for lv in LEVELS:
                            try:
                                u = t.format(service=s, lines=n, phrase=ph, level=lv)
                            except (KeyError, IndexError):
                                continue
                            for ctx in EASY_CTX[:2]:
                                out.append((ctx + u, {"service": s, "lines": n}))
        elif tool == "disk_usage":
            for p in DISK_PATHS:
                for ctx in EASY_CTX:
                    out.append((ctx + t.format(path=p), {"path": p}))
        elif tool in ("memory_usage", "cpu_usage", "network_status"):
            for ctx in EASY_CTX:
                out.append((ctx + t, {}))
        elif tool == "process_list":
            for lim in (5, 10, 15, 25):
                for sb in ("cpu", "memory", "pid", "name"):
                    lab = SORT_LAB[sb]
                    for pr in PROCS:
                        for th in THRESH:
                            try:
                                u = t.format(limit=lim, sort=lab, proc=pr, thresh=th)
                            except (KeyError, IndexError):
                                continue
                            out.append((u, {"limit": lim, "sort_by": sb}))
        elif tool == "port_check":
            for p in PORTS:
                for ctx in EASY_CTX:
                    out.append((ctx + t.format(port=p), {"port": p}))
        elif tool == "terminal":
            for c in TERMINAL_CMDS:
                for ctx in EASY_CTX[:2]:
                    out.append((ctx + t.format(command=c), {"command": c}))
        elif tool in ("package_query", "package_install"):
            for p in PACKAGES:
                for ctx in EASY_CTX:
                    out.append((ctx + t.format(package=p), {"package": p}))
        elif tool == "file_list":
            for d in DIRS:
                for ctx in EASY_CTX:
                    out.append((ctx + t.format(path=d), {"path": d}))
        elif tool == "file_read":
            for f in FILES:
                for ctx in EASY_CTX:
                    out.append((ctx + t.format(path=f), {"path": f}))
    return out


def med_cands(fam, rng):
    out = []
    for t in MED_FAMS[fam]:
        if fam == "pkg_chain":
            for p in PACKAGES:
                for ctx in MED_CTX:
                    out.append((ctx + t.format(package=p),
                                [("package_query", {"package": p}),
                                 ("package_install", {"package": p})]))
        elif fam == "file_chain":
            for d in DIRS:
                for ctx in MED_CTX:
                    out.append((ctx + t.format(dir=d, file=DIR_FILE[d]),
                                [("file_list", {"path": d}),
                                 ("file_read", {"path": DIR_FILE[d]})]))
        elif fam == "net_port":
            for p in PORTS:
                for ctx in MED_CTX:
                    out.append((ctx + t.format(port=p),
                                [("network_status", {}),
                                 ("port_check", {"port": p})]))
        elif fam == "status_log":
            for s in SERVICES:
                for n in LOG_LINES:
                    for ph in PHRASES[:4]:
                        for lv in LEVELS[:3]:
                            u = t.format(Service=s.capitalize(), service=s,
                                         lines=n, phrase=ph, level=lv)
                            out.append((u, [("service_status", {"service": s}),
                                            ("service_logs", {"service": s,
                                                              "lines": n})]))
        elif fam == "disk_file":
            for p in DISK_PATHS:
                for ctx in MED_CTX:
                    out.append((ctx + t.format(path=p, dir=DISK_DIR[p]),
                                [("disk_usage", {"path": p}),
                                 ("file_list", {"path": DISK_DIR[p]})]))
        elif fam == "res_proc":
            for lim in (5, 10, 15, 20):
                for ctx in MED_CTX[:4]:
                    u = ctx + t.format(limit=lim)
                    base = ("cpu_usage", {}) if "po CPU" in u else ("memory_usage", {})
                    sb = "memory" if base[0] == "memory_usage" else "cpu"
                    out.append((u, [base, ("process_list", {"limit": lim,
                                                            "sort_by": sb})]))
        elif fam == "status_restart":
            for s in SERVICES:
                for ctx in MED_CTX[:2]:
                    u = ctx + t.format(Service=s.capitalize(), service=s)
                    out.append((u, [("service_status", {"service": s}),
                                    ("service_restart", {"service": s})]))
        elif fam == "port_svc":
            for p in PORTS:
                svc = PORT_SVC[p]
                for ctx in MED_CTX:
                    u = t.format(port=p, service=svc, Service=svc.capitalize())
                    out.append((u, [("port_check", {"port": p}),
                                    ("service_status", {"service": svc})]))
    return out


HARD_PRE = ["", "Hitno. ", "Za dezurni zapisnik. ",
             "Prije intervencije na produkciji. "]


def hard_cands(fam, rng):
    out = []
    for t in HARD_FAMS[fam]:
        if fam == "pkg_verify":
            for p in PACKAGES:
                out.append((t.format(package=p),
                            [("package_query", {"package": p}),
                             ("package_install", {"package": p}),
                             ("package_query", {"package": p})]))
        elif fam == "disk_triage":
            for pa in DISK_PATHS:
                d = DISK_DIR[pa]
                out.append((t.format(path=pa, dir=d, file=DIR_FILE[d]),
                            [("disk_usage", {"path": pa}),
                             ("file_list", {"path": d}),
                             ("file_read", {"path": DIR_FILE[d]})]))
        elif fam == "net_triage":
            for p in PORTS:
                svc = PORT_SVC[p]
                out.append((t.format(port=p, service=svc,
                                     Service=svc.capitalize()),
                            [("network_status", {}),
                             ("port_check", {"port": p}),
                             ("service_status", {"service": svc})]))
        elif fam == "svc_recovery":
            for s in SERVICES:
                for n in (50, 100):
                    out.append((t.format(Service=s.capitalize(), service=s,
                                         lines=n),
                                [("service_status", {"service": s}),
                                 ("service_logs", {"service": s, "lines": n}),
                                 ("service_restart", {"service": s})]))
        elif fam == "log_escalation":
            for s in SERVICES:
                for ph in PHRASES[:4]:
                    u = t.format(Service=s.capitalize(), service=s,
                                 phrase=ph, a=50, b=200)
                    out.append((u, [("service_status", {"service": s}),
                                    ("service_logs", {"service": s,
                                                      "lines": 50}),
                                    ("service_logs", {"service": s,
                                                      "lines": 200})]))
        elif fam == "proc_drill":
            for u_tpl in [t]:
                for a_lim, b_lim, first in ((10, 5, "cpu"), (15, 10, "memory")):
                    base = ("cpu_usage", {}) if first == "cpu" else ("memory_usage", {})
                    u = u_tpl.format(a=a_lim, b=b_lim)
                    out.append((u, [base,
                                    ("process_list", {"limit": a_lim,
                                                      "sort_by": first}),
                                    ("process_list", {"limit": b_lim,
                                                      "sort_by": ("memory"
                                                                  if first == "cpu"
                                                                  else "cpu")})]))
    return [(pre + u, calls) for (u, calls) in out for pre in HARD_PRE]


EASY_QUOTA = {"service_status": 120, "service_restart": 100,
              "service_logs": 150, "disk_usage": 80, "memory_usage": 40,
              "cpu_usage": 40, "process_list": 150, "network_status": 40,
              "port_check": 100, "terminal": 100, "package_query": 100,
              "package_install": 80, "file_list": 50, "file_read": 50}
MED_QUOTA = {"pkg_chain": 200, "file_chain": 200, "net_port": 200,
             "status_log": 200, "disk_file": 100, "res_proc": 150,
             "status_restart": 100, "port_svc": 50}
HARD_QUOTA = {"pkg_verify": 120, "disk_triage": 120, "net_triage": 120,
              "svc_recovery": 120, "log_escalation": 60, "proc_drill": 60}


def main():
    rng = random.Random(SEED)
    seen = set()
    for fp in (V01, V02):
        for line in fp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                obj = json.loads(line)
                for m in obj.get("messages", []):
                    if m.get("role") == "user":
                        seen.add(norm(m.get("content", "")))
    ids = []
    for fp in (V01, V02):
        for line in fp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                ids.append(int(json.loads(line)["id"].rsplit("-", 1)[1]))
    nxt = max(ids) + 1

    out_rows = []

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

    # EASY: user + assistant(tool_call)
    for tool, q in EASY_QUOTA.items():
        for u, args in take(easy_cands(tool, rng), q, f"easy:{tool}"):
            out_rows.append({"difficulty": "easy", "messages": [
                {"role": "user", "content": u},
                {"role": "assistant", "content": "Provjeravam navedeno.",
                 "tool_calls": [{"name": tool, "arguments": args}]}]})
    # MEDIUM: user + assistant(call) + tool + assistant(final)
    for fam, q in MED_QUOTA.items():
        for u, calls in take(med_cands(fam, rng), q, f"med:{fam}"):
            (n1, a1), (n2, a2) = calls
            out_rows.append({"difficulty": "medium", "messages": [
                {"role": "user", "content": u},
                {"role": "assistant", "content": rng.choice(MED_ASST),
                 "tool_calls": [{"name": n1, "arguments": a1},
                               {"name": n2, "arguments": a2}]},
                {"role": "tool", "content": tool_resp(n1, a1)},
                {"role": "tool", "content": tool_resp(n2, a2)},
                {"role": "assistant",
                 "content": f"Gotovo: {final_text(n1, a1)} {final_text(n2, a2)}"}]})
    # HARD: 3 poziva, drugi/treci izvedeni iz prethodnih rezultata
    for fam, q in HARD_QUOTA.items():
        for u, calls in take(hard_cands(fam, rng), q, f"hard:{fam}"):
            (n1, a1), (n2, a2), (n3, a3) = calls
            out_rows.append({"difficulty": "hard", "thinking": True,
                             "messages": [
                {"role": "user", "content": u},
                {"role": "assistant",
                 "content": "Krecem od prve provjere pa nastavljam po nalazu.",
                 "tool_calls": [{"name": n1, "arguments": a1}]},
                {"role": "tool", "content": tool_resp(n1, a1)},
                {"role": "assistant",
                 "content": "Na osnovu gornjeg nalaza radim sljedeci korak.",
                 "tool_calls": [{"name": n2, "arguments": a2}]},
                {"role": "tool", "content": tool_resp(n2, a2)},
                {"role": "assistant",
                 "content": "Na osnovu prethodna dva nalaza radim zavrsni korak.",
                 "tool_calls": [{"name": n3, "arguments": a3}]},
                {"role": "tool", "content": tool_resp(n3, a3)},
                {"role": "assistant",
                 "content": (f"Zakljucak: {final_text(n1, a1)} "
                             f"{final_text(n2, a2)} {final_text(n3, a3)}")}]})
    assert len(out_rows) == 3000, len(out_rows)

    rng.shuffle(out_rows)
    with OUT.open("w", encoding="utf-8") as f:
        for k, r in enumerate(out_rows):
            f.write(json.dumps({
                "id": f"amj-fc-{nxt + k:04d}",
                "version": "0.3.0",
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
    print(f"difficulty: {diff}")
    print(f"alati: {json.dumps(tools, indent=1, ensure_ascii=False)}")
    print(f"prvi id: amj-fc-{nxt:04d}, zadnji: amj-fc-{nxt + len(out_rows) - 1:04d}")


if __name__ == "__main__":
    main()
