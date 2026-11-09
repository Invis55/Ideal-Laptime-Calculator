"""Car, tyre and condition models (point-mass, quasi-steady-state)."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
G = 9.81
RHO = 1.20  # air density, kg/m^3


@dataclass(frozen=True)
class Car:
    name: str
    mass_kg: float              # car + driver, no fuel
    power_kw: float             # peak power delivered to the wheels
    cda_m2: float               # drag area, high-downforce configuration
    cla_m2: float               # downforce area, high-downforce configuration
    mu_x: float                 # longitudinal tyre friction coefficient
    mu_y: float                 # lateral tyre friction coefficient
    drive_load_fraction: float  # share of vertical load on the driven (rear) axle
    crr: float = 0.012          # rolling resistance
    load_sensitivity: float = 0.0  # tyre grip coefficient falls as (load / static load)^-c
    ers_kw: float = 0.0            # extra electric power, energy-limited (0 = none modelled)
    ers_energy_mj: float = 0.0     # deployable electrical energy per lap
    ers_taper_kph: tuple[float, float] | None = None  # ERS fades to zero over this speed band
    low_drag_name: str | None = None
    low_drag_cda_factor: float = 1.0
    low_drag_cla_factor: float = 1.0
    description: str = ""

    def with_grip(self, factor: float) -> "Car":
        return replace(self, mu_x=self.mu_x * factor, mu_y=self.mu_y * factor)

    def with_extra_mass(self, kg: float) -> "Car":
        return replace(self, mass_kg=self.mass_kg + kg)


def load_cars() -> dict[str, Car]:
    raw = json.loads((DATA_DIR / "cars.json").read_text())
    cars = {}
    for key, c in raw.items():
        ld = c.get("low_drag") or {}
        cars[key] = Car(
            name=key, mass_kg=c["mass_kg"], power_kw=c["power_kw"], cda_m2=c["cda_m2"],
            cla_m2=c["cla_m2"], mu_x=c["mu_x"], mu_y=c["mu_y"],
            drive_load_fraction=c["drive_load_fraction"], crr=c.get("crr", 0.012),
            load_sensitivity=c.get("load_sensitivity", 0.0),
            ers_kw=c.get("ers_kw", 0.0), ers_energy_mj=c.get("ers_energy_mj", 0.0),
            ers_taper_kph=tuple(c["ers_taper_kph"]) if c.get("ers_taper_kph") else None,
            low_drag_name=ld.get("name"), low_drag_cda_factor=ld.get("cda_factor", 1.0),
            low_drag_cla_factor=ld.get("cla_factor", 1.0), description=c.get("description", ""),
        )
    return cars


def get_car(name: str) -> Car:
    cars = load_cars()
    key = name.strip().lower()
    if key not in cars:
        raise ValueError(f"Unknown car '{name}'. Available: {', '.join(cars)}")
    return cars[key]


def load_tyre_data() -> dict:
    return json.loads((DATA_DIR / "tyres.json").read_text())


def grip_multiplier(compound: str = "soft", conditions: str = "dry", tyre_age_laps: float = 0) -> float:
    data = load_tyre_data()
    comp = compound.strip().lower()
    cond = conditions.strip().lower()
    if comp not in data["compounds"]:
        raise ValueError(f"Unknown tyre '{compound}'. Available: {', '.join(data['compounds'])}")
    if cond not in data["conditions"]:
        raise ValueError(f"Unknown conditions '{conditions}'. Available: {', '.join(data['conditions'])}")
    c = data["compounds"][comp]
    wear = max(0.0, 1.0 - c["deg_per_lap"] * max(0.0, tyre_age_laps))
    return c["grip"] * data["conditions"][cond][c["type"]] * wear
