# Job qwen35-9b-lumi-joint16 (brief §3-4: restraint delta)

Recept (nakon joint15 REJECT + taksonomija 9 failova):
- Baza: joint08 adapter (sampion). NE joint14/15.
- Mix v0.50: v0.41 (1850) + restraint v0.1 (60 GOLD: ask/refuse prije
  mutacije, check-confirm-act, plan-first, log-lesson, HL-over-terminal).
  Ukupno 1910, tool 1200. Bez bench-overlapa (4 prompta parafrazirao).
- Hiperparametri: lr 2e-5, r16, 1 epoha (stabilno za joint11-15).
- Gate: v0.6 single-shot + LOOP. Uspjeh = popraviti >=4/9 failova
  (022/026/029/040/043/047/056/059/063) BEZ pada toola ispod 0.90.
  Inace REJECT.
