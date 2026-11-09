"""Command line: python -m laptime <track> [options]"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .api import simulate
from .geometry import ALIASES, available_tracks
from .timefmt import fmt_time, parse_time
from .vehicle import G, load_cars, load_tyre_data


def _print_report(r, your_time: float | None) -> None:
    rac, cen, st = r.racing, r.centerline, r.settings
    prof = rac.profile
    print(f"\n{r.track}  ({r.lap_length / 1000:.3f} km)  |  {r.car.name}  |  "
          f"{st['tyre']} tyres, {st['conditions']}, {st['fuel_kg']:g} kg fuel"
          + (f", {st['tyre_age_laps']:g}-lap-old tyres" if st['tyre_age_laps'] else ""))
    print("=" * 78)
    print(f"  IDEAL LAP            {fmt_time(rac.lap_time)}")
    for i, t in enumerate(rac.sector_times(r.lap_length), 1):
        print(f"    Sector {i}           {fmt_time(t)}")
    print(f"  Centerline lap       {fmt_time(cen.lap_time)}   "
          f"(the optimal line is worth {r.line_gain:.3f} s)")
    thr = (prof.ax > 0.2).mean() * 100
    print(f"  Top / min speed      {prof.top_speed * 3.6:.1f} / {prof.v.min() * 3.6:.1f} kph")
    print(f"  Peak cornering       {abs(prof.ay).max() / G:.2f} g    "
          f"peak braking {-prof.ax.min() / G:.2f} g    accelerating {thr:.0f}% of the lap")
    if r.car.low_drag_name:
        print(f"  {r.car.low_drag_name:<20} open on {prof.low_drag.mean() * 100:.0f}% of the lap")
    if r.car.ers_kw:
        print(f"  ERS deployed         {prof.ers_energy_mj:.2f} of {r.car.ers_energy_mj:g} MJ "
              f"(used on {prof.ers_active.mean() * 100:.0f}% of the lap, slowest sections first)")

    print("\n  Corner by corner (detected corners, numbering is not the official turn numbering)")
    print("  " + "-" * 76)
    print("   #   Dir  Type       Brake    Entry  Apex   Exit   Apex     Peak  Line")
    print("                       for      kph    kph    kph    radius   g     gains")
    for c in r.corners:
        brake = f"{c.brake_distance_m:4.0f} m" if c.kind == "braking" else "  flat"
        print(f"   C{c.number:<3}{c.direction:^5}{c.kind:<10} {brake}  {c.entry_kph:5.0f}  {c.apex_kph:5.0f}  "
              f"{c.exit_kph:5.0f}  {c.apex_radius_m:5.0f} m  {c.peak_lateral_g:4.1f}  {c.gain_s:+.2f} s")
    straights = r.line_gain - sum(c.gain_s for c in r.corners)
    print(f"   {'straights / kinks':<62}{straights:+.2f} s")

    if your_time is not None:
        gap = your_time - rac.lap_time
        pct = rac.lap_time / your_time * 100
        verdict = "faster than the model's ideal!" if gap < 0 else f"{pct:.1f}% of ideal pace"
        print(f"\n  Your lap {fmt_time(your_time)} vs ideal: {gap:+.3f} s  ({verdict})")
    print()


def _to_json(r) -> dict:
    p = r.racing.profile
    return {
        "track": r.track, "length_m": r.lap_length, "car": r.car.name, "settings": r.settings,
        "ideal_lap_s": r.racing.lap_time, "centerline_lap_s": r.centerline.lap_time,
        "sectors_s": r.racing.sector_times(r.lap_length), "top_speed_kph": p.top_speed * 3.6,
        "min_speed_kph": float(p.v.min() * 3.6), "ers_energy_mj": p.ers_energy_mj,
        "corners": [dict(c.__dict__, gain_s=c.gain_s) for c in r.corners],
    }


def main(argv: list[str] | None = None) -> int:
    cars, tyres = load_cars(), load_tyre_data()
    ap = argparse.ArgumentParser(
        prog="python -m laptime",
        description="Ideal lap time from real circuit geometry: optimal racing line + lap solver.")
    ap.add_argument("track", nargs="?", help="circuit name, e.g. Sakhir, bahrain, silverstone, spa")
    ap.add_argument("--list", action="store_true", help="list circuits, cars, tyres and conditions")
    ap.add_argument("--car", default="f1_2025", choices=sorted(cars))
    ap.add_argument("--tyre", default="soft", choices=sorted(tyres["compounds"]))
    ap.add_argument("--conditions", default="dry", choices=sorted(tyres["conditions"]))
    ap.add_argument("--fuel", type=float, default=0.0, metavar="KG", help="fuel load (default 0)")
    ap.add_argument("--tyre-age", type=float, default=0.0, metavar="LAPS", help="tyre age in laps")
    ap.add_argument("--margin", type=float, default=1.0, metavar="M",
                    help="closest the car's centre gets to the track edge (default 1.0)")
    ap.add_argument("--compare", metavar="M:SS.mmm", help="your own lap time to compare against")
    ap.add_argument("--plot", metavar="FILE.png", help="save a track map + speed trace")
    ap.add_argument("--json", action="store_true", help="print results as JSON")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    a = ap.parse_args(argv)

    if a.list:
        print("Circuits:  " + ", ".join(available_tracks()))
        print("Aliases:   " + ", ".join(sorted(ALIASES)))
        for k, c in cars.items():
            print(f"Car {k}: {c.description}")
        print("Tyres:     " + ", ".join(tyres["compounds"]))
        print("Conditions: " + ", ".join(tyres["conditions"]))
        return 0
    if not a.track:
        ap.error("give a track (or --list)")

    try:
        your = parse_time(a.compare) if a.compare else None
        r = simulate(a.track, a.car, a.tyre, a.conditions, a.fuel, a.tyre_age, a.margin)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if a.json:
        out = _to_json(r)
        if your is not None:
            out["your_lap_s"] = your
        print(json.dumps(out, indent=2))
    else:
        _print_report(r, your)
    if a.plot:
        from .plot import plot_lap
        plot_lap(r, a.plot)
        if not a.json:
            print(f"  Saved {a.plot}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
