"""Experimental Rothermel-grid simulation; not validated for fire operations."""
import heapq, math
import numpy as np
from .terrain import elevation, offset_coordinate
from .landcover import sample
from .wind import interpolate

# Provisional scenarios, not verified mappings for Korean fuels.
FUEL_SCENARIO = {10:'TL8', 20:'SH1', 30:'GR1', 40:'GR1'}
MAX_GRID_CELLS = 100_000

DIRECTIONS = [(0,1,90),(1,1,45),(1,0,0),(1,-1,315),(0,-1,270),(-1,-1,225),(-1,0,180),(-1,1,135)]

def simulate(lat, lon, field, *, radius=500, cell=50, moisture=.08, wind_factor=1., max_distance=100., wind_method="observed", ground_offset=0., canopy=0., vegetation="grass"):
    import pyrothermel
    if not all(math.isfinite(x) for x in (lat,lon,radius,cell,moisture,wind_factor,max_distance,ground_offset,canopy)):
        raise ValueError('입력값이 유한한 숫자여야 합니다.')
    if not (30 <= lat <= 40 and 124 <= lon <= 132 and 20 <= radius <= 1000 and 5 <= cell <= 200 and 0.01 <= moisture <= .6 and 0 <= wind_factor <= 2 and 10 <= max_distance <= 1000 and -500 <= ground_offset <= 500 and 0 <= canopy <= 60):
        raise ValueError('좌표 또는 시나리오 값이 지원 범위를 벗어났습니다.')
    half = math.ceil(radius / cell); count=2*half+1
    total_cells = count * count
    if total_cells > MAX_GRID_CELLS:
        raise ValueError(f'예상 격자 {total_cells:,}개가 상한 {MAX_GRID_CELLS:,}개를 초과합니다. 반경을 줄이거나 격자 간격을 늘리세요.')
    coords=[offset_coordinate(lat,lon,(c-half)*cell,(r-half)*cell) for r in range(count) for c in range(count)]
    heights=np.array([elevation(*p) for p in coords]).reshape(count,count)
    classes=np.array(sample(coords)).reshape(count,count)
    gn,ge=np.gradient(heights,cell); slopes=np.degrees(np.arctan(np.hypot(ge,gn)))
    # Behave expects aspect as downslope direction clockwise from north.
    aspects=np.degrees(np.arctan2(-ge,-gn))%360
    wind_metadata={'method':'observed interpolation'}
    if wind_method=='terrain':
        from .terrain_wind import run
        winds,wind_metadata=run(field,lat,lon,radius,coords,ground_offset=ground_offset,canopy=canopy,vegetation=vegetation)
    elif wind_method=='observed':
        winds=[interpolate(field,la,lo,max_distance) for la,lo in coords]
    else: raise ValueError('알 수 없는 바람장 계산 방식')
    moist=pyrothermel.MoistureScenario(moisture,moisture,moisture,0.6,0.9)
    fuel={code:pyrothermel.FuelModel.from_existing(name) for code,name in FUEL_SCENARIO.items()}
    rates=np.zeros((count,count,8)); valid=np.isin(classes,list(fuel)) & np.array([w is not None for w in winds]).reshape(count,count)
    for r in range(count):
        for c in range(count):
            code=int(classes[r,c])
            if not valid[r,c]: continue
            wind_e,wind_n=winds[r*count+c]
            velocity=math.hypot(wind_e,wind_n)*wind_factor*3.6
            wind_from=(math.degrees(math.atan2(wind_e,wind_n))+180)%360
            run=pyrothermel.PyrothermelRun(fuel[code],moist,velocity,wind_input_mode='direct_midflame',wind_direction=wind_from,slope=float(slopes[r,c]),aspect=float(aspects[r,c]))
            for k,(_,_,bearing) in enumerate(DIRECTIONS):
                rates[r,c,k]=max(0.,run.run_surface_fire_in_direction_of_interest(bearing)['spread_rate']/3.6)
    arrival=arrival_times(rates,valid,cell,half,half)
    cells=[]
    for i,(la,lo) in enumerate(coords):
        r,c=divmod(i,count); value=arrival[r,c]
        cells.append({'lat':la,'lon':lo,'landcover':int(classes[r,c]),'altitude_m':float(heights[r,c]),'slope_deg':float(slopes[r,c]),'arrival_min':float(value/60) if math.isfinite(value) else None,'wind':winds[i]})
    return {'wind_model':wind_metadata,'cells':cells,'cell_m':cell,'wind_observations':len(field['samples']),'wind_time_span_s':field['duration_s'],'wind_altitude_range_m':field['altitude_range_m'],'wind_newest_age_s':field['newest_age_s'],'wind_factor':wind_factor,'moisture':moisture,'fuel_scenarios':FUEL_SCENARIO,'warnings':['연구용 시나리오: 실제 화재 예측·대응에 사용 금지','토지피복에서 연료 모델을 임의 대응했으며 현장 검증되지 않음','연료 수분과 화염 높이 풍속 보정은 사용자 가정','관측 고도를 구분하지 않은 수평 보간이며 지표풍으로 검증되지 않음','지형 모델의 관측 경로 밖 결과는 관측값이 아닌 모델 추정값','미계산 영역은 안전을 뜻하지 않음']}

def arrival_times(rates,valid,cell,start_r,start_c):
    h,w=valid.shape
    if not valid[start_r,start_c]: raise ValueError('발화점이 유효한 바람 관측 범위 밖이거나 연료 시나리오가 없습니다.')
    times=np.full((h,w),np.inf);times[start_r,start_c]=0.;queue=[(0.,start_r,start_c)]
    while queue:
        t,r,c=heapq.heappop(queue)
        if t != times[r,c]: continue
        for k,(dr,dc,_) in enumerate(DIRECTIONS):
            rr,cc=r+dr,c+dc
            if not (0<=rr<h and 0<=cc<w and valid[rr,cc]): continue
            # Prevent diagonal jumping over unknown/unmodelled cells.
            if dr and dc and (not valid[r,cc] or not valid[rr,c]): continue
            v=rates[r,c,k]
            if v<=0: continue
            nt=t+cell*math.hypot(dr,dc)/v
            if nt<times[rr,cc]: times[rr,cc]=nt;heapq.heappush(queue,(nt,rr,cc))
    return times
