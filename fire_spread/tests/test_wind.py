import unittest
from fire_spread.wind import prepare, interpolate
from fire_spread.terrain import offset_coordinate

def state(samples,now=100):
    return {'mode':'LIVE','now':now,'drift':{'origin':[37.,127.], 'samples':samples}}

class WindTest(unittest.TestCase):
    def setUp(self):
        self.field=prepare(state([[95,0,0,100,1,0],[96,100,0,90,3,0],[97,0,100,80,1,2]]))
    def at(self,e,n): return interpolate(self.field,*offset_coordinate(37,127,e,n),max_distance=200)
    def test_different_positions_have_different_vectors(self):
        a=self.at(0,0);b=self.at(100,0)
        self.assertAlmostEqual(a[0],1,places=3);self.assertAlmostEqual(b[0],3,places=3)
    def test_no_extrapolation(self): self.assertIsNone(self.at(90,90))
    def test_distance_limit(self): self.assertIsNone(interpolate(self.field,*offset_coordinate(37,127,30,30),max_distance=10))
    def test_invalid_geometry(self):
        with self.assertRaises(ValueError): prepare(state([[95,0,0,10,1,0],[96,1,0,10,2,0],[97,2,0,10,3,0]]))
    def test_old_samples_rejected(self):
        with self.assertRaises(ValueError): prepare(state([[1,0,0,10,1,0],[2,100,0,10,2,0],[3,0,100,10,3,0]],now=300))
    def test_time_window_excludes_earlier_samples(self):
        f=prepare(state([[20,0,0,10,9,0],[95,0,0,10,1,0],[96,100,0,10,3,0],[97,0,100,10,1,2]]))
        self.assertEqual(len(f['samples']),3)

class ModelWindIntegrationTest(unittest.TestCase):
    def test_each_cell_gets_its_own_wind(self):
        import sys, types
        from unittest.mock import patch
        from fire_spread.model import simulate
        calls=[]
        class Scenario:
            def __init__(self,*args): pass
        class Fuel:
            @staticmethod
            def from_existing(name): return name
        class Run:
            def __init__(self,fuel,moisture,speed,**kwargs): calls.append((speed,kwargs['wind_direction']))
            def run_surface_fire_in_direction_of_interest(self,direction): return {'spread_rate':3.6}
        fake=types.SimpleNamespace(MoistureScenario=Scenario,FuelModel=Fuel,PyrothermelRun=Run)
        samples=[[95,-200,-200,10,1,0],[96,200,-200,10,3,0],[97,-200,200,10,1,2],[98,200,200,10,3,2]]
        field=prepare(state(samples))
        with patch.dict(sys.modules,{'pyrothermel':fake}), patch('fire_spread.model.elevation',return_value=0),patch('fire_spread.model.sample',side_effect=lambda pts:[10]*len(pts)):
            result=simulate(37,127,field,radius=100,cell=50,max_distance=500)
        self.assertEqual(len(calls),25)
        self.assertGreater(len({round(speed,3) for speed,direction in calls}),1)
        self.assertGreater(len({round(direction,3) for speed,direction in calls}),1)
        self.assertEqual(len(result['cells']),25)

class StoredWindTest(unittest.TestCase):
    def test_stored_file_does_not_need_live_clock(self):
        from fire_spread.wind import from_csv
        text='child_id,t_s,lat,lon,alt_m,wind_e_ms,wind_n_ms,accepted\na,1,37,127,100,1,0,1\na,2,37,127.001,90,2,0,1\na,3,37.001,127,80,0,2,1\n'
        field=from_csv(text)
        self.assertEqual(field['mode'],'저장된 관측');self.assertEqual(len(field['samples']),3)
        self.assertIsNotNone(interpolate(field,37.0001,127.0001,200))
    def test_rejects_combined_children(self):
        from fire_spread.wind import from_csv
        text='child_id,t_s,lat,lon,alt_m,wind_e_ms,wind_n_ms,accepted\na,1,37,127,100,1,0,1\nb,2,37,127.001,90,2,0,1\na,3,37.001,127,80,0,2,1\n'
        with self.assertRaises(ValueError): from_csv(text)
