"""Split the ideal lap into corners and describe how each one is taken."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import find_peaks

from .vehicle import G


@dataclass
class Corner:
    number: int
    kind: str              # "braking" or "flat-out"
    direction: str         # "L" or "R"
    station_start: float   # centerline station where the corner begins (braking point)
    station_apex: float
    station_end: float
    brake_distance_m: float
    entry_kph: float
    apex_kph: float
    exit_kph: float
    apex_radius_m: float
    peak_lateral_g: float
    time_s: float = 0.0
    time_centerline_s: float = 0.0

    @property
    def gain_s(self) -> float:
        """Time the optimal line saves over driving the centerline through this corner."""
        return self.time_centerline_s - self.time_s


def _zone_time(station, dt, a, b, length):
    """Time spent with station in [a, b) on a closed lap (handles wrap-around)."""
    st = np.mod(station, length)
    a, b = a % length, b % length
    sel = (st >= a) & (st < b) if a <= b else (st >= a) | (st < b)
    return float(dt[sel].sum())


def find_corners(profile, k, station, lap_length, centre_profile=None, centre_station=None,
                 min_dip_kph: float = 10.0, flat_g: float = 3.0) -> list[Corner]:
    v = profile.v * 3.6
    ax, ay = profile.ax, profile.ay
    n = len(v)
    pts_per_100m = max(1, int(round(100.0 / (profile.s[1] - profile.s[0]))))

    # --- braking corners: every meaningful dip in the speed trace -------------------
    v3 = np.tile(v, 3)
    apexes, _ = find_peaks(-v3, prominence=min_dip_kph, distance=pts_per_100m)
    apexes = sorted({a - n for a in apexes if n <= a < 2 * n})

    def peak_between(lo, hi):          # index of the fastest point in (lo, hi), circular
        idx = np.arange(lo + 1, hi) if hi > lo + 1 else np.array([lo])
        return int(idx[np.argmax(v[idx % n])])

    zones = []
    m = len(apexes)
    for q, a in enumerate(apexes):
        prev_a = apexes[q - 1] - (n if q == 0 else 0)
        next_a = apexes[(q + 1) % m] + (n if q == m - 1 else 0)
        i = peak_between(prev_a, a)       # braking point = top speed before this corner
        top_after = peak_between(a, next_a)
        j = a
        while j < top_after and not (ax[j % n] > 0 and abs(ay[j % n]) < 1.0 * G):
            j += 1                        # exit = straightened up and accelerating
        zones.append(("braking", i, a, j))

    # --- flat-out corners: big lateral load without braking --------------------------
    used = np.zeros(n, bool)
    for _, i, _, j in zones:
        used[np.arange(i, j + 1) % n] = True
    high = (np.abs(ay) > flat_g * G) & ~used
    if high.any():
        idx = np.flatnonzero(high)
        groups = np.split(idx, np.flatnonzero(np.diff(idx) > pts_per_100m // 2) + 1)
        starts = np.array([z[1] % n for z in zones]) if zones else np.array([], int)
        for g in groups:
            if len(g) < 3:
                continue
            # a flat-out bend that runs straight into a braking zone is the turn-in of that
            # corner, not a corner of its own
            ds = profile.s[1] - profile.s[0]
            if len(starts) and np.min((starts - g[-1]) % n) * ds <= 10.0:
                continue
            a = g[np.argmax(np.abs(ay[g]))]
            zones.append(("flat-out", g[0], a, g[-1]))

    zones.sort(key=lambda z: z[2])
    corners = []
    for num, (kind, i, a, j) in enumerate(zones, 1):
        ii, aa, jj = i % n, a % n, j % n
        rng = np.arange(i, j + 1) % n
        st_i, st_a, st_j = station[ii], station[aa], station[jj]
        brake_m = (profile.s[aa] - profile.s[ii]) % lap_length if kind == "braking" else 0.0
        c = Corner(
            number=num, kind=kind, direction="L" if k[aa] > 0 else "R",
            station_start=float(st_i), station_apex=float(st_a), station_end=float(st_j),
            brake_distance_m=float(brake_m), entry_kph=float(v[ii]), apex_kph=float(v[aa]),
            exit_kph=float(v[jj]), apex_radius_m=float(1.0 / max(abs(k[aa]), 1e-9)),
            peak_lateral_g=float(np.abs(ay[rng]).max() / G),
        )
        c.time_s = _zone_time(station, profile.dt, st_i, st_j, lap_length)
        if centre_profile is not None:
            c.time_centerline_s = _zone_time(centre_station, centre_profile.dt, st_i, st_j, lap_length)
        corners.append(c)
    return corners
