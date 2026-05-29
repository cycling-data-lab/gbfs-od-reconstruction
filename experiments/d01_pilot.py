"""
d01_pilot.py — Feed pilot for gbfs-od-reconstruction.

Estimates the five constants that govern the sampling-horizon law
(main text, Sec. "The sampling-horizon law")

    T* = dim_theta / ( lambda_min * delta_OD**4 * Lambda * kappa * q
                       * (1 - beta) * (1 - gamma) )

from identifier-tracked vehicle snapshots, and produces the thesis figure
T* vs q with the operational-monitoring frontier.

The five constants:
    q       identifier-persistence rate (IDs that persist origin -> destination)
    kappa   capture probability under the polling interval Delta (anti-aliasing)
    beta    rebalancing fraction (removed)
    gamma   GPS-jitter / collision loss
    Lambda  trip-generation rate (clean reconstructable trips per day)

Input  (real run):  per-day Parquet snapshots written by
    bikeshare-data-explorer/utils/vehicle_collector.py, schema
    [fetched_at, system_id, vehicle_id, lat, lon, station_id,
     is_disabled, is_reserved, vehicle_type_id].
    Pass --snapshots /path/to/data/vehicle_snapshots/<system_id>.

Input  (default):   a synthetic feed generator, so the data -> analysis ->
    figure pipeline is verifiable before any real snapshots exist.

Output:
    outputs/d01_pilot.json      structured per-feed constants + T* table
    figures/fig_d01_horizon.pdf thesis figure: T* vs q
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
FIG = ROOT / "figures"
OUT.mkdir(exist_ok=True)
FIG.mkdir(exist_ok=True)

sys.path.insert(0, str(ROOT / "experiments"))
from _plot_style import apply_paper_style, PALETTE, FIGSIZE  # noqa: E402

apply_paper_style()

SEED = 42

# Default sampling-horizon constants (see main text). Calibrated per-feed at run.
DIM_THETA = 6          # admissible dyadic cost features
LAMBDA_MIN = 1.0       # smallest eigenvalue of the projected feature Gram (well-conditioned)
DELTA_OD = 0.10        # target relative OD accuracy
T_MAX_DAYS = 180.0     # operational-monitoring horizon (frontier in the figure)
MIN_MOVE_M = 100.0     # GPS-jitter threshold for a real move
POLL_SEC = 60          # nominal polling interval Delta


# ── Sampling-horizon law ────────────────────────────────────────────────────

def horizon_days(q, Lambda, kappa, beta, gamma,
                 dim_theta=DIM_THETA, lambda_min=LAMBDA_MIN,
                 delta_od=DELTA_OD) -> float:
    """Required continuous-collection horizon T* in days (Theorem: horizon law)."""
    denom = (lambda_min * delta_od**4 * Lambda
             * kappa * q * (1.0 - beta) * (1.0 - gamma))
    return float("inf") if denom <= 0 else dim_theta / denom


# ── Synthetic feed (smoke test) ─────────────────────────────────────────────

def synthetic_snapshots(rng, n_vehicles=800, days=7, q_true=0.6,
                        beta_true=0.2, trips_per_veh_day=2.5,
                        poll_sec=POLL_SEC):
    """Simulate vehicle snapshots with ID rotation, rebalancing and 60s polling.

    Returns a list of "snapshot rows" (dict) mimicking the collector schema,
    plus the ground-truth trip count for sanity checks.
    """
    span_s = days * 86400
    rows = []
    true_trips = 0
    # Each physical vehicle generates a Poisson stream of trips; on each trip
    # its id is kept with prob q_true (persistent) or rotated (untrackable).
    for v in range(n_vehicles):
        base_id = f"veh{v:05d}"
        lat, lon = 48.85 + rng.normal(0, 0.02), 2.35 + rng.normal(0, 0.02)
        n_trips = rng.poisson(trips_per_veh_day * days)
        ts = np.sort(rng.uniform(0, span_s, size=n_trips))
        cur_id = base_id
        # initial parked observation
        rows.append(dict(t=0.0, vid=cur_id, lat=lat, lon=lon, is_disabled=False))
        for k, t0 in enumerate(ts):
            true_trips += 1
            is_rebal = rng.random() < beta_true
            # move to a new location
            dlat, dlon = rng.normal(0, 0.01), rng.normal(0, 0.01)
            lat, lon = lat + dlat, lon + dlon
            # id rotation breaks tracking for this trip
            if rng.random() > q_true:
                cur_id = f"veh{v:05d}r{k}"  # rotated -> new identifier
            # snapshot lands on the polling grid after arrival
            t_obs = (np.floor(t0 / poll_sec) + 1) * poll_sec
            rows.append(dict(t=float(t_obs), vid=cur_id, lat=lat, lon=lon,
                             is_disabled=is_rebal))
    return rows, true_trips, days


# ── Constant estimators ─────────────────────────────────────────────────────

def _haversine_m(lat1, lon1, lat2, lon2):
    R = 6_371_000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi, dlmb = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def reconstruct_and_estimate(rows, days, poll_sec=POLL_SEC,
                             min_move_m=MIN_MOVE_M):
    """Reconstruct moves and estimate (q, beta, gamma, Lambda).

    A move is a same-id consecutive displacement >= min_move_m. q is the share
    of moves that remain id-linked relative to all true displacements (here,
    proxied by the linked/(linked+unlinked-reappearance) ratio); beta the
    is_disabled fraction; gamma the sub-min_move (jitter) share; Lambda the
    linked clean trips per day.
    """
    # group rows by vehicle id, ordered in time
    by_id: dict[str, list] = {}
    for r in rows:
        by_id.setdefault(r["vid"], []).append(r)
    linked_moves = 0
    rebal = 0
    jitter = 0
    for vid, seq in by_id.items():
        seq.sort(key=lambda r: r["t"])
        for a, b in zip(seq[:-1], seq[1:]):
            d = _haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
            if d < min_move_m:
                jitter += 1
                continue
            linked_moves += 1
            if b["is_disabled"] or a["is_disabled"]:
                rebal += 1
    # ids that appear only once and then vanish => rotation-broken trips
    rotated = sum(1 for seq in by_id.values() if len(seq) == 1)
    total_disp = linked_moves + rotated
    q_hat = linked_moves / total_disp if total_disp else 0.0
    beta_hat = rebal / linked_moves if linked_moves else 0.0
    gamma_hat = jitter / (linked_moves + jitter) if (linked_moves + jitter) else 0.0
    clean = linked_moves * (1 - beta_hat)
    Lambda_hat = clean / days if days else 0.0
    return dict(q=q_hat, beta=beta_hat, gamma=gamma_hat, Lambda=Lambda_hat,
                linked_moves=linked_moves, rotated=rotated)


def aliasing_curve(rows, days, intervals=(60, 120, 300, 600)):
    """kappa(Delta): fraction of 60s-linked moves still recovered when the
    feed is thinned to a coarser polling interval. The estimand-correlated
    (non-separable) loss the paper warns about."""
    base = reconstruct_and_estimate(rows, days, poll_sec=60)["linked_moves"]
    curve = {}
    for dt in intervals:
        thinned = [r for r in rows if (int(r["t"]) % dt) == 0 or r["t"] == 0.0]
        m = reconstruct_and_estimate(thinned, days, poll_sec=dt)["linked_moves"]
        curve[dt] = (m / base) if base else 0.0
    return curve


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshots", type=str, default=None,
                    help="Path to a real vehicle_snapshots/<system> dir "
                         "(Parquet/day). Default: synthetic feed.")
    args = ap.parse_args()

    t0 = time.time()
    print("=" * 72)
    print("d01_pilot — estimate (q, kappa, beta, gamma, Lambda) -> T*")
    print("=" * 72)
    rng = np.random.default_rng(SEED)

    if args.snapshots:
        # Real-data path is deferred: load Parquet snapshots, then call the
        # same estimators on the reconstructed rows.
        raise NotImplementedError(
            "Real-data loading lands once the 7-day collector pilot has "
            "populated vehicle_snapshots/. Run without --snapshots for the "
            "synthetic smoke test.")

    rows, true_trips, days = synthetic_snapshots(rng)
    est = reconstruct_and_estimate(rows, days)
    kappa_curve = aliasing_curve(rows, days)
    kappa60 = kappa_curve[60]

    Tstar = horizon_days(q=est["q"], Lambda=est["Lambda"], kappa=kappa60,
                         beta=est["beta"], gamma=est["gamma"])
    print(f"  q={est['q']:.3f}  beta={est['beta']:.3f}  gamma={est['gamma']:.3f}"
          f"  Lambda={est['Lambda']:.1f}/day  kappa(60s)={kappa60:.3f}",
          flush=True)
    print(f"  true trips simulated = {true_trips}, "
          f"linked={est['linked_moves']}, rotated={est['rotated']}", flush=True)
    print(f"  => T* = {Tstar:.1f} days (delta_OD={DELTA_OD}, "
          f"dim_theta={DIM_THETA}, T_max={T_MAX_DAYS:.0f})", flush=True)

    result = dict(
        seed=SEED, synthetic=True, days=days, true_trips=int(true_trips),
        constants=est, aliasing_curve=kappa_curve,
        law=dict(dim_theta=DIM_THETA, lambda_min=LAMBDA_MIN,
                 delta_od=DELTA_OD, t_max_days=T_MAX_DAYS),
        Tstar_days=Tstar,
    )
    out_path = OUT / "d01_pilot.json"
    out_path.write_text(json.dumps(result, indent=2))
    print(f"  ✓ saved {out_path.name}", flush=True)

    # Thesis figure: T* vs q, for a few Lambda, with the operational frontier.
    q_grid = np.linspace(0.05, 1.0, 80)
    fig, ax = plt.subplots(figsize=FIGSIZE["single"])
    for k, Lam in enumerate((500, 3000, 10000)):
        T = [horizon_days(q=q, Lambda=Lam, kappa=kappa60,
                          beta=est["beta"], gamma=est["gamma"]) for q in q_grid]
        ax.plot(q_grid, T, color=PALETTE[k], lw=1.8,
                label=fr"$\Lambda={Lam}$ trips/day")
    ax.axhline(T_MAX_DAYS, color="0.35", ls="--", lw=1.0,
               label=f"operational frontier ({T_MAX_DAYS:.0f} d)")
    ax.axvline(est["q"], color=PALETTE[3], ls=":", lw=1.0,
               label=fr"pilot $\hat q={est['q']:.2f}$")
    ax.set_yscale("log")
    ax.set_xlabel(r"identifier-persistence rate $q$")
    ax.set_ylabel(r"required collection horizon $T^\star$ (days)")
    ax.set_title(r"Sampling-horizon law $T^\star \propto \delta^{-4} q^{-1}$")
    ax.legend(loc="upper right", fontsize=7)
    plt.tight_layout()
    fig_path = FIG / "fig_d01_horizon.pdf"
    plt.savefig(fig_path)
    plt.close(fig)
    print(f"  ✓ saved {fig_path.name}", flush=True)

    print(f"\n✓ d01 done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
