"""Dependency-free, offline 3-D viewer for horizontal wind samples at 3-D positions."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


COLORS = ["#2878c7", "#e87924", "#24975a", "#9a5db5", "#c2536f", "#31a5ac"]


def _data(estimates: list[dict], profile: list[dict]) -> dict:
    tracks = defaultdict(list)
    for row in estimates:
        if row["accepted"]:
            tracks[row["child_id"]].append([row["east_m"], row["north_m"], row["alt_m"]])
    for points in tracks.values():
        points.sort(key=lambda point: -point[2])
    measured = [{
        "id": r["child_id"], "x": r["east_m"], "y": r["north_m"], "z": r["alt_m"],
        "u": r["wind_e_ms"], "v": r["wind_n_ms"], "kind": "track estimate",
    } for r in profile]
    by_alt = defaultdict(list)
    for row in profile:
        by_alt[row["alt_m"]].append(row)
    inferred = []
    for altitude, points in by_alt.items():
        if len({p["child_id"] for p in points}) < 3:
            continue
        coords = [(p["east_m"], p["north_m"]) for p in points]
        if not any(abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) > 1e-3
                   for a in coords for b in coords for c in coords):
            continue
        x = sum(p["east_m"] for p in points) / len(points)
        y = sum(p["north_m"] for p in points) / len(points)
        weights = [1 / max((p["east_m"] - x) ** 2 + (p["north_m"] - y) ** 2, 1) for p in points]
        total = sum(weights)
        inferred.append({
            "id": "IDW", "x": x, "y": y, "z": altitude,
            "u": sum(w * p["wind_e_ms"] for w, p in zip(weights, points)) / total,
            "v": sum(w * p["wind_n_ms"] for w, p in zip(weights, points)) / total,
            "kind": "interpolated centroid",
        })
    return {"tracks": dict(tracks), "measured": measured, "inferred": inferred}


def write_html(estimates: list[dict], profile: list[dict], path: Path) -> None:
    payload = json.dumps(_data(estimates, profile), ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    html = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Child CanSat 3D wind view</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#0b1424;color:#e6edf7;font:14px system-ui,sans-serif}
header{padding:16px 22px;border-bottom:1px solid #25354d}h1{font-size:20px;margin:0 0 5px}
p{margin:0;color:#aebed4}.bar{display:flex;gap:20px;align-items:center;flex-wrap:wrap;padding:12px 22px;background:#111e32}
label{display:flex;gap:7px;align-items:center}input[type=range]{width:190px}main{height:calc(100vh - 152px);min-height:420px;position:relative}
canvas{width:100%;height:100%;display:block;cursor:grab}canvas:active{cursor:grabbing}
#readout{position:absolute;left:16px;bottom:14px;background:#101c30d9;padding:9px 12px;border:1px solid #33465f;border-radius:6px}
.legend{display:flex;gap:15px;padding:9px 22px;border-top:1px solid #25354d;color:#b5c5dc}.swatch{display:inline-block;width:13px;height:3px;vertical-align:middle;margin-right:5px}
</style></head><body>
<header><h1>Child CanSat — 3D trajectory and horizontal wind</h1><p>Drag to rotate · wheel to zoom · arrows point where the air moves. Height is observed altitude; vertical wind is not estimated.</p></header>
<div class="bar"><label>Show up to <input id="height" type="range"><span id="heightValue"></span></label>
<label><input id="tracks" type="checkbox" checked>Trajectories</label>
<label><input id="interpolated" type="checkbox" checked>Interpolated centroids</label>
<label>Arrow size <input id="arrow" type="range" min="1" max="12" value="5"><span id="arrowValue">5 m per m/s</span></label></div>
<main><canvas id="view"></canvas><div id="readout">Move over a colored arrow for values.</div></main>
<div class="legend" id="legend"></div>
<script>const DATA=__PAYLOAD__;
const COLORS=__COLORS__;
const canvas=document.getElementById('view'),ctx=canvas.getContext('2d');
const height=document.getElementById('height'),heightValue=document.getElementById('heightValue');
const tracksBox=document.getElementById('tracks'),interpolated=document.getElementById('interpolated');
const arrow=document.getElementById('arrow'),readout=document.getElementById('readout');
const ids=Object.keys(DATA.tracks).sort(), all=Object.values(DATA.tracks).flat();
const legend=document.getElementById('legend');
ids.forEach((id,i)=>{const item=document.createElement('span');item.textContent=id;
 const swatch=document.createElement('i');swatch.className='swatch';swatch.style.background=COLORS[i%COLORS.length];item.prepend(swatch);legend.append(item)});
const inferredLegend=document.createElement('span');inferredLegend.textContent='IDW estimate';
const inferredSwatch=document.createElement('i');inferredSwatch.className='swatch';inferredSwatch.style.background='#929bad';inferredLegend.prepend(inferredSwatch);legend.append(inferredLegend);
const limits=all.length?[0,1,2].map(i=>[Math.min(...all.map(p=>p[i])),Math.max(...all.map(p=>p[i]))]):[[0,1],[0,1],[0,1]];
const center=limits.map(v=>(v[0]+v[1])/2);let yaw=-0.65,pitch=0.48,zoom=1,panX=0,panY=0,hover=[];
height.min=Math.floor(limits[2][0]);height.max=Math.ceil(limits[2][1]);height.value=height.max;
function resize(){const d=window.devicePixelRatio||1;canvas.width=Math.round(canvas.clientWidth*d);canvas.height=Math.round(canvas.clientHeight*d);ctx.setTransform(d,0,0,d,0,0);draw()}
function project(p){const x=p[0]-center[0],y=p[1]-center[1],z=p[2]-center[2];
 const a=Math.cos(yaw)*x-Math.sin(yaw)*y,b=Math.sin(yaw)*x+Math.cos(yaw)*y;
 const span=Math.max(...limits.map(v=>v[1]-v[0]),1);const scale=Math.min(canvas.clientWidth,canvas.clientHeight)*0.72/span*zoom;
 return [canvas.clientWidth/2+panX+a*scale,canvas.clientHeight/2+panY-(Math.cos(pitch)*z-Math.sin(pitch)*b)*scale,
         Math.sin(pitch)*z+Math.cos(pitch)*b]}
function line(a,b,color,width=1,alpha=1){const p=project(a),q=project(b);ctx.strokeStyle=color;ctx.globalAlpha=alpha;ctx.lineWidth=width;
 ctx.beginPath();ctx.moveTo(p[0],p[1]);ctx.lineTo(q[0],q[1]);ctx.stroke();ctx.globalAlpha=1}
function label(p,text,color='#97a9c1'){const v=project(p);ctx.fillStyle=color;ctx.font='12px system-ui';ctx.fillText(text,v[0]+5,v[1]-5)}
function drawArrow(r,color,scale,alpha){const a=[r.x,r.y,r.z],b=[r.x+r.u*scale,r.y+r.v*scale,r.z];
 const p=project(a),q=project(b),angle=Math.atan2(q[1]-p[1],q[0]-p[0]);ctx.globalAlpha=alpha;
 ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=r.kind==='track estimate'?2.4:1.6;
 ctx.beginPath();ctx.moveTo(p[0],p[1]);ctx.lineTo(q[0],q[1]);ctx.stroke();
 ctx.beginPath();ctx.moveTo(q[0],q[1]);ctx.lineTo(q[0]-9*Math.cos(angle-0.48),q[1]-9*Math.sin(angle-0.48));
 ctx.lineTo(q[0]-9*Math.cos(angle+0.48),q[1]-9*Math.sin(angle+0.48));ctx.closePath();ctx.fill();ctx.globalAlpha=1;
 if(r.kind==='track estimate')hover.push({x:p[0],y:p[1],row:r})}
function draw(){if(!canvas.width)return;const w=canvas.clientWidth,h=canvas.clientHeight;ctx.clearRect(0,0,w,h);ctx.fillStyle='#0b1424';ctx.fillRect(0,0,w,h);
 const maxZ=+height.value; heightValue.textContent=maxZ+' m';document.getElementById('arrowValue').textContent=arrow.value+' m per m/s';
 const [xmin,xmax]=limits[0],[ymin,ymax]=limits[1];
 for(let i=0;i<=4;i++){let x=xmin+(xmax-xmin)*i/4,y=ymin+(ymax-ymin)*i/4;
   line([x,ymin,0],[x,ymax,0],'#263a52',1);line([xmin,y,0],[xmax,y,0],'#263a52',1)}
 line([xmin,ymin,0],[xmax,ymin,0],'#cf6872',2);line([xmin,ymin,0],[xmin,ymax,0],'#6fc6a0',2);
 line([xmin,ymin,0],[xmin,ymin,limits[2][1]],'#8eaff0',2);
 label([xmax,ymin,0],'East +','#cf6872');label([xmin,ymax,0],'North +','#6fc6a0');label([xmin,ymin,limits[2][1]],'Altitude +','#8eaff0');
 for(let z=0;z<=maxZ;z+=50){const p=[xmin,ymin,z];label(p,z+' m');line(p,[xmax,ymin,z],'#31455e',1,.6);line(p,[xmin,ymax,z],'#31455e',1,.6)}
 if(tracksBox.checked){ids.forEach((id,i)=>{let pts=DATA.tracks[id].filter(p=>p[2]<=maxZ);
   for(let j=1;j<pts.length;j++)line(pts[j-1],pts[j],COLORS[i%COLORS.length],1.7,.85);
   if(pts.length)label(pts[0],id,COLORS[i%COLORS.length])})}
 hover=[];const layers=[...DATA.measured.filter(r=>r.z<=maxZ).map(r=>({r,color:COLORS[ids.indexOf(r.id)%COLORS.length],a:1}))];
 if(interpolated.checked)layers.push(...DATA.inferred.filter(r=>r.z<=maxZ).map(r=>({r,color:'#9da8bb',a:.7})));
 layers.sort((a,b)=>project([a.r.x,a.r.y,a.r.z])[2]-project([b.r.x,b.r.y,b.r.z])[2]);
 layers.forEach(({r,color,a})=>drawArrow(r,color,+arrow.value,a));}
height.oninput=draw;tracksBox.onchange=draw;interpolated.onchange=draw;arrow.oninput=draw;window.onresize=resize;
let dragging=false,lastX=0,lastY=0;
canvas.onpointerdown=e=>{dragging=true;lastX=e.clientX;lastY=e.clientY;canvas.setPointerCapture(e.pointerId)};
canvas.onpointerup=()=>dragging=false;
canvas.onpointermove=e=>{if(dragging){yaw+=(e.clientX-lastX)*.008;pitch=Math.max(-1.3,Math.min(1.3,pitch+(e.clientY-lastY)*.008));lastX=e.clientX;lastY=e.clientY;draw();return}
 const rect=canvas.getBoundingClientRect(),mx=e.clientX-rect.left,my=e.clientY-rect.top;
 let hit=null,best=14;for(const h of hover){let d=Math.hypot(mx-h.x,my-h.y);if(d<best){best=d;hit=h.row}}
 readout.textContent=hit?`${hit.id} · ${hit.z.toFixed(0)} m · wind E ${hit.u.toFixed(2)}, N ${hit.v.toFixed(2)} m/s · speed ${Math.hypot(hit.u,hit.v).toFixed(2)} m/s`:'Move over a colored arrow for values.'};
canvas.onwheel=e=>{e.preventDefault();zoom=Math.max(.35,Math.min(4,zoom*(e.deltaY<0?1.1:.9)));draw()};
resize();</script></body></html>'''
    path.write_text(html.replace("__PAYLOAD__", payload).replace("__COLORS__", json.dumps(COLORS)), encoding="utf-8")


def write_preview(estimates: list[dict], profile: list[dict], path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = _data(estimates, profile)
    fig = plt.figure(figsize=(11, 8))
    ax = fig.add_subplot(111, projection="3d")
    for i, (child, points) in enumerate(sorted(data["tracks"].items())):
        if not points:
            continue
        x, y, z = zip(*points)
        ax.plot(x, y, z, color=COLORS[i % len(COLORS)], label=child, lw=1.6)
    for i, child in enumerate(sorted(data["tracks"])):
        vectors = [v for v in data["measured"] if v["id"] == child][::2]
        if vectors:
            ax.quiver([v["x"] for v in vectors], [v["y"] for v in vectors], [v["z"] for v in vectors],
                      [v["u"] for v in vectors], [v["v"] for v in vectors], [0] * len(vectors),
                      length=4, normalize=False, color=COLORS[i % len(COLORS)], arrow_length_ratio=.25)
    ax.set(xlabel="East (m)", ylabel="North (m)", zlabel="Relative altitude (m)")
    ax.set_title("3D child trajectories + horizontal wind estimates\nArrows have no measured vertical wind component")
    ax.view_init(elev=24, azim=-65)
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
