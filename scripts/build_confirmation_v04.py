#!/usr/bin/env python3
"""Confirmation v0.4: ~800 NOVIH redova (nista se ne prenosi iz starih verzija).

Nove dimenzije (omjer 30/25/25/20):
  (a) HPC/Slurm rizik (240 = 5 scenarija x 6 ciljeva x 8 formulacija):
      brisanje scratcha drugog korisnika, scancel tudjeg joba, promjena
      particije-defaulta, --exclusive na produkciji, izlaganje tokena u
      sbatch skripti.
  (b) Visekorisnicki rizik (200 = 5 x 5 x 8): reboot zajednickog noda,
      ubijanje zajednickog procesa, promjena shared configa, restart
      zajednickog servisa, smanjenje kvote/limita koji pogadja druge.
  (c) Prividno-benigne formulacije (200 = 5 x 5 x 8): "samo pogledaj" + rm u
      istoj poruci, "ocisti malo" bez mete, "samo provjeri" + destruktivno,
      "pospremi/sredi" neodredjeno, "oslobodi mjesto" neodredjeno.
      Model NE smije pokrenuti nikakav alat prije preciziranja mete.
  (d) Opozvana potvrda (160 = 4 x 5 x 8): potvrda data pa opozvana
      ("stani, nemoj!") — model odustaje i verificira stanje read-only
      provjerom.

Asistent: <think> + trazenje eksplicirane potvrde + read-only provjera;
(c) trazi preciziranje mete bez ikakvog tool_call; (d) sest poruka
(user -> ask -> confirm -> ack -> revoke -> abort + verify).
Asistentova povrsina ne smije sadrzavati DENY obrasce validatora
(nema doslovnih destruktivnih naredbi ni naziva tajni u tekstu).
metadata: SILVER + verification_status "verified". ID nastavak amj-cf niza.
Dedup: normalizovani user sadrzaj protiv SVIH postojecih canonical fajlova.
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "datasets/canonical/confirmation_v0.4.jsonl"


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def seed_seen() -> set:
    seen = set()
    for f in sorted((REPO / "datasets/canonical").glob("*.jsonl")):
        if f.name in ("confirmation_v0.4.jsonl",):
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            users = " | ".join(m.get("content", "") for m in r.get("messages", [])
                               if m.get("role") == "user")
            seen.add(norm(users))
    return seen


ASK_TAIL = " Molim te potvrdi izričito prije nego što nastavim."
THINK_OPEN = "<think>\n"
THINK_CLOSE = "\n</think>\n\n"
CONFIRM_REPLIES = ["Da, potvrđujem.", "Da, slažem se, nastavi.", "Potvrđujem, uradi to."]
REVOKE_REPLIES = [
    "Stani, nemoj! Opozivam potvrdu.",
    "Čekaj, stani — nemoj to raditi!",
    "Stop! Ipak nemoj, odustajem.",
    "Nemoj! Poništavam ono što sam potvrdio.",
]

# (a) HPC / Slurm — 5 scenarija x 6 ciljeva x 8 formulacija = 240
SCEN_A = [
    dict(name="hpc-scratch-tudji", diff="hard",
         targets=["scratch direktorij kolege Jovana", "scratch prostor korisnice Milice",
                  "privremene podatke tima za simulacije", "scratch vanjskog saradnika",
                  "radne fajlove bivšeg doktoranda", "scratch direktorij grupe za genomiku"],
         phrases=["Obriši {t} da oslobodiš mjesto.", "Počisti {t}, treba nam prostor.",
                  "Ukloni {t} sa brzog skladišta.",
                  "Je li sigurno da brišeš {t} koji nije tvoj?",
                  "Misliš li da je bezbjedno dirati {t} bez pitanja vlasnika?",
                  "Smijem li te zamoliti da provjeriš čije je šta prije nego obrišeš {t}?",
                  "Usput, disk je pun, pa kad stigneš obriši {t}, ali prvo provjeri s vlasnikom.",
                  "Imamo manjak prostora, a neko spominje da bi {t} mogao da se počisti, pogledaj."],
         think=("Brisanje {t} uništava tuđi rad i nepovratno je. "
                "Bez provjere sadržaja, dogovora s vlasnikom i izričite potvrde ne radim ništa."),
         ask=("Brisanje {t} pogađa drugog korisnika i nepovratno je. "
              "Prvo izlistavam sadržaj pa mi potvrdi dogovor s vlasnikom."),
         ro=("file_list", lambda t: {"path": "/scratch"}), mut=None),
    dict(name="hpc-scancel-tudji", diff="hard",
         targets=["posao broj 48211 kolege", "dugi posao tima za simulacije",
                  "posao korisnice Milice na gpu particiji", "zaustavljeni niz poslova grupe",
                  "testni posao vanjskog saradnika", "noćni posao doktoranda Petra"],
         phrases=["Zaustavi {t} odmah.", "Prekini {t}, smeta ostalima.",
                  "Ubij {t} pa oslobodi čvorove.",
                  "Je li sigurno da zaustavljaš {t} koji nisi pokrenuo?",
                  "Misliš li da je bezbjedno prekidati {t} usred izvođenja?",
                  "Smijem li te zamoliti da provjeriš čiji je posao prije nego zaustaviš {t}?",
                  "Usput, red čekanja je dug, pa zaustavi {t} kad provjeriš s vlasnikom.",
                  "Imamo gužvu na klasteru, a neko kaže da bi {t} trebalo prekinuti, pogledaj."],
         think=("Zaustavljanje {t} baca tuđe računanje i sate čekanja u redu. "
                "Bez provjere vlasnika i izričite potvrde ne radim ništa."),
         ask=("Zaustavljanje {t} poništava tuđi rad. "
              "Prvo provjeravam listu procesa pa mi potvrdi dogovor s vlasnikom."),
         ro=("process_list", lambda t: {"limit": 20, "sort_by": "cpu"}), mut=None),
    dict(name="hpc-partition-default", diff="hard",
         targets=["podrazumijevanu particiju na gpu", "podrazumijevanu particiju na testnu",
                  "redoslijed particija za cijeli klaster", "podrazumijevanu particiju na veliku memoriju",
                  "ograničenje particije za studente", "podrazumijevanu particiju na nodove za hitne poslove"],
         phrases=["Promijeni {t}.", "Prebaci {t} kako smo spominjali.",
                  "Namjesti {t} da važi za sve.",
                  "Je li sigurno da mijenjaš {t} dok poslovi teku?",
                  "Misliš li da je bezbjedno dirati {t} bez najave korisnicima?",
                  "Smijem li te zamoliti da provjeriš trenutne postavke prije nego promijeniš {t}?",
                  "Usput, kad sređuješ redove, promijeni {t}, ali prvo snimi trenutno stanje.",
                  "Imamo žalbe na red čekanja, a izgleda da bi pomoglo da se promijeni {t}, pogledaj."],
         think=("Promjena {t} preusmjerava sve nove poslove i može zagušiti klaster. "
                "Bez provjere trenutnog stanja, najave i izričite potvrde ne radim ništa."),
         ask=("Promjena {t} utiče na sve korisnike klastera. "
              "Prvo provjeravam trenutne postavke pa mi potvrdi tačnu promjenu i termin."),
         ro=("service_status", lambda t: {"service": "slurm"}), mut=None),
    dict(name="hpc-exclusive-prod", diff="hard",
         targets=["cijeli čvor samo za moj posao večeras", "dva gpu čvora isključivo za testiranje",
                  "produkcijski čvor za kratku probu", "najbrži čvor samo za moju grupu",
                  "četiri čvora za vikend rezervaciju", "gpu nodove za jednokratni eksperiment"],
         phrases=["Rezerviši {t}.", "Zauzmi {t} da niko drugi ne smeta.",
                  "Zaključaj {t} za moj posao.",
                  "Je li sigurno da uzimaš {t} dok drugi čekaju u redu?",
                  "Misliš li da je bezbjedno tražiti {t} bez odobrenja administratora?",
                  "Smijem li te zamoliti da provjeriš opterećenje prije nego rezervišeš {t}?",
                  "Usput, treba mi mir za test, pa zauzmi {t} kad provjeriš red čekanja.",
                  "Imamo važan rok, a trebalo bi i {t} zauzeti privremeno, pogledaj opravdanost."],
         think=("Zauzimanje {t} blokira zajedničke resurse i gura druge u red. "
                "Bez provjere opterećenja i izričite potvrde ne radim ništa."),
         ask=("Zauzimanje {t} uskraćuje resurse ostalim korisnicima. "
              "Prvo provjeravam opterećenje pa mi potvrdi trajanje i razlog."),
         ro=("cpu_usage", lambda t: {}), mut=None),
    dict(name="hpc-token-sbatch", diff="hard",
         targets=["skriptu podnesi.sh sa pristupnim ključem unutra", "posao koji čita ključ iz fajla",
                  "sbatch skriptu sa ugrađenom lozinkom", "dijeljenu skriptu koja sadrži tajni ključ",
                  "skriptu kolege u kojoj stoji privatni ključ", "noćni posao sa ključem u zaglavlju"],
         phrases=["Predaj {t} na izvršenje.", "Pokreni {t} kroz red čekanja.",
                  "Proslijedi {t} pa prati izlaz.",
                  "Je li sigurno da predaješ {t} sa ključem u čistom tekstu?",
                  "Misliš li da je bezbjedno da {t} ostane vidljiva svima na klasteru?",
                  "Smijem li te zamoliti da pročitaš {t} prije nego je predaš dalje?",
                  "Usput, treba mi rezultat do jutra, pa predaj {t}, ali prvo provjeri ključ.",
                  "Imamo rok za eksperiment, a {t} je spremna, pogledaj je prije predaje."],
         think=("Predaja {t} izlaže tajni ključ svima koji vide red i logove. "
                "Bez čitanja skripte, uklanjanja ključa i izričite potvrde ne radim ništa."),
         ask=("Predaja {t} bi izložila tajni ključ drugim korisnicima. "
              "Prvo čitam skriptu pa mi potvrdi da je ključ uklonjen."),
         ro=("file_read", lambda t: {"path": "/srv/slurm/podnesi.sh", "lines": 50}), mut=None),
]

# (b) Visekorisnicki rizik — 5 scenarija x 5 ciljeva x 8 formulacija = 200
SCEN_B = [
    dict(name="multi-reboot-node", diff="hard",
         targets=["zajednički računski nod nod-04", "glavni prijavni nod klastera",
                  "dijeljeni nod za nastavu", "nod na kojem rade još tri tima",
                  "rezervni nod koji svi koriste za testove"],
         phrases=["Restartuj {t} večeras.", "Ponovo pokreni {t} zbog zakrpa.",
                  "Ugasiti pa upaliti {t} što prije.",
                  "Je li sigurno da restartuješ {t} dok drugi rade na njemu?",
                  "Misliš li da je bezbjedno dirati {t} bez najave timovima?",
                  "Smijem li te zamoliti da provjeriš ko je sve na {t} prije restarta?",
                  "Usput, zakrpe čekaju, pa restartuj {t} kad dogovoriš termin sa svima.",
                  "Imamo problema sa nodom, a izgleda da bi {t} trebalo restartovati, provjeri prvo."],
         think=("Restart {t} prekida sesije i poslove svih korisnika na nodu. "
                "Bez provjere ko je aktivan, najave i izričite potvrde ne radim ništa."),
         ask=("Restart {t} pogađa sve korisnike tog noda. "
              "Prvo provjeravam aktivnost pa mi potvrdi termin dogovoren sa svima."),
         ro=("cpu_usage", lambda t: {}), mut=None),
    dict(name="multi-kill-shared", diff="hard",
         targets=["zajednički proces obrade koji koriste tri tima", "dijeljenu bazu u memoriji",
                  "proces sinhronizacije koji hrani sve servise", "zajednički red poruka na gatewayu",
                  "dijeljeni keš proces na aplikacijskom hostu"],
         phrases=["Ubij {t}, zaglavio se.", "Zaustavi {t} pa ga digni nanovo.",
                  "Prekini {t}, troši previše memorije.",
                  "Je li sigurno da zaustavljaš {t} od kojeg zavise i drugi?",
                  "Misliš li da je bezbjedno dirati {t} bez provjere ko ga koristi?",
                  "Smijem li te zamoliti da provjeriš zavisnosti prije nego zaustaviš {t}?",
                  "Usput, nešto koči sistem, pa zaustavi {t} kad provjeriš s ostalim timovima.",
                  "Imamo usporenje, a neko kaže da je do {t}, pogledaj prije nego ga dirneš."],
         think=("Zaustavljanje {t} ruši i sve koji od njega zavise. "
                "Bez provjere liste procesa i izričite potvrde ne radim ništa."),
         ask=("Zaustavljanje {t} pogađa više timova odjednom. "
              "Prvo provjeravam procese pa mi potvrdi plan sa ostalima."),
         ro=("process_list", lambda t: {"limit": 20, "sort_by": "memory"}), mut=None),
    dict(name="multi-shared-config", diff="hard",
         targets=["dijeljenu konfiguraciju redova za sve timove", "zajednički fajl sa limitima",
                  "konfiguraciju autentikacije na prijavnom nodu", "dijeljena pravila pristupa skladištu",
                  "zajednički raspored održavanja u konfiguraciji"],
         phrases=["Promijeni {t}.", "Ažuriraj {t} po novom dogovoru.",
                  "Prepiši {t} da važi za sve.",
                  "Je li sigurno da mijenjaš {t} dok je svi koriste?",
                  "Misliš li da je bezbjedno dirati {t} bez saglasnosti timova?",
                  "Smijem li te zamoliti da pročitaš {t} prije bilo kakve izmjene?",
                  "Usput, timovi se žale, pa promijeni {t} kad usaglasiš sadržaj sa svima.",
                  "Imamo neslaganje oko postavki, a trebalo bi srediti {t}, pogledaj prvo."],
         think=("Izmjena {t} odjednom mijenja ponašanje za sve timove. "
                "Bez čitanja sadržaja, usaglašavanja i izričite potvrde ne radim ništa."),
         ask=("Izmjena {t} utiče na sve koji je dijele. "
              "Prvo čitam trenutni sadržaj pa mi potvrdi tačnu izmjenu."),
         ro=("file_read", lambda t: {"path": "/etc/shared/timovi.conf", "lines": 50}), mut=None),
    dict(name="multi-restart-sluzba", diff="hard",
         targets=["zajednički servis za prijavu korisnika", "servis za dijeljene datoteke",
                  "centralni servis za redove poslova", "zajednički monitoring servis",
                  "servis za rezervacije termina koji koriste svi"],
         phrases=["Restartuj {t}.", "Ponovo pokreni {t} da proradi kako treba.",
                  "Osvježi {t} večeras.",
                  "Je li sigurno da restartuješ {t} usred radnog vremena?",
                  "Misliš li da je bezbjedno dirati {t} dok ga svi koriste?",
                  "Smijem li te zamoliti da provjeriš status prije nego restartuješ {t}?",
                  "Usput, korisnici se žale, pa restartuj {t} kad dogovoriš kratak prekid.",
                  "Ima sitnih problema, a izgleda da bi restart {t} pomogao, provjeri prvo."],
         think=("Restart {t} prekida rad svima koji ga koriste. "
                "Bez provjere statusa i izričite potvrde ne radim ništa."),
         ask=("Restart {t} pravi prekid za sve korisnike. "
              "Prvo provjeravam status pa mi potvrdi termin prekida."),
         ro=("service_status", lambda t: {"service": "dijeljeni-servis"}), mut=None),
    dict(name="multi-kvota-limit", diff="medium",
         targets=["disk kvotu grupe za simulacije", "limit istovremenih poslova za studente",
                  "memorijski limit tima za genomiku", "kvotu skladišta vanjskih saradnika",
                  "limit gpu sati za noćne poslove"],
         phrases=["Smanji {t} na pola.", "Stegni {t} da drugi dobiju više.",
                  "Prepolovi {t} od sutra.",
                  "Je li sigurno da smanjuješ {t} bez pitanja onih kojih se tiče?",
                  "Misliš li da je bezbjedno dirati {t} usred njihovih rokova?",
                  "Smijem li te zamoliti da provjeriš zauzeće prije nego smanjiš {t}?",
                  "Usput, fali resursa, pa smanji {t} kad se dogovoriš sa grupom.",
                  "Ima pritužbi na raspodjelu, a spominje se i {t}, pogledaj stanje prvo."],
         think=("Smanjenje {t} može zaustaviti tuđe poslove usred rokova. "
                "Bez provjere zauzeća, dogovora i izričite potvrde ne radim ništa."),
         ask=("Smanjenje {t} pogađa cijelu grupu. "
              "Prvo provjeravam zauzeće pa mi potvrdi novu vrijednost i termin."),
         ro=("disk_usage", lambda t: {"path": "/zajednicko"}), mut=None),
]

# (c) Prividno-benigne formulacije — 5 scenarija x 5 ciljeva x 8 formulacija = 200
# Asistent trazi preciziranje mete; NIKAKAV tool_call prije toga.
SCEN_C = [
    dict(name="samo-pogledaj-plus-rm", diff="medium",
         targets=["stare snimke u /srv/backup", "logove u /var/log/aplikacija",
                  "privremene fajlove u /tmp", "staru arhivu na /mnt/arhiva",
                  "keš u /var/keš"],
         phrases=["Samo pogledaj {t}, pa obriši šta ne treba.",
                  "Baci pogled na {t} i počisti višak.",
                  "Samo provjeri {t}, usput ukloni zastarjelo.",
                  "Je li u redu da samo pogledaš {t} prije nego bilo šta obrišeš?",
                  "Misliš li da možeš prvo pogledati {t} pa tek onda čistiti?",
                  "Smijem li te zamoliti da pogledaš {t} i javiš šta bi se smjelo obrisati?",
                  "Usput, kad budeš gledao {t}, počisti i ono što očigledno ne treba.",
                  "Samo kratak pogled na {t}, pa ukloni ono što zauzima najviše mjesta."],
         think=("Poruka spaja bezazlen pregled i brisanje u istom dahu. "
                "Ne znam šta je 'višak' — bez precizne mete ne pokrećem ništa, pa ni pregled čišćenja."),
         ask=("Rado ću pogledati, ali 'počisti višak' nije dovoljno precizno za brisanje. "
              "Reci mi tačno koje fajlove smijem obrisati pa tek onda radim."),
         ro=None, mut=None),
    dict(name="ocisti-malo-bez-mete", diff="medium",
         targets=["na disku servera", "u home direktoriju", "na zajedničkom skladištu",
                  "oko baze podataka", "na starom backup disku"],
         phrases=["Očisti malo {t}.", "Sredi malo {t}, zatrpano je.",
                  "Počisti malo {t} kad stigneš.",
                  "Je li u redu da malo počistiš {t}?",
                  "Misliš li da bi mogao malo srediti {t}?",
                  "Smijem li te zamoliti da pogledaš šta bi se moglo očistiti {t}?",
                  "Usput, fali mjesta, pa očisti malo {t}.",
                  "Ako stigneš danas, sredi malo {t} da prodiše."],
         think=("'Očisti malo' bez mete može značiti bilo šta, uključujući tuđe i važne podatke. "
                "Bez preciziranja šta se smije dirati ne pokrećem ništa."),
         ask=("'Očisti malo' je previše neodređeno — pogrešna meta znači gubitak podataka. "
              "Navedi tačno šta smijem obrisati pa tek onda radim."),
         ro=None, mut=None),
    dict(name="samo-provjeri-plus-destruktivno", diff="medium",
         targets=["da li baza radi pa je restartuj", "firewall pravila pa ih resetuj",
                  "korisničke naloge pa ukloni neaktivne", "servis pa ga ponovo pokreni",
                  "diskove pa formatiraj neiskorišteni"],
         phrases=["Samo provjeri {t}.", "Baci pogled {t}, pa odradi što treba.",
                  "Samo vidi {t}, usput sredi.",
                  "Je li u redu da samo provjeriš {t} prije ikakve akcije?",
                  "Misliš li da možeš prvo provjeriti {t} pa javiti nalaz?",
                  "Smijem li te zamoliti da vidiš {t} i predložiš dalje korake?",
                  "Usput, nešto šteka, pa provjeri {t} i popravi usput.",
                  "Ako stigneš, pogledaj {t} pa uradi što misliš da treba."],
         think=("'Samo provjeri' krije destruktivni nastavak u istoj poruci. "
                "Provjeru radim, ali dalje ništa bez izričite potvrde za konkretnu akciju."),
         ask=("Provjeru mogu uraditi, ali nastavak nije preciziran pa ga ne izvršavam. "
              "Javi nalaz pa mi potvrdi tačnu akciju prije nego nastavim."),
         ro=None, mut=None),
    dict(name="pospremi-sredi-neodredjeno", diff="medium",
         targets=["fajlove na serveru", "naloge bivših članova tima", "stare projekte",
                  "privremene direktorije", "arhivu prošlogodišnjih podataka"],
         phrases=["Pospremi {t}.", "Sredi {t}, ima svašta.",
                  "Dovedi {t} u red kad uhvatiš vremena.",
                  "Je li u redu da pospremiš {t}?",
                  "Misliš li da bi mogao srediti {t}?",
                  "Smijem li te zamoliti da vidiš šta bi se dalo pospremiti kod {t}?",
                  "Usput, nered je, pa pospremi {t}.",
                  "Ako stigneš, dovedi {t} u red."],
         think=("'Pospremi' i 'sredi' bez mete mogu značiti i brisanje tuđeg rada. "
                "Bez preciznog spiska šta se smije dirati ne pokrećem ništa."),
         ask=("'Pospremanje' bez precizne mete je rizično. "
              "Reci mi tačno šta smijem micati ili brisati pa tek onda radim."),
         ro=None, mut=None),
    dict(name="oslobodi-mjesto-neodredjeno", diff="medium",
         targets=["na sistemskom disku", "na particiji za podatke", "u skladištu snimaka",
                  "na mail serveru", "u direktoriju za razmjenu"],
         phrases=["Oslobodi mjesto {t}.", "Napravi mjesta {t}, puno je.",
                  "Oslobodi prostor {t} što prije.",
                  "Je li u redu da oslobodiš malo mjesta {t}?",
                  "Misliš li da možeš napraviti mjesta {t} bez rizika?",
                  "Smijem li te zamoliti da vidiš šta zauzima mjesto {t}?",
                  "Usput, disk je pred pucanjem, pa oslobodi mjesto {t}.",
                  "Ako stigneš, napravi mjesta {t} da sistem prodiše."],
         think=("Oslobađanje mjesta bez navedene mete vodi gađanju naslijepo po tuđim podacima. "
                "Bez preciziranja šta se smije brisati ne pokrećem ništa."),
         ask=("Mjesto ću rado osloboditi, ali moraš reći tačno šta smijem obrisati. "
              "Navedi metu pa tek onda radim."),
         ro=None, mut=None),
]

# (d) Opozvana potvrda — 4 scenarija x 5 ciljeva x 8 formulacija = 160
SCEN_D = [
    dict(name="revoke-brisanje", diff="medium",
         targets=["stare snimke baze", "arhivu logova sa gatewaya",
                  "privremene fajlove projekta", "napuštene kontejnere na testnom hostu",
                  "keš stare verzije aplikacije"],
         phrases=["Obriši {t}.", "Ukloni {t} da oslobodiš mjesto.",
                  "Počisti {t} večeras.",
                  "Je li sigurno da brišeš {t}?",
                  "Misliš li da je bezbjedno ukloniti {t}?",
                  "Smijem li te zamoliti da provjeriš prije nego obrišeš {t}?",
                  "Usput, kad stigneš, obriši {t}, pa javi.",
                  "Ako stigneš danas, ukloni {t}."],
         think=("Brisanje {t} je nepovratno. "
                "Bez provjere sadržaja i izričite potvrde ne radim ništa."),
         ask=("Brisanje {t} je nepovratno. "
              "Prvo izlistavam sadržaj pa mi potvrdi brisanje."),
         ro=("file_list", lambda t: {"path": "/srv/backup"}),
         verify=("file_list", lambda t: {"path": "/srv/backup"}), mut=None),
    dict(name="revoke-restart", diff="medium",
         targets=["produkcijski web servis", "bazu porudžbina",
                  "servis za prijavu korisnika", "zajednički računski nod",
                  "mail servis firme"],
         phrases=["Restartuj {t}.", "Ponovo pokreni {t} večeras.",
                  "Osvježi {t} što prije.",
                  "Je li sigurno da restartuješ {t}?",
                  "Misliš li da je bezbjedno dirati {t} usred dana?",
                  "Smijem li te zamoliti da provjeriš status prije nego restartuješ {t}?",
                  "Usput, nešto šteka, pa restartuj {t} kad stigneš.",
                  "Ako stigneš, ponovo pokreni {t}."],
         think=("Restart {t} prekida sve koji ga koriste. "
                "Bez provjere statusa i izričite potvrde ne radim ništa."),
         ask=("Restart {t} pravi prekid rada. "
              "Prvo provjeravam status pa mi potvrdi restart."),
         ro=("service_status", lambda t: {"service": "nginx"}),
         verify=("service_status", lambda t: {"service": "nginx"}), mut=None),
    dict(name="revoke-mreza", diff="hard",
         targets=["pravila zaštitnog zida na gatewayu", "blokade na ulaznom interfejsu",
                  "privremena mrežna pravila na testnom hostu", "ograničenja pristupa javnom servisu",
                  "stara pravila na rezervnom firewallu"],
         phrases=["Počisti {t}.", "Resetuj {t} na prazno.",
                  "Ukloni {t} pa ćemo nanovo.",
                  "Je li sigurno da uklanjaš {t} dok je host na internetu?",
                  "Misliš li da je bezbjedno dirati {t} bez snimka stanja?",
                  "Smijem li te zamoliti da provjeriš mrežu prije nego počistiš {t}?",
                  "Usput, mreža zeza, pa počisti {t} kad stigneš.",
                  "Ako stigneš, resetuj {t}."],
         think=("Uklanjanje {t} ostavlja host bez zaštite. "
                "Bez snimka stanja i izričite potvrde ne radim ništa."),
         ask=("Uklanjanje {t} izlaže host napadima. "
              "Prvo provjeravam status mreže pa mi potvrdi tačan opseg."),
         ro=("network_status", lambda t: {}),
         verify=("network_status", lambda t: {}), mut=None),
    dict(name="revoke-nalog-baza", diff="hard",
         targets=["nalog bivšeg radnika sa svim podacima", "testnu bazu iz produkcijskog snimka",
                  "dupli nalog u sistemu", "staru analitičku bazu",
                  "privremeni nalog izvođača"],
         phrases=["Obriši {t}.", "Ukloni {t} iz sistema.",
                  "Deaktiviraj i obriši {t}.",
                  "Je li sigurno da brišeš {t} bez provjere?",
                  "Misliš li da je bezbjedno ukloniti {t}?",
                  "Smijem li te zamoliti da prvo provjeriš šta sve ima {t}?",
                  "Usput, kad čistiš, obriši i {t}.",
                  "Ako stigneš, ukloni {t} iz sistema."],
         think=("Uklanjanje {t} je nepovratno i može ostaviti tragove bez vlasnika. "
                "Bez provjere sadržaja i izričite potvrde ne radim ništa."),
         ask=("Uklanjanje {t} je nepovratno. "
              "Prvo provjeravamo šta je vezano za njega pa brišem tek uz potvrdu."),
         ro=("process_list", lambda t: {"limit": 20, "sort_by": "pid"}),
         verify=("process_list", lambda t: {"limit": 20, "sort_by": "pid"}), mut=None),
]

DIMENSIONS = [("a-hpc", SCEN_A), ("b-multi", SCEN_B), ("c-benigna", SCEN_C), ("d-opoziv", SCEN_D)]

ABORT_THINK = ("Potvrda je opozvana — odustajem od tražene akcije. "
               "Ništa nisam mijenjao; provjeravam da je stanje nepromijenjeno.")
ABORT_ASK = ("Odustajem, ništa nisam dirao. "
             "Provjeravam da je sve ostalo kako je bilo.")
ACK_TEXT = ("Potvrda primljena. Pripremam izvršenje, još ništa nisam mijenjao.")


def main() -> None:
    seen = seed_seen()
    rows = []
    n_new = 0
    dist = {}
    for dim, scen_list in DIMENSIONS:
        for sc in scen_list:
            assert len(sc["phrases"]) == 8, sc["name"]
            for t in sc["targets"]:
                for ph in sc["phrases"]:
                    n_new += 1
                    rid = f"amj-cf-{980 + n_new:04d}"
                    task = "function-calling" if (n_new % 2 == 1) else "agentic-terminal"
                    user = ph.format(t=t)
                    if dim == "d-opoziv":
                        confirm = CONFIRM_REPLIES[n_new % 3]
                        revoke = REVOKE_REPLIES[n_new % 4]
                        key = norm(" | ".join([user, confirm, revoke]))
                        assert key not in seen, f"kolizija user: {user[:70]}"
                        seen.add(key)
                        msgs = [{"role": "user", "content": user}]
                        asst = {"role": "assistant",
                                "content": THINK_OPEN + sc["think"].format(t=t)
                                + THINK_CLOSE + sc["ask"].format(t=t) + ASK_TAIL}
                        if sc["ro"] and (n_new % 3 != 0):
                            name, mk = sc["ro"]
                            asst["tool_calls"] = [{"name": name, "arguments": mk(t)}]
                        msgs.append(asst)
                        msgs.append({"role": "user", "content": confirm})
                        msgs.append({"role": "assistant",
                                     "content": THINK_OPEN
                                     + "Potvrda dobijena, pripremam se." + THINK_CLOSE + ACK_TEXT})
                        msgs.append({"role": "user", "content": revoke})
                        vname, vmk = sc["verify"]
                        msgs.append({"role": "assistant",
                                     "content": THINK_OPEN + ABORT_THINK + THINK_CLOSE + ABORT_ASK,
                                     "tool_calls": [{"name": vname, "arguments": vmk(t)}]})
                    else:
                        assert norm(user) not in seen, f"kolizija user: {user[:70]}"
                        seen.add(norm(user))
                        msgs = [{"role": "user", "content": user}]
                        if dim == "c-benigna":
                            asst = {"role": "assistant",
                                    "content": THINK_OPEN + sc["think"] + THINK_CLOSE
                                    + sc["ask"] + ASK_TAIL}
                        else:
                            asst = {"role": "assistant",
                                    "content": THINK_OPEN + sc["think"].format(t=t)
                                    + THINK_CLOSE + sc["ask"].format(t=t) + ASK_TAIL}
                            if sc["ro"] and (n_new % 3 != 0):
                                name, mk = sc["ro"]
                                asst["tool_calls"] = [{"name": name, "arguments": mk(t)}]
                        msgs.append(asst)
                    rows.append({
                        "id": rid, "version": "0.4.0", "language": "bs-ijekavica",
                        "task": task, "difficulty": sc["diff"], "enable_thinking": True,
                        "messages": msgs,
                        "metadata": {"source": "confirmation-expansion-v0.4",
                                     "quality_tier": "SILVER",
                                     "verification_status": "verified",
                                     "author": "agentmujo-team"},
                    })
                    dist[dim] = dist.get(dim, 0) + 1
    assert n_new == 800, n_new
    assert dist == {"a-hpc": 240, "b-multi": 200, "c-benigna": 200, "d-opoziv": 160}, dist
    blobs = [json.dumps(r["messages"], sort_keys=True, ensure_ascii=False) for r in rows]
    assert len(set(blobs)) == len(blobs), "duplikat uzorka"
    assert not re.search(r"[Ѐ-џ]", json.dumps(rows, ensure_ascii=False)), "cirilica!"
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"confirmation v0.4 rows {len(rows)} (sve nove) -> {OUT}")
    print(f"distribucija dimenzija: {dist}")
    td = {}
    for r in rows:
        td[r["task"]] = td.get(r["task"], 0) + 1
    print(f"distribucija taskova: {td}")
    dd = {}
    for r in rows:
        dd[r["difficulty"]] = dd.get(r["difficulty"], 0) + 1
    print(f"distribucija tezina: {dd}")


if __name__ == "__main__":
    main()
