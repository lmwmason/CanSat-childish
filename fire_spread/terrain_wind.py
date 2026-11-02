"""WindNinja point initialization from altitude-binned CanSat observations."""
import csv,math,os,shutil,subprocess,tempfile
from pathlib import Path
import numpy as np
from .terrain import elevation,offset_coordinate

HEADER=['Station_Name','Coord_Sys(PROJCS,GEOGCS)','Datum(WGS84,NAD83,NAD27)','Lat/YCoord','Lon/XCoord','Height','Height_Units(meters,feet)','Speed','Speed_Units(mph,kph,mps,kts)','Direction(degrees)','Temperature','Temperature_Units(F,C)','Cloud_Cover(%)','Radius_of_Influence','Radius_of_Influence_Units(miles,feet,meters,km)','date_time']

def executable():
    value=os.environ.get('WINDNINJA_CLI') or shutil.which('WindNinja_cli')
    if not value or not Path(value).is_file(): raise ValueError('WindNinja 실행 경로가 없습니다. WINDNINJA_CLI를 설정하세요.')
    return str(Path(value).resolve())

def profile(field,bin_m=10.):
    buckets={}
    for t,e,n,z,u,v in field['samples']:
        buckets.setdefault(math.floor(z/bin_m),[]).append((e,n,z,u,v))
    rows=[]
    for _,values in sorted(buckets.items()):
        a=np.array(values);e,n,z,u,v=a.mean(axis=0)
        lat,lon=offset_coordinate(*field['origin'],float(e),float(n))
        rows.append({'lat':lat,'lon':lon,'altitude_m':float(z),'east':float(u),'north':float(v),'count':len(values)})
    return rows

def stations(field,ground_offset=0.,canopy=0.):
    out=[]
    for i,p in enumerate(profile(field)):
        ground=elevation(p['lat'],p['lon'])
        height=p['altitude_m']+ground_offset-ground-canopy
        if not 2<=height<=500: continue
        speed=math.hypot(p['east'],p['north'])
        direction=(math.degrees(math.atan2(p['east'],p['north']))+180)%360
        out.append([f'CanSat_{i}','GEOGCS','WGS84',p['lat'],p['lon'],height,'meters',speed,'mps',direction,20,'C',0,-1,'meters',''])
    if len(out)<2: raise ValueError('지형·수관 기준으로 유효한 고도 구간이 2개 이상 필요합니다. GPS와 지형의 고도 기준을 확인하세요.')
    return out

def run(field,lat,lon,radius,coords,*,ground_offset=0.,canopy=0.,vegetation='grass',work_root=None):
    import rasterio
    from rasterio.transform import from_origin
    from rasterio.warp import transform
    cli=executable()
    if vegetation not in ('grass','brush','trees'): raise ValueError('잘못된 지표 거칠기 유형')
    # Enlarge the DEM beyond the requested fire domain to reduce boundary influence.
    half=max(radius+500,1000);step=30.;n=math.ceil(2*half/step)+1
    epsg=32600+int((lon+180)//6)+1
    crs=f'EPSG:{epsg}';cx,cy=transform('EPSG:4326',crs,[lon],[lat]);left=cx[0]-half;top=cy[0]+half
    xx=[];yy=[]
    for r in range(n):
        for c in range(n):xx.append(left+(c+.5)*step);yy.append(top-(r+.5)*step)
    lons,lats=transform(crs,'EPSG:4326',xx,yy)
    dem=np.array([elevation(la,lo) for la,lo in zip(lats,lons)],dtype='float32').reshape(n,n)
    station_rows=stations(field,ground_offset,canopy)
    sx,sy=transform('EPSG:4326',crs,[s[4] for s in station_rows],[s[3] for s in station_rows])
    if any(not(left<x<left+n*step and top-n*step<y<top) for x,y in zip(sx,sy)):
        raise ValueError('관측 위치가 계산 지형 영역 밖입니다. 관측 지역에서 발화점을 선택하세요.')
    root=Path(work_root or Path(__file__).resolve().parent.parent/'log'/'fire-spread'/'windninja');root.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix='run-',dir=root)).resolve()
    with rasterio.open(work/'terrain.tif','w',driver='GTiff',height=n,width=n,count=1,dtype='float32',crs=crs,transform=from_origin(left,top,step,step)) as ds:ds.write(dem,1)
    station_files=[]
    for i,row in enumerate(station_rows):
        path=work/f'station_{i}.csv';station_files.append(path)
        with path.open('w',newline='') as f:
            writer=csv.writer(f);writer.writerow(HEADER);writer.writerow(row)
    (work/'stations.csv').write_text('Recent_Station_File_List,\n'+'\n'.join(p.name for p in station_files)+'\n')
    config={'num_threads':2,'elevation_file':work/'terrain.tif','initialization_method':'pointInitialization','match_points':'false','wx_station_filename':work/'stations.csv','output_wind_height':2,'units_output_wind_height':'m','output_speed_units':'mps','vegetation':vegetation,'mesh_resolution':30,'units_mesh_resolution':'m','write_ascii_output':'true','ascii_out_resolution':30,'units_ascii_out_resolution':'m','output_path':work}
    (work/'run.cfg').write_text('\n'.join(f'{k} = {v}' for k,v in config.items())+'\n')
    env=os.environ.copy();env['WINDNINJA_DATA']=str(Path(cli).parent.parent/'share'/'windninja');env['OMP_NUM_THREADS']='2';env['PROJ_DATA']=str(Path(cli).parent.parent/'share'/'proj');env['PROJ_LIB']=env['PROJ_DATA']
    try:
        result=subprocess.run([cli,str(work/'run.cfg')],capture_output=True,text=True,timeout=180,env=env)
    except subprocess.TimeoutExpired as exc:
        (work/'timeout.txt').write_text('WindNinja exceeded 180 seconds')
        raise ValueError(f'WindNinja 계산 시간 초과. 기록: {work}') from exc
    (work/'stdout.txt').write_text(result.stdout);(work/'stderr.txt').write_text(result.stderr)
    if result.returncode:raise ValueError(f'WindNinja 계산 실패. 기록: {work}')
    speeds=list(work.glob('*_vel.asc'));angles=list(work.glob('*_ang.asc'))
    if len(speeds)!=1 or len(angles)!=1:raise ValueError(f'WindNinja 출력 형식을 확인해야 합니다: {work}')
    with rasterio.open(speeds[0]) as speed,rasterio.open(angles[0]) as direction:
        xs,ys=transform('EPSG:4326',speed.crs,[c[1] for c in coords],[c[0] for c in coords]);points=list(zip(xs,ys));winds=[]
        for v,a in zip(speed.sample(points,masked=True),direction.sample(points,masked=True)):
            if np.ma.is_masked(v[0]) or np.ma.is_masked(a[0]): winds.append(None);continue
            magnitude=float(v[0]);angle=math.radians(float(a[0]));
            if not (math.isfinite(magnitude) and math.isfinite(angle)) or magnitude<0: winds.append(None);continue
            winds.append((-magnitude*math.sin(angle),-magnitude*math.cos(angle)))
    return winds,{'method':'WindNinja point initialization','station_count':len(station_rows),'profile_bin_count':len(profile(field)),'output_height_above_vegetation_m':2,'ground_offset_m':ground_offset,'canopy_height_m':canopy,'vegetation':vegetation,'log_directory':str(work),'profile':profile(field)}
