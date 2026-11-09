"""Minimum-curvature racing line.

Each point of the line is the centerline point pushed sideways along the track normal:
    p_i = c_i + a_i * n_i
We choose the offsets a_i to minimise the sum of squared second differences of the path
(a standard proxy for total squared curvature), subject to staying inside the track:
    -(w_right - margin) <= a_i <= (w_left - margin)
That is a bounded linear least-squares problem, solved exactly with scipy's lsq_linear.
This is how the line "opens up" every corner: late turn-in, use all the width, clip the apex,
run out to the edge on exit -- falling out of the maths rather than being hand-coded.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import splu
from scipy.spatial import cKDTree

from .geometry import Path2D, Track, closed_spline_path, interp_periodic


@dataclass
class RacingLine:
    path: Path2D              # the optimised line, resampled for simulation
    station: np.ndarray       # centerline station [m] of every point on `path`
    centerline: Path2D        # reference centerline at simulation resolution
    left_edge: np.ndarray     # (n, 2) track edges along the reference, for plotting
    right_edge: np.ndarray
    offset_ref: np.ndarray    # lateral offset at optimisation stations (+ = left)
    station_ref: np.ndarray


def _second_difference_system(c: Path2D, nrm: np.ndarray):
    n = len(c.x)
    i = np.arange(n)
    im, ip = (i - 1) % n, (i + 1) % n
    rows, cols, vals = [], [], []
    for axis in (0, 1):
        r = i + axis * n
        rows += [r, r, r]
        cols += [im, i, ip]
        vals += [nrm[im, axis], -2.0 * nrm[i, axis], nrm[ip, axis]]
    A = sparse.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
                          shape=(2 * n, n))
    cx, cy = c.x, c.y
    dcx = cx[im] - 2 * cx + cx[ip]
    dcy = cy[im] - 2 * cy + cy[ip]
    return A, -np.r_[dcx, dcy]



def _box_qp(H, f, lo, hi, max_iter: int = 100, tol: float = 1e-9) -> np.ndarray:
    """Minimise 0.5 x'Hx - f'x subject to lo <= x <= hi (projected Newton, Bertsekas 1982).

    H is sparse, banded and positive definite. Each iteration fixes the variables pinned
    against a track edge, takes an exact Newton step on the rest, and projects back.
    Converges in a handful of iterations where generic solvers take minutes.
    """
    H = sparse.csc_matrix(H)
    x = np.clip(np.zeros(len(f)), lo, hi)

    def q(v):
        return 0.5 * v @ (H @ v) - f @ v

    qx = q(x)
    for _ in range(max_iter):
        g = H @ x - f
        eps = 1e-7
        active = ((x <= lo + eps) & (g > 0)) | ((x >= hi - eps) & (g < 0))
        free = np.flatnonzero(~active)
        d = np.zeros_like(x)
        if len(free):
            Hff = H[free][:, free].tocsc()
            d[free] = splu(Hff).solve(-g[free])
        t, improved = 1.0, False
        while t > 1e-8:
            xn = np.clip(x + t * d, lo, hi)
            qn = q(xn)
            if qn <= qx - 1e-4 * abs(g @ (xn - x)) or qn < qx - 1e-14:
                improved = True
                break
            t *= 0.5
        if not improved:
            break
        step = np.max(np.abs(xn - x))
        x, qx = xn, qn
        if step < tol:
            break
    return x


def build_track_paths(track: Track, ds_sim: float = 2.0, ds_opt: float = 4.0):
    centre_opt, _ = closed_spline_path(track.x, track.y, ds_opt, smoothing=0.05)
    raw_s = np.r_[0.0, np.cumsum(np.hypot(np.diff(track.x), np.diff(track.y)))]
    scale = centre_opt.length / (raw_s[-1] + np.hypot(track.x[0] - track.x[-1], track.y[0] - track.y[-1]))
    wr = interp_periodic(centre_opt.s, raw_s * scale, track.w_right, centre_opt.length)
    wl = interp_periodic(centre_opt.s, raw_s * scale, track.w_left, centre_opt.length)
    # Survey widths occasionally include paved run-off (e.g. 22 m at parts of Sakhir).
    # Clip each side at its 95th percentile so the line can't exploit those spikes.
    wr = np.minimum(wr, np.percentile(wr, 95))
    wl = np.minimum(wl, np.percentile(wl, 95))
    return centre_opt, wr, wl


def optimise_racing_line(track: Track, margin: float = 1.0, ds_sim: float = 2.0,
                         ds_opt: float = 4.0, iterations: int = 8) -> RacingLine:
    """margin = how far the car's centre must stay from each edge (about half the car width)."""
    centre, wr, wl = build_track_paths(track, ds_sim, ds_opt)
    nrm = centre.normal_left
    A, b = _second_difference_system(centre, nrm)

    lo = -(wr - margin)
    hi = wl - margin
    bad = lo >= hi                        # very narrow spots: pin to centre
    lo[bad], hi[bad] = -1e-3, 1e-3
    # Second differences only approximate curvature when points are evenly spaced. Pushing
    # the line to the inside of a hairpin bunches points together, which would make a tight
    # line look artificially cheap. So reweight every point by 1/spacing^2 from the previous
    # solution (iteratively reweighted least squares) until the line settles.
    n = len(centre.x)
    alpha = np.zeros(n)
    for _ in range(iterations):
        lx = centre.x + alpha * nrm[:, 0]
        ly = centre.y + alpha * nrm[:, 1]
        d_next = np.hypot(np.roll(lx, -1) - lx, np.roll(ly, -1) - ly)
        h = 0.5 * (d_next + np.roll(d_next, 1))
        w = (ds_opt / h) ** 2
        W = sparse.diags(np.r_[w, w])
        Aw, bw = W @ A, W @ b
        H = (Aw.T @ Aw) + sparse.identity(n) * 1e-9
        alpha_new = _box_qp(H, Aw.T @ bw, lo, hi)
        converged = np.max(np.abs(alpha_new - alpha)) < 0.01
        alpha = alpha_new
        if converged:
            break

    lx = centre.x + alpha * nrm[:, 0]
    ly = centre.y + alpha * nrm[:, 1]
    line, _ = closed_spline_path(lx, ly, ds_sim, smoothing=0.01)

    # map every simulation point on the line back to a centerline station
    tree = cKDTree(np.column_stack([lx, ly]))
    _, idx = tree.query(np.column_stack([line.x, line.y]))
    station = centre.s[idx]

    centre_sim, _ = closed_spline_path(track.x, track.y, ds_sim, smoothing=0.05)
    left = np.column_stack([centre.x + wl * nrm[:, 0], centre.y + wl * nrm[:, 1]])
    right = np.column_stack([centre.x - wr * nrm[:, 0], centre.y - wr * nrm[:, 1]])
    return RacingLine(line, station, centre_sim, left, right, alpha, centre.s)
