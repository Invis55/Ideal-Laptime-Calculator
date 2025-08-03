import unittest
from engine.simulator import simulate_lap
from engine.track_loader import load_track
from engine.tyre_model import load_tyres

class TestSimulator(unittest.TestCase):

    def test_simulate_lap(self):
        track_data = load_track("spa")
        tyre_data = load_tyres()["soft"]
        result = simulate_lap(track_data, tyre_data, weather="dry")
        self.assertIn("total_time", result)

if __name__ == '__main__':
    unittest.main()
