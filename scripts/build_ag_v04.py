#!/usr/bin/env python3
"""Generise datasets/canonical/agentic_terminal_v0.4.jsonl (~1500 scenarija).

Template-expansion v0.4: NOVA HPC/Slurm domena (treba za LUMI worker).
Svaki scenarij je viseturni troubleshooting (easy 3, medium 4, hard 6 tool
koraka) kroz POSTOJECIH 14 alata iz configs/tools.yaml: HPC komande
(squeue/sinfo/scontrol/sacct/ml/lfs) idu SAMO kroz terminal tool kao
read-only, ostalo: file_read (sbatch skripte, slurm izlazi), disk_usage
(scratch/quota), file_list, process_list, memory_usage, cpu_usage,
network_status/package_query (pogresan trag koji se odbacuje).
Difficulty mix 25/50/25 (easy/medium/hard). ID nastavak od max iz v0.1-v0.3.
DEDUP: normaliziran prvi user problem ne smije postojati u v0.1/v0.2/v0.3
ni unutar v0.4. metadata SILVER / template-expansion-v0.4 / verified.
Koristenje: .venv/bin/python scripts/build_ag_v04.py
"""
import json
import random
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRCS = [REPO / "datasets/canonical/agentic_terminal_v0.1.jsonl",
        REPO / "datasets/canonical/agentic_terminal_v0.2.jsonl",
        REPO / "datasets/canonical/agentic_terminal_v0.3.jsonl"]
OUT = REPO / "datasets/canonical/agentic_terminal_v0.4.jsonl"

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
    s = (k * 53 + 29) % 86400
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def norm(s):
    return re.sub(r"\s+", " ", s.strip().lower())


def row(sid, diff, msgs, domain):
    return {"id": sid, "version": "0.4.0", "language": "bs-ijekavica",
            "task": "agentic-terminal", "difficulty": diff,
            "enable_thinking": True, "messages": msgs,
            "metadata": {"author": "agentmujo-team", "quality_tier": "SILVER",
                         "source": "template-expansion-v0.4",
                         "verification_status": "verified",
                         "domain": domain}}


APPS = ["gromacs", "vasp", "openfoam", "pytorch-trening", "tensorflow-trening",
        "lammps", "wrf", "cp2k"]


def jid(t):
    return 812000 + t


# ---------- 1. pending: job ceka zbog particije/limita ----------

def b_pending(rng, i, t, diff):
    job = jid(t)
    part = rng.choice(["long", "standard", "gpu"])
    reason = rng.choice(["PartitionTimeLimit", "QOSMaxTRESPerUser",
                         "ReqNodeNotAvail", "Priority"])
    detail = {"PartitionTimeLimit": f"trazeno vrijeme 7-00:00:00 prelazi limit particije {part} (5-00:00:00)",
              "QOSMaxTRESPerUser": "korisnicka kvota resursa (QOS normal) vec je popunjena drugim poslovima",
              "ReqNodeNotAvail": f"svi cvorovi particije {part} su zauzeti ili u odrzavanju",
              "Priority": "posao niskog prioriteta, ispred njega je 14 poslova"}[reason]
    m = [U(rng.choice([f"Moj Slurm posao {job} vec satima stoji u redu (PENDING), a nista se ne desava. Vidi zasto. (prijava HPC-{t})",
                       f"Posao {job} ne krece, squeue ga drzi u PD stanju. Dijagnostikuj. (prijava HPC-{t})",
                       f"Zaglavio mi je job {job} u redu cekanja na particiji {part}. Sta ga koci? (prijava HPC-{t})"]))]
    m += [T(f"Otvaram sbatch skriptu da vidim sta je posao {job} trazio.",
            [{"name": "file_read", "arguments": {"path": f"/home/korisnik/slurm/posao-{job}.sh", "lines": 50}}]),
          R({"path": f"/home/korisnik/slurm/posao-{job}.sh",
             "excerpt": f"#SBATCH --partition={part}\n#SBATCH --time=7-00:00:00\n#SBATCH --ntasks=64\nsrun ./{rng.choice(APPS)}.x"})]
    m += [T(f"Skripta trazi particiju {part}. Provjeravam status posla u redu.",
            [{"name": "terminal", "arguments": {"command": f"squeue -j {job} --format='%i %P %T %M %l %S'", "timeout_s": 30}}]),
          R({"output": f"{job} {part} PD 1:12:33 7-00:00:00 {reason}"})]
    m += [T("Posao ceka. Provjeravam procijenjeno vrijeme pokretanja.",
            [{"name": "terminal", "arguments": {"command": f"squeue --start -j {job}", "timeout_s": 30}}]),
          R({"output": f"{job}: procijenjeni start nepoznat (resursi nisu dostupni prije {ts(i)})"})]
    if diff in ("medium", "hard"):
        m += [T(f"Start se ne nazire. Provjeravam stanje particije {part}.",
                [{"name": "terminal", "arguments": {"command": f"sinfo -p {part} -o '%P %A %T %N'", "timeout_s": 30}}]),
              R({"output": f"{part} up 0/48/0/48 cvor[01-48] (svi zauzeti do {ts(i)})"})]
    if diff == "hard":
        m += [T("Particija je puna. Gledam detalje posla da provjerim ima li i ogranicenja kvote.",
                [{"name": "terminal", "arguments": {"command": f"scontrol show job {job} | grep -i -E 'qos|tres|time|depend'", "timeout_s": 30}}]),
              R({"output": f"QOS=normal TRES=cpu=64,node=2 TimeLimit=7-00:00:00; {detail}"}),
              T("I kvota igra ulogu. Provjeravam istoriju slicnih poslova da vidim koliko su stvarno trajali.",
                [{"name": "terminal", "arguments": {"command": "sacct -u $USER --starttime=2026-10-26 --format=JobID,Elapsed,Timelimit,State | head -8", "timeout_s": 30}}]),
              R({"output": "slicni poslovi: Elapsed 2-11:20:00 do 3-04:00:00, svi zavrsili prije 4. dana"})]
    m += [T(f"Dijagnoza: posao {job} ceka (PENDING) jer {detail}. Procijenjeni start se zato ne nazire. "
            f"Sljedeci korak: skratiti --time na 4-00:00:00 (prethodni slicni poslovi stali su u 4 dana) ili prebaciti posao "
            f"na particiju sa slobodnim kapacitetom, pa verifikacija kroz squeue i scontrol. Bez tvoje potvrde nista ne otkazujem niti ponovo saljem.")]
    return m


