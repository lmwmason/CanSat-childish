import unittest
import numpy as np
from fire_spread.model import arrival_times

class ArrivalTests(unittest.TestCase):
    def test_uniform_speed(self):
        valid=np.ones((3,3),bool);rate=np.ones((3,3,8));t=arrival_times(rate,valid,10,1,1)
        self.assertAlmostEqual(t[1,2],10);self.assertAlmostEqual(t[2,2],10*2**.5)
    def test_no_corner_cutting(self):
        valid=np.ones((3,3),bool);valid[1,2]=False;valid[2,1]=False
        t=arrival_times(np.ones((3,3,8)),valid,10,1,1)
        self.assertGreater(t[2,2],10*2**.5)
    def test_invalid_ignition(self):
        with self.assertRaises(ValueError): arrival_times(np.ones((1,1,8)),np.zeros((1,1),bool),10,0,0)

class BehaveConventionTests(unittest.TestCase):
    def test_eastward_wind_has_maximum_spread_eastward(self):
        try:
            import pyrothermel
        except ImportError:
            self.skipTest('pyrothermel is not installed')
        f=pyrothermel.FuelModel.from_existing('GR1')
        m=pyrothermel.MoistureScenario(.08,.08,.08,.6,.9)
        # Meteorological wind-from west corresponds to air moving east.
        r=pyrothermel.PyrothermelRun(f,m,10,wind_input_mode='direct_midflame',wind_direction=270,slope=0,aspect=0)
        self.assertAlmostEqual(r.run_surface_fire_in_direction_of_max_spread()['direction'],90,places=4)
        east=r.run_surface_fire_in_direction_of_interest(90)['spread_rate']
        west=r.run_surface_fire_in_direction_of_interest(270)['spread_rate']
        self.assertGreater(east,west)
