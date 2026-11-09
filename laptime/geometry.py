"""Track geometry: load real circuit centerlines, build smooth closed paths, compute curvature."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.interpolate import splev, splprep

TRACK_DIR = Path(__file__).parent / "data" / "tracks"

# Friendly names -> file stem in data/tracks
ALIASES = {
    "bahrain": "Sakhir", "britain": "Silverstone", "uk": "Silverstone",
    "belgium": "Spa", "spa-francorchamps": "Spa", "italy": "Monza",
    "japan": "Suzuka", "abu dhabi": "YasMarina", "abudhabi": "YasMarina",
    "yas marina": "YasMarina", "usa": "Austin", "cota": "Austin",
    "hungary": "Budapest", "hungaroring": "Budapest", "spain": "Catalunya",
    "barcelona": "Catalunya", "australia": "Melbourne", "albert park": "Melbourne",
    "mexico": "MexicoCity", "canada": "Montreal", "brazil": "SaoPaulo",
    "interlagos": "SaoPaulo", "malaysia": "Sepang", "china": "Shanghai",
    "austria": "Spielberg", "red bull ring": "Spielberg",
    "netherlands": "Zandvoort", "russia": "Sochi", "nurburgring": "Nuerburgring",
    "brands hatch": "BrandsHatch", "indianapolis": "IMS", "germany": "Hockenheim",
}


def available_tracks() -> list[str]:
    return sorted(p.stem for p in TRACK_DIR.glob("*.csv"))


def resolve_track_name(name: str) -> str:
    key = name.strip().lower()
    for stem in available_tracks():
        if stem.lower() == key:
            return stem
    if key in ALIASES:
        return ALIASES[key]
    raise ValueError(f"Unknown track '{name}'. Available: {', '.join(available_tracks())}")


@dataclass
class Track:
    name: str
    x: np.ndarray        # centerline, driving direction, not closed (last != first)
    y: np.ndarray
    w_right: np.ndarray  # distance from centerline to right edge [m]
    w_left: np.ndarray   # distance from centerline to left edge [m]


def load_track(name: str) -> Track:
    stem = resolve_track_name(name)
    d = np.loadtxt(TRACK_DIR / f"{stem}.csv", delimiter=",", comments="#")
    return Track(stem, d[:, 0], d[:, 1], d[:, 2], d[:, 3])


@dataclass
class Path2D:
    """A closed path sampled uniformly in arc length."""
    s: np.ndarray      # station [m], s[0] = 0
    x: np.ndarray
    y: np.ndarray
    k: np.ndarray      # signed curvature [1/m], positive = turning left
    ds: float
    length: float

    @property
    def tangent(self) -> np.ndarray:
        tx, ty = np.gradient(self.x), np.gradient(self.y)
        # wrap ends for a closed loop
        tx[0], ty[0] = self.x[1] - self.x[-1], self.y[1] - self.y[-1]
        tx[-1], ty[-1] = self.x[0] - self.x[-2], self.y[0] - self.y[-2]
        n = np.hypot(tx, ty)
        return np.column_stack([tx / n, ty / n])

    @property
    def normal_left(self) -> np.ndarray:
        t = self.tangent
        return np.column_stack([-t[:, 1], t[:, 0]])


def closed_spline_path(x, y, ds: float, smoothing: float = 0.0) -> tuple[Path2D, tuple]:
    """Fit a periodic spline through closed-loop points and resample every `ds` metres.

    Curvature comes from the spline's analytic derivatives, which is far less noisy than
    finite differences on raw survey points.
    """
    px = np.r_[x, x[0]]
    py = np.r_[y, y[0]]
    tck, _ = splprep([px, py], s=smoothing * len(px), per=1)

    # dense evaluation to get arc length as a function of the spline parameter
    u_dense = np.linspace(0, 1, 20 * len(px))
    xd, yd = splev(u_dense, tck)
    seg = np.hypot(np.diff(xd), np.diff(yd))
    s_dense = np.r_[0.0, np.cumsum(seg)]
    length = s_dense[-1]

    n = int(round(length / ds))
    s = np.linspace(0, length, n, endpoint=False)
    u = np.interp(s, s_dense, u_dense)
    xs, ys = splev(u, tck)
    dx, dy = splev(u, tck, der=1)
    ddx, ddy = splev(u, tck, der=2)
    k = (dx * ddy - dy * ddx) / np.power(dx * dx + dy * dy, 1.5)
    return Path2D(s, np.asarray(xs), np.asarray(ys), k, length / n, length), tck


def interp_periodic(s_query, s_ref, values, length):
    return np.interp(s_query, np.r_[s_ref, length], np.r_[values, values[0]])