# ---------- 2. oom: OOM-killed job -> trazi vise memorije ----------

def b_oom(rng, i, t, diff):
    job = jid(t)
    app = rng.choice(APPS)
    asked = rng.choice(["4G", "8G", "2G_po_jezgri"])
    asked_txt = asked.replace("_", " ")
    m = [U(rng.choice([f"Posao {job} ({app}) je ubijen usred izvrsavanja, sumnjam na memoriju. Potvrdi i predlozi popravak. (prijava HPC-{t})",
                       f"Job {job} puca sa OOM greskom. Koliko memorije mu stvarno treba? (prijava HPC-{t})",
                       f"{app} posao {job} zavrsio kao OUT_OF_MEMORY. Analiziraj lanac. (prijava HPC-{t})"]))]
    m += [T(f"Citam izlaznu datoteku posla {job} da nadjem trag ubijanja.",
            [{"name": "file_read", "arguments": {"path": f"/home/korisnik/slurm/slurm-{job}.out", "lines": 50}}]),
          R({"path": f"/home/korisnik/slurm/slurm-{job}.out",
             "excerpt": f"slurmstepd: error: posao {job} premasio limit memorije, ubijam ga; oom-kill u {ts(i)}"})]
    m += [T("Izlaz pokazuje prekoracenje memorije. Provjeravam zvanicno stanje posla.",
            [{"name": "terminal", "arguments": {"command": f"sacct -j {job} --format=JobID,State,MaxRSS,ReqMem", "timeout_s": 30}}]),
          R({"output": f"{job} OUT_OF_MEMORY MaxRSS=31.2G ReqMem={asked_txt}"})]
    m += [T(f"Posao je trazio {asked_txt}, a potrosio preko 31 GB. Otvaram sbatch skriptu da vidim zahtjev.",
            [{"name": "file_read", "arguments": {"path": f"/home/korisnik/slurm/posao-{job}.sh", "lines": 50}}]),
          R({"path": f"/home/korisnik/slurm/posao-{job}.sh",
             "excerpt": f"#SBATCH --mem={asked_txt}\n#SBATCH --ntasks=16\nsrun ./{app}.x ulaz.dat"})]
    if diff in ("medium", "hard"):
        m += [T("Zahtjev je premali. Mjerim memoriju login cvora da iskljucim sistemski pritisak.",
                [{"name": "memory_usage", "arguments": {}}]),
              R({"mem_pct": rng.randint(38, 52)})]
    if diff == "hard":
        m += [T("Login cvor je miran, taj trag odbacujem - problem je limit samog posla. Gledam detalje koraka.",
                [{"name": "terminal", "arguments": {"command": f"scontrol show job {job} | grep -i -E 'tres|mem|maxrss'", "timeout_s": 30}}]),
              R({"output": f"TRES=cpu=16,mem={asked_txt} MaxRSS=31.2G (korak {job}.0 ubijen pri {ts(i)})"}),
              T("Detalji potvrdjuju: korak je ubijen na limitu. Provjeravam ima li memorije na particiji za veci zahtjev.",
                [{"name": "terminal", "arguments": {"command": "sinfo -p standard -o '%P %m %A'", "timeout_s": 30}}]),
              R({"output": "standard 256000 MB po cvoru, 12 cvorova slobodno"})]
    m += [T(f"Dijagnoza: posao {job} je ubijen jer je trazio samo {asked_txt}, a stvarna potrosnja je 31.2 GB "
            f"(MaxRSS). Sljedeci korak: podici zahtjev na --mem=40G i ponovo poslati posao uz tvoju potvrdu, pa "
            f"verifikacija kroz sacct (State COMPLETED, MaxRSS ispod limita). Bez potvrde nista ne saljem.")]
    return m


