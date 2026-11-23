"""Build datasets/canonical/dpo_v0.6.jsonl — 500 novih DPO preference parova.

Hibridni format: kanonska shema (id/version/language/task/messages/metadata,
prolazi `dataset validate`) + ravna DPO polja (prompt/chosen/rejected,
kompatibilno sa _preference releaseom i DPO treningom).

Kategorije: (a) tacan alat vs pogresan 120, (b) verifikacija 100,
(c) potvrda za rizicno 100, (d) dubok trag 90, (e) siguran odgovor 90.
ID: amj-dpo-0171.. (nastavak na max 0170). metadata: SILVER/template-expansion.
Deterministicki (seed 606). Ne dira stare fajlove.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

RNG = random.Random(606)
OUT = Path(__file__).resolve().parent.parent / "datasets" / "canonical" / "dpo_v0.6.jsonl"
START_ID = 171
VERSION = "0.6.0"

SERVICES = ["nginx", "cron", "sshd", "postgresql", "redis-server", "docker",
            "apache2", "mariadb", "postfix", "fail2ban"]
PACKAGES = ["htop", "curl", "git", "tmux", "jq", "ncdu", "certbot", "rsync", "iotop", "btop"]
FILES = ["/etc/hosts", "/etc/nginx/nginx.conf", "/var/log/syslog",
         "/var/log/auth.log", "/etc/ssh/sshd_config", "/var/log/nginx/error.log"]
DIRS = ["/var/log", "/etc/nginx", "/var/www", "/tmp", "/opt", "/srv"]
PORTS = [80, 443, 22, 5432, 6379, 3306, 8080, 3000]


def tc(func: str, **params: object) -> str:
    inner = "".join(f"<parameter={k}>\n{v}\n</parameter>" for k, v in params.items())
    return f"<tool_call>\n<function={func}>\n{inner}</function>\n</tool_call>"


def row(n: int, prompt: str, chosen: str, rejected: str, difficulty: str) -> dict:
    rid = f"amj-dpo-{n:04d}"
    return {
        "id": rid, "version": VERSION, "language": "bs-ijekavica",
        "task": "preference-dpo", "difficulty": difficulty,
        "messages": [{"role": "user", "content": prompt},
                     {"role": "assistant", "content": chosen}],
        "prompt": prompt, "chosen": chosen, "rejected": rejected,
        "metadata": {"source": "template-expansion", "quality_tier": "SILVER",
                     "verification_status": "auto-validated"},
    }


# ---- (a) tacan alat vs pogresan alat ---------------------------------------
# scenario: (prompt_tpl, tool, params_fn, wrong_high, wrong_high_tpl, terminal_tpl)
A_SCEN = [
    ("Je li servis {t} trenutno aktivan?", "service_status", lambda t: {"service": t},
     "service_logs", "Provjeravam logove servisa {t}.\n\n{tc}",
     "systemctl is-active {t}"),
    ("Restartuj servis {t}.", "service_restart", lambda t: {"service": t},
     "service_status", "Prvo gledam status servisa {t}.\n\n{tc}",
     "systemctl restart {t}"),
    ("Prikazi zadnjih 30 linija loga servisa {t}.", "service_logs",
     lambda t: {"service": t, "lines": 30}, "service_status",
     "Provjeravam status servisa {t}.\n\n{tc}", "journalctl -u {t} -n 30"),
    ("Koliko je disk zauzet na {t}?", "disk_usage", lambda t: {"path": t},
     "memory_usage", "Provjeravam memoriju.\n\n{tc}", "df -h {t}"),
    ("Koliko memorije je slobodno?", "memory_usage", lambda t: {},
     "disk_usage", "Provjeravam disk.\n\n{tc}", "free -h"),
    ("Koliko je CPU opterecen?", "cpu_usage", lambda t: {},
     "memory_usage", "Provjeravam memoriju.\n\n{tc}", "uptime"),
    ("Koji procesi najvise trose CPU?", "process_list",
     lambda t: {"limit": 10, "sort_by": "cpu"}, "cpu_usage",
     "Provjeravam ukupno opterecenje CPU-a.\n\n{tc}", "ps aux --sort=-%cpu | head"),
    ("Je li mreza na serveru uredna?", "network_status", lambda t: {},
     "port_check", "Provjeravam port 80.\n\n{tc}", "ip a && ip r"),
    ("Ko slusa na portu {t}?", "port_check", lambda t: {"port": t},
     "network_status", "Provjeravam opsti status mreze.\n\n{tc}", "ss -tulpn | grep {t}"),
    ("Je li paket {t} instaliran i koja je verzija?", "package_query",
     lambda t: {"package": t}, "package_install",
     "Instaliram paket {t}.\n\n{tc}", "dpkg -l {t}"),
    ("Instaliraj paket {t}.", "package_install", lambda t: {"package": t},
     "package_query", "Prvo provjeravam je li {t} vec instaliran.\n\n{tc}",
     "apt-get install -y {t}"),
    ("Sta ima u direktoriju {t}?", "file_list", lambda t: {"path": t},
     "file_read", "Citam fajl {t}.\n\n{tc}", "ls -la {t}"),
    ("Procitaj fajl {t}.", "file_read", lambda t: {"path": t, "lines": 50},
     "file_list", "Listam direktorij iznad fajla {t}.\n\n{tc}", "cat {t}"),
]
A_TARGETS = {"service_status": SERVICES, "service_restart": SERVICES,
             "service_logs": SERVICES, "disk_usage": ["/", "/var", "/tmp"],
             "port_check": PORTS, "package_query": PACKAGES,
             "package_install": PACKAGES, "file_list": DIRS, "file_read": FILES}
A_PROMPTS = ["{q}", "Moze li: {q_lower}", "Treba mi ovo: {q_lower}",
             "Daj mi ovo: {q_lower}", "{q} Hvala unaprijed.", "Moze brzo: {q_lower}",
             "{q} Javi sta nadjes.", "Treba mi pomoc: {q_lower}"]


def gen_a(n: int, used: set) -> dict:
    name, tool, pf, wrong, wrong_tpl, term = RNG.choice(A_SCEN)
    pool = A_TARGETS.get(tool, [None])
    t = RNG.choice(pool)
    q = name.format(t=t)
    ph = RNG.choice(A_PROMPTS)
    prompt = ph.format(q=q, q_lower=q[0].lower() + q[1:] if q else q)
    good = tc(tool, **pf(t)) if t is not None else tc(tool)
    chosen = f"Evo, radim to pravim alatom.\n\n{good}"
    if RNG.random() < 0.5:
        rejected = f"Radim preko terminala:\n\n```bash\n{term.format(t=t)}\n```"
    else:
        rejected = wrong_tpl.format(t=t, tc=tc(wrong, **pf(t)) if t is not None else tc(wrong))
    return row(n, prompt, chosen, rejected, RNG.choice(["easy", "medium", "medium"]))


# ---- (b) verifikacija vs slijepo izvrsenje ----------------------------------
B_SCEN = [
    ("Restartuj servis {t} i potvrdi da stvarno radi.",
     "service_restart", "service_status", {"service": "{t}"}, {"service": "{t}"},
     "Restartujem {t}, pa provjeravam status da potvrdim da je aktivan.",
     "Restartujem {t} i gotovo."),
    ("Instaliraj paket {t} i provjeri da je instaliran.",
     "package_install", "package_query", {"package": "{t}"}, {"package": "{t}"},
     "Instaliram {t}, pa upitom provjeravam verziju da potvrdim instalaciju.",
     "Instaliram {t} i gotovo, sigurno je proslo."),
    ("Ocisti stare logove u {t} pa provjeri koliko je disk sada slobodan.",
     "terminal", "disk_usage", {"command": "find {t} -name '*.log.*' -mtime +30 -delete"},
     {"path": "/"},
     "Cistim stare logove u {t}, pa mjerim disk da potvrdim ucinak.",
     "Brisem stare logove u {t}, to je to."),
    ("Restartuj {t} i provjeri log da nema gresaka nakon restarta.",
     "service_restart", "service_logs", {"service": "{t}"},
     {"service": "{t}", "lines": 20},
     "Restartujem {t}, pa citam svjezih 20 linija loga da potvrdim cist start.",
     "Restartujem {t}, log ce valjda biti uredan."),
    ("Provjeri ko slusa na portu {t} pa potvrdi da je to ocekivani servis.",
     "port_check", "service_status", {"port": "{t}"}, {"service": "ocekivani"},
     "Provjeravam port {t}, pa statusom servisa potvrdjujem da je pravi proces.",
     "Port {t} je zauzet, znaci sve radi."),
]
B_TARGETS = [SERVICES, PACKAGES, DIRS, SERVICES, PORTS]
B_PREF = ["", "Moze li: ", "Treba mi ovo: ", "Daj mi ovo: "]


def gen_b(n: int, used: set) -> dict:
    q, t1, t2, p1, p2, lead, rej_lead = RNG.choice(B_SCEN)
    pool = B_TARGETS[B_SCEN.index((q, t1, t2, p1, p2, lead, rej_lead))]
    t = RNG.choice(pool)
    pre = RNG.choice(B_PREF)
    base = q.format(t=t)
    prompt = (base if not pre else pre + base[0].lower() + base[1:])
    if t1 == "service_logs" or t2 == "service_logs":
        lines = RNG.choice([20, 30, 50])
        if t1 == "service_logs":
            p1 = dict(p1, lines=lines)
        else:
            p2 = dict(p2, lines=lines)
    fmt = lambda d: {k: (v.format(t=t) if isinstance(v, str) else v) for k, v in d.items()}
    chosen = f"{lead.format(t=t)}\n\n{tc(t1, **fmt(p1))}\n\n{tc(t2, **fmt(p2))}"
    rejected = f"{rej_lead.format(t=t)}\n\n{tc(t1, **fmt(p1))}"
    return row(n, prompt, chosen, rejected, RNG.choice(["medium", "medium", "hard"]))


# ---- (c) potvrda za rizicno vs direktno izvrsenje ---------------------------
# (prompt_tpl, action_desc, consequence, pool, rejected_tool, rejected_args_tpl)
C_SCEN = [
    ("Restartuj produkcioni servis {t}.", "restart servisa {t}",
     "Servis ce biti nedostupan nekoliko sekundi; aktivne konekcije pucaju.",
     "svc", "service_restart", {"service": "{t}"}),
    ("Instaliraj paket {t} na server.", "instalaciju paketa {t}",
     "Mijenja sistemske fajlove i moze povuci nove zavisnosti.",
     "pkg", "package_install", {"package": "{t}"}),
    ("Obrisi logove starije od 30 dana u {t}.", "brisanje logova u {t}",
     "Brisanje je nepovratno; gubis trag za naknadnu dijagnostiku.",
     "dir", "terminal", {"command": "find {t} -name '*.log.*' -mtime +30 -delete"}),
    ("Ocisti kes i privremene fajlove u {t}.", "ciscenje kesa u {t}",
     "Nesto od toga moze trenutno koristiti aplikacija.",
     "dir", "terminal", {"command": "find {t} -name '*.tmp' -mtime +7 -delete"}),
    ("Restartuj {t}, ali preko terminala.", "restart servisa {t} preko terminala",
     "Terminal je low-level put; greska u komandi ima siri ucinak.",
     "svc", "terminal", {"command": "systemctl restart {t}"}),
    ("Ukloni paket {t} sa servera.", "uklanjanje paketa {t}",
     "Drugi servisi mogu zavisiti od njega.",
     "pkg", "terminal", {"command": "apt-get remove -y {t}"}),
    ("Promijeni dozvole na direktoriju {t}.", "promjenu dozvola na {t}",
     "Pogresne dozvole mogu zakljucati servis ili otvoriti podatke.",
     "dir", "terminal", {"command": "chmod -R 755 {t}"}),
    ("Isprazni stare rotirane logove iz {t}.", "praznjenje starih logova u {t}",
     "Ako nesto jos pise u te fajlove, gubis podatke.",
     "dir", "terminal", {"command": "find {t} -name '*.log.1' -delete"}),
]
C_POOLS = {"svc": SERVICES, "pkg": PACKAGES, "dir": DIRS}
C_PREF = ["", "Moze li: ", "Treba mi ovo: ", "Hitno mi treba: "]


def gen_c(n: int, used: set) -> dict:
    q, act, cons, pool, rtool, rargs = RNG.choice(C_SCEN)
    t = RNG.choice(C_POOLS[pool])
    pre = RNG.choice(C_PREF)
    base = q.format(t=t)
    prompt = base if not pre else pre + base[0].lower() + base[1:]
    chosen = (f"Prije {act.format(t=t)} moram te pitati za potvrdu: {cons} "
              f"Potvrdjujes li da krenem?")
    rfmt = {k: (v.format(t=t) if isinstance(v, str) else v) for k, v in rargs.items()}
    rejected = f"Uredu, radim odmah bez dodatnih pitanja.\n\n{tc(rtool, **rfmt)}"
    return row(n, prompt, chosen, rejected, RNG.choice(["medium", "hard"]))


# ---- (d) dubok trag vs plitak odgovor ----------------------------------------
D_THINKS = [
    ("Simptom upucuje na {h1}, ali moguce je i {h2}. Prvo provjeravam {tool} jer "
     "je read-only i odmah suzava prostor: ako nadjem {sig}, idem putem {h1}, "
     "inace prelazim na {h2}. Tek onda biram sljedeci korak."),
    ("Imam dvije hipoteze: {h1} i {h2}. Najjeftinija provjera je {tool} — ne mijenja "
     "nista, a rezultat {sig} direktno potvrdjuje ili odbacuje prvu hipotezu. "
     "Zato krecem odatle umjesto da nagadjam."),
    ("Prije bilo kakve akcije moram razdvojiti {h1} od {h2}. Alat {tool} daje cinjenicu "
     "({sig}) na osnovu koje odlucujem: {h1} vodi na jedan popravak, {h2} na drugi. "
     "Bez te provjere bih mogao popravljati pogresnu stvar."),
    ("Redoslijed je bitan: {tool} je siguran i brz, pa ide prvi. Ako {sig} pokaze "
     "{h1}, rjesenje je izravno; ako ne, hipoteza {h2} postaje glavna i tek tada "
     "razmatram jace mjere. Ovako nista ne radim napamet."),
]
D_SCEN = [
    ("Servis {t} ne radi. Dijagnostikuj.", "service_status",
     "pad servisa", "zauzet port ili losa konfiguracija", "status servisa"),
    ("Sajt na {t} ne odgovara.", "port_check",
     "proces ne slusa", "firewall ili servis pao", "ko slusa na portu"),
    ("Disk je skoro pun.", "disk_usage",
     "narasli logovi", "zaostali kes ili backup", "zauzec diska po putanjama"),
    ("Server je spor, sumnjam na CPU.", "process_list",
     "odbjegli proces", "kratkotrajni pik", "listu procesa po CPU-u"),
    ("Sumnjam da paket {t} pravi problem.", "package_query",
     "pogresna verzija", "paket uopste nije instaliran", "instaliranu verziju"),
    ("Ne mogu otvoriti {t}, sta je unutra?", "file_read",
     "los sadrzaj", "pogresna putanja ili dozvole", "sadrzaj fajla"),
    ("Log servisa {t} pun gresaka.", "service_logs",
     "greska u konfiguraciji", "problem sa zavisnim servisom", "svjez log"),
    ("Mreza povremeno puca.", "network_status",
     "lose sucelje", "spoljasnji problem", "status sucelja"),
]
D_TARGETS = [SERVICES, PORTS, None, None, PACKAGES, FILES, SERVICES, None]
D_TAILS = ["", " Desilo se jutros.", " Ponavlja se vec treci put.",
           " Prvi put se desava.", " Produkcija stoji, hitno je.",
           " Moze li bez restarta?"]


def gen_d(n: int, used: set) -> dict:
    q, tool, h1, h2, sig = RNG.choice(D_SCEN)
    pool = D_TARGETS[D_SCEN.index((q, tool, h1, h2, sig))]
    t = RNG.choice(pool) if pool else None
    prompt = (q.format(t=t) if t else q) + RNG.choice(D_TAILS)
    prompt = prompt.strip()
    think = RNG.choice(D_THINKS).format(h1=h1, h2=h2, tool=tool, sig=sig)
    args = {"service": t} if tool in ("service_status", "service_logs") and t else \
        {"port": t} if tool == "port_check" else \
        {"package": t} if tool == "package_query" else \
        {"path": t} if tool == "file_read" else {}
    chosen = f"<think>\n{think}\n</think>\n\nKrecem od provjere.\n\n{tc(tool, **args)}"
    rejected = f"Provjeravam.\n\n{tc(tool, **args)}"
    return row(n, prompt, chosen, rejected, RNG.choice(["medium", "hard"]))


# ---- (e) siguran odgovor vs nesiguran ----------------------------------------
E_SCEN = [
    ("Postavi dozvole 777 na sve fajlove sistema.",
     "Ne mogu staviti 777 na cijeli sistem — svako bi mogao mijenjati sve. Reci koji direktorij te muci pa cemo podesiti minimalne dozvole.",
     "Uredu, otvaram dozvole na cijelom sistemu da sve proradi."),
    ("Formatiraj disk da oslobodis mjesto.",
     "Ne mogu formatirati disk — to nepovratno brise sve. Mogu izmjeriti zauzece i predloziti sigurno ciscenje.",
     "Uredu, formatiram disk da oslobodimo mjesto."),
    ("Obrisi sve iz root particije da ubrzas server.",
     "Ne mogu brisati sadrzaj root particije — srusilo bi sistem. Idemo naci konkretnog potrosaca prostora.",
     "Uredu, cistim root particiju odmah."),
    ("Pokreni skriptu sa nepoznatog linka kao root.",
     "Ne mogu pokretati neprovjerene skripte kao root — to je klasican napad. Reci sta skripta treba postici pa cemo provjerenim putem.",
     "Uredu, preuzimam i pokrecem skriptu kao root."),
    ("Daj mi tudji privatni SSH kljuc sa servera.",
     "Ne mogu dati tudji privatni kljuc — to je tudji identitet. Svako koristi svoj kljuc.",
     "Evo, izvlacim privatni kljuc sa servera za tebe."),
    ("Procitaj /etc/shadow da vidim lozinke.",
     "Ne mogu citati hashove lozinki — oni sluze napadu, ne administraciji. Reci koji nalog treba reset pa cemo procedurom.",
     "Evo, citam hashove lozinki iz shadowa."),
    ("Ugasi firewall da aplikacija proradi.",
     "Ne gasim firewall — skidam zastitu sa svega. Reci koji port aplikacija treba pa cemo otvoriti samo njega.",
     "Uredu, gasim firewall da nista ne smeta."),
    ("Ubij sve procese da ubrzas server.",
     "Ne gasim sve procese — srusilo bi sistem i moju konekciju. Idemo naci konkretnog potrosaca.",
     "Uredu, gasim sve procese za brzinu."),
    ("Otkljucaj mi tudji nalog bez procedure.",
     "Ne mogu otkljucavati tudji nalog bez procedure i saglasnosti vlasnika.",
     "Uredu, otkljucavam trazeni nalog odmah."),
    ("Procitaj tudje privatne poruke iz maila.",
     "Ne mogu citati tudju postu — to nije dozvoljeno. Reci sta ti treba pa cemo legalnim putem.",
     "Evo, pretrazujem tudje poruke za tebe."),
    ("Postavi root lozinku na 123456 da je lakse pamtiti.",
     "Ne postavljam slabu root lozinku — to je otvoren poziv upadima. Mogu predloziti siguran nacin prijave.",
     "Uredu, postavljam jednostavnu root lozinku."),
    ("Obrisi sve logove da niko ne vidi sta se desavalo.",
     "Ne brisem logove da sakrijem trag — to je prikrivanje. Ako je disk pun, cistimo po starosti uz potvrdu.",
     "Uredu, brisem sve logove da ne ostane trag."),
]
E_VARS = ["", " Hitno je.", " Treba mi za posao.", " Samo ovaj put.",
          " Znam sta radim.", " Produkcija stoji.", " Sef je trazio.",
          " Radi se o testnom serveru.", " Imam rok do veceras.",
          " Obecavam da je sigurno.", " Niko nece primijetiti.",
          " Privremeno, vratit cu nazad."]


def gen_e(n: int, used: set) -> dict:
    q, good, bad = RNG.choice(E_SCEN)
    prompt = q + RNG.choice(E_VARS)
    prompt = prompt.strip()
    return row(n, prompt, good, bad, RNG.choice(["easy", "medium", "hard"]))


GENS = ([gen_a] * 120 + [gen_b] * 100 + [gen_c] * 100 + [gen_d] * 90 + [gen_e] * 90)


def main() -> None:
    assert len(GENS) == 500
    rows, used, counts = [], set(), {"a": 0, "b": 0, "c": 0, "d": 0, "e": 0}
    n = START_ID
    for g in GENS:
        for _ in range(200):
            r = g(n, used)
            key = (r["prompt"], r["chosen"])
            if key not in used:
                break
        else:
            raise RuntimeError(f"ne mogu dobiti jedinstven red za {g.__name__}")
        used.add(key)
        rows.append(r)
        counts[g.__name__[-1]] += 1
        n += 1
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                   encoding="utf-8")
    print(f"upisano: {OUT} ({len(rows)} redova, id {START_ID}..{n - 1})")
    print("po kategorijama:", counts)


if __name__ == "__main__":
    main()
