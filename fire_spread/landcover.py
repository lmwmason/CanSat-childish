"""Point sampling of ESA WorldCover 2021 COGs, grouped by geographic tile."""
from __future__ import annotations
from collections import defaultdict
import math

ROOT = 'https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map'

def tile_name(lat: float, lon: float) -> str:
    if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat < 90 and -180 <= lon < 180):
        raise ValueError('Invalid coordinate')
    south, west = 3 * math.floor(lat / 3), 3 * math.floor(lon / 3)
    return f'{"N" if south >= 0 else "S"}{abs(south):02d}{"E" if west >= 0 else "W"}{abs(west):03d}'

def tile_url(name: str) -> str:
    return f'{ROOT}/ESA_WorldCover_10m_2021_v200_{name}_Map.tif'

def sample(points):
    """Return integer map codes in input order; raise on missing tiles or invalid pixels."""
    import rasterio
    pts = list(points)
    groups = defaultdict(list)
    for i, (lat, lon) in enumerate(pts):
        groups[tile_name(lat, lon)].append((i, lat, lon))
    values = [None] * len(pts)
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', GDAL_HTTP_TIMEOUT='30'):
        for name, items in groups.items():
            with rasterio.open(tile_url(name)) as ds:
                if str(ds.crs) != 'EPSG:4326':
                    raise ValueError('Unexpected WorldCover CRS')
                for (i, lat, lon), value in zip(items, ds.sample([(lon, lat) for _,lat,lon in items], masked=True)):
                    if bool(value.mask[0]) or int(value[0]) == 0:
                        raise ValueError(f'WorldCover missing at {lat}, {lon}')
                    values[i] = int(value[0])
    return values
