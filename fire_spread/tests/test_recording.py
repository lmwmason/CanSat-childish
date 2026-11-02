import csv,io,json,math,unittest
from fire_spread.recording import load_observations

class RecordingInputTests(unittest.TestCase):
    def events(self):
        out=io.StringIO();w=csv.writer(out);w.writerow(['utc','elapsed_s','kind','checksum','data_json','frame_hex'])
        for i in range(80):
            data={'fix':1,'lat':37+0.0002*math.sin(i/25),'lon':127+0.0002*math.cos(i/25),'altitude_m':150-i}
            w.writerow(['',i,'GPS',True,json.dumps(data),''])
        return out.getvalue()
    def test_station_events_are_analyzed_without_intermediate_file(self):
        f=load_observations(self.events())
        self.assertEqual(f['source_format'],'events.csv')
        self.assertGreater(len(f['samples']),3)
    def test_no_gps_is_explicit_error(self):
        with self.assertRaises(ValueError): load_observations('elapsed_s,kind,checksum,data_json\n0,IMU,True,{}\n')
    def test_invalid_format(self):
        with self.assertRaises(ValueError): load_observations('hello,world\n1,2\n')