# ---------- 3. gpu-cpu: GPU job na CPU particiji ----------

def b_gpucpu(rng, i, t, diff):
    job = jid(t)
    app = rng.choice(["pytorch-trening", "tensorflow-trening", "gromacs-gpu"])
    m = [U(rng.choice([f"GPU trening {job} ({app}) se vuce kao da nema graficke. Provjeri gdje se izvrsava. (prijava HPC-{t})",
                       f"Posao {job} trazi GPU, ali sumnjam da je zavrsio na CPU particiji. (prijava HPC-{t})",
                       f"{app} job {job} radi 10x sporije nego inace. Je li dobio graficku? (prijava HPC-{t})"]))]
    m += [T(f"Otvaram sbatch skriptu posla {job}.",
            [{"name": "file_read", "arguments": {"path": f"/home/korisnik/slurm/posao-{job}.sh", "lines": 50}}]),
          R({"path": f"/home/korisnik/slurm/posao-{job}.sh",
             "excerpt": "#SBATCH --partition=standard\n#SBATCH --ntasks=8\n#SBATCH --gres=gpu:1\nsrun python treniraj.py"})]
    m += [T("Skripta trazi 1 GPU na particiji standard. Provjeravam ima li ta particija uopce grafickih.",
            [{"name": "terminal", "arguments": {"command": "sinfo -p standard -o '%P %G %A'", "timeout_s": 30}}]),
          R({"output": "standard (gres: nema) - CPU cvorovi, bez grafickih"})]
    m += [T("Particija standard nema GPU. Provjeravam gdje je posao zavrsio i sta je dobio.",
            [{"name": "terminal", "arguments": {"command": f"squeue -j {job} -o '%i %P %T %b'", "timeout_s": 30}}]),
          R({"output": f"{job} standard R gres=(null) - cvor cvor07, bez dodijeljene graficke"})]
    if diff in ("medium", "hard"):
        m += [T("Posao radi na CPU cvoru. Citam izlaz da potvrdim da trening pada na CPU.",
                [{"name": "file_read", "arguments": {"path": f"/home/korisnik/slurm/slurm-{job}.out", "lines": 50}}]),
              R({"path": f"/home/korisnik/slurm/slurm-{job}.out",
                 "excerpt": "torch.cuda.is_available(): False; upozorenje: trening na CPU, 1 epoha 42 min"})]
    if diff == "hard":
        m += [T("Trening je pao na CPU. Provjeravam GPU particiju ima li mjesta.",
                [{"name": "terminal", "arguments": {"command": "sinfo -p gpu -o '%P %G %A'", "timeout_s": 30}}]),
              R({"output": "gpu gres:gpu:4 po cvoru, 3 cvora slobodna"}),
              T("GPU particija ima slobodnih grafickih. Provjeravam detalje dodjele resursa.",
                [{"name": "terminal", "arguments": {"command": f"scontrol show job {job} | grep -i gres", "timeout_s": 30}}]),
              R({"output": f"GRES=(null) - planer je ignorisao gres zahtjev na particiji bez grafickih"})]
    m += [T(f"Dijagnoza: posao {job} ({app}) trazi --gres=gpu:1, ali je poslan na CPU particiju standard koja nema "
            f"grafickih, pa trening radi na CPU (epoha 42 min umjesto par minuta). Sljedeci korak: promijeniti "
            f"--partition=gpu u skripti i ponovo poslati uz tvoju potvrdu, pa verifikacija kroz scontrol (gres=gpu:1) i izlaz "
            f"(cuda available True). Bez potvrde nista ne saljem.")]
    return m


