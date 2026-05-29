"""
d02_persistence_audit.py — Identifier-persistence audit across French feeds.

Estimates, feed by feed, the identifier-persistence rate q — the single most
important and most bimodal constant in the sampling-horizon law (main text,
Sec. "The sampling-horizon law"; q enters T* as 1/q). q is the probability
that a vehicle's identifier survives a trip, so that the trip is recoverable
by disappearance->reappearance tracking.

How q is measured from a snapshot store (no ground truth needed)
----------------------------------------------------------------
A vehicle parked in a `free_bike_status` / `vehicle_status` feed is reported
under a stable identifier in every poll. When rented it leaves the feed; on
return it reappears. Two regimes:

  * persistent identifier  -> the SAME id reappears (a "linked" disappearance):
    the id's observation times show an internal gap.
  * rotating identifier (GBFS v2.0 privacy guidance) -> the id never returns;
    it terminates, and a fresh id appears for the returned vehicle.

Events are measured by RANK over the observed poll grid (the sorted distinct
fetch instants of this feed), which is robust to the dominant real-world
artifact: a *missed collection poll*. A poll the collector skipped simply is
not a grid instant, so two observations straddling it stay rank-adjacent and do
NOT fake a trip — whereas snapping to a fixed clock or differencing elapsed time
would count every missed poll as a disappearance for every vehicle (verified on
live data: feeds that lost one poll otherwise reported q=1.0 spuriously, with
linked == n_vehicles). Let grid rank r(t) index the distinct fetch instants
0..T-1. For each id:

  * a "linked disappearance" = consecutive observations whose grid ranks differ
    by more than 1 (the id was absent across >= 1 poll the feed still served to
    other vehicles, then came back);
  * a "terminal disappearance" = the id's last observation has rank
    <= T-1-REAPPEAR_MARGIN_POLLS (it vanished with room to have returned, and
    did not).

    q_hat = linked / (linked + terminal)

Blind spot (documented): a window in which EVERY vehicle is simultaneously out
produces no grid instant, so a trip spanning it is missed. This is implausible
for feeds with many vehicles but real for tiny ones, so q on feeds with
< MIN_VEHICLES_RELIABLE vehicles is flagged low-confidence (q_reliable=False).
`n_grid_gaps` reports detected missed polls.

The MIN_MOVE_M distance threshold is a DIAGNOSTIC only (reported as
`frac_linked_moved`); it does NOT gate q, so the numerator and denominator are
treated symmetrically. Duplicate (vehicle_id, fetched_at) rows — which the
collector can emit on a restart via its unconditional concat-append — are
dropped first.

Caveats (reported, not hidden): terminal disappearances conflate identifier
rotation with vehicles taken offline / moved to a depot, and a short collection
window right-censors long trips (a vehicle still out at the end looks terminal),
so q_hat is a *lower bound* on persistence — strongest as a discriminator
(rotating ~0 vs persistent high), tightened by multi-day data. Robust companion
signals are reported: mean observations per id and the fraction of ids seen once.

Input  (real run):  --snapshots PATH pointing at a vehicle_snapshots/ store
    (one dir per system_id, Parquet/day) written by
    bikeshare-data-explorer/utils/vehicle_collector.py, schema
    [fetched_at, system_id, vehicle_id, lat, lon, station_id,
     is_disabled, is_reserved, vehicle_type_id].

Input  (default):   a synthetic two-feed store (one persistent, one rotating),
    so the audit pipeline is verifiable before / without real data.

Output:
    outputs/d02_persistence_audit.csv     one row per feed
    outputs/d02_persistence_audit.json    summary + run metadata
    figures/fig_d02_persistence.pdf       q_hat per feed (only if matplotlib
                                           is importable; skipped otherwise)
"""
from __future__ import annotations

import argparse
import json
import math
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

SEED = 42

# Audit parameters
MIN_MOVE_M = 100.0            # DIAGNOSTIC only (frac_linked_moved); does NOT gate q
POLL_GAP_FACTOR = 1.5         # inter-snapshot delta > factor*poll_s => a missed poll
REAPPEAR_MARGIN_POLLS = 10    # terminal needs this many grid ranks of remaining window
MIN_SNAPSHOTS = 12            # must exceed REAPPEAR_MARGIN_POLLS+1, else q undefined
MIN_VEHICLES_RELIABLE = 20    # below this, all-out outages plausible -> q low-confidence
ROTATING_MAX = 0.20           # q_hat below -> "rotating" (privacy-compliant)
PERSISTENT_MIN = 0.60         # q_hat at/above -> "persistent" (trackable)

