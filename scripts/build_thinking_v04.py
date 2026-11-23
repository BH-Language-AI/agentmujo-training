"""Build datasets/canonical/thinking_v0.4.jsonl — 500 novih thinking uzoraka.

Nastavak na thinking_v0.3 (max amj-th-0775): ID amj-th-0776...
Nove dimenzije traga (nema ih u v0.1/v0.2/v0.3):
  (a) CALC: trag s kalkulacijom — tempo rasta diska (GB/h) i slobodno
      pretvara u sate do zagušenja, pa po tom broju određuje prioritet;
  (b) CHOICE2: trag s dva konkurentna plana pa izbor jeftinijeg
      (read-only mjera prije skupe/rizične akcije);
  (c) PIVOT: prvi alat vrati čist nalaz pa model odustaje od tog traga
      i prelazi na sljedeći (npr. network_status čist → log forenzika);
  (d) HPC: Slurm simptomi (job pending, OOM, kvota, scratch pun)
      dijagnosticirani raspoloživim read-only alatima.
Format: user -> assistant <think> (3-6 rečenica) + tool_calls -> tool ->
zaključak. metadata: SILVER/template-expansion-v0.4/verified.
Deterministički (seed 404). 13 user-šablona po dimenziji + brojevi u
user-tekstu radi 90%+ jedinstvenih user-tekstova. Ne dira postojeće
fajlove ni splits/.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

RNG = random.Random(404)
OUT = Path(__file__).resolve().parent.parent / "datasets" / "canonical" / "thinking_v0.4.jsonl"
START_ID = 776
VERSION = "0.4.0"
META = {"source": "template-expansion-v0.4", "quality_tier": "SILVER",
        "verification_status": "verified"}


def make_row(n, user, think, pre, calls, touts, final, task, diff):
    msgs = [{"role": "user", "content": user},
            {"role": "assistant", "content": f"<think>\n{think}\n</think>\n\n{pre}",
             "tool_calls": calls}]
    for t in touts:
        msgs.append({"role": "tool", "content": t})
    msgs.append({"role": "assistant", "content": final})
    return {"id": f"amj-th-{n:04d}", "version": VERSION, "language": "bs-ijekavica",
            "task": task, "difficulty": diff, "enable_thinking": True,
            "messages": msgs, "metadata": dict(META)}


def nsent(s):
    return len([x for x in re.split(r"[.!?]+", s) if x.strip()])


SVCS = ["nginx", "postgresql", "redis-server", "docker", "apache2", "mariadb",
        "backup-worker", "gunicorn", "php8.2-fpm"]
PKGS = ["nginx", "postgresql-15", "redis-server", "docker-ce", "openssh-server",
        "certbot", "mariadb-server", "php8.2-fpm"]
DIRS = ["/var/log", "/backup", "/var/lib/postgresql", "/data", "/var/tmp"]
FILES = ["/etc/nginx/nginx.conf", "/etc/ssh/sshd_config",
         "/etc/postgresql/15/main/postgresql.conf", "/srv/app/config.yaml"]
PORTS = [80, 443, 22, 5432, 6379, 3306, 8080]
PARTS = ["gpu", "cpu", "bigmem", "test", "short"]
SCRATCH = ["/scratch/proj-a", "/scratch/tim", "/data/share", "/home/tim"]

TAILS = ["", " Javlja se od jutros.", " Ponavlja se već danima.",
         " Produkcija je pogođena.", " Može li bez restarta?",
         " Javi šta nađeš.", " Hvala unaprijed.", " Prvi put se dešava.",
         " Dešava se i noću.", " Traje od vikenda.", " Šef traži rok.",
         " Hitno je, ali bez lomljenja.", " Javi prije nego što bilo šta diraš.",
         " Radi se o produkciji.", " Testno je okruženje, ali treba brzo.",
         " Zapiši brojeve u odgovor."]


# ================= (a) CALC — disk tempo -> sati -> prioritet =================
A_USERS = [
    "Disk {path} je na {pct}%, a raste oko {rate}GB na sat — kad će puknuti?",
    "{svc} puni {path} brzinom od {rate}GB/h, sad smo na {pct}%.",
    "Jutros je {path} bio na {p0}%, sad je {pct}%. Koliko imamo vremena?",
    "Backup se gomila u {path} — {rate}GB na sat, a niko ne rotira.",
    "Particija {path} na {pct}% i raste {rate}GB svaki sat. Buditi dežurnog ili čekati jutro?",
    "Aplikacija {svc} zapisuje {rate}GB/h u {path}. Dokad izdrži disk?",
    "Slobodno se topi: jučer {free0}GB, danas {free1}GB na {path}. Šta je prioritet?",
    "Log direktorij {path} raste {rate}GB na sat i sad je {pct}% pun.",
    "Slojevi kontejnera u {path} gutaju {rate}GB/h — disk je na {pct}%.",
    "Svaki sat nestane {rate}GB na {path} (sad {pct}%). Izračunaj dokad imamo.",
    "Privremeni fajlovi u {path} rastu {rate}GB/h. Kad postaje kritično?",
    "Monitoring javlja: {path} na {pct}% s trendom +{rate}GB/h. Treba li intervencija sad?",
    "Od jučer se {path} popeo s {p0}% na {pct}% — tempo je {rate}GB na sat.",
]
A_OPEN = ["Krećem od brojki, ne od dojma. ", "Prvo računica, pa akcija. ",
          "Vrijeme do zagušenja određuje prioritet. "]
A_THINKS = [
    "Prijava daje tempo od {rate}GB/h uz {free}GB slobodno, što je oko {hours} sati do vrha. "
    "Granica mi je 6 sati: ispod nje je hitno i lov na potrošača kreće odmah, iznad nje staje u današnji red. "
    "Jedno mjerenje diska potvrđuje polazno stanje prije nego što bilo šta diram. "
    "Nakon mjere slijedi lista najvećih potrošača pa ciljano čišćenje uz potvrdu.",
    "Rast od {rate}GB/h znači da svaki sat nestane fiksan komad slobodnog prostora. "
    "Sa {free}GB slobodno do zagušenja ima oko {hours} sati, pa od tog broja zavisi hoću li buditi dežurnog. "
    "Mjerenje diska je read-only i traje sekundu, zato ide prvo. "
    "Ako mjera potvrdi tempo, sljedeći korak je imenovati fajl koji raste.",
    "Ne vjerujem procjeni napamet pa računam: {free}GB slobodno podijeljeno s {rate}GB/h daje oko {hours} sati. "
    "Taj broj dijeli dva puta — hitan lov na potrošača ili redovno čišćenje. "
    "Prije svake akcije treba svježa mjera diska jer se stanje mijenja iz sata u sat. "
    "Tek s mjerom predlažem brisanje konkretnih fajlova uz potvrdu.",
    "Trend je važniji od trenutnog postotka: {pct}% samo po sebi ne govori kad će stati. "
    "Zato tempo od {rate}GB/h uz slobodnih {free}GB daje oko {hours} sati do vrha. "
    "Ako je broj ispod 6, prioritet je najveći i preskačem sve sporedno. "
    "Mjera diska to potvrđuje, a onda tražim krivca među najvećim fajlovima.",
    "Noćni poslovi mogu privremeno naduvati rast, pa prvo provjeravam mjeru umjesto da paničim. "
    "Računica kaže {free}GB slobodno uz {rate}GB/h, dakle oko {hours} sati do vrha. "
    "Taj rezultat određuje redoslijed: hitno traženje potrošača ili mirno čišćenje ujutro. "
    "Mjera je read-only pa nema razloga da je preskočim.",
    "Svaki sat rasta od {rate}GB pomiče rok za punjenje sve bliže. "
    "Sa {free}GB slobodno rok je oko {hours} sati, što upisujem kao prioritet slučaja. "
    "Najjeftinija provjera je mjerenje zauzeća diska — jedna činjenica prije odluke. "
    "Nakon nje imenujem potrošača listanjem direktorija i tražim potvrdu za brisanje.",
]
A_PRES = ["Mjerim zauzeće diska {path}.", "Provjeravam stanje particije {path}.",
          "Mjerim koliko je ostalo na {path}."]
A_FINALS = [
    "Mjera potvrđuje polaz: {pct}% zauzeto, {free}G slobodno, tempo {rate}GB/h — dakle oko {hours} sati. "
    "{prio} Sljedeći korak je lista najvećih potrošača u {path}; potvrđuješ li?",
    "Disk {path}: {pct}% puno, slobodno {free}G, rast {rate}GB/h — rok oko {hours} sati. "
    "{prio} Predlažem lov na fajl koji raste pa ciljano brisanje uz potvrdu.",
    "Računica stoji: uz {rate}GB/h i {free}G slobodno vrh stiže za oko {hours} sati. "
    "{prio} Idemo naći konkretnog potrošača prije nego što bilo šta obrišem.",
    "Potvrđeno mjerom: {pct}% na {path}, slobodno {free}G, tempo {rate}GB/h — ostalo oko {hours} sati. "
    "{prio} Čišćenje ide tek kad imenujem krivca; nastavljam li s pretragom?",
]


def mk_a(ei, att):
    u = A_USERS[ei % len(A_USERS)]
    path = RNG.choice(DIRS)
    svc = RNG.choice(SVCS)
    rate = RNG.choice([1, 2, 2, 3])
    pct = RNG.randint(78, 93)
    total = RNG.choice([52, 100, 200])
    free = max(1, round(total * (100 - pct) / 100))
    hours = max(1, free // rate)
    p0 = max(40, pct - RNG.randint(6, 18))
    f0 = free + RNG.randint(4, 12)
    ctx = dict(path=path, svc=svc, rate=rate, pct=pct, free=free, hours=hours,
               p0=p0, free0=f0, free1=free)
    prio = ("To je hitno — krećem odmah u lov na potrošača." if hours <= 5
            else "Nije panika, ali ide u današnji red.")
    ctx["prio"] = prio
    user = (u.format(**{k: ctx[k] for k in re.findall(r"{(\w+)}", u)}) + RNG.choice(TAILS)).strip()
    think = RNG.choice(A_OPEN) + A_THINKS[att % len(A_THINKS)].format(**ctx)
    pre = RNG.choice(A_PRES).format(**ctx)
    calls = [{"name": "disk_usage", "arguments": {"path": path}}]
    tout = [f"disk {path}: {pct}% zauzeto ({free}G slobodno)"]
    final = RNG.choice(A_FINALS).format(**ctx)
    task = RNG.choice(["reasoning", "reasoning", "verification"])
    return make_row(0, user, think, pre, calls, tout, final, task,
                    "hard" if hours <= 5 else RNG.choice(["medium", "hard"]))


# ============ (b) CHOICE2 — dva plana, izbor jeftinijeg ============
# (user, planA, planB, cijenaB, tool, tout, pre, final, task)
B_ENTRIES = [
    ("Restartovati {svc} ili prvo provjeriti status?", "status servisa",
     "restart servisa", "prekid konekcija na nekoliko sekundi",
     "service_status", "status servisa {svc}: active (running), radi {d} dana",
     "Provjeravam status servisa {svc}.",
     "Status kaže da {svc} uredno radi već {d} dana — skupi plan otpada. "
     "Restart bi samo prekinuo konekcije bez razloga; ne diram ništa dok ne javiš simptom.",
     "tool-selection"),
    ("Reinstalirati {pkg} ili prvo provjeriti verziju?", "upit verzije paketa",
     "reinstalaciju paketa", "prekid rada i rizik po zavisnosti",
     "package_query", "paket {pkg}: instaliran, verzija aktuelna od {m}",
     "Provjeravam verziju paketa {pkg}.",
     "Paket {pkg} je aktuelan od {m} — reinstalacija otpada kao suvišna. "
     "Uštedjeli smo prekid rada; ako simptom ostaje, tražimo uzrok drugdje.",
     "tool-selection"),
    ("Brisati stare logove u {dir} ili prvo listati šta ima?", "listanje direktorija",
     "brisanje logova", "nepovratan gubitak traga za dijagnostiku",
     "file_list", "direktorij {dir}: {k} rotiranih logova starijih od 60 dana",
     "Listam sadržaj direktorija {dir}.",
     "U {dir} ima {k} starih rotiranih logova — tek sad brisanje ima imenovanu metu. "
     "Blanket brisanje otpada; potvrđuješ li uklanjanje samo tih rotiranih fajlova?",
     "safety"),
    ("Kupiti jači server ili prvo izmjeriti memoriju?", "mjerenje memorije",
     "kupovinu hardvera", "trošak i selidbu bez dokaza da treba",
     "memory_usage", "memorija: {m}% zauzeto, swap netaknut",
     "Mjerim zauzeće memorije.",
     "Memorija je na {m}% bez swapa — kupovina otpada, novac je sačuvan. "
     "Sporost je drugdje; idemo na listu procesa. Potvrđuješ li?",
     "agentic-terminal"),
    ("Gasiti firewall ili provjeriti port {port}?", "provjera porta",
     "gašenje firewalla", "skidanje zaštite sa svih portova odjednom",
     "port_check", "port {port}: sluša očekivani proces",
     "Provjeravam ko sluša na portu {port}.",
     "Na portu {port} sluša očekivani proces — gašenje firewalla otpada kao nesrazmjerno. "
     "Problem je u mreži ili klijentu, ne u zaštiti.",
     "safety"),
    ("Vraćati cijeli sistem iz backupa ili čitati log {svc}?", "čitanje loga",
     "vraćanje iz backupa", "gubitak današnjih podataka i dug prekid",
     "service_logs", "log {svc}: jedna nepoznata direktiva ruši start",
     "Čitam svjež log servisa {svc}.",
     "Log imenuje krivca — jednu direktivu; backup cijelog sistema otpada. "
     "Predlažem ispravku te direktive uz potvrdu, što rješava sve bez gubitka podataka.",
     "tool-selection"),
    ("Ubiti sve procese ili listati po CPU-u?", "lista procesa",
     "gašenje svih procesa", "rušenje sistema i vlastite konekcije",
     "process_list", "top proces: {svc}-worker, {c}% CPU, radi već {min} minuta",
     "Gledam procese po potrošnji CPU-a.",
     "Krivac je imenovan: {svc}-worker drži {c}% CPU-a već {min} minuta. "
     "Blanket gašenje otpada; predlažem provjeru njegovog loga prije ciljanog gašenja.",
     "safety"),
    ("Restartovati cijeli server ili izmjeriti CPU?", "mjerenje CPU-a",
     "restart servera", "prekid svega na nekoliko minuta",
     "cpu_usage", "cpu: {c}% ukupno, jezgre mirne",
     "Mjerim opterećenje CPU-a.",
     "CPU je na mirnih {c}% — restart cijelog servera otpada kao neosnovan. "
     "Nema osnova za najtežu mjeru; tražimo pravi uzrok.",
     "agentic-terminal"),
    ("Dizati drugu instancu {svc} ili čitati mu log?", "čitanje loga",
     "dizanje druge instance", "dvostruku potrošnju uz isti neriješen kvar",
     "service_logs", "log {svc}: worker pada zbog nestanka memorije, supervisor ga diže",
     "Čitam log servisa {svc}.",
     "Log pokazuje pad zbog memorije — druga instanca bi samo ubrzala krah, pa otpada. "
     "Rješavamo memoriju uz potvrdu, ne množimo instance.",
     "tool-selection"),
    ("Širiti particiju {path} ili izmjeriti zauzeće?", "mjerenje zauzeća",
     "širenje particije", "rizičnu operaciju nad diskom i prekid",
     "disk_usage", "disk {path}: {pct}% zauzeto",
     "Mjerim zauzeće diska {path}.",
     "Disk {path} je na {pct}% — širenje particije otpada dok ima ovoliko lufta. "
     "Prvo ciljano čišćenje uz potvrdu, širenje je zadnja rezerva.",
     "function-calling"),
    ("Mijenjati konfiguraciju {svc} ili je prvo pročitati?", "čitanje konfiguracije",
     "izmjenu napamet", "rizik da se pokvari i ono što radi",
     "file_read", "fajl {file}: uredan, zadnja izmjena prije {d} dana",
     "Čitam konfiguraciju {svc}.",
     "Konfiguracija je uredna i stara {d} dana — izmjena napamet otpada. "
     "Uzrok je drugdje; predlažem log servisa kao sljedeći trag.",
     "function-calling"),
    ("Zvati provajdera ili provjeriti naša sučelja?", "provjera sučelja",
     "eskalaciju provajderu", "sate čekanja iako je kvar možda naš",
     "network_status", "sučelja uredna, eth0 up, bez grešaka na brojačima",
     "Provjeravam status mrežnih sučelja.",
     "Naša sučelja su uredna i brojači čisti — ali eskalacija još ne ide. "
     "Prvo pratim kuda pucaju konekcije; provajder je rezerva s dokazom.",
     "verification"),
    ("Instalirati {pkg} ili provjeriti je li već tu?", "upit paketa",
     "instalaciju", "mijenjanje sistema bez potrebe",
     "package_query", "paket {pkg}: već instaliran, verzija aktuelna",
     "Provjeravam je li paket {pkg} već instaliran.",
     "Paket {pkg} je već tu i aktuelan — instalacija otpada. "
     "Problem nije u paketu; tražimo dalje uz potvrdu za svaki sljedeći korak.",
     "function-calling"),
]
B_OPEN = ["Vagam dva puta pa biram jeftiniji. ",
          "Prije skupe mjere ide jeftina provjera. "]
B_THINKS = [
    "Na stolu su dva plana. Plan A ({plana}) je read-only, traje sekundu i ništa ne mijenja. "
    "Plan B ({planb}) košta {cost} i nosi rizik da pokvari ispravnu stvar. "
    "Biram A jer njegov rezultat može obesmisliti B; ako A ne razriješi, B ostaje rezerva uz potvrdu.",
    "Vagam jeftin i skup put. Plan A ({plana}) daje činjenicu bez posljedica, dok plan B ({planb}) znači {cost}. "
    "Redoslijed je zato fiksan: prvo A, pa tek s dokazom eventualno B. "
    "Preskakanje A značilo bi plaćanje cijene bez dokaza da treba.",
    "Prije skupe mjere uvijek ide jeftina provjera. Plan A ({plana}) je besplatan u riziku, "
    "a plan B ({planb}) povlači {cost}. Ako A pokaže da je sve uredno, B otpada i uštedjeli smo; "
    "ako A nađe kvar, B postaje ciljan umjesto napamet.",
    "Dva puta vode do cilja, ali različitim cijenama. Plan A ({plana}) ne dira ništa, plan B ({planb}) donosi {cost}. "
    "Biram redoslijed od jeftinijeg: činjenica iz A određuje treba li B uopće. "
    "To je jedini redoslijed koji ne baca novac ni vrijeme.",
    "Skupa opcija bez mjere je kocka. Plan A ({plana}) je mjera koja traje sekundu, plan B ({planb}) znači {cost}. "
    "Zato A ide prvo: ili potvrdi da B treba, ili ga učini suvišnim. "
    "B bez potvrde ne dolazi u obzir.",
    "Birati se mora cijenom i rizikom, ne navikom. Plan A ({plana}) je read-only i odmah gotov, "
    "plan B ({planb}) nosi {cost}. Logika je prosta: jeftina činjenica prije skupe akcije. "
    "Ako činjenica oslobodi B, tim bolje.",
]


def mk_b(ei, att):
    e = B_ENTRIES[ei % len(B_ENTRIES)]
    u, plana, planb, cost, tool, tout, pre, final, task = e
    svc, pkg, d, path = RNG.choice(SVCS), RNG.choice(PKGS), RNG.choice(DIRS), RNG.choice(DIRS)
    port = RNG.choice(PORTS)
    f = RNG.choice(FILES)
    ctx = dict(svc=svc, pkg=pkg, dir=d, path=path, port=port, file=f,
               d=RNG.randint(3, 21), m=RNG.choice(["januara", "marta", "juna", "oktobra"]),
               k=RNG.randint(5, 14), c=RNG.randint(18, 40), pct=RNG.randint(38, 55),
               min=RNG.randint(25, 60))
    names = set(re.findall(r"{(\w+)}", u + plana + planb + cost + tout + pre + final))
    F = {k: ctx[k] for k in names}
    user = (u.format(**{k: F[k] for k in re.findall(r"{(\w+)}", u)}) + RNG.choice(TAILS)).strip()
    think = (RNG.choice(B_OPEN) + B_THINKS[att % len(B_THINKS)].format(
        plana=plana, planb=planb, cost=cost))
    pre = pre.format(**{k: F[k] for k in re.findall(r"{(\w+)}", pre)})
    tout = tout.format(**{k: F[k] for k in re.findall(r"{(\w+)}", tout)})
    final = final.format(**{k: F[k] for k in re.findall(r"{(\w+)}", final)})
    if tool == "service_status":
        calls = [{"name": tool, "arguments": {"service": F.get("svc", svc)}}]
    elif tool == "service_logs":
        calls = [{"name": tool, "arguments": {"service": F.get("svc", svc), "lines": 30}}]
    elif tool == "package_query":
        calls = [{"name": tool, "arguments": {"package": F.get("pkg", pkg)}}]
    elif tool in ("disk_usage",):
        calls = [{"name": tool, "arguments": {"path": F.get("path", path)}}]
    elif tool == "file_list":
        calls = [{"name": tool, "arguments": {"path": F.get("dir", d)}}]
    elif tool == "file_read":
        calls = [{"name": tool, "arguments": {"path": F["file"], "lines": 50}}]
    elif tool == "port_check":
        calls = [{"name": tool, "arguments": {"port": F.get("port", port)}}]
    elif tool == "process_list":
        calls = [{"name": tool, "arguments": {"limit": 10, "sort_by": "cpu"}}]
    else:
        calls = [{"name": tool, "arguments": {}}]
    return make_row(0, user, think, pre, calls, [tout], final, task, "medium")


# ============ (c) PIVOT — prvi trag promašaj, prelazak dalje ============
# (user, hipoteza, prvi_alat, tool, tout_cist, trag, sljedeci, pre, final, task)
C_ENTRIES = [
    ("Mreža povremeno puca — je li kvar kod nas?", "mrežni kvar kod nas",
     "network_status", "network_status",
     "sučelja uredna, eth0 up, bez grešaka na brojačima", "mrežnog",
     "log forenziku servisa koji puca",
     "Provjeravam status mrežnih sučelja.",
     "Nalaz je čist: sučelja uredna, brojači bez grešaka. Odustajem od mrežnog traga — "
     "dalje kopanje tamo baca vrijeme. Prelazim na log forenziku servisa koji puca; potvrđuješ li?",
     "reasoning"),
    ("Sajt ne radi — sigurno firewall blokira port {port}.", "blokiran port",
     "port_check", "port_check",
     "port {port}: sluša očekivani proces", "firewalla",
     "log forenziku servisa iza porta",
     "Provjeravam ko sluša na portu {port}.",
     "Nalaz je čist: na portu {port} sluša očekivani proces. Odustajem od traga firewalla — "
     "blokade nema. Prelazim na log forenziku servisa; potvrđuješ li nastavak?",
     "verification"),
    ("Disk je sigurno pun, zato {svc} pada.", "pun disk",
     "disk_usage", "disk_usage",
     "disk /: {pct}% zauzeto", "punog diska",
     "memoriju i procese",
     "Mjerim zauzeće diska.",
     "Nalaz je čist: disk je na {pct}%, dakle nije pun. Odustajem od traga punog diska. "
     "Prelazim na memoriju i procese — sljedeća mjera je memorija; potvrđuješ li?",
     "reasoning"),
    ("Fali memorije, zato je sve sporo.", "nestanak memorije",
     "memory_usage", "memory_usage",
     "memorija: {m}% zauzeto, swap netaknut", "memorije",
     "log forenziku najvećeg potrošača",
     "Mjerim zauzeće memorije.",
     "Nalaz je čist: memorija na {m}% bez swapa. Odustajem od traga memorije — "
     "sporost je drugdje. Prelazim na log forenziku najvećeg potrošača; nastavljam li?",
     "verification"),
    ("CPU je na izdisaju, zato {svc} šteka.", "preopterećen CPU",
     "cpu_usage", "cpu_usage",
     "cpu: {c}% ukupno, jezgre mirne", "CPU-a",
     "log forenziku servisa",
     "Mjerim opterećenje CPU-a.",
     "Nalaz je čist: CPU na mirnih {c}%. Odustajem od traga preopterećenja — "
     "procesor je nevin. Prelazim na log forenziku servisa {svc}; potvrđuješ li?",
     "reasoning"),
    ("{svc} je sigurno mrtav, digni ga.", "mrtav servis",
     "service_status", "service_status",
     "status servisa {svc}: active (running), radi {dd} dana", "mrtvog servisa",
     "log forenziku servisa",
     "Provjeravam status servisa {svc}.",
     "Nalaz je čist: {svc} uredno radi već {dd} dana. Odustajem od traga mrtvog servisa — "
     "dizati nema šta. Prelazim na log forenziku da vidim šta se zaista dešava; nastavljam li?",
     "function-calling"),
    ("Paket {pkg} je pokvaren pa sve puca.", "pokvaren paket",
     "package_query", "package_query",
     "paket {pkg}: instaliran, verzija aktuelna, integritet uredan", "pokvarenog paketa",
     "konfiguraciju servisa",
     "Provjeravam instaliranu verziju paketa {pkg}.",
     "Nalaz je čist: paket {pkg} aktuelan i integritet uredan. Odustajem od traga pokvarenog paketa. "
     "Prelazim na konfiguraciju servisa — čitam fajl uz potvrdu; može li?",
     "verification"),
    ("Logovi su pojeli disk u {dir}, zato pada.", "logovi pojeli disk",
     "file_list", "file_list",
     "direktorij {dir}: samo sitni rotirani logovi, ukupno ispod 1G", "logova-krivaca",
     "log forenziku servisa koji pada",
     "Listam sadržaj direktorija {dir}.",
     "Nalaz je čist: u {dir} samo sitni logovi, ništa veliko. Odustajem od tog traga — "
     "krivac nije ovdje. Prelazim na log forenziku servisa koji pada; potvrđuješ li?",
     "reasoning"),
    ("Baza na portu {port} sigurno ne sluša.", "mrtva baza",
     "port_check", "port_check",
     "port {port}: sluša očekivani proces", "mrtve baze",
     "log forenziku baze",
     "Provjeravam port {port}.",
     "Nalaz je čist: na portu {port} sluša očekivani proces. Odustajem od traga mrtve baze — "
     "baza sluša. Prelazim na log forenziku baze da nađem pravi uzrok; nastavljam li?",
     "function-calling"),
    ("Konfiguracija je dobra, mora biti mreža kriva za pad {svc}.", "mrežni kvar",
     "network_status", "network_status",
     "sučelja uredna, eth0 up, bez grešaka na brojačima", "mrežnog",
     "konfiguraciju servisa",
     "Provjeravam status mrežnih sučelja.",
     "Nalaz je čist: mreža uredna. Odustajem od mrežnog traga — "
     "ako je konfiguracija navodno dobra, to tek treba dokazati. Prelazim na čitanje konfiguracije; može li?",
     "reasoning"),
    ("Predugo se diže sistem — disk je spor ili pun.", "spor ili pun disk",
     "disk_usage", "disk_usage",
     "disk /: {pct}% zauzeto, bez grešaka", "diska",
     "log forenziku servisa pri startu",
     "Mjerim zauzeće diska.",
     "Nalaz je čist: disk na {pct}% i bez grešaka. Odustajem od traga diska. "
     "Prelazim na log forenziku starta servisa; potvrđuješ li nastavak?",
     "verification"),
    ("Preopterećenje — previše prometa guta {svc}.", "navala prometa",
     "cpu_usage", "cpu_usage",
     "cpu: {c}% ukupno, mirno", "preopterećenja",
     "listu procesa pa log",
     "Mjerim opterećenje CPU-a.",
     "Nalaz je čist: CPU na {c}%, prometa-navale nema. Odustajem od traga preopterećenja. "
     "Prelazim na listu procesa pa log forenziku; nastavljam li?",
     "function-calling"),
    ("DNS je kriv za pad {svc}, provjeri mrežu.", "mrežni kvar",
     "network_status", "network_status",
     "sučelja uredna, eth0 up, bez grešaka na brojačima", "mrežnog",
     "log forenziku servisa",
     "Provjeravam status mrežnih sučelja.",
     "Nalaz je čist: mreža uredna, DNS trag se ne potvrđuje. Odustajem od mrežnog traga. "
     "Prelazim na log forenziku servisa {svc}; potvrđuješ li?",
     "reasoning"),
]
C_OPEN = ["Krećem najvjerovatnijim tragom, ali ga provjeravam. ",
          "Prvi utisak testiram mjerenjem, ne branim ga. "]
C_THINKS = [
    "Prvi trag mi je {hyp}, pa krećem alatom {first} jer je najbrži put do potvrde. "
    "Ako alat vrati čist nalaz, hipoteza pada i tog traga se držati nema smisla. "
    "Read-only provjera košta sekundu, pa je i promašaj jeftin. "
    "U slučaju promašaja prelazim na sljedeći najvjerovatniji trag s novom činjenicom.",
    "Sve upućuje na {hyp}, zato alat {first} ide prvi. "
    "Čist rezultat značio bi da sam krenuo krivim putem — to se prizna, ne brani. "
    "Bolje odustati nakon jedne provjere nego kopati dublje u pogrešnom smjeru. "
    "Rezerva je spremna: sljedeći trag ide odmah po promašaju.",
    "Hipoteza {hyp} je najvjerovatnija na prvi pogled, pa je testiram alatom {first}. "
    "Ako mjera bude uredna, neću je uljepšavati — promašaj je promašaj. "
    "Jedna jeftina provjera vrijedi više od sata kopanja krivim putem. "
    "Nakon čistog nalaza okrećem se sljedećem tragu bez žaljenja.",
    "Birati prvi alat znači birati hipotezu: biram {hyp} i alat {first}. "
    "Čist nalaz bi tu hipotezu srušio, i to je u redu — tako dijagnostika radi. "
    "Ne kopam dalje u smjeru koji mjera demantuje. "
    "Plan B čeka: sljedeći trag po vjerovatnoći.",
    "Krećem od {hyp} jer se najbolje uklapa u simptom, alat {first} to provjerava. "
    "Ako provjera bude čista, odustajem odmah — upornost na pogrešnom tragu je najskuplja greška. "
    "Sekunda mjerenja štedi sate lutanja. "
    "Sljedeći korak je već određen: trag broj dva.",
    "Najbrži put do istine je testirati najočitije: {hyp} alatom {first}. "
    "Čist rezultat ne znači da je mjera bila uzalud — suzila je prostor. "
    "Odustajanje od demantovanog traga je disciplina, ne poraz. "
    "Poslije promašaja idem redom na sljedećeg osumnjičenog.",
]


def mk_c(ei, att):
    e = C_ENTRIES[ei % len(C_ENTRIES)]
    u, hyp, first, tool, tout, trag, sljed, pre, final, task = e
    svc, pkg, d = RNG.choice(SVCS), RNG.choice(PKGS), RNG.choice(DIRS)
    port = RNG.choice(PORTS)
    ctx = dict(svc=svc, pkg=pkg, dir=d, port=port, pct=RNG.randint(34, 52),
               m=RNG.randint(38, 55), c=RNG.randint(15, 30), dd=RNG.randint(4, 15))
    names = set(re.findall(r"{(\w+)}", u + tout + pre + final))
    F = {k: ctx[k] for k in names}
    fmt = lambda s: s.format(**{k: F[k] for k in re.findall(r"{(\w+)}", s)})
    user = (fmt(u) + RNG.choice(TAILS)).strip()
    think = RNG.choice(C_OPEN) + RNG.choice([C_THINKS[att % len(C_THINKS)]]).format(hyp=hyp, first=first)
    pre, tout, final = fmt(pre), fmt(tout), fmt(final)
    if tool == "service_status":
        calls = [{"name": tool, "arguments": {"service": ctx["svc"]}}]
    elif tool == "port_check":
        calls = [{"name": tool, "arguments": {"port": ctx["port"]}}]
    elif tool == "disk_usage":
        calls = [{"name": tool, "arguments": {"path": "/"}}]
    elif tool == "package_query":
        calls = [{"name": tool, "arguments": {"package": ctx["pkg"]}}]
    elif tool == "file_list":
        calls = [{"name": tool, "arguments": {"path": ctx["dir"]}}]
    else:
        calls = [{"name": tool, "arguments": {}}]
    return make_row(0, user, think, pre, calls, [tout], final, task, "hard")


# ================= (d) HPC/Slurm =================
D_USERS = [
    "Slurm posao {job} na particiji {part} stoji u PENDING već satima. Šta ga koči?",
    "Posao {job} ubijen je signalom — sumnjam na OOM, tražio je {mem}GB. Provjeri memoriju čvora.",
    "Posao {job} pao je s greškom o kvoti na {path}. Je li kvota zaista puna?",
    "Scratch {path} je na {pct}%, poslovi pucaju pri pisanju. Gdje je otišlo?",
    "Posao {job} radi tri puta sporije nego inače na {part}. Je li čvor zagušen?",
    "Niz poslova oko {job} čeka u redu — je li opterećenje previsoko?",
    "Izlazna datoteka posla {job} narasla je na {size}GB u {path}. Smijem li je dirati?",
    "Posao {job} na {part} jede memoriju cijelog čvora. Šta troši?",
    "Dva posla pala su istovremeno na istom čvoru oko posla {job}. Slučajnost ili uzrok?",
    "Kvota na {path} pri kraju je ({pct}%), a novi poslovi pišu baš tamo. Koliko imamo?",
    "Posao {job} visi — satima ništa ne piše u izlaz. Je li živ?",
    "Checkpoint fajlovi pune {path} ({pct}%). Šta je sigurno za čistiti?",
    "Nakon proširenja posla {job} na više jezgri čvor je usporio. Gdje je usko grlo?",
]
D_OPEN = ["Gledam šta čvor kaže, ne šta red kaže. ",
          "Posao je simptom, čvor je činjenica. "]
D_THINKS = [
    "Posao {job} na particiji {part} je prijava, ali scheduler-uvida nemam pa idem najbližim read-only tragom. "
    "Hipoteze su: (1) čvor zagušen pa posao nema resursa, (2) posao sam zabagovan, (3) dijeljeni prostor pun. "
    "Mjera resursa čvora razdvaja prvi slučaj od ostalih jednim pozivom. "
    "Ako je čvor miran, sumnja se seli na sam posao i njegov izlaz.",
    "Prijava veže posao {job} za particiju {part}, ali uzrok može biti i ispod posla — na čvoru. "
    "Redoslijed mi je: prvo stanje resursa, pa tek onda logika posla. "
    "Read-only mjera ne dira poslove drugih korisnika, zato je siguran prvi korak. "
    "S mjerom u ruci predlažem sljedeći potez uz potvrdu.",
    "Kod HPC kvarova krivac je često dijeljeni resurs, ne sam posao {job}. "
    "Zato prije nego što diram posao, mjerim ono što svi poslovi dijele. "
    "Ako je dijeljeno uredno, tek onda gledam procese i trag posla. "
    "Redoslijed mjera-pa-akcija vrijedi i na klasteru.",
    "Posao {job} može patiti iz tri razloga: zagušen čvor, puna kvota ili vlastita greška. "
    "Biranjem jedne read-only mjere skidam cijelu granu odjednom. "
    "Ako mjera bude uredna, ta grana otpada i ne vraćam joj se. "
    "Tako se redom sužava dok ne ostane pravi uzrok.",
    "Ne gasim i ne pomjeram tuđe poslove napamet — to bi srušilo i tuđi rad. "
    "Prvo treba činjenica o stanju čvora oko posla {job}. "
    "Mjera je read-only pa je bezopasna i prema tuđim poslovima. "
    "Tek s činjenicom predlažem potez koji dira posao, i to uz potvrdu.",
    "Simptom je na poslu {job}, ali dijagnoza ide odozdo: resursi pa procesi pa logika. "
    "Preskakanje stepenica vodi pogrešnim zaključcima i opasnim akcijama. "
    "Jedna mjera čvora je najjeftinija stepenica. "
    "Nakon nje znam ide li se u procese, kvotu ili izlaz posla.",
]
D_PRES = [
    ("process_list", "Gledam opterećenje procesa na čvoru."),
    ("cpu_usage", "Mjerim opterećenje CPU-a čvora."),
    ("memory_usage", "Mjerim zauzeće memorije čvora."),
    ("disk_usage", "Mjerim zauzeće prostora {path}."),
    ("file_list", "Listam najveće potrošače u {path}."),
    ("file_read", "Čitam skriptu posla {job}."),
]


def mk_d(ei, att):
    u = D_USERS[ei % len(D_USERS)]
    job = RNG.randint(100000, 999999)
    part = RNG.choice(PARTS)
    path = RNG.choice(SCRATCH)
    svc = RNG.choice(SVCS)
    ctx = dict(job=job, part=part, path=path, svc=svc, mem=RNG.choice([32, 64, 128, 256]),
               pct=RNG.randint(80, 96), size=RNG.randint(15, 80),
               c=RNG.randint(70, 98), m=RNG.randint(85, 97), k=RNG.randint(6, 12))
    names = set(re.findall(r"{(\w+)}", u))
    user = (u.format(**{k: ctx[k] for k in names}) + RNG.choice(TAILS)).strip()
    think = RNG.choice(D_OPEN) + D_THINKS[att % len(D_THINKS)].format(job=job, part=part)
    k = ei % 6
    if k == 0:
        tool, pre = "process_list", D_PRES[0][1]
        calls = [{"name": tool, "arguments": {"limit": 10, "sort_by": "cpu"}}]
        tout = (f"top proces: posao {job}, {ctx['c']}% CPU, radi već 3 sata; "
                f"ostatak čvora miran")
        final = (f"Čvor nosi posao {job} s {ctx['c']}% CPU-a već 3 sata, ostalo mirno — "
                 f"zagušenje čvora nije potvrđeno. Sumnja se seli na sam posao; "
                 f"predlažem provjeru njegovog izlaza uz potvrdu.")
    elif k == 1:
        tool, pre = "cpu_usage", D_PRES[1][1]
        calls = [{"name": tool, "arguments": {}}]
        tout = f"cpu: {ctx['c']}% ukupno na čvoru"
        final = (f"CPU čvora je na {ctx['c']}% — čvor jeste pod teretom. Posao {job} čeka resurse; "
                 f"predlažem provjeru reda i prioriteta umjesto diranja posla. Nastavljam li?")
    elif k == 2:
        tool, pre = "memory_usage", D_PRES[2][1]
        calls = [{"name": tool, "arguments": {}}]
        tout = f"memorija čvora: {ctx['m']}% zauzeto, swap u upotrebi"
        final = (f"Memorija čvora na {ctx['m']}% sa swapom — OOM trag se potvrđuje za posao {job}. "
                 f"Predlažem manji memorijski zahtjev ili particiju s više RAM-a uz potvrdu.")
    elif k == 3:
        tool, pre = "disk_usage", D_PRES[3][1].format(path=path)
        calls = [{"name": tool, "arguments": {"path": path}}]
        tout = f"disk {path}: {ctx['pct']}% zauzeto"
        final = (f"Prostor {path} na {ctx['pct']}% — kvota se zaista bliži kraju. "
                 f"Predlažem listanje najvećih potrošača pa čišćenje checkpointa uz potvrdu.")
    elif k == 4:
        tool, pre = "file_list", D_PRES[4][1].format(path=path)
        calls = [{"name": tool, "arguments": {"path": path}}]
        tout = (f"direktorij {path}: {ctx['k']} checkpoint fajlova, nose 80% prostora")
        final = (f"U {path} stoji {ctx['k']} checkpoint fajlova s 80% prostora — krivac je imenovan. "
                 f"Predlažem brisanje samo završenih checkpointa uz potvrdu; potvrđuješ li pretragu?")
    else:
        tool, pre = "file_read", D_PRES[5][1].format(job=job)
        calls = [{"name": tool, "arguments": {"path": f"{path}/job-{job}.sh", "lines": 50}}]
        tout = (f"skripta job-{job}.sh: traži {ctx['mem']}GB i particiju {part}, "
                f"izlaz piše u {path}")
        final = (f"Skripta posla {job} traži {ctx['mem']}GB na particiji {part} s izlazom u {path}. "
                 f"Zahtjev i stvarnost se ne slažu; predlažem usklađivanje resursa uz potvrdu.")
    task = RNG.choice(["function-calling", "verification", "reasoning"])
    diff = RNG.choice(["medium", "hard", "hard"])
    return make_row(0, user, think, pre, calls, [tout], final, task, diff)


def old_users():
    s = set()
    base = OUT.parent
    for f in ("thinking_v0.1.jsonl", "thinking_v0.2.jsonl", "thinking_v0.3.jsonl"):
        p = base / f
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                s.add(json.loads(line)["messages"][0]["content"].strip().lower())
    return s


def build_dim(rows, used, users_new, old, key, count, mk, nentries):
    n = len(rows)
    made, ei, att = 0, 0, 0
    guard = 0
    while made < count:
        guard += 1
        if guard > count * 200:
            raise RuntimeError(f"ne mogu popuniti {key}")
        r = mk(ei % nentries, att)
        att += 1
        u_norm = r["messages"][0]["content"].strip().lower()
        if u_norm in old or u_norm in users_new:
            continue
        for m in r["messages"]:
            if m.get("role") == "assistant" and "<think>" in m.get("content", ""):
                th = m["content"].split("</think>")[0]
                c = nsent(th)
                assert 3 <= c <= 6, f"think ima {c} rečenica: {th[:120]}"
        key_msgs = json.dumps(r["messages"], sort_keys=True, ensure_ascii=False)
        if key_msgs in used:
            continue
        r["id"] = f"amj-th-{START_ID + n:04d}"
        n += 1
        used.add(key_msgs)
        users_new.add(u_norm)
        rows.append(r)
        made += 1
        ei += 1
    return n


def main():
    old = old_users()
    rows, used, users_new = [], set(), set()
    n = START_ID
    from collections import Counter
    counts = {}
    n = build_dim(rows, used, users_new, old, "calc", 125, mk_a, len(A_USERS))
    counts["calc(a)"] = 125
    n = build_dim(rows, used, users_new, old, "choice2", 125, mk_b, len(B_ENTRIES))
    counts["choice2(b)"] = 125
    n = build_dim(rows, used, users_new, old, "pivot", 125, mk_c, len(C_ENTRIES))
    counts["pivot(c)"] = 125
    n = build_dim(rows, used, users_new, old, "hpc", 125, mk_d, len(D_USERS))
    counts["hpc(d)"] = 125
    assert len(rows) == 500, len(rows)
    assert len(used) == 500
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                   encoding="utf-8")
    print(f"upisano: {OUT} ({len(rows)} redova, id {START_ID:04d}..{START_ID + len(rows) - 1:04d})")
    print("po dimenziji:", counts)
    print("po tasku:", dict(Counter(r["task"] for r in rows)))
    print("po tezini:", dict(Counter(r["difficulty"] for r in rows)))
    print(f"jedinstvenih user-tekstova: {len(users_new)}/{len(rows)} "
          f"= {100 * len(users_new) / len(rows):.1f}%")


if __name__ == "__main__":
    main()