# ---------- 4. scratch: quota pun ----------

def b_scratch(rng, i, t, diff):
    job = jid(t)
    app = rng.choice(APPS)
    pct = rng.randint(96, 99)
    m = [U(rng.choice([f"Posao {job} puca sa 'No space left', a radi u scratchu. Vidi kvotu. (prijava HPC-{t})",
                       f"Scratch mi je navodno pun pa {app} posao {job} ne moze pisati. Provjeri. (prijava HPC-{t})",
                       f"Job {job} staje pri pisanju rezultata na /scratch. Analiziraj prostor. (prijava HPC-{t})"]))]
    m += [T("Provjeravam zauzece scratch prostora.",
            [{"name": "disk_usage", "arguments": {"path": "/scratch"}}]),
          R({"path": "/scratch", "used_pct": pct, "avail": "310G"})]
    m += [T(f"Scratch je na {pct}%. Citam izlaz posla da potvrdim vezu.",
            [{"name": "file_read", "arguments": {"path": f"/home/korisnik/slurm/slurm-{job}.out", "lines": 50}}]),
          R({"path": f"/home/korisnik/slurm/slurm-{job}.out",
             "excerpt": f"{ts(i)} {app}: greska pri pisanju snimka: No space left on device (/scratch/korisnik)"})]
    m += [T("Greska potvrdjuje pun scratch. Provjeravam kvotu korisnika.",
            [{"name": "terminal", "arguments": {"command": "lfs quota -h /scratch 2>/dev/null || quota -s", "timeout_s": 30}}]),
          R({"output": "korisnik: 9.6T od 10T (96%), 1.2M fajlova od 1M (prekoracen i broj fajlova)"})]
    if diff in ("medium", "hard"):
        m += [T("Kvota je probijena i po prostoru i po broju fajlova. Listam sta zauzima najvise.",
                [{"name": "file_list", "arguments": {"path": "/scratch/korisnik"}}]),
              R({"path": "/scratch/korisnik", "files": ["stari-checkpointi/ (6.1T)", "tmp-fragmenti/ (2.8T)", "rezultati/"]})]
    if diff == "hard":
        m += [T("Najvise trose stari checkpointi. Provjeravam stanje posla da vidim je li jos ziv.",
                [{"name": "terminal", "arguments": {"command": f"sacct -j {job} --format=JobID,State,Elapsed", "timeout_s": 30}}]),
              R({"output": f"{job} FAILED (nedostatak prostora u {ts(i)})"}),
              T("Posao je pao. Provjeravam CPU login cvora da iskljucim i taj trag.",
                [{"name": "cpu_usage", "arguments": {}}]),
              R({"cpu_pct": rng.randint(18, 33)})]
    m += [T(f"Dijagnoza: scratch kvota je na {pct}% (9.6T od 10T, prekoracen i broj fajlova), pa posao {job} ne moze "
            f"pisati snimke i pada. Sljedeci korak: obrisati stare checkpointe i tmp-fragmente uz tvoju potvrdu "
            f"(arhiva prije brisanja), pa ponovno slanje i verifikacija kvotom i sacct stanjem. Bez potvrde nista ne brisem.")]
    return m


# ---------- 5. modul: modul se ne ucitava ----------