VEHICLE_COLS = ["fetched_at", "vehicle_id", "lat", "lon", "is_disabled"]


# ── Geometry ────────────────────────────────────────────────────────────────

def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ── Per-feed audit ──────────────────────────────────────────────────────────

def audit_feed(df: pd.DataFrame, system_id: str) -> dict:
    """Compute persistence statistics for one feed from its snapshot rows."""
    rec = {"system_id": system_id, "n_obs": int(len(df))}
    if df.empty:
        rec.update(status="empty", q_hat=None, persistence_class="undetermined")
        return rec

    df = df.copy()
    df["fetched_at"] = pd.to_datetime(df["fetched_at"], utc=True, errors="coerce")
    df = df.dropna(subset=["fetched_at", "vehicle_id"])
    # Drop duplicate (vehicle_id, fetched_at) rows: the collector re-appends a
    # whole snapshot on restart/retry (vehicle_collector.py concat), which would
    # otherwise double observation counts.
    df = df.drop_duplicates(subset=["vehicle_id", "fetched_at"])
    if "is_disabled" not in df.columns:
        df["is_disabled"] = False
    df["is_disabled"] = df["is_disabled"].fillna(False).astype(bool)
    rec["n_obs_dedup"] = int(len(df))

    # Snapshot timeline in real time (datetime64[us] after to_numpy, UTC).
    all_t = df["fetched_at"].to_numpy()
    uniq = np.unique(all_t)              # sorted unique poll instants
    T = len(uniq)
    n_vehicles = int(df["vehicle_id"].nunique())
    feed_end = all_t.max()
    span_min = float((feed_end - all_t.min()) / np.timedelta64(1, "m")) if T > 1 else 0.0

    poll_s = float("nan")
    if T >= 2:
        deltas = np.diff(uniq) / np.timedelta64(1, "s")
        pos = deltas[deltas > 0]
        if pos.size:
            poll_s = float(np.median(pos))

    rec.update(n_snapshots=int(T), n_vehicles=n_vehicles,
               span_min=round(span_min, 1),
               poll_s=None if math.isnan(poll_s) else round(poll_s, 1))

    if T < MIN_SNAPSHOTS or math.isnan(poll_s) or poll_s <= 0:
        rec.update(status="insufficient_snapshots", q_hat=None, linked=0, terminal=0,
                   beta_hat=None, frac_linked_moved=None, lambda_per_day=None,
                   mean_obs_per_vehicle=round(len(df) / max(n_vehicles, 1), 2),
                   frac_seen_once=None, persistence_class="undetermined")
        return rec

    safe_rank = T - 1 - REAPPEAR_MARGIN_POLLS
    n_grid_gaps = int(np.sum(deltas > POLL_GAP_FACTOR * poll_s))  # missed collection polls

    linked = 0          # id absent across >=1 served poll, then reappeared (same id)
    linked_moved = 0    # of those, moved >= MIN_MOVE_M (diagnostic)
    linked_rebal = 0    # of those, touched is_disabled (rebalancing proxy)
    terminal = 0        # id's last obs at rank <= safe_rank, never returned
    seen_once = 0
    obs_counts: list[int] = []

    df = df.sort_values(["vehicle_id", "fetched_at"])
    for _vid, g in df.groupby("vehicle_id", sort=False):
        ot = g["fetched_at"].to_numpy()
        ranks = np.searchsorted(uniq, ot)             # position in the observed poll grid
        lat = g["lat"].to_numpy(dtype=float)
        lon = g["lon"].to_numpy(dtype=float)
        dis = g["is_disabled"].to_numpy()
        obs_counts.append(len(ot))
        if len(ot) == 1:
            seen_once += 1
        for a in range(len(ranks) - 1):
            if ranks[a + 1] - ranks[a] > 1:           # absent across >=1 served poll
                linked += 1
                if bool(dis[a]) or bool(dis[a + 1]):
                    linked_rebal += 1
                if not (np.isnan(lat[a]) or np.isnan(lon[a])
                        or np.isnan(lat[a + 1]) or np.isnan(lon[a + 1])):
                    if _haversine_m(lat[a], lon[a], lat[a + 1], lon[a + 1]) >= MIN_MOVE_M:
                        linked_moved += 1
        if ranks[-1] <= safe_rank:                    # terminal disappearance
            terminal += 1

    denom = linked + terminal
    q_hat = (linked / denom) if denom > 0 else None
    beta_hat = (linked_rebal / linked) if linked > 0 else None
    frac_moved = (linked_moved / linked) if linked > 0 else None
    days = span_min / (60.0 * 24.0)
    lambda_per_day = (linked / days) if days > 0 else None
    obs_arr = np.asarray(obs_counts)
    frac_once = seen_once / n_vehicles if n_vehicles else None

    if q_hat is None:
        cls = "undetermined"
    elif q_hat < ROTATING_MAX:
        cls = "rotating"
    elif q_hat >= PERSISTENT_MIN:
        cls = "persistent"
    else:
        cls = "mixed"

    rec.update(
        status="ok",
        q_hat=None if q_hat is None else round(q_hat, 4),
        q_reliable=bool(q_hat is not None and n_vehicles >= MIN_VEHICLES_RELIABLE),
        linked=int(linked), terminal=int(terminal),
        n_grid_gaps=int(n_grid_gaps),
        beta_hat=None if beta_hat is None else round(beta_hat, 4),
        frac_linked_moved=None if frac_moved is None else round(frac_moved, 4),
        lambda_per_day=None if lambda_per_day is None else round(lambda_per_day, 1),
        mean_obs_per_vehicle=round(float(obs_arr.mean()), 2),
        frac_seen_once=None if frac_once is None else round(frac_once, 4),
        persistence_class=cls,
    )
    return rec


