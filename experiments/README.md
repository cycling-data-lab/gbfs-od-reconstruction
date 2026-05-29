# `experiments/` — numbered, reproducible scripts

Every experimental result reported in the manuscript is produced by exactly
one numbered script in this directory. The convention:

```
d{NN}_{short_name}.py
```

where:

- `NN` is a zero-padded two-digit number (`d01`, `d02`, …). Numbering reflects
  the **order in which experiments were added**, not their order in the paper.
- `short_name` is a short snake_case description (e.g. `d01_pilot`,
  `d03_aliasing_curve`).

## What every script must do

1. **Read from a known cache directory** (`outputs/` by default).
2. **Pin `SEED = 42`** in every stochastic step.
3. **Write structured output** to `outputs/d{NN}_{short_name}.{json,csv,npz}`.
4. **Print one line of progress per step** (`flush=True` on long runs).
5. **Document non-trivial design decisions in the header docstring.**

## Recommended numbered backbone (this paper)

| ID  | Purpose | Notes |
|:---:|:---|:---|
| d01 | Feed pilot: estimate `(q, κ, β, γ, Λ)` → `T*`; thesis figure `T*` vs `q` | Synthetic smoke test until the collector pilot lands |
| d02 | Identifier-persistence audit across all French feeds | `q̂` feed-by-feed (the critical, bimodal constant) |
| d03 | Aliasing curve `κ(Δ)` by interval subsampling | Quantifies the non-separable, estimand-correlated loss |
| d04 | Admissible cost features + projected Gram `λ_min` | Two-way-centred dyadic features (distance, directed elevation, circuity, protected-lane, barriers) |
| d05 | Inverse-OT cost estimation from the tracked micro-sample | Ground-metric learning, mod-𝒩 |
| d06 | Forward entropic-OT reconstruction under censored margins | Sinkhorn; report the comparability/precision tension in ε |
| d07 | Per-network `T*` table + figure generator | Reads d02–d06, writes `figures/*.pdf` |
| ... | (extend as the paper grows) | |

## Plot style

All figures import `_plot_style.py` and call `apply_paper_style()` at the top
(Paul Tol bright palette, colour-blind safe). See `d01_pilot.py` for the
pattern.

## Cache files

Caches live under `outputs/_*.npz` / `outputs/_*.parquet` and are
`.gitignore`d; the first run of a downstream script regenerates them
deterministically. Per-run logs go under `logs/` (also gitignored).