def b_module(rng, i, t, diff):
    job = jid(t)
    mod = rng.choice(["gromacs/2024.2", "vasp/6.4.3", "python/3.11-sci", "cuda/12.4"])
    base = mod.split("/")[0]
    m = [U(rng.choice([f"Posao {job} odmah pada, izgleda da se modul {mod} ne ucitava. Provjeri. (prijava HPC-{t})",
                       f"Job {job}: 'command not found' nakon ml load. Vidi sta je sa modulima. (prijava HPC-{t})",
                       f"Ne radi mi {base} u poslu {job}, modul javlja gresku. Dijagnostikuj. (prijava HPC-{t})"]))]
    m += [T(f"Otvaram sbatch skriptu posla {job}.",
            [{"name": "file_read", "arguments": {"path": f"/home/korisnik/slurm/posao-{job}.sh", "lines": 50}}]),
          R({"path": f"/home/korisnik/slurm/posao-{job}.sh",
             "excerpt": f"module purge\nml load {mod}\nsrun {base}.x ulaz.dat"})]
    m += [T(f"Skripta ucitava {mod}. Provjeravam postoji li ta verzija na klasteru.",
            [{"name": "terminal", "arguments": {"command": f"ml spider {base} 2>&1 | head -20", "timeout_s": 30}}]),
          R({"output": f"dostupne verzije: {base}/2023.1, {base}/2023.4 (verzija {mod.split('/')[-1]} povucena u oktobru)"})]
    m += [T("Trazena verzija je povucena. Citam izlaz posla za potvrdu.",
            [{"name": "file_read", "arguments": {"path": f"/home/korisnik/slurm/slurm-{job}.out", "lines": 50}}]),
          R({"path": f"/home/korisnik/slurm/slurm-{job}.out",
             "excerpt": f"Lmod: greska: modul {mod} ne postoji; {base}.x: command not found"})]
    if diff in ("medium", "hard"):
        m += [T("Greska potvrdjena. Provjeravam sta je uopce dostupno za taj alat.",
                [{"name": "terminal", "arguments": {"command": f"module avail {base} 2>&1 | head -10", "timeout_s": 30}}]),
              R({"output": f"{base}/2023.4 (preporucen), {base}/2023.1; zavisi od gcc/12.2"})]
    if diff == "hard":
        m += [T("Postoji novija preporucena verzija. Provjeravam sistem modula da iskljucim infrastrukturni kvar.",
                [{"name": "package_query", "arguments": {"package": "lmod"}}]),
              R({"package": "lmod", "installed": True}),
              T("Sistem modula je ispravan, taj trag odbacujem. Provjeravam istoriju posla.",
                [{"name": "terminal", "arguments": {"command": f"sacct -j {job} --format=JobID,State,ExitCode", "timeout_s": 30}}]),
              R({"output": f"{job} FAILED ExitCode 127:0 (komanda nije pronadjena)"})]
    m += [T(f"Dijagnoza: posao {job} pada jer modul {mod} vise ne postoji (verzija povucena), pa izvrsna datoteka "
            f"nije na putanji (exit 127). Sljedeci korak: zamijeniti sa {base}/2023.4 (uz pripadajuci gcc/12.2) u skripti "
            f"i ponovo poslati uz tvoju potvrdu, pa verifikacija kroz ml load i sacct. Bez potvrde nista ne mijenjam.")]
    return m


# ---------- 6. stuck-r: job visi u R stanju ----------

def b_stuckr(rng, i, t, diff):
    job = jid(t)
    app = rng.choice(APPS)
    m = [U(rng.choice([f"Posao {job} ({app}) je u R stanju tri dana, a log se ne mice. Je li zaglavio? (prijava HPC-{t})",
                       f"Job {job} radi, ali ne napreduje - izlaz stoji na istom redu danima. Provjeri. (prijava HPC-{t})",
                       f"Sumnjam da mi je posao {job} zapeo (R, bez napretka). Dijagnostikuj. (prijava HPC-{t})"]))]
    m += [T(f"Provjeravam status posla {job} u redu.",
            [{"name": "terminal", "arguments": {"command": f"squeue -j {job} -o '%i %P %T %M %N'", "timeout_s": 30}}]),
          R({"output": f"{job} standard R 3-02:11:00 cvor11"})]
    m += [T("Posao je u R stanju preko 3 dana. Citam kraj izlazne datoteke da vidim ima li napretka.",
            [{"name": "file_read", "arguments": {"path": f"/home/korisnik/slurm/slurm-{job}.out", "lines": 50}}]),
          R({"path": f"/home/korisnik/slurm/slurm-{job}.out",
             "excerpt": "korak 412/5000 od 10-30 08:12; nakon toga nijedan novi red 2 dana"})]
    m += [T("Izlaz stoji 2 dana. Provjeravam detalje posla - ceka li na nesto.",
            [{"name": "terminal", "arguments": {"command": f"scontrol show job {job} | grep -i -E 'state|reason|depend|time'", "timeout_s": 30}}]),
          R({"output": "JobState=RUNNING Reason=None Dependency=(null) TimeLimit=7-00:00:00"})]
    if diff in ("medium", "hard"):
        m += [T("Nema zavisnosti ni razloga cekanja. Provjeravam potrosnju koraka - radi li ista.",
                [{"name": "terminal", "arguments": {"command": f"sacct -j {job} --format=JobID,AveCPU,MaxRSS", "timeout_s": 30}}]),
              R({"output": f"{job}.0 AveCPU=00.4% MaxRSS=1.1G (proces gotovo ne trosi CPU)"})]
    if diff == "hard":
        m += [T("Proces ne trosi CPU - ceka na nesto. Provjeravam mrezu da iskljucim mrezni uzrok.",
                [{"name": "network_status", "arguments": {}}]),
              R({"interfaces": {"eth0": "up"}, "gateway_ok": True, "rx_packets": 950000 + i}),
              T("Mreza je uredna, taj trag odbacujem. Gledam procese da iskljucim lokalni uzrok.",
                [{"name": "process_list", "arguments": {"limit": 10, "sort_by": "cpu"}}]),
              R({"top": [{"name": "bash", "pid": 1200 + i, "cpu": 1}]})]
    m += [T(f"Dijagnoza: posao {job} ({app}) je formalno u R stanju, ali bez napretka 2 dana uz AveCPU 0.4% - ceka na "
            f"ulaz (vjerovatno zakljucavanje datoteke na dijeljenom sistemu ili cekanje na medjurezultat), a ne racuna. "
            f"Sljedeci korak: provjeriti zaglavljene lockove na cvoru cvor11, pa tek onda otkazivanje (scancel) i ponovno "
            f"slanje uz tvoju potvrdu. Bez potvrde nista ne otkazujem.")]
    return m


