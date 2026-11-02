import unittest
from unittest.mock import patch
from PIL import Image
from fire_spread.terrain import tile_pixel, elevation, offset_coordinate

class TerrainTest(unittest.TestCase):
    def test_equator_tile_and_pixel(self):
        self.assertEqual(tile_pixel(0, 0, 2), (2, 2, 0, 0))
    def test_decode_pixel(self):
        with patch('fire_spread.terrain._tile', return_value=Image.new('RGB', (256, 256), (128, 23, 128))):
            self.assertEqual(elevation(37.5, 127), 23.5)
    def test_reject_invalid_coordinate(self):
        with self.assertRaises(ValueError): tile_pixel(float('nan'), 0)
    def test_offset_directions(self):
        lat, lon = offset_coordinate(37, 127, 100, 100)
        self.assertGreater(lat, 37); self.assertGreater(lon, 127)
if __name__ == '__main__': unittest.main()
