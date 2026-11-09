"""High-level entry point: simulate(track, car, ...) -> LapComparison."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .corners import Corner, find_corners
from .geometry import Path2D, load_track
from .racing_line import RacingLine, optimise_racing_line
from .solver import SpeedProfile, solve_lap
from .vehicle import Car, get_car, grip_multiplier


@dataclass
class LapResult:
    name: str                 # "racing line" or "centerline"
    path: Path2D
    station: np.ndarray       # centerline station of each point
    profile: SpeedProfile

    @property
    def lap_time(self) -> float:
        return self.profile.lap_time

    def sector_times(self, length: float, sectors: int = 3) -> list[float]:
        st = np.mod(self.station, length)
        edges = np.linspace(0, length, sectors + 1)
        return [float(self.profile.dt[(st >= a) & (st < b)].sum()) for a, b in zip(edges[:-1], edges[1:])]


@dataclass
class LapComparison:
    track: str
    car: Car
    settings: dict
    line: RacingLine
    racing: LapResult
    centerline: LapResult
    corners: list[Corner] = field(default_factory=list)

    @property
    def lap_length(self) -> float:
        return self.line.centerline.length

    @property
    def line_gain(self) -> float:
        return self.centerline.lap_time - self.racing.lap_time


def simulate(track: str, car: str | Car = "f1_2025", tyre: str = "soft", conditions: str = "dry",
             fuel_kg: float = 0.0, tyre_age_laps: float = 0.0, margin: float = 1.0) -> LapComparison:
    """Optimise the racing line for `track` and solve the ideal lap on it and on the centerline."""
    tr = load_track(track)
    base = get_car(car) if isinstance(car, str) else car
    grip = grip_multiplier(tyre, conditions, tyre_age_laps)
    vehicle = base.with_grip(grip).with_extra_mass(fuel_kg)

    rl = optimise_racing_line(tr, margin=margin)
    racing = LapResult("racing line", rl.path, rl.station, solve_lap(rl.path.k, rl.path.ds, vehicle))
    c = rl.centerline
    centre_station = c.s * (rl.station_ref[-1] + (rl.station_ref[1] - rl.station_ref[0])) / c.length
    centre = LapResult("centerline", c, centre_station, solve_lap(c.k, c.ds, vehicle))

    length = rl.station_ref[-1] + (rl.station_ref[1] - rl.station_ref[0])
    corners = find_corners(racing.profile, rl.path.k, rl.station, length, centre.profile, centre_station)
    settings = dict(tyre=tyre, conditions=conditions, fuel_kg=fuel_kg, tyre_age_laps=tyre_age_laps,
                    margin=margin, grip_multiplier=grip)
    return LapComparison(tr.name, base, settings, rl, racing, centre, corners)
