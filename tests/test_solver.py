import dataclasses

import numpy as np
import pytest

from laptime.solver import corner_speed_limit, solve_lap, top_speed
from laptime.vehicle import G, RHO, get_car, grip_multiplier


def test_corner_speed_matches_closed_form_without_load_sensitivity():
    car = dataclasses.replace(get_car("f1_2025"), load_sensitivity=0.0)
    r = 60.0
    m, mu, cla = car.mass_kg, car.mu_y, car.cla_m2
    expected = np.sqrt(mu * m * G / (m / r - 0.5 * RHO * mu * cla))
    got = corner_speed_limit(np.array([1 / r]), car, 200.0)[0]
    assert got == pytest.approx(expected, rel=1e-6)


def test_constant_radius_circle_runs_at_its_limit():
    car = get_car("f1_2025")
    k = np.full(1000, 1 / 80.0)
    prof = solve_lap(k, 0.5, car)
    vlim = corner_speed_limit(np.array([1 / 80.0]), car, 999.0)[0]
    # Steady state sits just below the pure lateral limit: the friction ellipse has to leave
    # some longitudinal grip to overcome drag, exactly like a real car on a skidpad.
    assert np.ptp(prof.v) < 1e-3                       # constant speed
    assert 0.95 * vlim < prof.v[0] < vlim
    assert prof.lap_time == pytest.approx(500.0 / prof.v[0], rel=1e-3)


def test_top_speed_is_power_equals_drag():
    car = get_car("f1_2025")
    v = top_speed(car, low_drag=False)
    cda = car.cda_m2
    resist = 0.5 * RHO * cda * v ** 2 + car.crr * (car.mass_kg * G + 0.5 * RHO * car.cla_m2 * v ** 2)
    assert v * resist == pytest.approx(car.power_kw * 1e3, rel=1e-4)
    assert 320 < v * 3.6 < 380


def test_more_grip_is_faster_and_more_fuel_is_slower():
    from laptime.geometry import load_track
    from laptime.racing_line import optimise_racing_line
    p = optimise_racing_line(load_track("Monza")).path
    car = get_car("f1_2025")
    base = solve_lap(p.k, p.ds, car).lap_time
    assert solve_lap(p.k, p.ds, car.with_grip(1.05)).lap_time < base
    assert solve_lap(p.k, p.ds, car.with_extra_mass(50)).lap_time > base


def test_2026_ers_respects_energy_budget():
    from laptime.geometry import load_track
    from laptime.racing_line import optimise_racing_line
    p = optimise_racing_line(load_track("Sakhir")).path
    car = get_car("f1_2026")
    prof = solve_lap(p.k, p.ds, car)
    assert prof.ers_energy_mj <= car.ers_energy_mj + 1e-6
    assert prof.ers_energy_mj > 0.9 * car.ers_energy_mj


def test_tyres_and_conditions():
    assert grip_multiplier("soft", "dry") > grip_multiplier("hard", "dry")
    assert grip_multiplier("wet", "wet") > grip_multiplier("soft", "wet")
    assert grip_multiplier("soft", "dry", tyre_age_laps=10) < grip_multiplier("soft", "dry")
    with pytest.raises(ValueError):
        grip_multiplier("ultrasoft")