# ── Store loading ───────────────────────────────────────────────────────────

def load_feed(system_dir: Path) -> tuple[pd.DataFrame, int]:
    """Concatenate the per-day Parquet snapshots of one system directory."""
    files = sorted(system_dir.glob("????-??-??.parquet"))
    frames = []
    for f in files:
        try:
            frames.append(pd.read_parquet(f, columns=list(VEHICLE_COLS)))
        except Exception:
            try:
                frames.append(pd.read_parquet(f))   # fall back to all columns
            except Exception as e:
                print(f"      [warn] {f.name}: {type(e).__name__}: {e}", flush=True)
    if not frames:
        return pd.DataFrame(), 0
    return pd.concat(frames, ignore_index=True), len(files)


def audit_store(snapshots_root: Path) -> list[dict]:
    rows = []
    systems = sorted(d for d in snapshots_root.iterdir() if d.is_dir())
    print(f"  scanning {len(systems)} system dirs under {snapshots_root}", flush=True)
    for sd in systems:
        df, n_files = load_feed(sd)
        rec = audit_feed(df, sd.name)
        rec["n_files"] = n_files
        rows.append(rec)
        q = rec.get("q_hat")
        qs = ("%.3f" % q) if isinstance(q, (int, float)) else "n/a"
        print(f"  ✓ {sd.name:30s} snaps={rec.get('n_snapshots','?'):>4} "
              f"veh={rec.get('n_vehicles','?'):>5} q={qs:>6} "
              f"[{rec.get('persistence_class','?')}]", flush=True)
    return rows


# ── Synthetic fallback (smoke test) ──────────────────────────────────────────

def synthetic_store(rng) -> list[dict]:
    """Two synthetic feeds — one persistent (q~1), one rotating (q~0) — to
    verify the audit end to end without real data."""
    def make_feed(q_true, n_vehicles=150, snaps=70, poll_s=60, trip_prob=0.04):
        t0 = np.datetime64("2026-05-29T12:00:00")
        rows = []
        for v in range(n_vehicles):
            cur = f"v{v:04d}"
            lat = 43.6 + rng.normal(0, 0.01)
            lon = 3.88 + rng.normal(0, 0.01)
            k = 0
            while k < snaps:
                rows.append(dict(fetched_at=t0 + np.timedelta64(k * poll_s, "s"),
                                 vehicle_id=cur, lat=lat, lon=lon, is_disabled=False))
                if rng.random() < trip_prob:            # rented after this poll
                    trip_len = int(rng.integers(2, 8))   # absent for trip_len polls
                    k += trip_len + 1
                    lat += rng.normal(0, 0.01)
                    lon += rng.normal(0, 0.01)
                    if rng.random() > q_true:            # identifier rotates on return
                        cur = f"v{v:04d}_{k}"
                else:
                    k += 1
        return pd.DataFrame(rows)

    out = []
    for name, q in (("synthetic_persistent", 0.95), ("synthetic_rotating", 0.05)):
        rec = audit_feed(make_feed(q), name)
        rec["n_files"] = 1
        rec["q_true"] = q
        out.append(rec)
        print(f"  ✓ {name:30s} q_true={q} -> q_hat={rec.get('q_hat')} "
              f"[{rec.get('persistence_class')}]", flush=True)
    return out


