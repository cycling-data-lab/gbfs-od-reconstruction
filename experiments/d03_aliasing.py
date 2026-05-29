"""
d03_aliasing.py — The aliasing curve κ(Δ): how polling cadence attenuates the
cost–distance relationship (empirical support for main-text Corollary 4).

Corollary 4 states that the polling bias is non-separable AND correlated with
the estimand: a trip is resolvable only if it lasts longer than the polling
interval Δ, and duration t ∝ distance, so coarser polling preferentially drops
SHORT trips and flattens the recovered deterrence (distance) coefficient. This
script demonstrates that two ways.

(A) Synthetic, mechanism-isolating.
    Trip distances follow the gravity deterrence d ~ Exp(beta_true) (mean
    1/beta_true metres). At interval Δ a trip is resolvable only if its duration
    t = d/v exceeds Δ, i.e. distances below d_min(Δ) = v·Δ are lost. A downstream
    analyst who fits beta naively to the surviving (left-truncated) sample
    recovers
        beta_hat(Δ) = 1 / mean(d | d >= d_min) = beta_true / (1 + beta_true·v·Δ),
    a monotone ATTENUATION toward 0 as Δ grows. We confirm the empirical
    estimator matches this closed form — even the 60 s "favourable" cadence
    already attenuates the coefficient.

(B) Real validation on a PERSISTENT feed (q ≈ 1).
    Re-reconstruct linked trips at the native 60 s grid, then at subsampled grids
    (keep every k-th snapshot), and report the retention
    κ(kΔ) = n_trips(kΔ)/n_trips(Δ) and the upward shift of the mean recovered
    move distance (short trips vanish first) — validating mechanism (A) on data.

Output:
    outputs/d03_aliasing.json     synthetic + real curves
    outputs/d03_aliasing.csv      flat per-interval table
    figures/fig_d03_aliasing.pdf  two panels (only if matplotlib importable)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
FIG = ROOT / "figures"
OUT.mkdir(exist_ok=True)
FIG.mkdir(exist_ok=True)

sys.path.insert(0, str(ROOT / "experiments"))
from d02_persistence_audit import load_feed, _haversine_m   # noqa: E402

SEED = 42

V_MPS = 4.0                      # cycling speed ~14.4 km/h (duration = distance/v)
BETA_TRUE = 1.0 / 1500.0         # gravity deterrence: mean trip 1500 m
SYN_DELTAS = (60, 120, 180, 300, 600, 900)   # polling intervals to probe (s)
REAL_STRIDES = (1, 2, 3, 5, 10)              # keep every k-th 60 s snapshot
MIN_MOVE_M = 100.0


# ── (A) Synthetic attenuation ─────────────────────────────────────────────────

def synthetic_attenuation(rng, n=400_000) -> list[dict]:
    d = rng.exponential(1.0 / BETA_TRUE, size=n)          # distances ~ Exp(beta)
    rows = []
    for D in SYN_DELTAS:
        d_min = V_MPS * D                                  # distances below this are aliased away
        kept = d[d >= d_min]
        kappa = len(kept) / n
        beta_hat = (1.0 / float(kept.mean())) if len(kept) > 10 else None
        analytic = BETA_TRUE / (1.0 + BETA_TRUE * d_min)   # closed form
        rows.append(dict(
            delta_s=int(D), d_min_m=round(d_min, 1), kappa=round(kappa, 4),
            beta_hat=None if beta_hat is None else beta_hat,
            beta_ratio=None if beta_hat is None else round(beta_hat / BETA_TRUE, 4),
            analytic_ratio=round(analytic / BETA_TRUE, 4),
        ))
    return rows


# ── (B) Real κ(Δ) on a persistent feed ────────────────────────────────────────

def _linked_at_stride(df: pd.DataFrame, uniq: np.ndarray, k: int) -> tuple[int, list[float]]:
    """Count linked trips and their move distances when only every k-th snapshot
    is kept (an effective polling interval of k·poll)."""
    fr = np.searchsorted(uniq, df["fetched_at"].to_numpy())   # rank on full grid
    mask = (fr % k) == 0
    sub = df.loc[mask].copy()
    sub["krank"] = fr[mask] // k                              # rank on the kept grid
    n_linked = 0
    dists: list[float] = []
    for _vid, g in sub.sort_values(["vehicle_id", "krank"]).groupby("vehicle_id", sort=False):
        kr = g["krank"].to_numpy()
        lat = g["lat"].to_numpy(dtype=float)
        lon = g["lon"].to_numpy(dtype=float)
        for a in range(len(kr) - 1):
            if kr[a + 1] - kr[a] > 1:                         # absent across >=1 kept poll
                n_linked += 1
                if not (np.isnan(lat[a]) or np.isnan(lon[a])
                        or np.isnan(lat[a + 1]) or np.isnan(lon[a + 1])):
                    m = _haversine_m(lat[a], lon[a], lat[a + 1], lon[a + 1])
                    if m >= MIN_MOVE_M:
                        dists.append(float(m))
    return n_linked, dists


def real_aliasing(feed_dir: Path) -> dict:
    df, n_files = load_feed(feed_dir)
    if df.empty:
        return {"feed": feed_dir.name, "status": "empty"}
    df["fetched_at"] = pd.to_datetime(df["fetched_at"], utc=True, errors="coerce")
    df = df.dropna(subset=["fetched_at", "vehicle_id"])
    df = df.drop_duplicates(subset=["vehicle_id", "fetched_at"])
    all_t = df["fetched_at"].to_numpy()
    uniq = np.unique(all_t)
    T = len(uniq)
    deltas = np.diff(uniq) / np.timedelta64(1, "s")
    poll_s = float(np.median(deltas[deltas > 0])) if T >= 2 else float("nan")

    base_linked = None
    curve = []
    for k in REAL_STRIDES:
        if T // k < 5:
            continue
        n_linked, dists = _linked_at_stride(df, uniq, k)
        if k == 1:
            base_linked = n_linked
        curve.append(dict(
            stride=int(k), eff_delta_s=None if np.isnan(poll_s) else round(poll_s * k, 1),
            n_linked=int(n_linked),
            kappa=None if not base_linked else round(n_linked / base_linked, 4),
            mean_move_m=round(float(np.mean(dists)), 1) if dists else None,
            median_move_m=round(float(np.median(dists)), 1) if dists else None,
        ))
    return {"feed": feed_dir.name, "status": "ok", "n_files": n_files,
            "n_snapshots": int(T), "poll_s": None if np.isnan(poll_s) else round(poll_s, 1),
            "n_vehicles": int(df["vehicle_id"].nunique()), "curve": curve}


# ── Figure (optional) ─────────────────────────────────────────────────────────

def make_figure(syn: list[dict], real: dict | None) -> str | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"  [info] matplotlib unavailable ({type(e).__name__}); skipping figure.",
              flush=True)
        return None
    npan = 2 if (real and real.get("status") == "ok") else 1
    fig, axes = plt.subplots(1, npan, figsize=(3.4 * npan, 3.0))
    axes = np.atleast_1d(axes)
    ax = axes[0]
    D = [r["delta_s"] for r in syn]
    ax.plot(D, [r["beta_ratio"] for r in syn], "o-", color="#EE6677", label=r"empirical $\hat\beta/\beta$")
    ax.plot(D, [r["analytic_ratio"] for r in syn], "--", color="#4477AA", label="closed form")
    ax.set_xlabel(r"polling interval $\Delta$ (s)")
    ax.set_ylabel(r"distance-coefficient ratio")
    ax.set_ylim(0, 1.02)
    ax.set_title("(A) synthetic attenuation")
    ax.legend(fontsize=7)
    if npan == 2:
        ax2 = axes[1]
        c = [r for r in real["curve"] if r.get("kappa") is not None]
        ax2.plot([r["eff_delta_s"] for r in c], [r["kappa"] for r in c], "s-",
                 color="#228833", label=r"$\kappa(\Delta)$ retention")
        ax2.set_xlabel(r"effective interval $\Delta$ (s)")
        ax2.set_ylabel(r"trip retention $\kappa$")
        ax2.set_ylim(0, 1.02)
        ax2.set_title(f"(B) real feed: {real['feed']}")
        ax2.legend(fontsize=7)
    fig.tight_layout()
    path = FIG / "fig_d03_aliasing.pdf"
    fig.savefig(path)
    plt.close(fig)
    return str(path.name)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshots", type=str, default=None,
                    help="vehicle_snapshots/ root (for the real-feed validation).")
    ap.add_argument("--feed", type=str, default=None,
                    help="system_id of a PERSISTENT feed to validate on (e.g. capcotentin).")
    args = ap.parse_args()

    t0 = time.time()
    print("=" * 72)
    print("d03_aliasing — κ(Δ): polling cadence vs the cost–distance coefficient")
    print("=" * 72)
    rng = np.random.default_rng(SEED)

    syn = synthetic_attenuation(rng)
    print("  (A) synthetic attenuation of the distance coefficient:")
    for r in syn:
        print(f"    Δ={r['delta_s']:>4}s  d_min={r['d_min_m']:>7.0f}m  "
              f"κ={r['kappa']:.3f}  β̂/β={r['beta_ratio']}  (closed form {r['analytic_ratio']})",
              flush=True)

    real = None
    if args.snapshots and args.feed:
        feed_dir = Path(args.snapshots).expanduser() / args.feed
        if not feed_dir.exists():
            print(f"  ERROR: feed dir not found: {feed_dir}", file=sys.stderr)
            sys.exit(2)
        print(f"\n  (B) real validation on persistent feed '{args.feed}':", flush=True)
        real = real_aliasing(feed_dir)
        if real.get("status") == "ok":
            for r in real["curve"]:
                print(f"    stride={r['stride']:>2} (Δ≈{r['eff_delta_s']}s)  "
                      f"trips={r['n_linked']:>5}  κ={r['kappa']}  "
                      f"mean_move={r['mean_move_m']}m", flush=True)
        else:
            print(f"    {real.get('status')}", flush=True)

    result = dict(seed=SEED, params=dict(v_mps=V_MPS, beta_true=BETA_TRUE,
                  syn_deltas=list(SYN_DELTAS), real_strides=list(REAL_STRIDES)),
                  synthetic=syn, real=real)
    (OUT / "d03_aliasing.json").write_text(json.dumps(result, indent=2))
    flat = pd.DataFrame(syn); flat.insert(0, "part", "synthetic")
    if real and real.get("status") == "ok":
        rc = pd.DataFrame(real["curve"]); rc.insert(0, "part", f"real:{real['feed']}")
        flat = pd.concat([flat, rc], ignore_index=True)
    flat.to_csv(OUT / "d03_aliasing.csv", index=False)
    print(f"\n  ✓ wrote d03_aliasing.json and d03_aliasing.csv", flush=True)

    fig = make_figure(syn, real)
    if fig:
        print(f"  ✓ wrote {fig}", flush=True)
    print(f"\n✓ d03 done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
