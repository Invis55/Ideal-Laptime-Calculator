import unittest
from engine.physics import calculate_aero_downforce, calculate_braking_distance

class TestPhysics(unittest.TestCase):

    def test_downforce(self):
        downforce = calculate_aero_downforce(300, 1.5)  # speed km/h, aero_coeff
        self.assertGreater(downforce, 0)

    def test_braking_distance(self):
        dist = calculate_braking_distance(300, 100, 3.5)
        self.assertGreater(dist, 0)

if __name__ == '__main__':
    unittest.main()
