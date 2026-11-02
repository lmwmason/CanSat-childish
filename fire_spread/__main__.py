"""Local research interface; stored wind analysis is the default input."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen
import json
from .model import simulate
from .wind import prepare, from_csv, interpolate
from .recording import load_observations
from .terrain_wind import profile
from .terrain import offset_coordinate

ROOT = Path(__file__).resolve().parent.parent
HTML = (Path(__file__).parent / 'index.html').read_bytes()

def station_field():
    with urlopen('http://127.0.0.1:8765/api/state', timeout=5) as response:
        return prepare(json.load(response))

def describe(field):
    observations=[]
    for s in field['samples']:
        lat,lon=offset_coordinate(*field['origin'],s[1],s[2])
        observations.append({'lat':lat,'lon':lon,'east':s[4],'north':s[5],'altitude':s[3]})
    polygon=[offset_coordinate(*field['origin'],east,north) for east,north in field['hull']]
    evalues=[p[0] for p in field['hull']]; nvalues=[p[1] for p in field['hull']]
    step=max(max(evalues)-min(evalues),max(nvalues)-min(nvalues))/14
    vectors=[]
    if step>0:
        for i in range(15):
            for j in range(15):
                lat,lon=offset_coordinate(*field['origin'],min(evalues)+i*step,min(nvalues)+j*step)
                velocity=interpolate(field,lat,lon,100.)
                if velocity is not None: vectors.append({'lat':lat,'lon':lon,'east':velocity[0],'north':velocity[1]})
    return {'count':len(observations),'altitude_range_m':field['altitude_range_m'], 'duration_s':field['duration_s'], 'mode':field['mode'],'observations':observations,'polygon':polygon,'vectors':vectors,'vector_spacing_m':step,'profile':profile(field)}


class Handler(BaseHTTPRequestHandler):
    def respond(self,status,content,typ):
        self.send_response(status);self.send_header('Content-Type',typ);self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(content)
    def json(self,status,obj): return self.respond(status,json.dumps(obj,ensure_ascii=False,allow_nan=False).encode(),'application/json')
    def do_GET(self):
        if self.path=='/': return self.respond(200,HTML,'text/html; charset=utf-8')
        if self.path=='/wind':
            try: return self.json(200,describe(station_field()))
            except Exception as e: return self.json(503,{'error':str(e)})
        self.respond(404,b'Not found','text/plain')
    def do_POST(self):
        if self.path not in ('/inspect','/simulate'): return self.respond(404,b'Not found','text/plain')
        if self.headers.get('Origin','') not in ('http://127.0.0.1:8766','http://localhost:8766'): return self.respond(403,b'Forbidden','text/plain')
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=51_000_000: raise ValueError('파일 또는 요청 크기가 너무 큽니다.')
            d=json.loads(self.rfile.read(size))
            field=station_field() if d.get('source')=='live' else load_observations(str(d.get('csv','')))
            if self.path=='/inspect': return self.json(200,describe(field))
            return self.json(200,simulate(float(d['lat']),float(d['lon']),field,radius=float(d['radius']),cell=float(d['cell']),moisture=float(d['moisture']),wind_factor=float(d['wind_factor']),max_distance=float(d['max_distance']),wind_method=str(d.get('wind_method','observed')),ground_offset=float(d.get('ground_offset',0)),canopy=float(d.get('canopy',0)),vegetation=str(d.get('vegetation','grass'))))
        except Exception as e: return self.json(400,{'error':str(e)})

def main():
    server=ThreadingHTTPServer(('127.0.0.1',8766),Handler)
    print('연구용 지도: http://127.0.0.1:8766',flush=True)
    server.serve_forever()
if __name__=='__main__':main()
