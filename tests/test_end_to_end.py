import json

import pytest

import laptime
from laptime.__main__ import main

# 2025 pole laps the f1_2025 preset is calibrated against (official FIA timing)
POLES_2025 = {"Sakhir": 89.841, "Silverstone": 84.892, "Spa": 100.562, "Monza": 78.792, "Suzuka": 86.983}


@pytest.mark.parametrize("track,pole", POLES_2025.items())
def test_2025_car_within_3_percent_of_real_pole(track, pole):
    r = laptime.simulate(track, "f1_2025")
    assert abs(r.racing.lap_time - pole) / pole < 0.03


def test_racing_line_beats_centerline_and_sectors_add_up():
    r = laptime.simulate("Suzuka")
    assert r.racing.lap_time < r.centerline.lap_time - 5
    assert sum(r.racing.sector_times(r.lap_length)) == pytest.approx(r.racing.lap_time, rel=1e-6)


def test_corners_are_sane():
    r = laptime.simulate("Sakhir")
    assert 7 <= len(r.corners) <= 15
    for c in r.corners:
        if c.kind == "braking":          # flat-out corners can still be accelerating
            assert c.entry_kph > c.apex_kph and c.exit_kph > c.apex_kph
            assert 10 <= c.brake_distance_m <= 300
        else:
            assert c.peak_lateral_g > 3
    assert sum(c.gain_s for c in r.corners) < r.line_gain


def test_cli_text_and_json(capsys, tmp_path):
    assert main(["bahrain", "--compare", "1:31.694"]) == 0
    out = capsys.readouterr().out
    assert "IDEAL LAP" in out and "Your lap 1:31.694" in out
    png = tmp_path / "lap.png"
    assert main(["monza", "--json", "--plot", str(png)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["track"] == "Monza" and data["corners"] and png.stat().st_size > 50_000


def test_cli_rejects_unknown_track(capsys):
    assert main(["narnia"]) == 2
    assert "Unknown track" in capsys.readouterr().err
