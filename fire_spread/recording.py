"""Offline adapters for files already written by the KAIST ground station."""
import csv
import io
import json
import math
from .wind import from_csv

MAX_TEXT = 50_000_000

def load_observations(text):
    if len(text) > MAX_TEXT:
        raise ValueError('입력 기록은 50 MB 이하여야 합니다.')
    first=text.lstrip('\ufeff \t\r\n')
    if first.startswith('{'):
        fixes=traffic_fixes(first)
        return estimate_fixes(fixes,'traffic.jsonl')
    reader=csv.DictReader(io.StringIO(first))
    names=set(reader.fieldnames or ())
    if {'elapsed_s','kind','data_json'}.issubset(names):
        return estimate_fixes(event_fixes(reader),'events.csv')
    if {'wind_e_ms','wind_n_ms'}.issubset(names):
        return from_csv(first)
    raise ValueError('지상국 events.csv 또는 traffic.jsonl 파일을 선택하세요.')

def gps_fix(t,data):
    if not data.get('fix'): return None
    try: values=(float(t),float(data['lat']),float(data['lon']),float(data['altitude_m']))
    except (KeyError,TypeError,ValueError): return None
    if not all(math.isfinite(v) for v in values): return None
    return values

def event_fixes(reader):
    fixes=[]
    # JPEG hex may exceed Python's default CSV field limit.
    csv.field_size_limit(MAX_TEXT)
    for row in reader:
        if row.get('kind')!='GPS': continue
        if row.get('checksum','').lower() not in ('true','1'): continue
        fix=gps_fix(row['elapsed_s'],json.loads(row['data_json']))
        if fix: fixes.append(fix)
    return fixes

def traffic_fixes(text):
    from kaist_ground_station.protocol import StreamParser
    parser=StreamParser();fixes=[];last=-math.inf
    for line in text.splitlines():
        if not line.strip(): continue
        row=json.loads(line);t=float(row['t'])
        if not math.isfinite(t) or t<last: raise ValueError('기록 시각은 유한하고 오름차순이어야 합니다.')
        last=t
        if row['direction']!='rx': continue
        for frame in parser.feed(bytes.fromhex(row['hex']),t):
            if frame.kind=='GPS' and frame.checksum:
                fix=gps_fix(t,frame.data)
                if fix: fixes.append(fix)
    return fixes

def estimate_fixes(fixes,source):
    from wind_field import core
    if len(fixes)<5: raise ValueError('기록에 바람을 추정할 유효 GPS 관측이 부족합니다.')
    if any(b[0] <= a[0] for a,b in zip(fixes,fixes[1:])):
        # Merge duplicate reception times, but reject resets / concatenated sessions.
        if any(b[0]<a[0] for a,b in zip(fixes,fixes[1:])): raise ValueError('여러 세션이 섞인 기록은 사용할 수 없습니다. 한 기록을 선택하세요.')
        fixes=list(dict((f[0],f) for f in fixes).values())
    rows=[{'child_id':'recording','t_s':t,'lat':lat,'lon':lon,'alt_m':alt,'pressure_hPa':math.nan,'temp_C':math.nan} for t,lat,lon,alt in fixes]
    result,_=core.estimate(rows,core.Config(window_s=11.,release_exclude_s=0.,altitude_bin_m=5.))
    # Match the complete smoothing windows used by the station's drift view.
    result=[r for r in result if r['t_s']<=fixes[-1][0]-5.5]
    out=io.StringIO();fields=['child_id','t_s','lat','lon','alt_m','wind_e_ms','wind_n_ms','accepted']
    writer=csv.DictWriter(out,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(result)
    field=from_csv(out.getvalue());field['mode']='저장된 지상국 기록';field['source_format']=source
    return field
