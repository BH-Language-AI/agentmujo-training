#!/usr/bin/env python3
"""Confirmation v0.3: ~800 NOVIH redova (nista se ne prenosi iz starih verzija).

Novi scenariji (10): migracija baze, promjena DNS-a, otvaranje SSH na internet,
brisanje korisnika, format particije, downgrade paketa, promjena vlasnistva,
flush pravila zastitnog zida, zamjena TLS certifikata, dodavanje sistemskog
cron zadatka. Svaki: 8 ciljeva x 10 formulacija (direktna naredba / pitanje
"je li sigurno da..." / usputni zahtjev u duzoj poruci).

Asistent: <think> + trazenje eksplicirane potvrde + suhi pregled/provjera
prije akcije; dio redova ima read-only tool_call, a downgrade redovi svakog
sedmog imaju 4-turn potvrda -> izvrsenje sigurnim high-level alatom.
Asistentova povrsina ne smije sadrzavati DENY obrasce validatora (npr. bez
doslovnih destruktivnih naredbi u tekstu).
metadata: SILVER + verification_status "verified". ID nastavak amj-cf niza.
Dedup: normalizovani user sadrzaj protiv SVIH postojecih canonical fajlova.
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "datasets/canonical/confirmation_v0.3.jsonl"


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def seed_seen() -> set:
    seen = set()
    for f in sorted((REPO / "datasets/canonical").glob("*.jsonl")):
        if f.name in ("confirmation_v0.3.jsonl",):
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

SCEN = [
    dict(name="db-migrate", diff="hard",
         targets=["bazu kupaca na novi klaster", "bazu porudžbina na verziju 16",
                  "skladišnu bazu na drugi host", "bazu korisnika na novi server",
                  "transakcijsku bazu na veću instancu", "analitičku bazu u novi region",
                  "testnu bazu iz produkcijskog snimka", "arhivsku bazu na jeftinije skladište"],
         phrases=["Migriraj {t} večeras.", "Prebaci {t} na novu okolinu odmah.",
                  "Kreni sa migracijom: {t}.",
                  "Je li sigurno da migriraš {t} bez zastoja?",
                  "Misliš li da je bezbjedno prebaciti {t} usred radnog vremena?",
                  "Smijem li te zamoliti da provjeriš može li se {t} migrirati bez gubitaka?",
                  "Usput, kad stigneš, migriraj {t}, pa mi javi kako je prošlo i koliko je trajalo.",
                  "Imamo dosta posla danas, a između ostalog bi trebalo migrirati {t} kad uhvatiš vremena.",
                  "Samo da te podsjetim da u planu stoji i migracija, dakle {t}, pa pogledaj kad može.",
                  "Ako nije problem, prebaci {t}, usput provjeri jesu li svi podaci na broju nakon toga."],
         think=("Migracija {t} nosi rizik zastoja i gubitka podataka. "
                "Bez provjere backupa, plana povratka i izričite potvrde ne radim ništa."),
         ask=("Migracija {t} može izazvati zastoj i gubitak podataka. "
              "Prvo provjeravam backup i status, pa mi potvrdi plan i termin."),
         ro=("service_status", lambda t: {"service": "postgres"}), mut=None),
    dict(name="dns-change", diff="hard",
         targets=["glavni domen na nove servere", "MX zapise na novog provajdera",
                  "poddomenu api na novu adresu", "TXT zapise za verifikaciju",
                  "CNAME za cdn", "NS zapise domena",
                  "AAAA zapise na ipv6", "TTL na pet minuta"],
         phrases=["Promijeni {t} odmah.", "Prebaci {t} na nove vrijednosti.",
                  "Odredi {t} kako smo dogovorili.",
                  "Je li sigurno da mijenjaš {t} usred radnog dana?",
                  "Misliš li da je bezbjedno dirati {t} bez najave korisnicima?",
                  "Smijem li te zamoliti da provjeriš posljedice prije nego promijeniš {t}?",
                  "Usput, kad budeš radio na mreži, promijeni {t}, pa provjeri širenje promjene.",
                  "Imamo gužvu sa sajtom, a trebalo bi i {t} promijeniti, pogledaj kad stigneš.",
                  "Samo napominjem da je u planu i promjena, dakle {t}, pa se javi prije nego kreneš.",
                  "Ako stigneš danas, promijeni {t}, usput smanji TTL pa posmatraj širenje."],
         think=("Promjena {t} širi se sporo i greška ruši dostupnost. "
                "Tražim provjeru trenutnog stanja i potvrdu prije izmjene."),
         ask=("Greška u {t} ruši dostupnost servisa. "
              "Prvo provjeravam trenutno stanje pa mi potvrdi tačne vrijednosti."),
         ro=("network_status", lambda t: {}), mut=None),
    dict(name="ssh-open", diff="hard",
         targets=["SSH na portu 22 prema cijelom internetu", "SSH pristup za vanjske izvođače",
                  "port 22 na javnom interfejsu", "SSH za hitnu podršku izvana",
                  "port 2222 prema svima", "SSH preko javne adrese",
                  "udaljeni SSH za administratore van mreže", "SSH na rezervnom linku prema van"],
         phrases=["Otvori {t}.", "Omogući {t} bez odlaganja.",
                  "Pusti {t} da proradi.",
                  "Je li sigurno da otvaraš {t}?",
                  "Misliš li da je bezbjedno izložiti {t}?",
                  "Smijem li te zamoliti da provjeriš rizik prije nego otvoriš {t}?",
                  "Usput, izvođači zovu, pa kad stigneš otvori {t}, ali javi mi prije toga.",
                  "Imamo hitan slučaj sa podrškom, a usput bi trebalo i {t} otvoriti privremeno.",
                  "Samo da znaš, u planu je i otvaranje, dakle {t}, pa provjeri alternative prije toga.",
                  "Ako nije problem, otvori {t} na kratko, usput ograniči ko smije prići."],
         think=("Otvaranje {t} izlaže sistem napadima sa interneta. "
                "Nudim sigurnije alternative i tražim potvrdu uz obrazloženje."),
         ask=("Otvaranje {t} je visok rizik. Predlažem VPN ili ograničenje pristupa "
              "umjesto potpunog otvaranja."),
         ro=("port_check", lambda t: {"port": 22}), mut=None),
    dict(name="user-del", diff="medium",
         targets=["nalog bivšeg radnika", "stari servisni nalog",
                  "privremeni nalog izvođača", "dupli nalog u sistemu",
                  "nalog pripravnika", "testnog korisnika",
                  "nalog vanjskog saradnika", "neaktivni nalog iz prošle godine"],
         phrases=["Obriši {t}.", "Ukloni {t} iz sistema.",
                  "Deaktiviraj i obriši {t}.",
                  "Je li sigurno da brišeš {t} bez provjere vlasništva fajlova?",
                  "Misliš li da je bezbjedno ukloniti {t} dok traju projekti?",
                  "Smijem li te zamoliti da prvo provjeriš čega sve ima {t} prije brisanja?",
                  "Usput, kad čistiš naloge, obriši i {t}, pa mi reci šta je sve bilo vezano za njega.",
                  "Imamo reviziju naloga, a između ostalog treba ukloniti i {t} kad provjeriš.",
                  "Samo napominjem da je na spisku za čišćenje i {t}, pa pogledaj prije nego obrišeš.",
                  "Ako stigneš, ukloni {t}, usput sačuvaj popis njegovih fajlova prije toga."],
         think=("Brisanje {t} je nepovratno i može ostaviti fajlove bez vlasnika. "
                "Tražim provjeru sadržaja i izričitu potvrdu prije brisanja."),
         ask=("Brisanje {t} ostavlja fajlove bez vlasnika. "
              "Prvo provjeravamo šta je vezano za nalog pa brišem tek uz potvrdu."),
         ro=None, mut=None),
    dict(name="part-format", diff="hard",
         targets=["particiju /dev/sdb1", "novi disk /dev/sdc",
                  "rezervnu particiju /dev/sdd1", "stari disk /dev/sde",
                  "particiju za backup /dev/sdf1", "testni disk /dev/sdg",
                  "eksternu particiju /dev/sdh1", "rezervni disk /dev/sdi"],
         phrases=["Formatiraj {t}.", "Pripremi {t} za upotrebu brisanjem sadržaja.",
                  "Očisti {t} pa je dodijeli sistemu.",
                  "Je li sigurno da formatiraš {t} dok je sistem podignut?",
                  "Misliš li da je bezbjedno dirati {t} bez provjere šta je na njoj?",
                  "Smijem li te zamoliti da provjeriš sadržaj prije nego formatiraš {t}?",
                  "Usput, kad sređuješ diskove, formatiraj {t}, ali prvo mi reci šta je gore.",
                  "Imamo višak diskova, a trebalo bi i {t} pripremiti, pogledaj kad možeš.",
                  "Samo napominjem da je u planu i priprema, dakle {t}, pa provjeri prije nego kreneš.",
                  "Ako stigneš danas, očisti {t}, usput provjeri zauzeće ostalih diskova."],
         think=("Formatiranje {t} je nepovratno. "
                "Bez provjere sadržaja, backupa i izričite potvrde ne radim ništa."),
         ask=("Formatiranje {t} briše sve bez povratka. "
              "Prvo provjeravamo sadržaj i zauzeće pa radim tek uz pisanu potvrdu."),
         ro=("disk_usage", lambda t: {"path": "/"}), mut=None),
    dict(name="pkg-downgrade", diff="medium",
         targets=["nginx na prošlu verziju", "postgres na verziju 14",
                  "redis na starije izdanje", "certbot na prethodnu verziju",
                  "docker na stabilnu granu", "python na 3.10",
                  "node na LTS izdanje", "grafanu na verziju od prošlog mjeseca"],
         phrases=["Vrati {t}.", "Spusti {t} jer nova pravi probleme.",
                  "Deinstaliraj novo pa namjesti {t}.",
                  "Je li sigurno da vraćaš {t} na produkciji?",
                  "Misliš li da je bezbjedno spuštati {t} bez provjere zavisnosti?",
                  "Smijem li te zamoliti da provjeriš koja je verzija prije nego vratiš {t}?",
                  "Usput, nova verzija puca, pa kad stigneš vrati {t}, javi kako radi poslije.",
                  "Imamo žalbe korisnika, a izgleda da bi pomoglo da se vrati {t} kad provjeriš.",
                  "Samo napominjem da je u planu i vraćanje, dakle {t}, pa provjeri zavisnosti prije toga.",
                  "Ako stigneš, spusti {t}, usput provjeri da li je paket uopšte instaliran."],
         think=("Vraćanje {t} mijenja sistem i može slomiti zavisnosti. "
                "Prvo provjeravam instalirano stanje pa tražim potvrdu."),
         ask=("Vraćanje {t} može slomiti zavisnosti. "
              "Prvo provjeravam trenutnu verziju pa mi potvrdi vraćanje."),
         ro=("package_query", lambda t: {"package": t.split()[0]}),
         mut=("package_install", lambda t: {"package": t.split()[0]})),
    dict(name="chown-www", diff="hard",
         targets=["vlasništvo /var/www na deploy korisnika", "vlasništvo /var/www na www-data grupu",
                  "vlasnika /srv/podaci na aplikaciju", "grupu /opt/aplikacija na tim",
                  "vlasništvo /home/dijeljeno na voditelja", "vlasnika skripte za deploy na ci korisnika",
                  "grupu /var/log/aplikacija na analitiku", "vlasništvo /srv/backup na backup korisnika"],
         phrases=["Promijeni {t}.", "Prebaci {t} odmah.",
                  "Namjesti {t} kako treba.",
                  "Je li sigurno da mijenjaš {t} na produkciji?",
                  "Misliš li da je bezbjedno dirati {t} bez provjere trenutnog stanja?",
                  "Smijem li te zamoliti da provjeriš ko je sada vlasnik prije nego promijeniš {t}?",
                  "Usput, deploy puca zbog prava, pa promijeni {t} kad stigneš, javi rezultat.",
                  "Imamo problema sa dozvolama, a između ostalog treba i {t} promijeniti.",
                  "Samo napominjem da je u planu i promjena, dakle {t}, pa prvo izlistaj stanje.",
                  "Ako stigneš, prebaci {t}, usput provjeri sadržaj direktorija prije toga."],
         think=("Promjena {t} može slomiti servise i otvoriti pristup. "
                "Prvo izlistavam stanje pa tražim potvrdu sa obrazloženjem."),
         ask=("Promjena {t} utiče na sve servise koji tu čitaju i pišu. "
              "Prvo izlistavam stanje pa mi potvrdi tačnu promjenu."),
         ro=("file_list", lambda t: {"path": _first_path(t)}), mut=None),
    dict(name="fw-flush", diff="hard",
         targets=["sva pravila zaštitnog zida", "privremena pravila na gatewayu",
                  "stara pravila na testnom hostu", "blokade na ulaznom interfejsu",
                  "testna pravila na stagingu", "sva pravila prije migracije",
                  "pravila na rezervnom firewallu", "suvišna pravila na javnom hostu"],
         phrases=["Počisti {t}.", "Ukloni {t} pa ćemo nanovo.",
                  "Resetuj {t} na prazno.",
                  "Je li sigurno da uklanjaš {t} dok je host na internetu?",
                  "Misliš li da je bezbjedno dirati {t} bez snimka stanja?",
                  "Smijem li te zamoliti da provjeriš mrežu prije nego počistiš {t}?",
                  "Usput, mreža zeza, pa kad stigneš počisti {t}, ali prvo snimi stanje.",
                  "Imamo problema sa pristupom, a neko spominje da bi trebalo i {t} počistiti.",
                  "Samo napominjem da je u planu i čišćenje, dakle {t}, pa provjeri prije toga.",
                  "Ako stigneš, resetuj {t}, usput provjeri status mreže prije i poslije."],
         think=("Uklanjanje {t} ostavlja host bez zaštite. "
                "Bez snimka stanja, užeg plana i izričite potvrde ne radim ništa."),
         ask=("Uklanjanje {t} izlaže host napadima. "
              "Prvo provjeravam status mreže pa mi potvrdi tačan opseg."),
         ro=("network_status", lambda t: {}), mut=None),
    dict(name="tls-cert", diff="medium",
         targets=["certifikat za glavni domen", "certifikat za api poddomenu",
                  "wildcard certifikat", "certifikat za internu alatku",
                  "certifikat za mail server", "certifikat za staging okolinu",
                  "istekli certifikat na gatewayu", "certifikat za rezervni domen"],
         phrases=["Zamijeni {t}.", "Obnovi {t} odmah.",
                  "Namjesti novi {t}.",
                  "Je li sigurno da mijenjaš {t} usred dana?",
                  "Misliš li da je bezbjedno dirati {t} bez provjere isteka?",
                  "Smijem li te zamoliti da provjeriš trenutni certifikat prije nego zamijeniš {t}?",
                  "Usput, pregledači javljaju grešku, pa zamijeni {t} kad stigneš.",
                  "Imamo upozorenje o isteku, a trebalo bi i {t} obnoviti, pogledaj kad možeš.",
                  "Samo napominjem da je u planu i obnova, dakle {t}, pa provjeri prije toga.",
                  "Ako stigneš, obnovi {t}, usput provjeri lanac certifikata poslije."],
         think=("Zamjena {t} može prekinuti saobraćaj ako lanac nije potpun. "
                "Prvo provjeravam postojeće fajlove pa tražim potvrdu."),
         ask=("Zamjena {t} traži potpun lanac inače pada saobraćaj. "
              "Prvo provjeravam postojeće fajlove pa mi potvrdi zamjenu."),
         ro=("file_list", lambda t: {"path": "/etc/ssl"}), mut=None),
    dict(name="cron-root", diff="medium",
         targets=["noćni backup u planer kao root", "skriptu za čišćenje u sistemski planer",
                  "provjeru diska u planer svakog sata", "sinhronizaciju u planer kao root",
                  "restart servisa u noćni planer", "izvještaj o logovima u jutarnji planer",
                  "rotaciju ključeva u sedmični planer", "skeniranje virusa u planer kao root"],
         phrases=["Dodaj {t}.", "Ubaci {t} da se vrti redovno.",
                  "Namjesti {t}.",
                  "Je li sigurno da dodaješ {t}?",
                  "Misliš li da je bezbjedno puštati {t} sa najvišim pravima?",
                  "Smijem li te zamoliti da provjeriš skriptu prije nego dodaš {t}?",
                  "Usput, treba nam automatika, pa dodaj {t} kad stigneš, javi raspored.",
                  "Imamo ručnih poslova previše, a trebalo bi i {t} dodati u planer.",
                  "Samo napominjem da je u planu i automatika, dakle {t}, pa provjeri prije toga.",
                  "Ako stigneš, ubaci {t}, usput provjeri šta se već vrti u planeru."],
         think=("Dodavanje {t} daje redovne povlastice skripti. "
                "Prvo tražim uvid u skriptu i raspored pa izričitu potvrdu."),
         ask=("Dodavanje {t} pokreće skriptu sa visokim pravima. "
              "Prvo mi pokaži skriptu i raspored pa potvrdi dodavanje."),
         ro=None, mut=None),
]


def _first_path(t: str) -> str:
    m = re.search(r"/[\w./-]+", t)
    return m.group(0) if m else "/var/www"


THINK_OPEN = "<think>\n"
THINK_CLOSE = "\n</think>\n\n"
CONFIRM_REPLIES = ["Da, potvrđujem.", "Da, slažem se, nastavi.", "Potvrđujem, uradi to."]


def main() -> None:
    seen = seed_seen()
    rows = []
    n_new = 0
    for si, sc in enumerate(SCEN):
        assert len(sc["targets"]) == 8 and len(sc["phrases"]) == 10, sc["name"]
        for ti, t in enumerate(sc["targets"]):
            for pi, ph in enumerate(sc["phrases"]):
                n_new += 1
                rid = f"amj-cf-{180 + n_new:04d}"
                task = "function-calling" if (n_new % 2 == 1) else "agentic-terminal"
                user = ph.format(t=t)
                assert norm(user) not in seen, f"kolizija user: {user[:70]}"
                seen.add(norm(user))
                think_ask = THINK_OPEN + sc["think"].format(t=t) + THINK_CLOSE + sc["ask"].format(t=t) + ASK_TAIL
                msgs = [{"role": "user", "content": user}]
                asst = {"role": "assistant", "content": think_ask}
                if sc["ro"] and (n_new % 3 != 0):
                    name, mk = sc["ro"]
                    asst["tool_calls"] = [{"name": name, "arguments": mk(t)}]
                msgs.append(asst)
                if sc["mut"] and (n_new % 7 == 0):
                    mname, mmk = sc["mut"]
                    msgs.append({"role": "user", "content": CONFIRM_REPLIES[n_new % 3]})
                    msgs.append({"role": "assistant",
                                 "content": (THINK_OPEN + "Potvrda dobijena. Izvršavam traženo "
                                             "high-level alatom pa radim obaveznu provjeru." + THINK_CLOSE
                                             + "Potvrda primljena, izvršavam."),
                                 "tool_calls": [{"name": mname, "arguments": mmk(t)}]})
                rows.append({
                    "id": rid, "version": "0.3.0", "language": "bs-ijekavica",
                    "task": task, "difficulty": sc["diff"], "enable_thinking": True,
                    "messages": msgs,
                    "metadata": {"source": "template-expansion-v0.3",
                                 "quality_tier": "SILVER",
                                 "verification_status": "verified",
                                 "author": "agentmujo-team"},
                })
    assert n_new == 800, n_new
    blobs = [json.dumps(r["messages"], sort_keys=True, ensure_ascii=False) for r in rows]
    assert len(set(blobs)) == len(blobs), "duplikat uzorka"
    assert not re.search(r"[Ѐ-џ]", json.dumps(rows, ensure_ascii=False)), "cirilica!"
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"confirmation v0.3 rows {len(rows)} (sve nove) -> {OUT}")


if __name__ == "__main__":
    main()