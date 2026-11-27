"""SAL2B proba: base Salamandra-2B + LoRA adapter, greedy, 10 bosanskih promptova -> JSON."""
import json
import sys

ADAPTER = sys.argv[1]
OUT = sys.argv[2]

PROMPTS = [
    "Definiši šta znači 'himen'.",
    "Je li riječ 'Neuhvatljivo' imenica, glagol ili neka druga vrsta riječi?",
    "Prevedi na engleski: Zima nam se bliži, a sa njom stiže i radost.",
    "Napiši kratku čestitku za rođendan na bosanskom jeziku.",
    "Sažmi u jednoj rečenici šta je fotosinteza.",
    "Koji je glavni grad Bosne i Hercegovine i koja rijeka protiče kroz njega?",
    "Objasni ukratko šta je fotosinteza.",
    "Napiši primjer pravilne upotrebe riječi 'neću'.",
    "Kako se na engleskom kaže 'hvala' i kada se koristi?",
    "Sastavi dvije rečenice o Jahorini zimi.",
]

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

tok = AutoTokenizer.from_pretrained(ADAPTER, trust_remote_code=True)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token
base = "BSC-LT/salamandra-2b"
model = AutoModelForCausalLM.from_pretrained(
    base, torch_dtype=torch.bfloat16, device_map="auto", trust_remote_code=True)
model = PeftModel.from_pretrained(model, ADAPTER)
model.eval()

res = []
for p in PROMPTS:
    text = tok.apply_chat_template(
        [{"role": "user", "content": p}], tokenize=False, add_generation_prompt=True)
    inp = tok(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**inp, max_new_tokens=128, do_sample=False,
                             eos_token_id=tok.eos_token_id,
                             pad_token_id=tok.pad_token_id)
    gen = tok.decode(out[0][inp["input_ids"].shape[1]:], skip_special_tokens=True)
    res.append({"prompt": p, "output": gen.strip()})
    print(f"Q: {p}\nA: {gen.strip()}\n---", flush=True)

with open(OUT, "w") as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
print(f"PROBE_SAVED {len(res)} -> {OUT}")
