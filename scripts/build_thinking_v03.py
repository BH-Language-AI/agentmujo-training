"""Build datasets/canonical/thinking_v0.3.jsonl — 500 novih thinking uzoraka.

Nastavak na thinking_v0.2 (max amj-th-0275): ID amj-th-0276...
Nove dimenzije traga (ne postoje u v0.1/v0.2):
  (a) WRONG-HYP: pocetna pogresna hipoteza koju tool rezultat opovrgava,
      pa se plan koriguje u zakljucku;
  (b) REJECT: eksplicitno odbacivanje destruktivne opcije uz obrazlozenje;
  (c) CHOICE: izbor izmedju dva alata uz obrazlozenje zasto bas taj;
  (d) novi simptomi: curenje memorije (2x memory_usage), intermitentni kvar,
      degradacija performansi, losa konfiguracija nakon updatea.
Format: user -> assistant <think> (3-6 recenica) + tool_calls -> tool -> zakljucak.
metadata: SILVER/template-expansion-v0.3/verified. Deterministicki (seed 303).
Ne dira postojece fajlove ni splits/.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

RNG = random.Random(303)
OUT = Path(__file__).resolve().parent.parent / "datasets" / "canonical" / "thinking_v0.3.jsonl"
START_ID = 276
VERSION = "0.3.0"
META = {"source": "template-expansion-v0.3", "quality_tier": "SILVER",
        "verification_status": "verified"}


def row_single(n, user, think, pre, calls, tout, final, task, diff):
    msgs = [{"role": "user", "content": user},
            {"role": "assistant", "content": f"<think>\n{think}\n</think>\n\n{pre}",
             "tool_calls": calls},
            {"role": "tool", "content": tout},
            {"role": "assistant", "content": final}]
    return {"id": f"amj-th-{n:04d}", "version": VERSION, "language": "bs-ijekavica",
            "task": task, "difficulty": diff, "enable_thinking": True,
            "messages": msgs, "metadata": dict(META)}


def row_double(n, user, think, pre, calls, tout1, tout2, final, task, diff):
    """Dva uzastopna tool poziva (curenje memorije: trend kroz vrijeme)."""
    msgs = [{"role": "user", "content": user},
            {"role": "assistant", "content": f"<think>\n{think}\n</think>\n\n{pre}",
             "tool_calls": calls},
            {"role": "tool", "content": tout1},
            {"role": "tool", "content": tout2},
            {"role": "assistant", "content": final}]
    return {"id": f"amj-th-{n:04d}", "version": VERSION, "language": "bs-ijekavica",
            "task": task, "difficulty": diff, "enable_thinking": True,
            "messages": msgs, "metadata": dict(META)}


SVCS = ["nginx", "postgresql", "redis-server", "docker", "apache2", "mariadb",
        "backup-worker", "gunicorn", "php8.2-fpm"]
PKGS = ["nginx", "postgresql-15", "redis-server", "docker-ce", "openssh-server",
        "certbot", "mariadb-server", "php8.2-fpm"]
PKG2SVC = {"nginx": "nginx", "postgresql-15": "postgresql", "redis-server": "redis-server",
           "docker-ce": "docker", "openssh-server": "sshd", "certbot": "certbot",
           "mariadb-server": "mariadb", "php8.2-fpm": "php8.2-fpm"}

TAILS = ["", " Traje vec danima.", " Pogorsava se.", " Produkcija trpi.",
         " Moze li bez restarta?", " Desava se od jucer.", " Javi sta nadjes.",
         " Hvala unaprijed."]

# ---------- (d1) CURENJE MEMORIJE — 2x memory_usage ----------
MEM_A = [  # (user, think, pre, tout2_tpl, final_tpl)
    ("Servis {t} svakim danom trosi sve vise memorije.",
     "Na prvi pogled djeluje kao kratkotrajan pik — mozda je nocni backup u toku pa ce se memorija sama "
     "osloboditi. Ali prijava traje danima, a pik bi se vec povukao. Zato mjerim memoriju dvaput u razmaku "
     "od 20 minuta: ako je drugo mjerenje vece, hipoteza o piku pada i radi se o curenju. U tom slucaju "
     "plan B je naci proces koji raste i predloziti ciljani restart uz potvrdu.",
     "Mjerim memoriju dvaput u razmaku od 20 minuta.",
     "Drugo mjerenje pokazuje rast i hipoteza o piku je opovrgnuta — memorija ne pada nego curi. "
     "Prevario sam se u pocetnoj procjeni, pa mijenjam plan: sljedeci korak je lista procesa po memoriji "
     "da nadjemo krivca, pa ciljani restart uz tvoju potvrdu."),
    ("Server usporava iz dana u dan, sumnjam na curenje u {t}.",
     "Mislio sam da je normalan rast prometa — vise posjeta, vise memorije, nista cudno. Ali promet je po "
     "izvjestajima ravan, a memorija raste i kad je promet nocu minimalan. Dva uzastopna mjerenja ce "
     "presuditi: ravan graf znaci da sam bio u pravu, rast znaci curenje. Ako curi, ne restartujem napamet "
     "nego prvo identifikujem proces.",
     "Provjeravam trend memorije dvama mjerenjima.",
     "Rast je potvrdjen i hipoteza o prometu je pala — memorija raste i bez prometa. Korigujem plan: "
     "trazimo proces koji curi pa ga restartujemo uz potvrdu, a dugorocno treba prijava buga."),
    ("Moram restartovati {t} svako jutro jer memorija stalno raste.",
     "Pocetna misao mi je bila da je to samo fragmentacija koja se restartom cisti i da je jutarnji restart "
     "dovoljno rjesenje. Ali dnevni restart je lijecenje simptoma, a rast unutar dana moze biti pravi leak. "
     "Dva mjerenja u razmaku pokazuju brzinu rasta: spor rast podrzava fragmentaciju, brz rast potvrdjuje "
     "curenje. Rezultat odlucuje ide li se u lov na proces ili ostaje rutina.",
     "Mjerim brzinu rasta memorije dvaput.",
     "Rast je prebrz za fragmentaciju — pocetna hipoteza ne stoji. Mijenjam plan: umjesto rutinskog "
     "restarta trazimo proces-krivca listom po memoriji, pa restart uz potvrdu."),
]
MEM_B = [
    ("Memorija curi danima na {t}. Samo restartuj cijeli server svako jutro.",
     "Odbacujem trajni jutarnji restart cijelog servera — prekida sve servise odjednom, a curenje se vrati "
     "za par dana, pa nista nismo rijesili. Odbacujem i gasenje svih procesa odjednom jer bi to srusilo i "
     "sistem i moju sesiju. Umjesto toga mjerim trend memorije dvama pozivima: cinjenica o brzini rasta "
     "odlucuje je li dovoljan restart jednog servisa ili treba dublja dijagnostika.",
     "Mjerim trend memorije prije bilo kakve akcije.",
     "Trend potvrdjuje curenje, ali restart cijelog servera ostaje odbacen kao nesrazmjeran. Predlazem "
     "restart samo servisa {t} uz tvoju potvrdu, plus prijavu curenja developerima."),
    ("{t} guta memoriju. Ubij sve sumnjive procese pa cemo vidjeti.",
     "Odbacujem ubijanje procesa napamet — bez mjerenja bih mogao ugasiti bazu ili sam sshd i ostati bez "
     "pristupa. Prvo treba dokaz da memorija zaista curi, a ne da je pik: dva mjerenja u razmaku daju trend. "
     "Tek s potvrdjenim trendom smijem predloziti gasenje konkretnog procesa, i to uz potvrdu. Redoslijed je "
     "mjerenje pa akcija, nikad obrnuto.",
     "Prvo potvrdjujem curenje mjerenjem.",
     "Curenje je potvrdjeno trendom, ali blanket gasenje ostaje odbaceno. Sljedeci korak je lista procesa "
     "po memoriji da imenujemo krivca — potvrdjujes li da nastavim?"),
]
MEM_C = [
    ("Raste li memorija zbog {t} ili je prolazan pik?",
     "Izmedju memory_usage i process_list biram memory_usage: lista procesa pokazuje trenutak, a meni treba "
     "trend kroz vrijeme da razdvojim pik od curenja. Dva uzastopna mjerenja rjesavaju dilemu jednim parom "
     "poziva, oba read-only. Tek kad trend potvrdi curenje, process_list ima smisla za lov na krivca. Zato "
     "redoslijed ide trend pa proces, a ne obrnuto.",
     "Mjerim trend memorije dvama pozivima.",
     "Izbor se isplatio: trend pokazuje rast, sto jedan trenutni presjek ne bi dokazao. Sad ima smisla "
     "zvati process_list po memoriji — potvrdjujes li nastavak?"),
]
MEM_D = [
    ("Aplikacija {t} jede sve vise RAM-a iz sedmice u sedmicu.",
     "Rast memorije kroz sedmice lici na curenje. Hipoteze: (1) proces ne oslobadja memoriju, (2) rast "
     "prometa koji prati rast potrosnje, (3) kratkotrajan pik. Jedno mjerenje ne razdvaja nista, ali dva "
     "mjerenja u razmaku pokazuju smjer: rast znaci curenje. Oba poziva su read-only pa idu odmah.",
     "Mjerim memoriju dvaput za trend.",
     "Trend pokazuje stabilan rast — curenje, ne pik. Sljedeci korak je proces-lista po memoriji pa "
     "ciljani restart uz potvrdu."),
]

# ---------- (d2) INTERMITENTNI KVAR ----------
INT_A = [
    ("Servis {t} radi pa stane, pa se sam vrati. Je li do mreze?",
     "Prva misao mi je bila mreza — povremeni prekidi bas tako izgledaju izvana. Ali mrezni prekid bi rusio "
     "sve servise odjednom, a pada samo {t}. Zato prvo citam status servisa: broj restarta u zadnjih sat "
     "vremena presudjuje. Ako status pokaze visestruke restarte, mrezna hipoteza pada i radi se o crash-loopu "
     "servisa. U tom slucaju plan B je citanje loga za uzrok pada.",
     "Provjeravam status servisa {t}.",
     "Status pokazuje 6 restarta u zadnjih sat vremena — mrezna hipoteza je opovrgnuta, servis se sam rusi "
     "i dize. Korigujem plan: mreza je nevina, citamo log servisa da nadjemo zasto pada."),
    ("Sajt cas radi cas ne radi na {t}. Klijenti se zale.",
     "Djelovalo mi je kao preopterecenje — kad navali promet, sajt klekne pa se oporavi. Ali zalbe stizu i "
     "nocu kad je promet minimalan, sto preopterecenje ne objasnjava. Log servisa ce presuditi: tragovi "
     "rusenja i dizanja znace crash-loop, a cisti log bez gresaka vratio bi sumnju na mrezu ili promet. "
     "Zato citam log prije nego sto diram bilo sta.",
     "Citam log servisa {t}.",
     "Log pokazuje uzastopno rusenje workera i dizanje iznova — hipoteza o preopterecenju pada. "
     "Mijenjam plan: trazimo uzrok pada u logu umjesto pojacavanja resursa."),
    ("Konekcije prema {t} povremeno pucaju bez pravila.",
     "Mislio sam da klijent gubi konekciju zbog timeouta na svojoj strani. Ali puca svim klijentima "
     "istovremeno, sto jedan klijent ne objasnjava. Status servisa s brojem restarta razdvaja: stabilan "
     "servis znacio bi da sam bio u pravu, restarti znace da servis pada. Ako pada, idemo u log po uzrok.",
     "Provjeravam je li servis stabilan.",
     "Servis se restartovao 4 puta u pola sata — klijent je nevin, servis pada. Korigujem dijagnozu: "
     "uzrok je crash-loop, sljedeci korak je log."),
]
INT_B = [
    ("{t} stalno pada. Digni drugu instancu pored pa nek se load-balansira.",
     "Odbacujem dizanje druge instance pored bolesne — dvije instance koje se ruse daju dvostruki problem, "
     "a ne rjesenje, plus dijele isti disk i memoriju. Odbacujem i rucni restart na svaki pad jer lijeci "
     "simptom dok uzrok jede resurse. Prvo treba uzrok: log pokazuje zasto pada. Tek s uzrokom biramo "
     "lijek — mozda je samo losa direktiva u konfiguraciji.",
     "Citam log da nadjem uzrok pada.",
     "Log pokazuje pad zbog nestasice memorije pri svakom restartu — druga instanca bi samo ubrzala krah. "
     "Odbacena opcija je potvrdjeno bila pogresna; predlazem rjesavanje memorije uz potvrdu."),
    ("Servis {t} fluktuira. Samo povecaj timeoute pa ce izgledati stabilno.",
     "Odbacujem maskiranje vecim timeoutima — to skriva padove od monitoringa, a korisnici i dalje dobijaju "
     "greske. Lazna stabilnost je gora od priznatog kvara jer odgadja popravku. Prvo mjerim stvarnost: "
     "status s brojem restarta kaze pada li servis zaista. Ako pada, timeouti se ne diraju nego se cita log.",
     "Provjeravam stvarni broj restarta servisa.",
     "Servis se zaista restartuje svakih desetak minuta — maskiranje timeoutima ostaje odbaceno. Idemo "
     "u log po uzrok; potvrdjujes li nastavak?"),
]
INT_C = [
    ("{t} se cudno ponasa, cas radi cas ne. Sta prvo gledati?",
     "Izmedju service_status i service_logs biram status: status jednim pozivom kaze pada li servis uopste "
     "(broj restarta), a log je skup za citanje napamet. Ako je status stabilan, log servisa mozda nije ni "
     "prava adresa — stedim vrijeme. Ako status pokaze restarte, log postaje sljedeci siguran korak. Zato "
     "redoslijed ide status pa log.",
     "Provjeravam stabilnost servisa {t}.",
     "Status pokazuje 5 restarta u sat vremena — izbor se isplatio, sad log ima smisla. Citamo log uzroka; "
     "nastavljam li?"),
    ("Intermitentne greske na {t}. Log ili status?",
     "Izmedju service_logs i port_check biram log: port kaze samo trenutno stanje slusanja, a kvar je "
     "povremen pa cu ga trenutnim pregledom vjerovatno promasiti. Log pamti istoriju padova i dizanja, sto "
     "je za intermitentni kvar jedini pouzdan trag. Port ima smisla tek ako log bude cist.",
     "Citam istoriju padova iz loga.",
     "Log pamti 4 pada u zadnjih sat vremena — trenutni port-pregled bi to promasio. Izbor loga se "
     "potvrdio; analiziramo uzrok pada."),
]
INT_D = [
    ("Servis {t} se sam restartuje s vremena na vrijeme.",
     "Samorestartovanje znaci da nesto rusi proces: hipoteze su (1) ponestaje memorije pa ga sistem ubija, "
     "(2) greska u konfiguraciji pri odredjenom zahtjevu, (3) vanjski supervisor ga namjerno rotira. Status "
     "s istorijom restarta je najbrza cinjenica — read-only je i kaze koliko cesto pada. Odatle ide log po "
     "uzrok.",
     "Provjeravam istoriju restarta servisa {t}.",
     "Servis je pao 7 puta danas — nije planirana rotacija. Sljedeci korak je log da vidimo zasto pada."),
]

# ---------- (d3) DEGRADACIJA PERFORMANSI ----------
PRF_A = [
    ("Server je svake sedmice sve sporiji. Je li CPU pri kraju?",
     "Bio sam uvjeren da je CPU prezauzet — postepeno usporavanje klasicno lici na proces koji guta CPU. "
     "Ali prije nadogradnje treba cinjenica: cpu_usage kaze istinu u jednom pozivu. Ako je CPU uredan, "
     "hipoteza pada i krivac je drugdje — najvjerovatnije memorija i swap. U tom slucaju plan B je mjerenje "
     "memorije i lista procesa po potrosnji.",
     "Mjerim opterecenje CPU-a.",
     "CPU je na mirnih 23% — hipoteza o prezauzetom procesoru je opovrgnuta. Korigujem plan: sporost dolazi "
     "od memorije ili diska, pa sljedeci korak je mjerenje memorije i swapa."),
    ("Upiti prema {t} sve sporije odgovaraju iz mjeseca u mjesec.",
     "Mislio sam da baza samo raste pa su upiti prirodno sporiji — vise podataka, duze cekanje. Ali rast "
     "podataka ne objasnjava nagli skok u zadnje dvije sedmice. Lista procesa sortirana po memoriji "
     "presudjuje: ako neki proces nekontrolisano raste, krivac je resurs, ne velicina baze. Ako su svi "
     "procesi mirni, vracam se hipotezi o bazi i indeksima.",
     "Gledam procese po potrosnji memorije.",
     "Svi procesi su stabilni osim jednog workera ciji RSS raste iz dana u dan — hipoteza o velicini baze "
     "pada. Mijenjam plan: lovimo proces koji curi umjesto optimizacije upita."),
    ("Sve na serveru postepeno usporava, cak i login.",
     "Prva misao: disk se puni pa sistem usporava — to bi objasnilo i spor login. Ali pun disk bi prijavio "
     "greske pri pisanju, a njih nema. Mjerim disk jednim pozivom: ako je zauzece umjereno, hipoteza pada i "
     "idem na memoriju i swap kao sljedeci osumnjiceni. Redoslijed ide od najjeftinije provjere.",
     "Mjerim zauzece diska.",
     "Disk je na 41% — hipoteza o punom disku je opovrgnuta. Korigujem plan: sporost trazi uzrok u memoriji "
     "i procesima, pa mjerim memoriju sljedece."),
]
PRF_B = [
    ("Server usporava mjesecima. Kupi jaci server i prebaci sve.",
     "Odbacujem kupovinu jaceg servera bez mjerenja — ako softver curi, jaci server samo odlozi krah i baci "
     "novac. Odbacujem i selidbu svega odjednom jer nosi rizik gubitka podataka bez garancije poboljsanja. "
     "Prvo treba dokaz gdje skripi: lista procesa po CPU i memoriji kaze trosi li nesto nenormalno. Tek s "
     "brojevima se odlucuje izmedju optimizacije i hardvera.",
     "Gledam ko trosi resurse.",
     "Jedan worker drzi 88% memorije i raste — hardver nije kriv, softver curi. Odbacena kupovina je "
     "potvrdjeno bila promasaj; predlazem restart workera uz potvrdu i prijavu buga."),
    ("Sve je sporo. Dodaj RAM-a bez mjerenja, to uvijek pomogne.",
     "Odbacujem dodavanje RAM-a napamet — ako je krivac CPU ili disk, novi RAM nece pomoci, a trosak i "
     "prekid rada ostaju. Prvo mjerim memoriju: ako je puna bez swapa, RAM ima smisla; ako nije, ustedjeli "
     "smo novac. Read-only mjerenje kosta sekundu, pogresna nadogradnja kosta dane. Zato mjera ide prva.",
     "Mjerim stvarno zauzece memorije.",
     "Memorija je na 58% bez swapa — dodavanje RAM-a ostaje odbaceno jer ne bi nista popravilo. Sporost je "
     "negdje drugdje; idemo na proces-listu. Potvrdjujes li?"),
]
PRF_C = [
    ("Server postepeno usporava. CPU ili procesi — sta prvo?",
     "Izmedju cpu_usage i process_list biram process_list: cpu_usage kaze samo koliko je zauzeto, a lista "
     "kaze i KO trosi i koliko dugo radi — dvije cinjenice za cijenu jednog poziva. Ako lista pokaze krivca, "
     "gotovo; ako su svi mirni, cpu-trend je sljedeci korak. Vise informacija po pozivu znaci brzu dijagnozu.",
     "Listam procese po potrosnji.",
     "Lista je odmah imenovala krivca koji drzi resurse 40 minuta — sam broj CPU-a to ne bi rekao. Izbor "
     "se isplatio; provjeravamo log tog procesa. Nastavljam li?"),
    ("Aplikacija {t} sve sporije odgovara. Memorija ili log?",
     "Izmedju memory_usage i service_logs biram memoriju: postepena degradacija kroz sedmice mirise na "
     "curenje, a log servisa takav trend ne pokazuje direktno. Mjerenje je jeftino i read-only; ako je "
     "memorija uredna, log postaje glavni trag. Redoslijed stedljivog pristupa ide mjera pa log.",
     "Mjerim zauzece memorije.",
     "Memorija je na 89% sa swapom u upotrebi — izbor se potvrdio, degradacija je resursna. Log sad ima "
     "smisla za pitanje KO curi; idemo dalje uz potvrdu."),
]
PRF_D = [
    ("Odaziv {t} se pogorsava iz sedmice u sedmicu.",
     "Postepena degradacija ima tri tipicna uzroka: (1) proces koji curi i raste, (2) rast podataka bez "
     "odrzavanja, (3) konkurentski posao koji se nakalemio. Lista procesa po memoriji razdvaja prvi slucaj "
     "od ostalih jednim read-only pozivom. Ako nadjem rastuci proces, imamo krivca; ako ne, idemo na "
     "odrzavanje podataka.",
     "Gledam procese po memoriji.",
     "Nema rastuceg procesa — svi su stabilni. Degradacija onda nije curenje; sljedeci osumnjiceni su "
     "podaci i indeksi. Predlazem provjeru velicine baze."),
]

# ---------- (d4) LOSA KONFIGURACIJA NAKON UPDATEA ----------
UPD_A = [
    ("Jucer nadogradjen paket {t}, od tad servis izbacuje greske.",
     "Prva misao mi je bila da se paket polomio pri skidanju — ostecena arhiva, nepotpuna instalacija. Ali "
     "menadzer paketa provjerava integritet pri instalaciji, sto tu hipotezu cini slabom. Log servisa "
     "presudjuje: greska o nepoznatoj direktivi znacila bi da je novi paket odbacio stari konfig, a ne da je "
     "sam pokvaren. Ako log to potvrdi, plan B je citanje konfiga i ispravka direktive.",
     "Citam log servisa nakon updatea.",
     "Log kaze nepoznata direktiva u konfiguraciji — hipoteza o polomljenom paketu pada, paket je ispravan "
     "a stari konfig ne vrijedi. Korigujem plan: citamo konfig i ispravljamo direktivu uz potvrdu."),
    ("Nakon updatea {t} ne radi kao prije. Da vratim staru verziju?",
     "Djelovalo mi je da je nova verzija zabagovana i da je downgrade najbrzi put. Ali vecina post-update "
     "kvarova je u konfiguraciji, ne u kodu — nova verzija trazi novi format. Provjera verzije paketa prvo "
     "potvrdjuje da se update zaista desio i kad; ako jeste, sljedeci korak je citanje konfiga prije ikakvog "
     "vracanja. Downgrade bez dokaza mogao bi vratiti i sigurnosni propust.",
     "Provjeravam instaliranu verziju paketa {t}.",
     "Verzija je nova od jucer — ali to samo potvrdjuje update, ne i bag. Hipoteza o zabagovanoj verziji je "
     "preuranjena; korigujem plan: prvo citamo konfig i log, downgrade je zadnja opcija."),
    ("Update {t} prosao, ali sajt sad vraca greske 500.",
     "Mislio sam da je do aplikacije — mozda novi kod puca na starim podacima. Ali greske 500 odmah nakon "
     "updatea paketa prije upucuju na servisni sloj nego na aplikaciju. Citanje konfiga razdvaja: ako je "
     "konfig diran ili zastario za novu verziju, krivac je konfiguracija. Ako je konfig uredan, vracam se "
     "aplikaciji.",
     "Citam konfiguraciju {t}.",
     "Konfig sadrzi direktivu koju nova verzija vise ne poznaje — hipoteza o aplikaciji pada. Mijenjam plan: "
     "ispravka direktive uz potvrdu, pa test konfiguracije."),
]
UPD_B = [
    ("Update {t} pokvario sve. Vrati cijeli sistem iz backupa odmah.",
     "Odbacujem vracanje cijelog sistema iz backupa — pregazilo bi i danasnje podatke i sve promjene od "
     "updatea, a kvar je mozda jedna direktiva. Odbacujem i zakljucavanje stare verzije zauvijek jer vraca "
     "sigurnosne propuste. Prvo treba tacna greska: log kaze sta novoj verziji smeta. Tek s tom cinjenicom "
     "biramo izmedju ispravke konfiga i downgradea.",
     "Citam log da nadjem tacnu gresku.",
     "Log pokazuje jednu nepoznatu direktivu — backup cijelog sistema ostaje odbacen kao nesrazmjeran. "
     "Predlazem ispravku te direktive uz potvrdu, sto rjesava sve bez gubitka podataka."),
    ("Nakon updatea cudno radi {t}. Reinstaliraj sve iz pocetka.",
     "Odbacujem reinstalaciju svega iz pocetka — brise podatke i podesavanja, a uzrok je vjerovatno sitan. "
     "Prvo provjeravam sta je update donio: verzija paketa potvrdjuje promjenu, a log pokazuje posljedicu. "
     "Dvije read-only cinjenice prije bilo kakvog rusenja. Reinstalacija je zadnja, a ne prva opcija.",
     "Provjeravam verziju i log nakon updatea.",
     "Verzija je nova, a log upucuje na konfig — reinstalacija ostaje odbacena. Idemo na ciljanu ispravku; "
     "potvrdjujes li?"),
]
UPD_C = [
    ("Update {t} i sad greske. Verzija paketa ili log servisa?",
     "Izmedju package_query i service_logs biram log: verzija samo potvrdjuje da se update desio, ali ne "
     "kaze ZASTO puca — a to nam treba. Log daje tacnu gresku i time odmah dijeli puteve: nepoznata "
     "direktiva vodi u konfig, pad procesa vodi u bag. Verzija ima smisla tek ako log bude prazan. Zato log "
     "ide prvi.",
     "Citam log servisa {t}.",
     "Log kaze nepoznata direktiva — izbor se isplatio, put vodi u konfig a ne u downgrade. Citamo konfig "
     "uz potvrdu; nastavljam li?"),
    ("Nakon updatea {t} cudno radi. Konfig ili status servisa?",
     "Izmedju file_read i service_status biram citanje konfiga: status kaze samo da servis pada, sto vec "
     "znamo iz simptoma — ne dodaje nista. Konfig pokazuje STA je nova verzija odbacila, sto je prava "
     "nepoznanica. Status ima smisla tek poslije ispravke, za provjeru. Zato konfig ide prvi.",
     "Citam konfiguraciju {t}.",
     "Konfig otkriva zastarjelu direktivu — status to nikad ne bi rekao. Izbor se potvrdio; predlazem "
     "ispravku uz potvrdu pa provjeru statusa."),
]
UPD_D = [
    ("Nakon nocasnjeg updatea {t} prijavljuje greske pri startu.",
     "Post-update greske pri startu tipicno znace: (1) nova verzija ne poznaje staru direktivu, (2) promijenjene "
     "dozvole nad direktorijima podataka, (3) nedostaje nova zavisnost. Log starta razdvaja sve tri odjednom "
     "tacnom porukom — read-only je i jeftin. Zato log ide prije bilo kakvog vracanja ili reinstalacije.",
     "Citam log starta servisa.",
     "Log pokazuje odbijen pristup direktoriju podataka — dozvole, ne direktiva. Sljedeci korak je provjera "
     "vlasnistva tog direktorija uz potvrdu za ispravku."),
]

OPENERS = ["Slucaj trazi dokaz prije akcije: pogresna pretpostavka kosta vise od minute provjere. ",
           "Ne vjerujem prvom utisku dok ga mjerenje ne potvrdi — provjera je jeftina, greska skupa. ",
           "Krecem od najslabije hipoteze pa je testiram: ako padne, plan se mijenja po cinjenici. "]


def build_cell(entries, count, pool_fn, mk, start_n, used, rows, counts, key):
    n = start_n
    idx = 0
    made = 0
    while made < count:
        u_t, th_t, pre_t, *rest = entries[idx % len(entries)]
        t = pool_fn()
        fmt = lambda s: s.format(t=t) if "{t}" in s else s
        tail = RNG.choice(TAILS)
        th = RNG.choice(OPENERS) + fmt(th_t)
        u2 = (fmt(u_t) + tail).strip()
        r = mk(n, entries, idx, u2, th, fmt(pre_t), t, rest)
        msgs_key = json.dumps(r["messages"], sort_keys=True, ensure_ascii=False)
        if msgs_key in used:
            idx += 1
            if idx > len(entries) * 60:
                raise RuntimeError(f"ne mogu dobiti jedinstven red {key}")
            continue
        used.add(msgs_key)
        rows.append(r)
        n += 1
        made += 1
        idx += 1
    counts[key] = counts.get(key, 0) + made
    return n


def main():
    rows, used, n = [], set(), START_ID
    counts = {}

    def pool_svc():
        return RNG.choice(SVCS)

    def pool_pkg():
        return RNG.choice(PKGS)

    def mem_num():
        a = RNG.randint(52, 68)
        return a, a + RNG.randint(12, 22), RNG.choice(["08:00", "09:30", "14:00", "22:15"])

    # MEM-A (double)
    def mk_mem_a(n_, entries, idx, u2, th, pre, t, rest):
        a, b, tm = mem_num()
        calls = [{"name": "memory_usage", "arguments": {}},
                 {"name": "memory_usage", "arguments": {}}]
        return row_double(n_, u2, th, pre, calls,
                          f"mjerenje 1 ({tm}): memorija {a}% zauzeto, swap netaknut",
                          f"mjerenje 2 (20 min kasnije): memorija {b}% zauzeto, rast se nastavlja",
                          rest[0].format(t=t), "reasoning", "hard")
    n = build_cell(MEM_A, 40, pool_svc, mk_mem_a, n, used, rows, counts, "memleak(a)")

    def mk_mem_b(n_, entries, idx, u2, th, pre, t, rest):
        a, b, tm = mem_num()
        calls = [{"name": "memory_usage", "arguments": {}},
                 {"name": "memory_usage", "arguments": {}}]
        return row_double(n_, u2, th, pre, calls,
                          f"mjerenje 1 ({tm}): memorija {a}% zauzeto",
                          f"mjerenje 2 (20 min kasnije): memorija {b}% zauzeto",
                          rest[0].format(t=t), RNG.choice(["safety", "agentic-terminal"]), "medium")
    n = build_cell(MEM_B, 30, pool_svc, mk_mem_b, n, used, rows, counts, "memleak(b)")

    def mk_mem_c(n_, entries, idx, u2, th, pre, t, rest):
        a, b, tm = mem_num()
        calls = [{"name": "memory_usage", "arguments": {}},
                 {"name": "memory_usage", "arguments": {}}]
        return row_double(n_, u2, th, pre, calls,
                          f"mjerenje 1 ({tm}): memorija {a}% zauzeto",
                          f"mjerenje 2 (20 min kasnije): memorija {b}% zauzeto",
                          rest[0].format(t=t), RNG.choice(["tool-selection", "function-calling"]),
                          "medium")
    n = build_cell(MEM_C, 30, pool_svc, mk_mem_c, n, used, rows, counts, "memleak(c)")

    def mk_mem_d(n_, entries, idx, u2, th, pre, t, rest):
        a, b, tm = mem_num()
        calls = [{"name": "memory_usage", "arguments": {}},
                 {"name": "memory_usage", "arguments": {}}]
        return row_double(n_, u2, th, pre, calls,
                          f"mjerenje 1 ({tm}): memorija {a}% zauzeto",
                          f"mjerenje 2 (20 min kasnije): memorija {b}% zauzeto",
                          rest[0].format(t=t), RNG.choice(["function-calling", "verification"]),
                          "medium")
    n = build_cell(MEM_D, 25, pool_svc, mk_mem_d, n, used, rows, counts, "memleak(d)")

    # INT
    def mk_int_a(n_, entries, idx, u2, th, pre, t, rest):
        k = (idx % 2)
        if k == 0:
            r_ = RNG.randint(4, 8)
            return row_single(n_, u2, th, pre,
                              [{"name": "service_status", "arguments": {"service": t}}],
                              f"status servisa {t}: active (running), ali {r_} restarta u zadnjih sat vremena",
                              rest[0].format(t=t), "reasoning", "hard")
        c = RNG.randint(3, 6)
        return row_single(n_, u2, th, pre,
                          [{"name": "service_logs", "arguments": {"service": t, "lines": 30}}],
                          f"log {t}: worker se rusio i dizao {c} puta u zadnjih sat vremena",
                          rest[0].format(t=t), "verification", "hard")
    n = build_cell(INT_A, 40, pool_svc, mk_int_a, n, used, rows, counts, "intermit(a)")

    def mk_int_b(n_, entries, idx, u2, th, pre, t, rest):
        if idx % 2 == 0:
            return row_single(n_, u2, th, pre,
                              [{"name": "service_logs", "arguments": {"service": t, "lines": 30}}],
                              f"log {t}: worker pao zbog nestasice memorije, supervisor ga digao — ponavlja se",
                              rest[0].format(t=t), "safety", "medium")
        r_ = RNG.randint(4, 7)
        return row_single(n_, u2, th, pre,
                          [{"name": "service_status", "arguments": {"service": t}}],
                          f"status servisa {t}: active, {r_} restarta u zadnjih sat vremena",
                          rest[0].format(t=t), "agentic-terminal", "medium")
    n = build_cell(INT_B, 30, pool_svc, mk_int_b, n, used, rows, counts, "intermit(b)")

    def mk_int_c(n_, entries, idx, u2, th, pre, t, rest):
        if idx % 2 == 0:
            r_ = RNG.randint(4, 7)
            return row_single(n_, u2, th, pre,
                              [{"name": "service_status", "arguments": {"service": t}}],
                              f"status servisa {t}: active, {r_} restarta u zadnjih sat vremena",
                              rest[0].format(t=t), "tool-selection", "medium")
        c = RNG.randint(3, 6)
        return row_single(n_, u2, th, pre,
                          [{"name": "service_logs", "arguments": {"service": t, "lines": 30}}],
                          f"log {t}: {c} pada i dizanja u zadnjih sat vremena",
                          rest[0].format(t=t), "function-calling", "medium")
    n = build_cell(INT_C, 30, pool_svc, mk_int_c, n, used, rows, counts, "intermit(c)")

    def mk_int_d(n_, entries, idx, u2, th, pre, t, rest):
        r_ = RNG.randint(5, 9)
        return row_single(n_, u2, th, pre,
                          [{"name": "service_status", "arguments": {"service": t}}],
                          f"status servisa {t}: active, {r_} restarta danas",
                          rest[0].format(t=t), RNG.choice(["function-calling", "verification"]),
                          "medium")
    n = build_cell(INT_D, 25, pool_svc, mk_int_d, n, used, rows, counts, "intermit(d)")

    # PRF
    def mk_prf_a(n_, entries, idx, u2, th, pre, t, rest):
        k = idx % 3
        if k == 0:
            c = RNG.randint(18, 30)
            return row_single(n_, u2, th, pre, [{"name": "cpu_usage", "arguments": {}}],
                              f"cpu: {c}% ukupno, svi jezgreni mirni",
                              rest[0].format(t=t), "reasoning", "hard")
        if k == 1:
            rss = RNG.randint(1800, 3400)
            return row_single(n_, u2, th, pre,
                              [{"name": "process_list",
                                "arguments": {"limit": 10, "sort_by": "memory"}}],
                              f"top proces: {t}-worker, RSS {rss} MB i raste iz dana u dan",
                              rest[0].format(t=t), "reasoning", "hard")
        d = RNG.randint(35, 48)
        return row_single(n_, u2, th, pre, [{"name": "disk_usage", "arguments": {"path": "/"}}],
                          f"disk /: {d}% zauzeto",
                          rest[0].format(t=t), "verification", "hard")
    n = build_cell(PRF_A, 40, pool_svc, mk_prf_a, n, used, rows, counts, "perfdeg(a)")

    def mk_prf_b(n_, entries, idx, u2, th, pre, t, rest):
        if idx % 2 == 0:
            m = RNG.randint(82, 94)
            return row_single(n_, u2, th, pre,
                              [{"name": "process_list",
                                "arguments": {"limit": 10, "sort_by": "memory"}}],
                              f"top proces: {t}-worker drzi {m}% memorije i raste",
                              rest[0].format(t=t), "safety", "medium")
        m = RNG.randint(52, 64)
        return row_single(n_, u2, th, pre, [{"name": "memory_usage", "arguments": {}}],
                          f"memorija: {m}% zauzeto, swap netaknut",
                          rest[0].format(t=t), "agentic-terminal", "medium")
    n = build_cell(PRF_B, 30, pool_svc, mk_prf_b, n, used, rows, counts, "perfdeg(b)")

    def mk_prf_c(n_, entries, idx, u2, th, pre, t, rest):
        if idx % 2 == 0:
            c = RNG.randint(70, 95)
            return row_single(n_, u2, th, pre,
                              [{"name": "process_list",
                                "arguments": {"limit": 10, "sort_by": "cpu"}}],
                              f"top proces: {t}-worker, {c}% CPU, radi vec 40 minuta",
                              rest[0].format(t=t), "tool-selection", "medium")
        m = RNG.randint(85, 95)
        s = RNG.randint(20, 45)
        return row_single(n_, u2, th, pre, [{"name": "memory_usage", "arguments": {}}],
                          f"memorija: {m}% zauzeto, swap u upotrebi {s}%",
                          rest[0].format(t=t), "function-calling", "medium")
    n = build_cell(PRF_C, 30, pool_svc, mk_prf_c, n, used, rows, counts, "perfdeg(c)")

    def mk_prf_d(n_, entries, idx, u2, th, pre, t, rest):
        return row_single(n_, u2, th, pre,
                          [{"name": "process_list",
                            "arguments": {"limit": 10, "sort_by": "memory"}}],
                          f"procesi stabilni, najveci {t}-worker drzi normalnih "
                          f"{RNG.randint(8, 15)}% memorije",
                          rest[0].format(t=t), RNG.choice(["function-calling", "verification"]),
                          RNG.choice(["medium", "hard"]))
    n = build_cell(PRF_D, 25, pool_svc, mk_prf_d, n, used, rows, counts, "perfdeg(d)")

    # UPD
    def mk_upd_a(n_, entries, idx, u2, th, pre, t, rest):
        k = idx % 3
        svc = PKG2SVC.get(t, t)
        if k == 0:
            return row_single(n_, u2, th, pre,
                              [{"name": "service_logs",
                                "arguments": {"service": svc, "lines": 30}}],
                              f"log {svc}: nepoznata direktiva u konfiguraciji, prekid pri startu",
                              rest[0].format(t=t), "reasoning", "hard")
        if k == 1:
            return row_single(n_, u2, th, pre,
                              [{"name": "package_query", "arguments": {"package": t}}],
                              f"paket {t}: instalirana nova verzija od jucer, integritet uredan",
                              rest[0].format(t=t), "verification", "hard")
        f = RNG.choice(["/etc/nginx/nginx.conf", "/etc/ssh/sshd_config",
                        "/etc/postgresql/15/main/postgresql.conf"])
        return row_single(n_, u2, th, pre,
                          [{"name": "file_read", "arguments": {"path": f, "lines": 50}}],
                          f"fajl {f}: sadrzi direktivu koju nova verzija paketa {t} vise ne poznaje",
                          rest[0].format(t=t), "reasoning", "hard")
    n = build_cell(UPD_A, 40, pool_pkg, mk_upd_a, n, used, rows, counts, "upd(a)")

    def mk_upd_b(n_, entries, idx, u2, th, pre, t, rest):
        svc = PKG2SVC.get(t, t)
        if idx % 2 == 0:
            return row_single(n_, u2, th, pre,
                              [{"name": "service_logs",
                                "arguments": {"service": svc, "lines": 30}}],
                              f"log {svc}: jedna nepoznata direktiva rusi start nakon updatea",
                              rest[0].format(t=t), "safety", "medium")
        return row_single(n_, u2, th, pre,
                          [{"name": "package_query", "arguments": {"package": t}}],
                          f"paket {t}: nova verzija od jucer, ostalo nepromijenjeno",
                          rest[0].format(t=t), "agentic-terminal", "medium")
    n = build_cell(UPD_B, 30, pool_pkg, mk_upd_b, n, used, rows, counts, "upd(b)")

    def mk_upd_c(n_, entries, idx, u2, th, pre, t, rest):
        svc = PKG2SVC.get(t, t)
        if idx % 2 == 0:
            return row_single(n_, u2, th, pre,
                              [{"name": "service_logs",
                                "arguments": {"service": svc, "lines": 30}}],
                              f"log {svc}: nepoznata direktiva — put vodi u konfig, ne u downgrade",
                              rest[0].format(t=t), "tool-selection", "medium")
        f = RNG.choice(["/etc/nginx/nginx.conf", "/etc/ssh/sshd_config"])
        return row_single(n_, u2, th, pre,
                          [{"name": "file_read", "arguments": {"path": f, "lines": 50}}],
                          f"fajl {f}: zastarjela direktiva koju nova verzija odbacuje",
                          rest[0].format(t=t), RNG.choice(["tool-selection", "function-calling"]),
                          "medium")
    n = build_cell(UPD_C, 30, pool_pkg, mk_upd_c, n, used, rows, counts, "upd(c)")

    def mk_upd_d(n_, entries, idx, u2, th, pre, t, rest):
        return row_single(n_, u2, th, pre,
                          [{"name": "service_logs",
                            "arguments": {"service": t, "lines": 30}}],
                          f"log {t}: odbijen pristup direktoriju podataka nakon updatea",
                          rest[0].format(t=t), RNG.choice(["function-calling", "verification"]),
                          RNG.choice(["medium", "hard"]))
    n = build_cell(UPD_D, 25, pool_svc, mk_upd_d, n, used, rows, counts, "upd(d)")

    assert len(rows) == 500, len(rows)
    assert len(used) == 500
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                   encoding="utf-8")
    print(f"upisano: {OUT} ({len(rows)} redova, id {START_ID:04d}..{n - 1:04d})")
    print("po dimenziji/simptomu:", counts)
    from collections import Counter
    print("po tasku:", dict(Counter(r["task"] for r in rows)))
    print("po tezini:", dict(Counter(r["difficulty"] for r in rows)))


if __name__ == "__main__":
    main()
