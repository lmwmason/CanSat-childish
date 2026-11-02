import unittest
from fire_spread.landcover import tile_name

class LandCoverTest(unittest.TestCase):
    def test_tile(self): self.assertEqual(tile_name(37.5, 127), 'N36E126')
    def test_tile_boundary(self): self.assertEqual(tile_name(39, 129), 'N39E129')
    def test_negative_floor(self): self.assertEqual(tile_name(-0.1, -0.1), 'S03W003')
    def test_invalid(self):
        with self.assertRaises(ValueError): tile_name(float('nan'), 0)
