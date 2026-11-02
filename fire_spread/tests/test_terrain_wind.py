import unittest
from unittest.mock import patch
from fire_spread.terrain_wind import profile,stations
from fire_spread.wind import from_csv

class ProfileTests(unittest.TestCase):
    def field(self):
        return {'origin':[37,127],'samples':[(0,0,0,25,2,0),(1,1,0,26,0,2),(2,2,0,45,-1,0)]}
    def test_altitude_bins_preserve_vector_components(self):
        p=profile(self.field())
        self.assertEqual(len(p),2);self.assertEqual(p[0]['east'],1);self.assertEqual(p[0]['north'],1)
    def test_sensor_height_and_from_direction(self):
        with patch('fire_spread.terrain_wind.elevation',return_value=10):
            rows=stations(self.field(),ground_offset=3,canopy=2)
        self.assertAlmostEqual(rows[0][5],16.5)
        self.assertAlmostEqual(rows[0][9],225.)
    def test_impossible_heights_are_rejected(self):
        with patch('fire_spread.terrain_wind.elevation',return_value=1000):
            with self.assertRaises(ValueError): stations(self.field())
    def test_collinear_record_is_available_for_profile_model(self):
        text='child_id,t_s,lat,lon,alt_m,wind_e_ms,wind_n_ms,accepted\na,0,37,127,50,1,0,1\na,1,37,127,40,2,0,1\na,2,37,127,30,3,0,1\n'
        self.assertEqual(len(profile(from_csv(text))),3)

    def test_single_valid_altitude_is_not_silently_used(self):
        f={'origin':[37,127],'samples':[(0,0,0,25,2,0),(1,1,0,26,0,2)]}
        with patch('fire_spread.terrain_wind.elevation',return_value=10):
            with self.assertRaises(ValueError): stations(f)
