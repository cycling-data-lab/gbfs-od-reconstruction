# gbfs-od-reconstruction

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/license/MIT)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Status: working draft](https://img.shields.io/badge/Status-working%20draft-orange.svg)](./paper.tex)
[![DOI](https://img.shields.io/badge/DOI-pending%20Zenodo-blue.svg)](./CITATION.cff)

> **Manuscript:** *Standard compliance bounds origin–destination
> identifiability in GBFS bike-sharing feeds: a cost-learning and
> sampling-horizon analysis.* Rohan Fossé and Gaël Pallares, CESI LINEACT
> (EA 7527), 2026. **In preparation for submission to *Computer Standards &
> Interfaces* (Elsevier).**

## What this is

Reconstructing origin–destination (OD) flows from public GBFS bike-sharing
feeds is split between two regimes — underdetermined inference from station
stock **counts**, and deterministic **tracking** of per-vehicle identifiers —
the latter exposed to temporal aliasing and to the privacy-driven identifier
rotation recommended by the GBFS standard. This work treats the
identifier-tracked sample not as ground truth but as a **partial empirical
sample that constrains the cost structure** of an entropic optimal-transport /
gravity model whose margins are pinned by the station counts, and asks when
the resulting OD is *identifiable* at all.

Two results frame the paper:

1. **The transport cost is identifiable only modulo additive station effects**,
   and the bias from incomplete observation equals the **non-separable**
   component of the log-selection probability. Station-emptiness censoring is
   separable and **cancels**; 60-second polling is **not** — its capture
   probability depends on travel time, the very quantity being estimated.
2. **A sampling-horizon law.** The continuous-collection time to reconstruct
   OD to accuracy `δ` scales as `δ⁻⁴` and inversely with the
   identifier-persistence rate `q`, giving a **standard-compliance threshold**
   `q_min` below which operational OD monitoring is infeasible.

## Headline result (fill from the pilot before going public)

| Quantity | Value |
|:---|:---:|
| Sampling-horizon law | `T* ∝ δ_OD⁻⁴ · q⁻¹ · Λ⁻¹ · λ_min⁻¹` |
| Standard-compliance threshold | `q_min` = _to estimate_ |
| French networks audited | _N to confirm_ |
| Identifier-persistence range `q` observed | _[lo, hi] from the 7-day pilot_ |

## What's in here

```text
gbfs-od-reconstruction/
├── paper.tex                     # Main manuscript (iopjournal class — see note below)
├── paper_si.tex                  # Supplementary Information (proofs)
├── iopjournal.cls                # IOP journal class (template default; switch to elsarticle for CS&I)
├── orcid.pdf                     # ORCID icon for the \orcid{} macro
├── cover_letter.md               # Cover-letter draft (CS&I)
├── .zenodo.json                  # Zenodo deposit metadata
├── CITATION.cff                  # Citation File Format
├── references/references.bib     # BibTeX (seeded with the core literature)
├── experiments/                  # d01 ... dNN numbered, reproducible
│   ├── _plot_style.py              # Paul Tol palette plot helper
│   ├── d01_pilot.py                # Feed pilot: estimate q, κ(Δ), β, γ, Λ → T*
│   └── README.md                   # Script-numbering convention + backbone
├── figures/                      # Publication figures (PDF)
├── outputs/                      # Per-experiment JSON / CSV / NPZ
├── drafts/                       # Design notes
└── README.md                     # This file
```

## Data dependency (read before running)

The vehicle-level collector and the OD literature review live in the sibling
**`bikeshare-data-explorer`** repository
(`utils/vehicle_collector.py`, `papers/od_reconstruction_litreview.md`). The
analysis here consumes per-day vehicle snapshots
(`free_bike_status` / `vehicle_status`, persistent `vehicle_id` + position)
produced by that collector.

> **Status:** as of the v0.1 scaffold, no vehicle snapshots have been
> accumulated yet. `experiments/d01_pilot.py` therefore runs on a synthetic
> feed by default and is the first thing to run against real data once a
> 7-day pilot of the collector has populated the snapshot store. The five
> constants `(q, κ, β, γ, Λ)` are feed-specific and **measured**, not assumed.

## Reproducing

```bash
# Build the manuscript
pdflatex paper.tex && bibtex paper && pdflatex paper.tex && pdflatex paper.tex

# Run the feed pilot (synthetic by default; --snapshots PATH for real data)
python3.12 experiments/d01_pilot.py
```

Master random seed `SEED = 42` in every stochastic script. Heavy caches are
not committed; they regenerate deterministically on first run.

## Submission: switching to `elsarticle`

This repo was scaffolded from the org's IOP `paper-template`, so it ships
`iopjournal.cls`. *Computer Standards & Interfaces* is an **Elsevier**
journal. Before submission:

1. `\documentclass[review,3p,times]{elsarticle}`.
2. Move title/authors/affiliations/abstract/keywords and the IOP back-matter
   macros (`\ack`, `\funding`, `\roles`, `\data`) into an
   `\begin{frontmatter} … \end{frontmatter}` block, plus a CRediT
   author-statement.
3. The body, theorems, equations and `references.bib` are class-agnostic and
   carry over unchanged.

## How to cite

Machine-readable citation in [`CITATION.cff`](./CITATION.cff). Plain BibTeX:

```bibtex
@unpublished{FossePallares2026GbfsOD,
  author = {Foss\'e, Rohan and Pallares, Ga\"el},
  title  = {Standard Compliance Bounds Origin--Destination Identifiability
            in {GBFS} Bike-Sharing Feeds},
  note   = {Manuscript in preparation, CESI LINEACT, 2026.
            \url{https://github.com/cycling-data-lab/gbfs-od-reconstruction}},
  year   = {2026}
}
```

## Sibling repos

- [gbfs-audit-catalogue](https://github.com/cycling-data-lab/gbfs-audit-catalogue) — the static feed-quality audit (Paper 01, *Computer Standards & Interfaces*); this paper is its dynamic-layer extension.
- [bikeshare-data-explorer](https://github.com/cycling-data-lab/bikeshare-data-explorer) — the GBFS collection infrastructure and the OD literature review.
- [bikeshare-demand-forecasting](https://github.com/cycling-data-lab/bikeshare-demand-forecasting) — demand prediction on the dock-based panel.
- [bikeshare-gsp-tools](https://github.com/cycling-data-lab/bikeshare-gsp-tools) — graph-signal-processing toolkit.

## License

[MIT](./LICENSE).

## Contact

Rohan Fossé — [rfosse@cesi.fr](mailto:rfosse@cesi.fr) — [ORCID](https://orcid.org/0009-0002-2195-0198)
Gaël Pallares — [ORCID](https://orcid.org/0009-0002-8680-604X)
