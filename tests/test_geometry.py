import numpy as np
import pytest

from laptime.geometry import available_tracks, closed_spline_path, load_track, resolve_track_name

OFFICIAL_LENGTH_M = {"Sakhir": 5412, "Silverstone": 5891, "Spa": 7004, "Monza": 5793, "Suzuka": 5807}


def test_all_tracks_load():
    names = available_tracks()
    assert len(names) == 25
    for n in names:
        t = load_track(n)
        assert len(t.x) > 300 and np.all(t.w_left > 0) and np.all(t.w_right > 0)


@pytest.mark.parametrize("name,official", OFFICIAL_LENGTH_M.items())
def test_centerline_length_matches_official(name, official):
    t = load_track(name)
    path, _ = closed_spline_path(t.x, t.y, 2.0, smoothing=0.05)
    assert abs(path.length - official) / official < 0.01


def test_aliases_and_case():
    assert resolve_track_name("bahrain") == "Sakhir"
    assert resolve_track_name("SPA") == "Spa"
    with pytest.raises(ValueError):
        resolve_track_name("Narnia")


def test_circle_curvature_is_one_over_radius():
    th = np.linspace(0, 2 * np.pi, 400, endpoint=False)
    path, _ = closed_spline_path(50 * np.cos(th), 50 * np.sin(th), 1.0)
    assert np.allclose(path.k, 1 / 50, rtol=1e-3)
    assert abs(path.length - 2 * np.pi * 50) < 0.5
