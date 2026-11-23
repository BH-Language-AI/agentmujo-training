#!/bin/bash
#SBATCH --job-name=amj-thinkprobe
#SBATCH --account=project_465003647
#SBATCH --partition=small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=amj-thinkprobe-%j.out
# Think-proba: llama-server BEZ --reasoning off (reasoning auto) + enable_thinking:true.
# Dumpa cijeli message objekat (content + reasoning_content) za 3 sonde, loop SYSTEM.
# Upotreba: sbatch probe-think.sbatch <model-q8.gguf> <out.json>
set -euo pipefail
MODEL="${1:?upotreba: sbatch probe-think.sbatch <model> <out>}"
OUT="${2:?upotreba: sbatch probe-think.sbatch <model> <out>}"
LLAMACPP_BIN="$(dirname "$MODEL")/llama.cpp/build/bin"
SYS="Ti si AgentMujo, asistent za administraciju Linux servera. Odgovaraj na bosanskom jeziku (ijekavica). Dostupni alati: service_status(service), service_restart(service), service_logs(service, lines), disk_usage(path), memory_usage(), cpu_usage(), process_list(limit, sort_by), network_status(), port_check(port), package_query(package), package_install(package), file_list(path), file_read(path, lines), terminal(command, timeout_s). Ako zadatak zahtijeva alat, odgovori KANONSKIM formatom. Preferiraj high-level alat. Nikada ne pretpostavljaj uspjeh — verifikuj. Opasne zahtjeve odbij ili traži potvrdu."
"$LLAMACPP_BIN/llama-server" -m "$MODEL" --port 8898 -c 4096 \
  --n-gpu-layers 0 -t 16 > "$(dirname "$OUT")/thinkprobe_server.log" 2>&1 &
SRV=$!
for i in $(seq 1 60); do
  sleep 10
  if curl -sf http://127.0.0.1:8898/health > /dev/null 2>&1; then break; fi
  if [ "$i" = "60" ]; then echo "SERVER_NIJE_DIGAO"; kill $SRV 2>/dev/null || true; exit 1; fi
done
> "$OUT"
for P in "Da li je nginx servis trenutno aktivan?" "Prikaži zadnjih 20 linija nginx loga." "Ko slusa na portu 22?"; do
  python3 - "$SYS" "$P" "$OUT" <<'EOF' >> "$OUT"
import json, sys, urllib.request
SYS, P, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
body = {"messages": [{"role": "system", "content": SYS},
                     {"role": "user", "content": P}],
        "temperature": 0.0, "max_tokens": 300, "stream": False,
        "enable_thinking": True}
req = urllib.request.Request("http://127.0.0.1:8898/v1/chat/completions",
                             data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"})
try:
    d = json.loads(urllib.request.urlopen(req, timeout=300).read().decode())
    msg = d["choices"][0]["message"]
    rec = {"prompt": P, "keys": sorted(msg.keys()),
           "content": (msg.get("content") or "")[:800],
           "reasoning_content": (msg.get("reasoning_content") or "")[:800]}
except Exception as e:
    rec = {"prompt": P, "error": str(e)[:200]}
print(json.dumps(rec, ensure_ascii=False))
EOF
done
kill $SRV 2>/dev/null || true
echo THINKPROBE_DONE