# ---------- 7. array: array job djelimicno pao ----------

def b_array(rng, i, t, diff):
    job = jid(t)
    app = rng.choice(APPS)
    bad = sorted(rng.sample(range(1, 51), 3))
    m = [U(rng.choice([f"Array posao {job} ({app}, 50 zadataka) djelimicno je pao. Vidi koji indeksi i zasto. (prijava HPC-{t})",
                       f"Job array {job} zavrsio mjesovito - neki indeksi FAILED. Analiziraj. (prijava HPC-{t})",
                       f"Od 50 zadataka u nizu {job} palo ih je nekoliko. Nadji uzrok. (prijava HPC-{t})"]))]
    m += [T(f"Provjeravam stanje svih zadataka niza {job}.",
            [{"name": "terminal", "arguments": {"command": f"sacct -j {job} --format=JobID,State,ExitCode | head -20", "timeout_s": 30}}]),
          R({"output": f"{job}_[{bad[0]},{bad[1]},{bad[2]}] FAILED; ostalih 47 COMPLETED"})]
    m += [T(f"Pala su 3 od 50 zadataka ({bad[0]}, {bad[1]}, {bad[2]}). Citam log prvog palog.",
            [{"name": "file_read", "arguments": {"path": f"/home/korisnik/slurm/slurm-{job}_{bad[0]}.out", "lines": 50}}]),
          R({"path": f"/home/korisnik/slurm/slurm-{job}_{bad[0]}.out",
             "excerpt": f"ucitavam ulaz_{bad[0]}.dat: datoteka ne postoji ili je prazna"})]
    m += [T("Pali zadatak ne nalazi ulaz. Listam direktorij ulaza da vidim sta nedostaje.",
            [{"name": "file_list", "arguments": {"path": "/scratch/korisnik/ulazi"}}]),
          R({"path": "/scratch/korisnik/ulazi",
             "files": ["ulaz_1.dat, ulaz_2.dat i ostali prisutni", f"nedostaju: ulaz_{bad[0]}.dat, ulaz_{bad[1]}.dat, ulaz_{bad[2]}.dat"]})]
    if diff in ("medium", "hard"):
        m += [T("Nedostaju bas ulazi palih zadataka. Otvaram sbatch skriptu da vidim mapiranje indeksa.",
                [{"name": "file_read", "arguments": {"path": f"/home/korisnik/slurm/posao-{job}.sh", "lines": 50}}]),
              R({"path": f"/home/korisnik/slurm/posao-{job}.sh",
                 "excerpt": "#SBATCH --array=1-50\nsrun ./preproces.sh ulaz_${SLURM_ARRAY_TASK_ID}.dat"})]
    if diff == "hard":
        m += [T("Mapiranje je 1-1. Provjeravam log drugog palog da potvrdim isti uzrok.",
                [{"name": "file_read", "arguments": {"path": f"/home/korisnik/slurm/slurm-{job}_{bad[1]}.out", "lines": 50}}]),
              R({"path": f"/home/korisnik/slurm/slurm-{job}_{bad[1]}.out",
                 "excerpt": f"ucitavam ulaz_{bad[1]}.dat: datoteka ne postoji ili je prazna"}),
              T("Isti uzrok. Provjeravam disk da iskljucim pun scratch kao uzrok nestanka.",
                [{"name": "disk_usage", "arguments": {"path": "/scratch"}}]),
              R({"path": "/scratch", "used_pct": rng.randint(44, 58), "avail": "6.1T"})]
    m += [T(f"Dijagnoza: od 50 zadataka niza {job} pala su 3 ({bad[0]}, {bad[1]}, {bad[2]}) jer im nedostaju ulazne datoteke "
            f"(preproces ih nije generisao), a ne zbog koda - ostalih 47 je uspjesno. Sljedeci korak: "
            f"dogenerisati 3 ulaza i ponovo poslati samo pale indekse (--array={bad[0]},{bad[1]},{bad[2]}) uz tvoju potvrdu, pa "
            f"verifikacija kroz sacct. Bez potvrde nista ne saljem.")]
    return m


