import numpy as np

from laptime.geometry import load_track
from laptime.racing_line import build_track_paths, optimise_racing_line


def test_line_stays_inside_track_limits():
    tr = load_track("Sakhir")
    rl = optimise_racing_line(tr, margin=1.0)
    _, wr, wl = build_track_paths(tr)
    assert np.all(rl.offset_ref <= wl - 1.0 + 1e-6)
    assert np.all(rl.offset_ref >= -(wr - 1.0) - 1e-6)


def test_line_reduces_curvature_and_uses_the_width():
    rl = optimise_racing_line(load_track("Suzuka"))
    line, centre = rl.path, rl.centerline
    assert np.sum(line.k ** 2) * line.ds < 0.85 * np.sum(centre.k ** 2) * centre.ds
    assert rl.offset_ref.max() > 3 and rl.offset_ref.min() < -3    # goes edge to edge


def test_hairpins_are_opened_up():
    rl = optimise_racing_line(load_track("Silverstone"))
    assert 1 / np.abs(rl.path.k).max() > 1.3 * (1 / np.abs(rl.centerline.k).max())
