# Job qwen35-9b-lumi-joint15 (hipoteza a: veci confirmation mix)

Recept (nakon joint14 REJECT):
- Baza: joint08 adapter (sampion). NE joint14.
- Mix v49: v0.41 (1850) + 500 confirmation SA alatom (sve svjeze,
  ask + read-only check; bez prose-only) + 150 safety edge
  (escalation 43 + exfil 42 + poison 37 + false-verif 28).
  Ukupno 2500, tool 1693 (68%).
- Hiperparametri: lr 2e-5, r16, 1 epoha (stabilno za joint11-14).
- Gate: v0.6 single-shot + LOOP. Uspjeh = loop conf >= 0.85
  uz tool >= 0.85 i bez pada safetyja (inace REJECT, linija se zatvara).
