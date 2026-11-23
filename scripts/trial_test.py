#!/usr/bin/env python3
"""Trial test: isto pitanje na 2B/4B/9B lokalno + snimi odgovore."""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmark"))
from llama_bench import SYSTEM

Q = "Korisnik: Nginx ne radi, sajt se ne otvara. Dijagnostikuj i popravi."
MODELS = ["agentmujo:latest", "agentmujo-4b-q8:latest", "agentmujo-9b-q8:latest"]
out = {}
for m in MODELS:
    body = {"model": m, "prompt": SYSTEM + "\n\n" + Q,
            "stream": False, "options": {"num_predict": 150, "temperature": 0.0}}
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=1500) as r:
            d = json.loads(r.read().decode())
        out[m] = d.get("response", "")
        print(f"OK {m}: {len(out[m])} chars", flush=True)
    except Exception as e:
        out[m] = f"GRESKA: {e}"
        print(f"FAIL {m}: {e}", flush=True)
Path("/tmp/opencode/trial_local.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("snimljeno /tmp/opencode/trial_local.json")
