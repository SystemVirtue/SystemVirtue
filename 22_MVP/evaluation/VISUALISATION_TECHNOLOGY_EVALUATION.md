# Visualisation Technology Evaluation — SystemVirtue MVP

**Date:** 2026-10-09 · **Status:** decision record for UI visualisation scope
· **Governing docs:** `12_TECHNOLOGY_RESEARCH/TECHNOLOGY_LANDSCAPE.md`,
`06_VISUALISATION/VISUAL_PARADIGMS.md`, `15_TECHNICAL_SPECIFICATION` §3
("large visualisations must aggregate rather than render every entity").

## Selection criteria (from the package)

Scale, accessibility, interaction, mobile support, ecosystem maturity,
licence, maintenance cost, integration with semantic state — under the
overriding principle: **the least complex technology capable of satisfying
the validated requirement**. "Start with conventional accessible DOM/SVG
representations. Introduce GPU rendering only when measured scale requires
it." And from VISUAL_PARADIGMS: **the graph is never the only source of
meaning** — every visualisation must have an equivalent semantic text form
(architectural invariant 10).

## Measured reality (2026-10-09)

- Canonical store: 97 entities (82 curated + 15 live registry records),
  80+ relationships, 93+ claims.
- Scale test (`tests/test_scale.py`): 10× corpus (~820 entities) — bounded
  graph traversal and search both inside a 2 s budget; a depth-2 graph
  neighbourhood stays under 40 nodes by construction.

We are orders of magnitude below every GPU renderer's break-even point.

## Candidates

| Technology | Verdict at measured scale | Grounding |
| --- | --- | --- |
| DOM/SVG (current, vanilla, no deps) | **Keep now.** Real text nodes give free keyboard and screen-reader access; trivially testable; pain starts in the low thousands of elements. | Current implementation; Zhao et al. (2025), *Graph visualization efficiency of popular web-based libraries*, shows SVG trails GPU renderers on large graphs — irrelevant at current scale. |
| D3 (modules) | **Adopt techniques, packages later if ever.** Scales, hierarchy, axes; renderer-agnostic. Consider tree-shaken modules only when layout logic genuinely grows. | Mature (ISC); D3-based renders sit mid-pack in performance comparisons (Memgraph benchmarks). |
| Cytoscape.js | **Reserve** for when graph *interaction* becomes product-core (compound clusters, path finding, advanced layouts). MIT licence. | "Sluggish with large graphs (>10,000 elements), especially with complex layouts" (Linkurious, Ogma vs Cytoscape.js). |
| Sigma.js v3 (+ Graphology) | **Threshold-B choice** — WebGL network renderer, "considerably quicker in rendering bigger graphs" (Memgraph). Accessibility cost is real: pixel output requires a parallel DOM/table equivalent. MIT. | WebGL-based graph rendering pipeline. |
| deck.gl (WebGL2/WebGPU) | **Not MVP.** GPU framework "for visual exploratory data analysis of large datasets"; v9.4 substantially expands experimental WebGPU support (2026). Reserve for the million-entity ecosystem map (open question #7). | deck.gl docs / What's New 2026; OpenJS Foundation v9 announcement. |
| WebGPU charting (emerging libs) | **Watch only.** 1M+ point charts exist; tooling young; worst accessibility story (pixel output). | Community tooling 2025–2026. |
| React Flow | **No** — node-editor UX pattern, not analytics visualisation; would force a framework onto the vanilla stack. | — |

## Adoption ladder

Every rung keeps invariant 10: a text equivalent of every visualisation is
mandatory, interactions are keyboard-reachable, and no meaning is conveyed
by colour alone.

1. **Now (current state):** SVG + hand-rolled scales/aggregation, zero
   dependencies. Aggregation lives in `/api/overview`; charts are decorative
   (`aria-hidden`) over authoritative tables.
2. **Threshold A — ~1,000 rendered elements in one view (measured):** that
   view moves to Canvas 2D behind the same data contract; the table/list
   equivalent remains the accessible interface.
3. **Threshold B — ~5,000+ simultaneous nodes in one view:** Sigma.js v3
   (WebGL) for that view only, with mandatory DOM/table equivalent and
   keyboard navigation path.
4. **deck.gl / WebGPU:** research spike only if the ecosystem map grows
   toward million-entity scale (open question #7: optimal graph aggregation
   at million-entity scale). Not planned work.

Thresholds are literature-informed estimates to be validated by measurement
when first approached, not commitments.

## Consequences for the MVP

- No visualisation dependency is introduced at current scale; the expansion
  ships as vanilla SVG + pure aggregation code.
- The Ecosystem map and Changes & freshness views are data-table-first with
  decorative charts.
- The relationship view stays SVG with depth/zoom controls; a bounded
  neighbourhood is a requirement (`/api/graph?depth=`), not an accident.
- Revisit this document when any view approaches Threshold A.

## Sources

- Zhao et al. (2025). *Graph visualization efficiency of popular web-based
  libraries.* (peer-reviewed benchmark of web graph-visualisation libraries)
- Linkurious. *Ogma vs Cytoscape.js* — notes Cytoscape.js sluggishness
  beyond 10,000 elements.
- Memgraph. *You Want a Fast, Easy-To-Use, and Popular Graph Visualization
  Tool* — D3 mid-pack; WebGL (Sigma.js) faster on big graphs.
- deck.gl documentation and What's New (v9.4, 2026) — WebGPU expansion.
- Package criteria: `12_TECHNOLOGY_RESEARCH/TECHNOLOGY_LANDSCAPE.md`,
  `06_VISUALISATION/VISUAL_PARADIGMS.md`.
