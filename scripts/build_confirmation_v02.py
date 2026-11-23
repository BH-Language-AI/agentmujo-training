#!/usr/bin/env python3
"""Confirmation v0.2: 200 redova (20 prenesenih iz v0.1 + 180 novih).

Svaki novi red: korisnik trazi rizicno -> asistent sa <think> trazi eksplicitnu
potvrdu i nudi suhi pregled/provjeru prije akcije. Trećina redova dodaje
read-only tool_call (provjera stanja), a dio restart/install scenarija ima
4 poruke: potvrda korisnika -> izvrsenje sigurnim high-level alatom.
Asistentova povrsina ne smije sadrzavati DENY obrasce validatora.
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OLD = REPO / "datasets/canonical/confirmation_v0.1.jsonl"
OUT = REPO / "datasets/canonical/confirmation_v0.2.jsonl"

ASK_TAIL = " Molim te potvrdi izričito prije nego što nastavim."

# scenario: tezina, ciljevi (5), fraze (3 sa {t}), think (sa {t}), ask (sa {t}),
# read-only alat ili None, mutirajuci alat za 4-turn ili None
SCEN = [
    dict(name="restart-svc", diff="medium",
         targets=["postgres", "nginx", "redis", "apache2", "docker"],
         phrases=["Restartuj {t} sada.", "Restartuj {t} na produkciji.",
                  "Ugasi pa ponovo upali servis {t}."],
         think=("Restart servisa {t} prekida sve njegove aktivne konekcije. "
                "Bez potvrde ne radim mutacije; prvo provjeravam status pa tražim potvrdu."),
         ask=("Restart servisa {t} će prekinuti aktivne konekcije. "
              "Prvo ću provjeriti status, pa mi potvrdi da smijem restartovati."),
         ro=("service_status", lambda t: {"service": t}),
         mut=("service_restart", lambda t: {"service": t})),
    dict(name="reboot", diff="hard",
         targets=["cijeli server", "produkcijski server", "ovu mašinu", "glavni host", "bazu i aplikaciju zajedno"],
         phrases=["Restartuj {t} večeras.", "Rebootuj {t} odmah.", "Ugasi i upali {t}."],
         think=("Reboot gasi sve servise odjednom i nosi rizik da nešto ne ustane. "
                "Tražim termin, provjeru servisa i izričitu potvrdu."),
         ask=("Reboot gasi sve odjednom i nešto možda ne ustane nazad. "
              "Predlažem provjeru servisa pa dogovor termina."),
         ro=None, mut=None),
    dict(name="rm-delete", diff="hard",
         targets=["/var/log/staro", "/tmp/sve", "/srv/backup/staro", "/var/cache", "/opt/slike/stare"],
         phrases=["Obriši {t} da oslobodimo mjesto.", "Ukloni cijeli sadržaj {t}.",
                  "Počisti {t} bez ostavljanja traga."],
         think=("Brisanje direktorija {t} je nepovratno. Nikad ne brišem bez "
                "popisa šta se briše i izričite potvrde; prvo listam sadržaj."),
         ask=("Brisanje je nepovratno pa prvo listam šta se tačno nalazi u {t}, "
              "a brišem tek kad potvrdiš konkretan popis."),
         ro=("file_list", lambda t: {"path": t}), mut=None),
    dict(name="firewall-port", diff="medium",
         targets=["8080", "5432", "6379", "3000", "22"],
         phrases=["Otvori port {t} prema van.", "Dodaj pravilo za port {t}.",
                  "Pusti sav saobraćaj na port {t}."],
         think=("Otvaranje porta {t} širi napadnu površinu. Prvo provjeravam ko "
                "već sluša na portu pa tražim potvrdu sa obrazloženjem."),
         ask=("Otvaranje porta {t} izlaže servis internetu. Prvo provjeravam "
              "šta sluša na njemu, pa mi potvrdi uz obrazloženje."),
         ro=("port_check", lambda t: {"port": int(t)}), mut=None),
    dict(name="chmod", diff="hard",
         targets=["/var/www", "/opt/aplikacija", "/srv/podaci", "skriptu za deploy", "/home/dijeljeno"],
         phrases=["Daj svima puna prava na {t}.", "Otključaj {t} da svako može sve.",
                  "Postavi najšire dozvole na {t}."],
         think=("Najšire dozvole na {t} znače da svako može mijenjati i brisati. "
                "To je sigurnosni rizik; predlažem uže dozvole i tražim potvrdu."),
         ask=("Puna prava za sve na {t} su sigurnosni rizik. Predlažem uže "
              "dozvole samo za potrebne korisnike."),
         ro=None, mut=None),
    dict(name="drop-db", diff="hard",
         targets=["kupci", "porudzbine", "skladiste", "korisnici", "transakcije"],
         phrases=["Obriši tabelu {t}.", "Isprazni tabelu {t} bez povratka.",
                  "Sruši bazu {t} i napravi praznu."],
         think=("Brisanje tabele {t} je nepovratan gubitak podataka. Bez backupa "
                "i pisane potvrde ne radim ništa; prvo nudim provjeru backupa."),
         ask=("Brisanje tabele {t} je nepovratno. Prvo provjeravamo backup i "
              "obim, a brišem tek uz pisanu potvrdu."),
         ro=None, mut=None),
    dict(name="pkg-install", diff="medium",
         targets=["nginx", "postgresql", "redis", "certbot", "htop"],
         phrases=["Instaliraj paket {t}.", "Dodaj {t} na server.", "Namjesti {t} odmah."],
         think=("Instalacija paketa {t} mijenja sistem i može povući zavisnosti. "
                "Prvo provjeravam da li već postoji pa tražim potvrdu."),
         ask=("Instalacija paketa {t} mijenja sistem. Prvo provjeravam da li je "
              "već instaliran, pa mi potvrdi instalaciju."),
         ro=("package_query", lambda t: {"package": t}),
         mut=("package_install", lambda t: {"package": t})),
    dict(name="sys-update", diff="medium",
         targets=["sistem", "sve pakete", "kernel", "sigurnosne zakrpe", "produkcijski server"],
         phrases=["Ažuriraj {t} večeras.", "Pokreni update na {t}.",
                  "Instaliraj sva ažuriranja na {t}."],
         think=("Ažuriranje može restartovati servise i kernel. Treba termin, "
                "backup i redoslijed provjere; tražim potvrdu plana."),
         ask=("Ažuriranje može oboriti servise. Predlažem plan: backup, termin, "
              "provjera svakog servisa."),
         ro=None, mut=None),
    dict(name="stop-svc", diff="medium",
         targets=["apache2", "nginx", "postgres", "redis", "cron"],
         phrases=["Zaustavi servis {t}.", "Ugasi {t} da oslobodiš resurse.", "Stopiraj {t} odmah."],
         think=("Zaustavljanje servisa {t} prekida sve što on opslužuje. "
                "Provjeravam status pa tražim potvrdu prije gašenja."),
         ask=("Gašenje servisa {t} obara sve što on opslužuje. Prvo provjeravam "
              "status pa mi potvrdi gašenje."),
         ro=("service_status", lambda t: {"service": t}), mut=None),
    dict(name="del-logs", diff="medium",
         targets=["/var/log", "/var/log/nginx", "/var/log/postgresql", "/tmp", "/var/tmp"],
         phrases=["Obriši stare logove u {t}.", "Počisti {t} da oslobodiš mjesto.",
                  "Izbaci sve iz {t}."],
         think=("Brisanje logova u {t} je nepovratno i briše trag za dijagnostiku. "
                "Prvo mjerim zauzeće pa tražim potvrdu konkretnih fajlova."),
         ask=("Prije brisanja provjeravam koliko {t} zauzima. Potvrdi mi nakon "
              "toga koje tačno smijem obrisati."),
         ro=("disk_usage", lambda t: {"path": t}), mut=None),
    dict(name="kill-proc", diff="medium",
         targets=["CPU", "memoriju", "disk", "mrežu", "sistem"],
         phrases=["Ubij proces koji najviše troši {t}.", "Zaustavi najteži proces po {t}.",
                  "Sruši proces koji guši {t}."],
         think=("Gašenje procesa koji najviše troši {t} može srušiti kritičan servis. "
                "Prvo listam procese pa tražim potvrdu konkretnog PID-a."),
         ask=("Prvo listam procese da vidimo šta najviše troši {t}. Potvrdi mi "
              "koji konkretno smijem zaustaviti."),
         ro=("process_list", lambda t: {"limit": 5, "sort_by": "cpu"}), mut=None),
    dict(name="expose", diff="hard",
         targets=["bazu podataka", "redis", "administratorski panel", "SSH", "unutrašnji API"],
         phrases=["Izloži {t} prema internetu.", "Otvor pristup {t} svima vani.",
                  "Objavi {t} na javnoj adresi."],
         think=("Izlaganje {t} internetu je visok rizik. Nudim sigurnije "
                "alternative (VPN, restrikcija IP) i tražim potvrdu."),
         ask=("Izlaganje {t} internetu je visok rizik. Predlažem VPN ili "
              "ograničenje pristupa umjesto potpunog otvaranja."),
         ro=("network_status", lambda t: {}), mut=None),
]

THINK_OPEN = "<think>\n"
THINK_CLOSE = "\n</think>\n\n"
CONFIRM_REPLIES = ["Da, potvrđujem.", "Da, slažem se, nastavi.", "Potvrđujem, uradi to."]


def main() -> None:
    old_rows = [json.loads(l) for l in OLD.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = list(old_rows)
    n_new = 0
    for si, sc in enumerate(SCEN):
        assert len(sc["targets"]) == 5 and len(sc["phrases"]) == 3, sc["name"]
        for ti, t in enumerate(sc["targets"]):
            for pi, ph in enumerate(sc["phrases"]):
                n_new += 1
                rid = f"amj-cf-{n_new:04d}"
                task = "function-calling" if (n_new % 2 == 1) else "agentic-terminal"
                user = ph.format(t=t)
                think_ask = THINK_OPEN + sc["think"].format(t=t) + THINK_CLOSE + sc["ask"].format(t=t) + ASK_TAIL
                msgs = [{"role": "user", "content": user}]
                asst = {"role": "assistant", "content": think_ask}
                if sc["ro"] and (n_new % 3 != 0):
                    name, mk = sc["ro"]
                    asst["tool_calls"] = [{"name": name, "arguments": mk(t)}]
                msgs.append(asst)
                # svaki sedmi restart/install red: potvrda -> izvrsenje sigurnim alatom
                if sc["mut"] and (n_new % 7 == 0):
                    mname, mmk = sc["mut"]
                    msgs.append({"role": "user", "content": CONFIRM_REPLIES[n_new % 3]})
                    msgs.append({"role": "assistant",
                                 "content": (THINK_OPEN + "Potvrda dobijena. Izvršavam traženo "
                                             "high-level alatom pa radim obaveznu provjeru." + THINK_CLOSE
                                             + "Potvrda primljena, izvršavam."),
                                 "tool_calls": [{"name": mname, "arguments": mmk(t)}]})
                rows.append({
                    "id": rid, "version": "0.2.0", "language": "bs-ijekavica",
                    "task": task, "difficulty": sc["diff"], "enable_thinking": True,
                    "messages": msgs,
                    "metadata": {"source": "template-expansion-v0.2",
                                 "quality_tier": "SILVER",
                                 "verification_status": "auto-validated",
                                 "author": "agentmujo-team"},
                })
    assert n_new == 180, n_new
    assert len(rows) == 200, len(rows)
    blobs = [json.dumps(r["messages"], sort_keys=True, ensure_ascii=False) for r in rows]
    assert len(set(blobs)) == len(blobs), "duplikat uzorka"
    blob = json.dumps(rows, ensure_ascii=False)
    assert not re.search(r"[Ѐ-џ]", blob), "cirilica!"
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"confirmation rows {len(rows)} (starih {len(old_rows)}, novih {n_new}) -> {OUT}")


if __name__ == "__main__":
    main()
