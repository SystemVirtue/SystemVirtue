# NASA-TLX (cognitive load)

Administer after **each** condition. Rate each dimension 0–100
(0 = very low, 100 = very high). Use the unweighted average.

1. **Mental demand** — How much thinking, deciding, or remembering was required?
2. **Physical demand** — How much physical activity was required?
3. **Temporal demand** — How hurried or rushed was the pace?
4. **Performance** — How successful were you in accomplishing what you were asked?
5. **Effort** — How hard did you have to work to achieve your performance?
6. **Frustration** — How insecure, discouraged, irritated, or stressed did you feel?

Note: dimension 4 is conventionally inverted in reporting; this study records
raw values and reports the plain mean (computed by
`validation/metrics.py::score_nasa_tlx`).

Record responses in `validation/out/questionnaires.json` under the
participant id, keyed `nasa_tlx.systemvirtue` / `nasa_tlx.baseline`.