# ── Figure (optional) ─────────────────────────────────────────────────────────

def make_figure(rows: list[dict]) -> str | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"  [info] matplotlib unavailable ({type(e).__name__}); "
              f"skipping figure.", flush=True)
        return None
    feeds = [r for r in rows if isinstance(r.get("q_hat"), (int, float))]
    feeds.sort(key=lambda r: r["q_hat"])
    if not feeds:
        print("  [info] no feed with a defined q_hat; skipping figure.", flush=True)
        return None
    names = [r["system_id"] for r in feeds]
    q = [r["q_hat"] for r in feeds]
    fig, ax = plt.subplots(figsize=(6.0, max(2.5, 0.22 * len(feeds))))
    ax.barh(range(len(feeds)), q, color="#4477AA")
    ax.axvline(ROTATING_MAX, color="0.4", ls=":", lw=0.8)
    ax.axvline(PERSISTENT_MIN, color="0.4", ls=":", lw=0.8)
    ax.set_yticks(range(len(feeds)))
    ax.set_yticklabels(names, fontsize=6)
    ax.set_xlabel(r"identifier-persistence rate $\hat q$")
    ax.set_xlim(0, 1)
    ax.set_title("d02 — identifier persistence by feed")
    fig.tight_layout()
    path = FIG / "fig_d02_persistence.pdf"
    fig.savefig(path)
    plt.close(fig)
    return str(path.name)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshots", type=str, default=None,
                    help="Path to a vehicle_snapshots/ store (one dir per "
                         "system_id). Default: synthetic two-feed smoke test.")
    args = ap.parse_args()

    t0 = time.time()
    print("=" * 72)
    print("d02_persistence_audit — feed-by-feed identifier persistence q")
    print("=" * 72)
    rng = np.random.default_rng(SEED)

    synthetic = args.snapshots is None
    if synthetic:
        print("  no --snapshots: running synthetic smoke test", flush=True)
        rows = synthetic_store(rng)
        root_str = "synthetic"
    else:
        root = Path(args.snapshots).expanduser()
        if not root.exists():
            print(f"  ERROR: snapshots path not found: {root}", file=sys.stderr)
            sys.exit(2)
        rows = audit_store(root)
        root_str = str(root)

    defined = [r for r in rows if isinstance(r.get("q_hat"), (int, float))]
    q_vals = [r["q_hat"] for r in defined]
    n_rot = sum(1 for r in rows if r.get("persistence_class") == "rotating")
    n_per = sum(1 for r in rows if r.get("persistence_class") == "persistent")
    n_mix = sum(1 for r in rows if r.get("persistence_class") == "mixed")

    summary = dict(
        seed=SEED, synthetic=synthetic, snapshots_root=root_str,
        n_feeds=len(rows), n_feeds_q_defined=len(defined),
        q_median=round(float(np.median(q_vals)), 4) if q_vals else None,
        q_min=round(float(np.min(q_vals)), 4) if q_vals else None,
        q_max=round(float(np.max(q_vals)), 4) if q_vals else None,
        n_rotating=n_rot, n_persistent=n_per, n_mixed=n_mix,
        params=dict(min_move_m=MIN_MOVE_M, poll_gap_factor=POLL_GAP_FACTOR,
                    reappear_margin_polls=REAPPEAR_MARGIN_POLLS,
                    min_snapshots=MIN_SNAPSHOTS,
                    rotating_max=ROTATING_MAX, persistent_min=PERSISTENT_MIN),
    )

    df_out = pd.DataFrame(rows)
    csv_path = OUT / "d02_persistence_audit.csv"
    df_out.to_csv(csv_path, index=False)
    json_path = OUT / "d02_persistence_audit.json"
    json_path.write_text(json.dumps(dict(summary=summary, feeds=rows), indent=2))
    print(f"\n  ✓ wrote {csv_path.name} ({len(rows)} feeds) and {json_path.name}",
          flush=True)
    print(f"  q defined on {len(defined)}/{len(rows)} feeds | "
          f"median q={summary['q_median']} | "
          f"persistent={n_per} mixed={n_mix} rotating={n_rot}", flush=True)

    fig_name = make_figure(rows)
    if fig_name:
        print(f"  ✓ wrote {fig_name}", flush=True)

    print(f"\n✓ d02 done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
