"""Quasi-steady-state lap solver.

1. Corner limit: at every point the fastest the car can go is where the tyres' lateral grip
   exactly supplies the centripetal force m*v^2*k. Grip grows with downforce (speed squared),
   but real tyres are load-sensitive: their friction coefficient falls as load rises, so
       F_max(N) = mu * N0 * (N / N0)^(1 - c),   N = m g + 1/2 rho ClA v^2,  N0 = m g
   and the corner speed is the root of  m v^2 |k| = F_max(N(v)), found by bisection.
2. Forward pass: accelerate as hard as power, rear-tyre traction and the friction ellipse
   allow, never exceeding the corner limit.
3. Backward pass: walking the lap in reverse, find how late you can brake (all four tyres,
   aero drag helping) and still make each corner.
4. The ideal speed everywhere is the minimum of the three. Integrating ds / v gives the lap.
The lap is solved over three consecutive laps and the middle one kept, so it is a flying lap.

Energy-limited ERS (2026 cars): the battery cannot run 350 kW all lap. Electrical energy is
worth the most where the car is slow, so the solver deploys below a speed threshold and
searches for the threshold that spends exactly the per-lap budget.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .vehicle import RHO, G, Car

LOW_DRAG_MAX_CURVATURE = 1.0 / 1500.0   # active aero / DRS only on near-straights


@dataclass
class SpeedProfile:
    s: np.ndarray
    v: np.ndarray            # m/s
    v_corner: np.ndarray     # grip-limited corner speed, m/s
    ax: np.ndarray           # longitudinal accel, m/s^2
    ay: np.ndarray           # lateral accel, m/s^2
    dt: np.ndarray           # time spent on each segment, s
    low_drag: np.ndarray     # bool, low-drag mode active
    ers_active: np.ndarray   # bool, electrical deployment active
    ers_energy_mj: float     # electrical energy actually deployed
    lap_time: float
    top_speed: float


def grip_force(mu: float, nz, car: Car):
    """Maximum tyre force for vertical load nz, including load sensitivity."""
    n0 = car.mass_kg * G
    return mu * n0 * np.power(nz / n0, 1.0 - car.load_sensitivity)


def corner_speed_limit(k: np.ndarray, car: Car, v_top: float) -> np.ndarray:
    m = car.mass_kg
    ak = np.abs(k)

    def surplus(v2):  # available lateral grip minus required centripetal force
        nz = m * G + 0.5 * RHO * car.cla_m2 * v2
        return grip_force(car.mu_y, nz, car) - m * v2 * ak

    hi = np.full_like(ak, v_top * v_top)
    flat_out = surplus(hi) >= 0
    lo = np.zeros_like(ak)
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        ok = surplus(mid) >= 0
        lo = np.where(ok, mid, lo)
        hi = np.where(ok, hi, mid)
    return np.where(flat_out, v_top, np.minimum(np.sqrt(lo), v_top))


def ers_power(car: Car, v: float) -> float:
    if car.ers_kw <= 0:
        return 0.0
    p = car.ers_kw * 1e3
    if car.ers_taper_kph:
        a, b = car.ers_taper_kph[0] / 3.6, car.ers_taper_kph[1] / 3.6
        if v >= b:
            return 0.0
        if v > a:
            p *= (b - v) / (b - a)
    return p


def top_speed(car: Car, low_drag: bool = True, with_ers: bool = True) -> float:
    cda = car.cda_m2 * (car.low_drag_cda_factor if low_drag else 1.0)
    cla = car.cla_m2 * (car.low_drag_cla_factor if low_drag else 1.0)
    v = 50.0
    for _ in range(300):  # solve P(v) = v * (drag + rolling)
        p = car.power_kw * 1e3 + (ers_power(car, v) if with_ers else 0.0)
        resist = 0.5 * RHO * cda * v * v + car.crr * (car.mass_kg * G + 0.5 * RHO * cla * v * v)
        v = 0.7 * v + 0.3 * p / resist
    return v


def _forward(k, ds, car, v_lim, v0, low, ers_mask):
    n = len(k)
    v = np.empty(n)
    p_ers_used = np.zeros(n)
    v[0] = min(v0, v_lim[0])
    m, p_base = car.mass_kg, car.power_kw * 1e3
    n0, c = m * G, car.load_sensitivity
    for i in range(n - 1):
        vi = v[i]
        cda = car.cda_m2 * (car.low_drag_cda_factor if low[i] else 1.0)
        cla = car.cla_m2 * (car.low_drag_cla_factor if low[i] else 1.0)
        nz = m * G + 0.5 * RHO * cla * vi * vi
        lat = m * vi * vi * abs(k[i])
        load = (nz / n0) ** (1.0 - c)
        r = min(1.0, lat / (car.mu_y * n0 * load))
        traction = car.mu_x * n0 * load * car.drive_load_fraction * math.sqrt(1.0 - r * r)
        p_e = ers_power(car, vi) if ers_mask[i] else 0.0
        vv = max(vi, 1.0)
        drive = min(traction, (p_base + p_e) / vv)
        p_ers_used[i] = max(0.0, min(p_e, drive * vv - p_base))
        a = (drive - 0.5 * RHO * cda * vi * vi - car.crr * nz) / m
        v[i + 1] = min(math.sqrt(max(vi * vi + 2.0 * a * ds, 0.0)), v_lim[i + 1])
    return v, p_ers_used


def _backward(k, ds, car, v_lim, v_end):
    n = len(k)
    v = np.empty(n)
    v[-1] = min(v_end, v_lim[-1])
    m = car.mass_kg
    n0, c = m * G, car.load_sensitivity
    for i in range(n - 1, 0, -1):
        vi = v[i]
        nz = m * G + 0.5 * RHO * car.cla_m2 * vi * vi   # flaps closed under braking
        lat = m * vi * vi * abs(k[i - 1])
        load = (nz / n0) ** (1.0 - c)
        r = min(1.0, lat / (car.mu_y * n0 * load))
        brake = car.mu_x * n0 * load * math.sqrt(1.0 - r * r)
        d = (brake + 0.5 * RHO * car.cda_m2 * vi * vi + car.crr * nz) / m
        v[i - 1] = min(math.sqrt(vi * vi + 2.0 * d * ds), v_lim[i - 1])
    return v


def _solve(k, ds, car, v_lim, low, v_thresh):
    n = len(k)
    k3, lim3, low3 = np.tile(k, 3), np.tile(v_lim, 3), np.tile(low, 3)
    v_start = float(v_lim.min())
    # deploy wherever the car is below the threshold speed (decided on the grip-limited
    # profile; refined once on the actual speed)
    mask3 = np.ones(3 * n, bool) if v_thresh is None else None
    if mask3 is None:
        vb = _backward(k3, ds, car, lim3, v_start)
        vf0, _ = _forward(k3, ds, car, lim3, v_start, low3, np.ones(3 * n, bool))
        mask3 = np.minimum(vf0, vb) < v_thresh
    vf, p_ers = _forward(k3, ds, car, lim3, v_start, low3, mask3)
    vb = _backward(k3, ds, car, lim3, v_start)
    v = np.minimum(vf, vb)[n:2 * n + 1]
    on_throttle = vf[n:2 * n] <= vb[n:2 * n] + 1e-9
    v_mid = 0.5 * (v[:-1] + v[1:])
    dt = ds / v_mid
    used = p_ers[n:2 * n] * on_throttle
    energy = float(np.sum(used * dt)) / 1e6
    return v, dt, energy, used > 0


def solve_lap(k: np.ndarray, ds: float, car: Car) -> SpeedProfile:
    n = len(k)
    v_top = top_speed(car, low_drag=car.low_drag_name is not None)
    low = np.abs(k) < LOW_DRAG_MAX_CURVATURE if car.low_drag_name else np.zeros(n, bool)
    v_lim = corner_speed_limit(k, car, v_top)

    v, dt, energy, ers_on = _solve(k, ds, car, v_lim, low, None)
    if car.ers_kw > 0 and car.ers_energy_mj > 0 and energy > car.ers_energy_mj:
        lo, hi = 0.0, float(v_top) + 1.0          # bisection on the deployment threshold
        best = None
        for _ in range(18):
            mid = 0.5 * (lo + hi)
            res = _solve(k, ds, car, v_lim, low, mid)
            if res[2] <= car.ers_energy_mj:
                lo, best = mid, res
            else:
                hi = mid
        v, dt, energy, ers_on = best if best is not None else _solve(k, ds, car, v_lim, low, 0.0)

    ax = (v[1:] ** 2 - v[:-1] ** 2) / (2 * ds)
    vv = v[:-1]
    s = np.arange(n) * ds
    return SpeedProfile(s, vv, v_lim, ax, vv * vv * k, dt, low, ers_on, energy,
                        float(dt.sum()), float(vv.max()))
