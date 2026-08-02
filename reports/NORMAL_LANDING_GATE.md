# Normal Landing Gate

- status: **PASS**
- primary evidence: `logs\teacher_real_micro_20260803_030549_704516`
- primary Gate artifact: `artifacts\p36_teacher_real_gate_v9_reclassification_20260803_030549_v2.json`
- episodes / floors: 3 / `[2, 9, 7]`
- mean / median / Q25 / CVaR25: 6.000 / 7.000 / 4.500 / 2.000
- reach floor 3: 2/3
- reach floor 5: 2/3
- reach-3 check: True

The completed bounded natural run passes the current semantic Gate. This clears the three-episode micro Gate only; the single floor-2 lower-tail episode still requires the planned 10-episode stability Gate before P4.0 Student training.
