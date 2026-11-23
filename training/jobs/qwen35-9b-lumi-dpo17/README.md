# Job qwen35-9b-lumi-dpo17 (hipoteza: DPO-restraint na joint08)

Recept: dpo03 (jedini DPO koji je radio: beta 0.1, lr 5e-6, 3 epohe,
r16) — 81 restraint par (ask-mutate 36, refuse 20, check-first 6,
log-lesson 6, HL 8, no-tool 5), baza joint08 adapter.
DPO pipeline spaja adapter u cistu bazu pa krece svjezim LoRA slojem
(merge_and_unload) — NEMA double-count zamke.
Gate: v0.6 single-shot + LOOP. Uspjeh = conf/safety gore BEZ pada
toola ispod 0.85 i BEZ kratki-SYSTEM kolapsa (sonda: kratki prompt).
