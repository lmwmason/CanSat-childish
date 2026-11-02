"""Local, time-windowed horizontal drift field. Heights are not converted to surface wind."""
import math
import numpy as np
from .terrain import EARTH_RADIUS_M

def cross(a,b,c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])

def hull(points):
    p=sorted(set((float(x),float(y)) for x,y in points))
    if len(p)<3: return p
    lo=[]
    for q in p:
        while len(lo)>=2 and cross(lo[-2],lo[-1],q)<=0: lo.pop()
        lo.append(q)
    hi=[]
    for q in reversed(p):
        while len(hi)>=2 and cross(hi[-2],hi[-1],q)<=0: hi.pop()
        hi.append(q)
    return lo[:-1]+hi[:-1]

def inside(poly,p):
    return len(poly)>=3 and all(cross(a,b,p)>=-1e-7 for a,b in zip(poly,poly[1:]+poly[:1]))

def prepare(state,max_age=120.,window=60.):
    if state.get('mode') not in ('LIVE','REPLAY'): raise ValueError('실행 중인 지상국 세션이 필요합니다.')
    drift=state.get('drift') or {}; origin=drift.get('origin'); raw=drift.get('samples') or []
    if not origin or len(origin)!=2: raise ValueError('바람 관측의 기준 좌표가 없습니다.')
    now=float(state['now']); valid=[]
    for s in raw:
        if len(s)!=6: continue
        try: t,e,n,alt,ve,vn=map(float,s)
        except (ValueError,TypeError): continue
        if all(math.isfinite(x) for x in (t,e,n,alt,ve,vn)) and 0 <= now-t <= max_age:
            valid.append((t,e,n,alt,ve,vn))
    if not valid: raise ValueError('지정 시간 안에 유효한 바람 관측이 없습니다.')
    newest=max(s[0] for s in valid);valid=[s for s in valid if newest-s[0]<=window]
    polygon=hull([(s[1],s[2]) for s in valid])
    if len(polygon)<3: raise ValueError('바람 관측이 세 점 이상 넓게 분포하지 않아 2차원 영역을 보간할 수 없습니다.')
    area=abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(polygon,polygon[1:]+polygon[:1])))/2
    if area < 1.: raise ValueError('관측 경로가 거의 일직선이어서 2차원 보간 영역이 없습니다.')
    return {'origin':list(map(float,origin)), 'samples':valid, 'hull':polygon,'newest_age_s':now-newest,'duration_s':newest-min(s[0] for s in valid),'altitude_range_m':[min(s[3] for s in valid),max(s[3] for s in valid)],'mode':state['mode']}

def interpolate(field,lat,lon,max_distance=100.):
    lat0,lon0=field['origin']
    e=EARTH_RADIUS_M*math.cos(math.radians(lat0))*math.radians(lon-lon0)
    n=EARTH_RADIUS_M*math.radians(lat-lat0)
    if not inside(field['hull'],(e,n)): return None
    samples=field['samples']; d=np.array([math.hypot(s[1]-e,s[2]-n) for s in samples])
    if d.min()>max_distance: return None
    indices=np.where(d<=max_distance)[0]
    if not len(indices): return None
    if d.min()<1e-6:
        indices=np.where(d<1e-6)[0];weights=np.ones(len(indices))
    else: weights=1/np.maximum(d[indices],1.)**2
    ve=sum(weights[j]*samples[i][4] for j,i in enumerate(indices))/sum(weights)
    vn=sum(weights[j]*samples[i][5] for j,i in enumerate(indices))/sum(weights)
    return float(ve),float(vn)

def from_csv(text, window=60.):
    """Read one previously analyzed wind_samples.csv without treating relative time as UTC."""
    import csv,io
    if len(text)>2_000_000: raise ValueError('파일 크기가 너무 큽니다.')
    reader=csv.DictReader(io.StringIO(text))
    required={'t_s','lat','lon','alt_m','wind_e_ms','wind_n_ms','accepted','child_id'}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError('windField wind_samples.csv 형식이 아닙니다.')
    rows=[];ids=set()
    for i,r in enumerate(reader):
        if i>=20000: raise ValueError('표본 수가 너무 많습니다.')
        if r.get('accepted','').strip() not in ('1','1.0'): continue
        try: t,lat,lon,alt,ve,vn=(float(r[k]) for k in ('t_s','lat','lon','alt_m','wind_e_ms','wind_n_ms'))
        except (TypeError,ValueError,KeyError): continue
        if not all(math.isfinite(v) for v in (t,lat,lon,alt,ve,vn)) or not (30<=lat<=40 and 124<=lon<=132): continue
        ids.add(r.get('child_id','').strip());rows.append((t,lat,lon,alt,ve,vn))
    if len(ids)!=1: raise ValueError('서로 다른 Child 자료를 합치지 말고 한 비행의 파일을 선택하세요.')
    if not rows: raise ValueError('유효한 관측이 없습니다.')
    newest=max(r[0] for r in rows); rows=[r for r in rows if newest-r[0]<=window]
    lat0,lon0=rows[0][1:3]
    samples=[(t,EARTH_RADIUS_M*math.cos(math.radians(lat0))*math.radians(lon-lon0),EARTH_RADIUS_M*math.radians(lat-lat0),alt,ve,vn) for t,lat,lon,alt,ve,vn in rows]
    polygon=hull([(s[1],s[2]) for s in samples])
    if len(samples)<3: raise ValueError('바람 관측이 3개 이상 필요합니다.')
    return {'origin':[lat0,lon0],'samples':samples,'hull':polygon,'newest_age_s':0.,'duration_s':newest-min(s[0] for s in samples),'altitude_range_m':[min(s[3] for s in samples),max(s[3] for s in samples)],'mode':'저장된 관측','child_id':next(iter(ids))}
