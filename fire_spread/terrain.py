"""Fetch and decode Terrarium elevation tiles; not a fire prediction model."""
from __future__ import annotations
import io
import math
from functools import lru_cache
from urllib.request import Request, urlopen
from PIL import Image

EARTH_RADIUS_M = 6371008.8
TILE_URL = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'

def tile_pixel(lat: float, lon: float, zoom: int = 14):
    if not (math.isfinite(lat) and math.isfinite(lon) and -85 < lat < 85 and -180 <= lon < 180 and 0 <= zoom <= 15):
        raise ValueError('Invalid coordinate or zoom')
    n = 1 << zoom
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    tx, ty = int(x), int(y)
    return tx, ty, min(255, int((x-tx)*256)), min(255, int((y-ty)*256))

@lru_cache(maxsize=128)
def _tile(zoom: int, x: int, y: int):
    request = Request(TILE_URL.format(z=zoom, x=x, y=y), headers={'User-Agent': 'CanSat-fire-research/0.1'})
    with urlopen(request, timeout=20) as response:
        data = response.read(4_000_001)
    if len(data) > 4_000_000:
        raise ValueError('Terrain tile exceeds size limit')
    image = Image.open(io.BytesIO(data)).convert('RGB')
    if image.size != (256, 256):
        raise ValueError('Unexpected terrain tile size')
    return image

def elevation(lat: float, lon: float, zoom: int = 14) -> float:
    tx, ty, px, py = tile_pixel(lat, lon, zoom)
    red, green, blue = _tile(zoom, tx, ty).getpixel((px, py))
    return red * 256 + green + blue / 256 - 32768

def offset_coordinate(lat: float, lon: float, east_m: float, north_m: float):
    """Local approximation for small domains away from the poles."""
    if abs(lat) >= 80:
        raise ValueError('Local projection is limited to latitudes below 80 degrees')
    return (lat + math.degrees(north_m / EARTH_RADIUS_M),
            lon + math.degrees(east_m / (EARTH_RADIUS_M * math.cos(math.radians(lat)))))
