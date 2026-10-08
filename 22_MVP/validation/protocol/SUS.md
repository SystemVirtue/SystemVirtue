# System Usability Scale (SUS)

Administer after **each** condition. 5-point scale: 1 = strongly disagree,
5 = strongly agree. All ten items must be answered.

1. I think that I would like to use this system frequently.
2. I found the system unnecessarily complex.
3. I thought the system was easy to use.
4. I think that I would need the support of a technical person to be able to use this system.
5. I found the various functions in this system were well integrated.
6. I thought there was too much inconsistency in this system.
7. I would imagine that most people would learn to use this system very quickly.
8. I found the system very cumbersome to use.
9. I felt very confident using the system.
10. I needed to learn a lot of things before I could get going with this system.

## Scoring (computed automatically by `validation/metrics.py::score_sus`)

- Odd items (1,3,5,7,9): contribution = response − 1
- Even items (2,4,6,8,10): contribution = 5 − response
- Sum × 2.5 → 0–100. Reference: 68 is the historical average.

Record responses in `validation/out/questionnaires.json` under the
participant id, keyed `sus.systemvirtue` / `sus.baseline`.
