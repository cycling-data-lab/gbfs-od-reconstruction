"""
_plot_style.py — Centralised publication-quality plot style for the
materials-applicability-bound figures.

Design principles (Nature/Science/IOP conventions, 2026 best
practice) :
  - Sans-serif figure font (Liberation Sans / DejaVu Sans, falls back
    cleanly across systems) regardless of the paper's LaTeX serif body.
    This is the modern journal convention : figures read better at
    small print sizes with sans-serif.
  - Colourblind-safe Paul Tol "bright" palette (7 high-contrast
    colours) as the default cycle.  Validated under all three common
    forms of colour-vision deficiency.
  - Minimal chartjunk : only left + bottom spines, light grid at
    α = 0.25, no ticks on the inactive spines.
  - Larger, cleaner type : 10 pt axis labels, 11 pt titles, 9 pt
    tick labels.  Standard for two-column journal layouts.
  - Robust math typesetting via mathtext (no LaTeX dependency for
    PDF rendering — keeps build fast and portable).
  - Higher default linewidths and marker sizes for legibility at
    PDF zoom levels typical of reviewer screens.

Usage in a figure script :

    from _plot_style import apply_paper_style, PALETTE, FIGSIZE
    apply_paper_style()
    ...
    fig, ax = plt.subplots(figsize=FIGSIZE["single"])
    ax.plot(x, y, color=PALETTE[0])
"""
from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt

# Paul Tol "bright" palette — colourblind-safe up to deuteranopia and
# protanopia ; high contrast on white background.
# https://personal.sron.nl/~pault/data/colourschemes.pdf
PALETTE = [
    "#4477AA",  # blue
    "#EE6677",  # red
    "#228833",  # green
    "#CCBB44",  # yellow
    "#66CCEE",  # light blue
    "#AA3377",  # purple
    "#BBBBBB",  # grey
]

# A dedicated palette for the chem / random / ElMD / shuffled-knn trio
# used across §sec:circularity-check.  Chem stays the headline blue,
# null is muted grey, ElMD is the green third option.
NULL_COLOURS = {
    "chem":     "#4477AA",
    "ElMD":     "#228833",
    "random":   "#BBBBBB",
    "shuffled": "#AA3377",
}

# Standard figure sizes (inches) keyed to journal column widths.
# Most physics journals use 3.4 in (single-column) and 7.0 in (double-
# column) ; we provide both.
FIGSIZE = {
    "single":  (3.5, 2.6),
    "wide":    (5.5, 3.4),     # 1.5 columns
    "double":  (7.2, 4.4),     # 2 columns, standard aspect
    "double_short": (7.2, 3.0),
    "double_tall":  (7.2, 5.5),
    "square":  (4.0, 4.0),
}


def apply_paper_style():
    """Apply the global rcParams once at the top of a figure script.
    Idempotent — safe to call multiple times."""
    # Start from a clean modern base, then override.
    try:
        plt.style.use("seaborn-v0_8-whitegrid")
    except OSError:
        plt.style.use("default")

    mpl.rcParams.update({
        # === Fonts ===
        "font.family": "sans-serif",
        "font.sans-serif": [
            "Liberation Sans", "Source Sans Pro", "DejaVu Sans",
            "Arial", "Helvetica", "sans-serif",
        ],
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,
        "legend.title_fontsize": 9,
        "mathtext.fontset": "dejavusans",
        "mathtext.default": "regular",

        # === Lines & markers ===
        "lines.linewidth": 1.6,
        "lines.markersize": 5.5,
        "lines.markeredgewidth": 0.8,
        "patch.linewidth": 0.8,

        # === Axes / spines ===
        "axes.linewidth": 0.8,
        "axes.edgecolor": "#333333",
        "axes.labelcolor": "#222222",
        "axes.titleweight": "regular",
        "axes.titlepad": 8,
        "axes.labelpad": 4,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.prop_cycle": mpl.cycler(color=PALETTE),

        # === Grid ===
        "axes.grid": True,
        "axes.grid.axis": "both",
        "grid.color": "#CCCCCC",
        "grid.linestyle": "-",
        "grid.linewidth": 0.5,
        "grid.alpha": 0.5,

        # === Ticks ===
        "xtick.color": "#444444",
        "ytick.color": "#444444",
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.size": 3.5,
        "ytick.major.size": 3.5,
        "xtick.major.width": 0.7,
        "ytick.major.width": 0.7,
        "xtick.minor.size": 0,  # disable minor ticks by default
        "ytick.minor.size": 0,

        # === Legend ===
        "legend.frameon": True,
        "legend.framealpha": 0.92,
        "legend.edgecolor": "#CCCCCC",
        "legend.fancybox": False,
        "legend.borderpad": 0.5,

        # === Output ===
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.05,
        "figure.dpi": 110,
        "figure.facecolor": "white",
        "figure.edgecolor": "white",
        "pdf.fonttype": 42,   # TrueType (editable text in PDF)
        "ps.fonttype": 42,
    })