# ---------- 8. checkpoint: checkpoint/restart ----------

def b_checkpoint(rng, i, t, diff):
    job = jid(t)
    app = rng.choice(APPS)
    m = [U(rng.choice([f"Dugacak posao {job} ({app}) ubijen je na limitu vremena, a nema sacuvanog stanja. Predlozi checkpoint strategiju. (prijava HPC-{t})",
                       f"Job {job} pao na TIME_LIMIT pri 95% posla i sve je izgubljeno. Kako to sprijeciti? (prijava HPC-{t})",
                       f"Posao {job} stalno gubi dane racunanja jer nema checkpointa. Analiziraj. (prijava HPC-{t})"]))]
    m += [T(f"Provjeravam kako je posao {job} zavrsio.",
            [{"name": "terminal", "arguments": {"command": f"sacct -j {job} --format=JobID,State,Elapsed,Timelimit", "timeout_s": 30}}]),
          R({"output": f"{job} TIME_LIMIT Elapsed 6-23:58:00 Timelimit 7-00:00:00"})]
    m += [T("Posao je ubijen 2 minute prije kraja limita. Otvaram skriptu da vidim ima li cuvanja stanja.",
            [{"name": "file_read", "arguments": {"path": f"/home/korisnik/slurm/posao-{job}.sh", "lines": 50}}]),
          R({"path": f"/home/korisnik/slurm/posao-{job}.sh",
             "excerpt": f"#SBATCH --time=7-00:00:00\nsrun ./{app}.x (bez checkpoint opcija, bez trap USR1)"})]
    m += [T("Skripta nema cuvanje stanja. Citam kraj izlaza da vidim dokle je stigao.",
            [{"name": "file_read", "arguments": {"path": f"/home/korisnik/slurm/slurm-{job}.out", "lines": 50}}]),
          R({"path": f"/home/korisnik/slurm/slurm-{job}.out",
             "excerpt": "korak 4750/5000 (95%); primljen SIGTERM; stanje nije sacuvano"})]
    if diff in ("medium", "hard"):
        m += [T("95% posla izgubljeno. Provjeravam direktorij checkpointa ima li ista iskoristivo.",
                [{"name": "file_list", "arguments": {"path": "/scratch/korisnik/checkpoint"}}]),
              R({"path": "/scratch/korisnik/checkpoint", "files": ["prazno - nijedan checkpoint nikad nije zapisan"]})]
    if diff == "hard":
        m += [T("Nema nijednog checkpointa. Gledam istoriju koliko korisnikovi poslovi stvarno traju.",
                [{"name": "terminal", "arguments": {"command": "sacct -u $USER --starttime=2026-10-01 --format=JobID,Elapsed,State | head -8", "timeout_s": 30}}]),
              R({"output": "prethodni: 5-12:00:00, 6-08:00:00, 4-20:00:00 (svi blizu limita 7 dana)"}),
              T("Svi poslovi traju blizu limita. Provjeravam memoriju login cvora da iskljucim i taj trag.",
                [{"name": "memory_usage", "arguments": {}}]),
              R({"mem_pct": rng.randint(40, 55)})]
    m += [T(f"Dijagnoza: posao {job} ({app}) izgubio je 95% racunanja jer nema checkpoint/restart mehanizma, a trajanje "
            f"(skoro 7 dana) je tik uz vremenski limit particije. Sljedeci korak: (1) ukljuciti periodicno "
            f"cuvanje stanja svakih 12 sati u /scratch/korisnik/checkpoint, (2) podijeliti posao na lance od 3 dana sa zavisnoscu "
            f"(--dependency=afterok), pa ponovno slanje uz tvoju potvrdu. Bez potvrde nista ne saljem.")]
    return m


# ---------- 9. lustre: spor I/O -> optimizacija pisanja ----------

