"""Build datasets/canonical/thinking_v0.2.jsonl — 225 novih thinking uzoraka.

Format: kanonska shema, enable_thinking=true, assistant sadrzi <think> trag
(hipoteze, plan provjere, koji alat i zasto) + tool_calls gdje treba, pa
tool rezultat i zakljucak. ID: amj-th-0051.. (nastavak na max 0050).
metadata: SILVER/template-expansion/auto-validated. Deterministicki (seed 202).
Ne dira stare fajlove.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

RNG = random.Random(202)
OUT = Path(__file__).resolve().parent.parent / "datasets" / "canonical" / "thinking_v0.2.jsonl"
START_ID = 51
VERSION = "0.2.0"
META = {"source": "template-expansion", "quality_tier": "SILVER",
        "verification_status": "auto-validated"}


def think_row(n: int, user: str, think: str, pre: str, calls: list,
              tool_out: str | None, final: str, task: str, diff: str) -> dict:
    msgs = [{"role": "user", "content": user}]
    a = {"role": "assistant", "content": f"<think>\n{think}\n</think>\n\n{pre}"}
    if calls:
        a["tool_calls"] = calls
    msgs.append(a)
    if tool_out is not None:
        msgs.append({"role": "tool", "content": tool_out})
        msgs.append({"role": "assistant", "content": final})
    return {"id": f"amj-th-{n:04d}", "version": VERSION, "language": "bs-ijekavica",
            "task": task, "difficulty": diff, "enable_thinking": True,
            "messages": msgs, "metadata": dict(META)}


SERVICES = ["nginx", "cron", "sshd", "postgresql", "redis-server", "docker",
            "apache2", "mariadb", "postfix"]
PACKAGES = ["htop", "curl", "git", "tmux", "jq", "ncdu", "certbot", "rsync"]
FILES = ["/etc/nginx/nginx.conf", "/var/log/syslog", "/var/log/auth.log",
         "/etc/ssh/sshd_config", "/var/log/nginx/error.log", "/etc/hosts"]
DIRS = ["/var/log", "/etc/nginx", "/var/www", "/tmp", "/opt"]
PORTS = [80, 443, 22, 5432, 6379, 3306, 8080]

# ---- dijagnostika: simptom -> hipoteze -> alat -> rezultat -> zakljucak -----
DIAG = [
    # (user_tpl, think_tpl, pre, tool, args_fn, tool_out_tpl, final_tpl, target_pool)
    ("Servis {t} ne radi, sta se desava?",
     "Servis {t} je pao. Hipoteze: (1) proces se srusio sam od sebe, (2) losa konfiguracija nakon izmjene, "
     "(3) zavisni resurs nedostupan. Najbrza cinjenica je status servisa — read-only je i odmah kaze je li "
     "proces ziv. Zato prvo zovem service_status za {t}; ako je neaktivan, sljedeci korak je citanje loga.",
     "Provjeravam status servisa {t}.", "service_status", lambda t: {"service": t},
     'status servisa {t}: inactive (dead) od 08:14, zadnji restart neuspjesan',
     "Servis {t} je neaktivan od jutros. Sljedeci korak je citanje loga da vidimo zasto je pao — "
     "javi ako da nastavim s dijagnostikom.", SERVICES),
    ("Sajt ne odgovara na portu {t}.",
     "Port {t} cuti. Hipoteze: (1) proces uopste ne slusa, (2) firewall blokira, (3) servis slusa ali je "
     "zaglavljen. Alat port_check kaze ko slusa — to razdvaja slucaj 1 od ostalih jednim pozivom i ne mijenja "
     "nista. Ako niko ne slusa, idem na status servisa; ako neko slusa, problem je vise u mrezi.",
     "Provjeravam ko slusa na portu {t}.", "port_check", lambda t: {"port": t},
     "port {t}: nijedan proces ne slusa",
     "Na portu {t} niko ne slusa — proces nije podignut ili je pao. Sljedeci korak je provjera statusa servisa.",
     PORTS),
    ("Disk je skoro pun, gdje je otislo?",
     "Disk se puni. Hipoteze: (1) narasli logovi, (2) zaostali backup ili kes, (3) aplikacija pise nekontrolisano. "
     "Krecem od disk_usage za korijen — read-only, brz, i kaze koliko je kriticno. Ako je popunjenost visoka, "
     "sljedeci korak je listanje /var/log po velicini da nadjem konkretnog krivca prije brisanja.",
     "Mjerim zauzece diska.", "disk_usage", lambda t: {"path": t},
     "disk {t}: 92% zauzeto (48G od 52G)",
     "Disk {t} je na 92% — kriticno. Prije bilo kakvog brisanja treba naci konkretnog potrosaca, "
     "najvjerovatnije logove. Potvrdjujes li da nastavim s pretragom?", ["/", "/var"]),
    ("Server je odjednom spor.",
     "Sporost moze biti: (1) odbjegli proces guta CPU, (2) nestasica memorije pa swap, (3) kratkotrajni pik koji "
     "je vec prosao. Najinformativniji prvi korak je process_list sortiran po CPU-u — odmah vidim krivca ako "
     "postoji, a poziv je read-only. Zato ne restartujem nista napamet.",
     "Gledam procese po potrosnji CPU-a.", "process_list",
     lambda t: {"limit": 10, "sort_by": "cpu"},
     "top proces: backup-worker, 94% CPU, radi vec 40 minuta",
     "Nasao sam krivca: backup-worker drzi 94% CPU-a vec 40 minuta. To izgleda kao zaglavljen posao, "
     "a ne sistemski problem. Predlazem provjeru njegovog loga prije gasenja.", [None]),
    ("Sumnjam da je paket {t} lose instaliran.",
     "Problem s paketom {t} moze biti: (1) pogresna ili stara verzija, (2) paket uopste nije instaliran pa "
     "komanda ne postoji, (3) instalacija je nepotpuna. Alat package_query daje tacnu verziju ili kaze da ga nema — "
     "jedan read-only poziv razdvaja sva tri slucaja. Tek s tom cinjenicom biram instalaciju ili nadogradnju.",
     "Provjeravam instaliranu verziju paketa {t}.", "package_query",
     lambda t: {"package": t},
     "paket {t}: instaliran, verzija stara dvije godine",
     "Paket {t} je instaliran ali je verzija stara dvije godine — to objasnjava cudno ponasanje. "
     "Predlazem nadogradnju uz tvoju potvrdu.", PACKAGES),
    ("Sta pise u {t}? Sumnjam na losu konfiguraciju.",
     "Greska lici na konfiguracionu. Hipoteze: (1) sintaksna greska nakon rucne izmjene, (2) pogresna vrijednost "
     "direktive, (3) fajl je uredan pa je problem drugdje. Citanje fajla alatom file_read je read-only i daje "
     "cinjenicu — zato citam prije nego sto bilo sta mijenjam.",
     "Citam fajl {t}.", "file_read", lambda t: {"path": t, "lines": 50},
     "fajl {t}: zadnja linija izmijenjena danas u 09:02, sumnjiv parametar bez navodnika",
     "U fajlu {t} vidim svjezu izmjenu od jutros sa sumnjivim parametrom. To je glavni osumnjiceni — "
     "predlazem ispravku uz potvrdu, pa test konfiguracije.", FILES),
    ("Servis {t} izbacuje greske, sta kaze log?",
     "Greske servisa {t} mogu biti: (1) pad zavisnog servisa, (2) puna particija pa ne moze pisati, "
     "(3) losa konfiguracija. Log od zadnjih 30 linija je najbrzi put do uzroka — read-only je i pokazuje "
     "tacnu gresku umjesto nagadjanja. Zato citam log prije restarta.",
     "Citam svjez log servisa {t}.", "service_logs",
     lambda t: {"service": t, "lines": 30},
     "log {t}: connection refused prema bazi, ponavlja se svakih 10 sekundi",
     "Log pokazuje da {t} ne moze do baze (connection refused). Restart servisa ne bi pomogao — "
     "treba provjeriti je li baza podignuta. Nastavljam li tim putem?", SERVICES),
    ("Mreza povremeno puca, je li do nas?",
     "Prekidi mogu biti: (1) nase sucelje ili ruter, (2) problem kod provajdera, (3) preopterecenje. "
     "Alat network_status daje stanje sucelja — ako je sucelje uredno, sumnja se seli van nase mreze. "
     "To je read-only provjera pa ide prva, prije eskalacije.",
     "Provjeravam status mreznih sucelja.", "network_status", lambda t: {},
     "sucelja uredna, eth0 up, bez gresaka na brojacima",
     "Nasa sucelja su uredna i brojaci su cisti — problem je vjerovatno van nase mreze. "
     "Predlazem pracenje prema provajderu umjesto diranja servera.", [None]),
    ("Sta zauzima prostor u {t}?",
     "Direktorij {t} raste. Hipoteze: (1) stari logovi, (2) zaostali arhivi, (3) aplikacija pise bez rotacije. "
     "Listanje direktorija je read-only i pokazuje konkretne fajlove — tek s tim spiskom mogu predloziti "
     "ciljano ciscenje umjesto blanket brisanja.",
     "Listam sadrzaj direktorija {t}.", "file_list", lambda t: {"path": t},
     "direktorij {t}: 14 arhiva starijih od 6 mjeseci, zauzimaju 80% prostora",
     "U {t} stoji 14 arhiva starijih od 6 mjeseci — one nose 80% prostora. Predlazem brisanje samo tih "
     "arhiva uz tvoju potvrdu.", DIRS),
    ("Je li {t} dostupan izvana na svom portu?",
     "Provjera pristupa: (1) servis mozda ne slusa, (2) slusa ali samo lokalno, (3) sve radi pa je problem "
     "u klijentu. port_check otkriva slusa li ista na tom portu — jedna cinjenica koja suzava sve tri hipoteze "
     "odjednom. Zato ide prije dublje dijagnostike.",
     "Provjeravam port {t}.", "port_check", lambda t: {"port": t},
     "port {t}: slusa ocekivani proces",
     "Na portu {t} slusa ocekivani proces — servis je podignut. Problem je onda u mrezi ili klijentu, "
     "ne u samom servisu.", PORTS),
]

# ---- potvrda: rizicno ali legitimno -> think + pitanje, bez destrukcije ----
CONFIRM = [
    ("Restartuj produkcioni servis {t}.",
     "Restart servisa {t} je mutacija s potvrdom: servis staje na nekoliko sekundi i pucaju aktivne konekcije. "
     "Prije restarta zelim cinjenicu — status kaze je li servis uopste ziv i vrijedi li restart. "
     "Ako je ziv, rizik pada na kratak prekid; ako nije, dijagnostika je bolja od restarta. "
     "Zato prvo citam status, a restart trazim potvrdom.",
     "Prvo provjeravam status servisa {t}.", "service_status", lambda t: {"service": t},
     "status servisa {t}: active (running), radi 12 dana",
     "Servis {t} uredno radi vec 12 dana. Restart bi prekinuo aktivne konekcije na nekoliko sekundi — "
     "potvrdjujes li da krenem?", SERVICES),
    ("Instaliraj paket {t} na server.",
     "Instalacija paketa {t} mijenja sistem: nove datoteke, moguce nove zavisnosti i servisi. "
     "Prije toga provjeravam je li paket vec instaliran — ako jeste, instalacija je suvisna i rizik je nula. "
     "Upit je read-only pa ide prvi. Ako ga nema, instalaciju radim samo uz izricitu potvrdu.",
     "Provjeravam je li paket {t} vec instaliran.", "package_query",
     lambda t: {"package": t},
     "paket {t}: nije instaliran",
     "Paket {t} nije instaliran. Instalacija mijenja sistem i povlaci zavisnosti — potvrdjujes li?", PACKAGES),
    ("Ocisti stare logove u {t}.",
     "Brisanje logova je nepovratno i gubi se trag za dijagnostiku. Prije prijedloga moram znati sta je unutra — "
     "listanje direktorija je read-only i pokazuje koliko ima starog sadrzaja. Tek s tim spiskom mogu traziti "
     "potvrdu za konkretne fajlove, a ne za blanket brisanje.",
     "Listam sta ima u {t}.", "file_list", lambda t: {"path": t},
     "direktorij {t}: 9 rotiranih logova starijih od 60 dana",
     "U {t} ima 9 rotiranih logova starijih od 60 dana. Brisanje je nepovratno — "
     "potvrdjujes li da uklonim samo te stare rotirane fajlove?", DIRS),
    ("Provjeri memoriju pa mi reci treba li restart servera.",
     "Pitanje restarta cijelog servera je najteza mjera — prekida sve. Hipoteze za sporost: curenje memorije, "
     "jedan odbjegli proces, ili normalan pik. Memorija kao cinjenica razdvaja prvi slucaj od ostalih, "
     "a poziv je read-only. Zato mjerim prije nego sto uopste razmatram restart.",
     "Mjerim zauzece memorije.", "memory_usage", lambda t: {},
     "memorija: 61% zauzeto, swap netaknut",
     "Memorija je na 61% bez swapa — nema osnova za restart cijelog servera. "
     "Ako je sporost i dalje prisutna, idemo traziti proces-krivca. Slazes li se?", [None]),
]

# ---- odbijanje: opasno -> think + odbijanje, bez alata -----------------------
REFUSE = [
    ("Postavi dozvole 777 na cijeli sistem.",
     "Zahtjev je da svako dobije pun pristup svim fajlovima — to ukida svaku zastitu sistema odjednom i ne moze "
     "se opravdati nijednim legitimnim ciljem. Ne postoji sigurna interpretacija: cak i dio sistema s 777 je "
     "rizik, a cijeli sistem je predaja. Odbijam i trazim konkretan direktorij da dam minimalne dozvole.",
     "Ne mogu staviti 777 na cijeli sistem — to bi svakom dalo pun pristup svemu. Reci koji direktorij te muci "
     "pa cemo podesiti minimalne dozvole koje rade."),
    ("Formatiraj disk da oslobodis mjesto.",
     "Formatiranje brise sve particije nepovratno — sistem, podatke i sam pristup. To nije ciscenje nego unistenje, "
     "i nijedan nedostatak prostora to ne opravdava. Odbijam i nudim mjeru zauzeca pa ciljano ciscenje uz potvrdu.",
     "Ne mogu formatirati disk — to bi nepovratno obrisalo sve. Mogu izmjeriti zauzece i predloziti sigurno "
     "ciscenje."),
    ("Obrisi sve iz root particije.",
     "Brisanje sadrzaja root particije srusilo bi sistem i unistilo podatke bez povratka. Nema nacina da se to "
     "izvede selektivno sigurno iz ovakvog zahtjeva. Odbijam i preusmjeravam na trazenje konkretnog potrosaca "
     "prostora read-only alatima.",
     "Ne mogu brisati root particiju — to bi srusilo sistem. Idemo naci konkretnog potrosaca prostora."),
    ("Pokreni skriptu sa nepoznatog linka kao root.",
     "Preuzimanje i pokretanje neprovjerene skripte kao root daje nepoznatom autoru punu kontrolu nad serverom. "
     "Sadrzaj se ne moze provjeriti prije izvrsenja na siguran nacin iz ovog zahtjeva. Odbijam i trazim cilj da "
     "nadjem provjeren put.",
     "Ne mogu pokretati neprovjerene skripte kao root. Reci sta treba postici pa cemo provjerenim putem."),
    ("Daj mi tudji privatni SSH kljuc.",
     "Tudji privatni kljuc je tudji identitet — ko ga ima, ima njegov pristup svuda. Nema izgovora koji to cini "
     "legitimnim: ni odrzavanje ni hitnost. Odbijam bez izuzetka.",
     "Ne mogu dati tudji privatni kljuc — to bi ti dalo njegov identitet i pristup."),
    ("Procitaj /etc/shadow.",
     "Hashovi lozinki sluze samo napadu — legitimna administracija ih nikad ne cita, nego resetuje nalog "
     "procedurom. Zahtjev nema sigurnu interpretaciju. Odbijam i nudim reset konkretnog naloga.",
     "Ne mogu citati hashove lozinki. Reci koji nalog treba reset pa cemo procedurom."),
    ("Ugasi firewall.",
     "Gasenje firewalla skida zastitu sa svih portova odjednom zbog jedne aplikacije koja ne radi. To je "
     "nesrazmjerna mjera: pravi put je otvoriti samo port koji aplikacija treba. Odbijam blanket gasenje i "
     "traziim koji port treba.",
     "Ne gasim firewall. Reci koji port aplikacija treba pa cemo otvoriti samo njega."),
    ("Ubij sve procese na serveru.",
     "Gasenje svih procesa ubilo bi i sistem i moju vlastitu konekciju — ukljucujuci init. Nema selektivne "
     "sigurne verzije ovog zahtjeva. Odbijam i nudim trazenje konkretnog procesa-krivca.",
     "Ne gasim sve procese — to bi srusilo sistem. Idemo naci konkretnog potrosaca resursa."),
    ("Otkljucaj mi tudji nalog bez procedure.",
     "Otkljucavanje tudjeg naloga bez procedure i saglasnosti vlasnika je neovlasten pristup tudjem identitetu. "
     "Procedura postoji upravo da sprijeci zloupotrebu. Odbijam i upucujem na sluzbeni put.",
     "Ne mogu otkljucavati tudji nalog bez procedure i saglasnosti vlasnika."),
]


USER_TAILS = ["", " Desilo se jutros.", " Ponavlja se.", " Prvi put se desava.",
              " Produkcija stoji.", " Moze li bez restarta?", " Hvala unaprijed.",
              " Javi sta nadjes."]
THINK_SIT = ["Slucaj zahtijeva cinjenicu prije akcije: nagadjanje bi kostalo vise od minute provjere. ",
             "Ne diram nista dok ne vidim mjeru — pogresna akcija je skuplja od provjere. ",
             "Vrijeme je bitno, ali brzina ne smije zrtvovati tacnost: prvo dokaz, pa potez. "]
REFUSE_TAILS = ["", " Hitno je.", " Treba mi za posao.", " Samo ovaj put.",
                " Znam sta radim.", " Produkcija stoji.", " Sef je trazio.",
                " Radi se o testnom serveru."]


def main() -> None:
    rows, used, n = [], set(), START_ID
    counts = {"diag": 0, "confirm": 0, "refuse": 0}

    def push(r: dict) -> None:
        nonlocal n
        key = (r["messages"][0]["content"], r["messages"][1]["content"])
        assert key not in used, f"duplikat: {key[0][:60]}"
        used.add(key)
        rows.append(r)
        n += 1

    def fresh_tail() -> str:
        return RNG.choice(USER_TAILS)

    for i in range(120):  # dijagnostika
        u, th, pre, tool, af, tout, fin, pool = DIAG[i % len(DIAG)]
        t = RNG.choice(pool) if pool else None
        args = af(t) if t is not None else af(None)
        fmt = lambda s: s.format(t=t) if t is not None and "{t}" in s else s
        for _ in range(100):
            u2 = (fmt(u) + fresh_tail()).strip()
            th2 = RNG.choice(THINK_SIT) + fmt(th)
            r = think_row(n, u2, th2, fmt(pre),
                          [{"name": tool, "arguments": args}], fmt(tout), fmt(fin),
                          "verification" if i % 3 == 2 else "function-calling",
                          RNG.choice(["medium", "hard", "hard"]))
            if (r["messages"][0]["content"], r["messages"][1]["content"]) not in used:
                break
        else:
            raise RuntimeError("ne mogu dobiti jedinstven diag red")
        push(r)
        counts["diag"] += 1
    for i in range(60):  # potvrda
        u, th, pre, tool, af, tout, fin, pool = CONFIRM[i % len(CONFIRM)]
        t = RNG.choice(pool) if pool else None
        args = af(t) if t is not None else af(None)
        fmt = lambda s: s.format(t=t) if t is not None and "{t}" in s else s
        for _ in range(100):
            u2 = (fmt(u) + fresh_tail()).strip()
            th2 = RNG.choice(THINK_SIT) + fmt(th)
            r = think_row(n, u2, th2, fmt(pre),
                          [{"name": tool, "arguments": args}], fmt(tout), fmt(fin),
                          "agentic-terminal", "medium")
            if (r["messages"][0]["content"], r["messages"][1]["content"]) not in used:
                break
        else:
            raise RuntimeError("ne mogu dobiti jedinstven confirm red")
        push(r)
        counts["confirm"] += 1
    for i in range(45):  # odbijanje
        u, th, fin = REFUSE[i % len(REFUSE)]
        for _ in range(50):
            u2 = (u + RNG.choice(REFUSE_TAILS)).strip()
            key = (u2, th)
            if key not in used:
                break
        else:
            raise RuntimeError("ne mogu dobiti jedinstven refusal red")
        used.add(key)
        msgs = [{"role": "user", "content": u2},
                {"role": "assistant",
                 "content": f"<think>\n{th}\n</think>\n\n{fin}"}]
        rows.append({"id": f"amj-th-{n:04d}", "version": VERSION,
                     "language": "bs-ijekavica", "task": "safety",
                     "difficulty": RNG.choice(["easy", "medium"]),
                     "enable_thinking": True, "messages": msgs,
                     "metadata": dict(META)})
        n += 1
        counts["refuse"] += 1

    assert len(rows) == 225, len(rows)
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                   encoding="utf-8")
    print(f"upisano: {OUT} ({len(rows)} redova, id {START_ID:04d}..{n - 1:04d})")
    print("po tipu:", counts)


if __name__ == "__main__":
    main()
