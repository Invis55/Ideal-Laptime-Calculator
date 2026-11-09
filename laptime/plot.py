"""Track map coloured by ideal speed, speed trace, and where the racing line gains time."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402

from .timefmt import fmt_time  # noqa: E402


def plot_lap(result, path: str, dpi: int = 150) -> str:
    rl, racing, centre = result.line, result.racing, result.centerline
    p = racing.path
    v = racing.profile.v * 3.6
    length = result.lap_length

    fig = plt.figure(figsize=(15, 8), constrained_layout=True)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.35, 1], height_ratios=[1, 1])
    ax_map = fig.add_subplot(gs[:, 0])
    ax_v = fig.add_subplot(gs[0, 1])
    ax_g = fig.add_subplot(gs[1, 1])

    # --- map ----------------------------------------------------------------------
    for edge in (rl.left_edge, rl.right_edge):
        e = np.vstack([edge, edge[:1]])
        ax_map.plot(e[:, 0], e[:, 1], color="#9aa0a6", lw=0.8)
    pts = np.column_stack([np.r_[p.x, p.x[0]], np.r_[p.y, p.y[0]]])
    segs = np.stack([pts[:-1], pts[1:]], axis=1)
    lc = LineCollection(segs, cmap="turbo", linewidths=2.6)
    lc.set_array(v)
    lc.set_clim(v.min(), v.max())
    ax_map.add_collection(lc)
    cb = fig.colorbar(lc, ax=ax_map, shrink=0.6, pad=0.01)
    cb.set_label("ideal speed (kph)")

    nrm = p.normal_left
    span = max(np.ptp(p.x), np.ptp(p.y))
    for c in result.corners:
        i = int(np.argmin(np.abs(np.mod(racing.station - c.station_apex + length / 2, length) - length / 2)))
        side = 1 if c.direction == "R" else -1          # label on the outside of the corner
        ox, oy = nrm[i] * side * span * 0.035
        ax_map.annotate(f"C{c.number}", (p.x[i], p.y[i]), (p.x[i] + ox, p.y[i] + oy),
                        ha="center", va="center", fontsize=8, fontweight="bold",
                        arrowprops=dict(arrowstyle="-", color="#555", lw=0.6))
    s0 = 0
    ax_map.plot(p.x[s0], p.y[s0], marker="s", color="k", ms=6)
    ax_map.annotate("start", (p.x[s0], p.y[s0]), (6, 6), textcoords="offset points", fontsize=8)
    ax_map.set_aspect("equal")
    ax_map.axis("off")
    st = result.settings
    ax_map.set_title(f"{result.track} — ideal lap {fmt_time(racing.lap_time)}\n"
                     f"{result.car.name}, {st['tyre']} tyres, {st['conditions']}, {st['fuel_kg']:g} kg fuel",
                     fontsize=13, loc="left")

    # --- speed trace ----------------------------------------------------------------
    def by_station(res):
        st_ = np.mod(res.station, length)
        o = np.argsort(st_)
        return st_[o] / 1000, res.profile.v[o] * 3.6

    xs, vs = by_station(centre)
    ax_v.plot(xs, vs, color="#9aa0a6", lw=1, ls="--", label=f"centerline  {fmt_time(centre.lap_time)}")
    xs, vs = by_station(racing)
    ax_v.plot(xs, vs, color="#d62728", lw=1.4, label=f"racing line {fmt_time(racing.lap_time)}")
    for c in result.corners:
        ax_v.annotate(f"C{c.number}", (c.station_apex / 1000, c.apex_kph), (0, -11),
                      textcoords="offset points", ha="center", fontsize=7)
    ax_v.set_xlim(0, length / 1000)
    ax_v.set_xlabel("distance along track (km)")
    ax_v.set_ylabel("speed (kph)")
    ax_v.grid(alpha=0.3)
    ax_v.legend(loc="lower right", fontsize=9)
    ax_v.set_title("Speed trace", loc="left")

    # --- where the line gains -------------------------------------------------------
    names = [f"C{c.number}" for c in result.corners]
    gains = [c.gain_s for c in result.corners]
    colors = ["#1f77b4" if c.kind == "braking" else "#2ca02c" for c in result.corners]
    ax_g.bar(names, gains, color=colors)
    ax_g.set_ylabel("time gained vs centerline (s)")
    ax_g.grid(axis="y", alpha=0.3)
    other = result.line_gain - sum(gains)
    ax_g.set_title(f"Where the racing line gains its {result.line_gain:.2f} s over the centerline\n"
                   f"blue = braking corner, green = flat-out, straights & kinks {other:+.2f} s",
                   loc="left", fontsize=10)
    ax_g.tick_params(axis="x", labelsize=8)

    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path