def b_lustre(rng, i, t, diff):
    job = jid(t)
    app = rng.choice(APPS)
    m = [U(rng.choice([f"Posao {job} ({app}) je spor, sumnjam na Lustre I/O - pise hiljade malih fajlova. Potvrdi. (prijava HPC-{t})",
                       f"Job {job} provodi vise vremena u pisanju nego u racunanju. Analiziraj I/O. (prijava HPC-{t})",
                       f"{app} posao {job} staje pri svakom snimanju na /pfs. Vidi je li do Lustrea. (prijava HPC-{t})"]))]
    m += [T(f"Citam izlaz posla {job} da vidim udio pisanja.",
            [{"name": "file_read", "arguments": {"path": f"/home/korisnik/slurm/slurm-{job}.out", "lines": 50}}]),
          R({"path": f"/home/korisnik/slurm/slurm-{job}.out",
             "excerpt": f"korak 100: racunanje 4.2 s, pisanje snimka 61.8 s (I/O dominira u {ts(i)})"})]
    m += [T("Pisanje traje 15x duze od racunanja. Provjeravam obrazac pisanja na Lustreu.",
            [{"name": "terminal", "arguments": {"command": "lfs getstripe /pfs/korisnik/rezultati 2>/dev/null; ls /pfs/korisnik/rezultati | wc -l", "timeout_s": 30}}]),
          R({"output": "stripe_count=1, 48200 malih fajlova (po priblizno 40 KB)"})]
    m += [T("48 hiljada malih fajlova sa jednim stripeom - klasican obrazac sporog Lustrea. Listam direktorij za potvrdu.",
            [{"name": "file_list", "arguments": {"path": "/pfs/korisnik/rezultati"}}]),
          R({"path": "/pfs/korisnik/rezultati", "files": ["korak_00001.dat ... korak_48200.dat (40 KB svaki)"]})]
    if diff in ("medium", "hard"):
        m += [T("Obrazac potvrdjen. Provjeravam mrezu da iskljucim mrezni uzrok sporosti.",
                [{"name": "network_status", "arguments": {}}]),
              R({"interfaces": {"eth0": "up"}, "gateway_ok": True, "rx_packets": 960000 + i})]
    if diff == "hard":
        m += [T("Mreza je uredna, taj trag odbacujem. Provjeravam zauzece datotecnog sistema.",
                [{"name": "disk_usage", "arguments": {"path": "/pfs"}}]),
              R({"path": "/pfs", "used_pct": rng.randint(62, 74), "avail": "1.2P"}),
              T("Mjesta ima, dakle nije do kapaciteta. Gledam stanje posla.",
                [{"name": "terminal", "arguments": {"command": f"sacct -j {job} --format=JobID,State,Elapsed,AveCPU", "timeout_s": 30}}]),
              R({"output": f"{job} RUNNING Elapsed 2-06:00:00 AveCPU=11.2% (jezgre cekaju na I/O)"})]
    m += [T(f"Dijagnoza: posao {job} ({app}) gubi vrijeme jer pise 48 hiljada malih fajlova (40 KB) na Lustre sa jednim "
            f"stripeom - svaki snimak 62 s naspram 4 s racunanja, jezgre cekaju na I/O (AveCPU 11%). Sljedeci korak: "
            f"agregirati izlaz u jedan HDF5/NetCDF fajl ili pisati na lokalni /tmp pa premjestiti na kraj, uz "
            f"tvoju potvrdu za izmjenu skripte, pa verifikacija vremenima koraka. Bez potvrde nista ne mijenjam.")]
    return m


BUILDERS = [b_pending, b_oom, b_gpucpu, b_scratch, b_module,
            b_stuckr, b_array, b_checkpoint, b_lustre]
DOMAINS = {b_pending: "hpc-pending", b_oom: "hpc-oom", b_gpucpu: "hpc-gpu-cpu",
           b_scratch: "hpc-scratch", b_module: "hpc-module",
           b_stuckr: "hpc-stuck-r", b_array: "hpc-array",
           b_checkpoint: "hpc-checkpoint", b_lustre: "hpc-lustre"}


def main():
    rng = random.Random(202604)
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
    # 25/50/25 od 1500: prvih 6 domena 42/84/42, zadnje 3 domene 41/82/41
    jobs = []
    for idx, fn in enumerate(BUILDERS):
        e, md, h = (42, 84, 42) if idx < 6 else (41, 82, 41)
        jobs += [("easy", fn)] * e + [("medium", fn)] * md + [("hard", fn)] * h
    assert len(jobs) == 1500, len(jobs)
    rng.shuffle(jobs)
    rows, seen_new = [], set()
    for k, (diff, fn) in enumerate(jobs):
        t = nxt + k
        msgs = fn(rng, k, t, diff)
        first = norm(msgs[0]["content"])
        assert first not in old_first, f"kolizija sa v0.1-v0.3: {first[:80]}"
        assert first not in seen_new, f"kolizija unutar v0.4: {first[:80]}"
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
            assert nsteps == 3, (fn.__name__, nsteps)
        elif diff == "medium":
            assert nsteps == 4, (fn.__name__, nsteps)
        else:
            assert nsteps == 6, (fn.__name__, nsteps)
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
