"""Three.js WebGL scene + live sidebar — the hero app.

Renders one self-contained HTML file that:
  - Fills the viewport with a Martian terrain scene
  - Has a docked sidebar showing live mission stats (reads plan.json)
  - Auto-refreshes when plan.json changes
  - Animates a detailed rover along the planned route
  - Shows dust particles + darkened sky during storm sols
  - Draws waypoint dots on the route colour-coded by sol
"""
from __future__ import annotations
import json
import numpy as np
from pathlib import Path


def render_three(elev, tclass, tau, route, deposits, start,
                 save="demo/plan_three.html",
                 title="Sol-Window Planner"):
    H, W = elev.shape
    step = max(1, max(H, W) // 220)
    e = elev[::step, ::step].astype(float)
    tc = tclass[::step, ::step].astype(int)
    h, w = e.shape

    payload = {
        "title": title,
        "w": w, "h": h, "step": step,
        "elev": e.flatten().tolist(),
        "eMin": float(e.min()), "eMax": float(e.max()),
        "terrainClass": tc.flatten().tolist(),
        "route": [[int(r // step), int(c // step)] for r, c in route.path],
        "routeSols": list(map(int, route.sols)),
        "eta": float(route.eta_sols),
        "totalKm": float(route.total_m) / 1000.0,
        "idleSols": int(route.idle_sols),
        "tau": [float(x) for x in tau],
        "deposits": [
            {"row": int(row // step), "col": int(col // step),
             "name": name, "depth": float(depth), "yield": float(y)}
            for row, col, depth, y, name in
            zip(deposits.row, deposits.col, deposits.depth_m,
                deposits.yield_kg_m2, deposits["name"])
        ],
        "start": [int(start[0] // step), int(start[1] // step)],
    }
    html = _HTML.replace("__PAYLOAD__", json.dumps(payload))
    Path(save).parent.mkdir(parents=True, exist_ok=True)
    Path(save).write_text(html)
    return save


_HTML = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>Sol-Window Planner · Mission View</title>
<style>
:root{
  --bg:#0f0806;--panel:rgba(20,10,5,0.85);--border:#6b3f22;
  --text:#e8d7b7;--dim:#c9a37c;--fade:#a07a55;
  --accent:#ffb060;--route:#ff5040;
  --coral-50:#3a1a10;--coral-80:#ff9b83;
  --green-50:#123420;--green-80:#8ff0b2;
  --blue-50:#0f2036;--blue-80:#8fc0ff;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0;height:100%;background:#000;color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
  overflow:hidden;}
#stage{position:absolute;top:0;left:0;right:340px;bottom:0;}
#scene{position:absolute;inset:0;}
#hud{position:absolute;top:14px;left:14px;padding:12px 16px;
  background:var(--panel);border:1px solid var(--border);border-radius:10px;
  backdrop-filter:blur(6px);min-width:240px;font-size:12px;z-index:10;}
#hud h1{margin:0 0 4px;font-size:14px;font-weight:600;color:#ffd7a8;letter-spacing:0.02em}
#hud .sub{font-size:10px;color:var(--dim);margin-bottom:8px;text-transform:uppercase;letter-spacing:0.06em}
#hud .row{display:flex;justify-content:space-between;gap:14px;padding:2px 0}
#hud .row b{color:#ffd7a8;font-variant-numeric:tabular-nums;font-weight:600}
#hud .status{margin-top:8px;padding:5px 10px;border-radius:6px;font-weight:700;
  text-align:center;font-size:10px;letter-spacing:0.08em;text-transform:uppercase;}
.status.drive{background:var(--blue-50);color:var(--blue-80)}
.status.hold{background:var(--coral-50);color:var(--coral-80);animation:pulse 1.4s ease-in-out infinite}
.status.arrive{background:var(--green-50);color:var(--green-80)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.55}}
#legend{position:absolute;bottom:14px;left:14px;padding:10px 14px;
  background:var(--panel);border:1px solid var(--border);border-radius:10px;
  font-size:10px;line-height:1.7;backdrop-filter:blur(6px);z-index:10;}
#legend .dot{display:inline-block;width:9px;height:9px;border-radius:50%;
  margin-right:7px;vertical-align:middle}
#sol-log{position:absolute;bottom:132px;left:14px;padding:8px 11px;
  background:var(--panel);border:1px solid var(--border);border-radius:10px;
  font-size:10px;line-height:1.45;backdrop-filter:blur(6px);z-index:10;
  max-height:170px;overflow-y:auto;min-width:206px;max-width:268px;}
#sol-log .sol-log-title{font-size:9px;letter-spacing:0.12em;color:var(--dim);
  font-weight:700;margin-bottom:5px;text-transform:uppercase}
#sol-log .line{font-variant-numeric:tabular-nums;color:var(--text);padding:1px 0;white-space:nowrap}
#sol-log .line.hold{color:var(--coral-80)}
#sol-log .line.now{color:var(--accent);font-weight:600}
#controls{position:absolute;bottom:14px;left:50%;transform:translateX(-50%);
  padding:10px 18px;background:var(--panel);border:1px solid var(--border);
  border-radius:10px;display:flex;align-items:center;gap:12px;
  backdrop-filter:blur(6px);z-index:10;}
#controls button{background:#3d1f11;color:#ffd7a8;border:1px solid var(--border);
  border-radius:6px;padding:6px 12px;font-size:11px;cursor:pointer;font-weight:600;
  letter-spacing:0.03em;}
#controls button:hover{background:#5c2c17}
#controls input[type="range"]{width:200px;accent-color:var(--accent)}
#controls .sol-label{font-size:11px;color:var(--dim);min-width:64px;
  font-variant-numeric:tabular-nums}
#tooltip{position:absolute;padding:6px 10px;background:rgba(20,10,5,0.95);
  border:1px solid var(--border);border-radius:6px;font-size:11px;
  pointer-events:none;display:none;z-index:100;white-space:nowrap}

/* SIDEBAR */
#sidebar{position:absolute;top:0;right:0;bottom:0;width:340px;
  background:var(--bg);border-left:1px solid var(--border);
  overflow-y:auto;padding:20px;font-size:12px;}
#sidebar header{display:flex;justify-content:space-between;align-items:center;
  padding-bottom:14px;border-bottom:1px solid var(--border);}
#sidebar h2{margin:0;font-size:14px;font-weight:600;color:#ffd7a8;letter-spacing:0.02em}
#sidebar .sub{font-size:10px;color:var(--dim);margin-top:3px;text-transform:uppercase;letter-spacing:0.06em}
#pill{padding:3px 8px;border-radius:999px;font-size:9px;font-weight:700;
  letter-spacing:0.08em;text-transform:uppercase;background:var(--green-50);
  color:var(--green-80);border:1px solid #1f5030}
#pill.stale{background:var(--coral-50);color:var(--coral-80)}
.stats{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:16px 0}
.stat{padding:10px;background:var(--panel);border:1px solid var(--border);
  border-radius:8px;text-align:center}
.stat b{display:block;font-size:18px;font-weight:600;color:#ffd7a8;
  font-variant-numeric:tabular-nums}
.stat small{display:block;margin-top:2px;font-size:9px;color:var(--dim);
  text-transform:uppercase;letter-spacing:0.05em}
h3{font-size:11px;font-weight:600;margin:18px 0 8px;color:var(--text);
  text-transform:uppercase;letter-spacing:0.08em}
.tl{display:grid;gap:2px}
.tl-row{display:grid;grid-template-columns:44px 1fr 40px;align-items:center;
  gap:8px;padding:7px 10px;background:var(--panel);
  border:1px solid var(--border);border-radius:6px;font-size:11px;}
.tl-row.hl{border-color:#8a4020;background:rgba(255,80,64,0.06)}
.tl-row.current{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent) inset}
.tl-row .d b{display:block;font-weight:600;font-size:11px}
.tl-row .d small{display:block;font-size:9px;color:var(--dim);
  margin-top:1px;font-variant-numeric:tabular-nums}
.tl-row .body{font-size:10px;color:var(--dim);line-height:1.4}
.tl-row .body b{color:var(--text);font-weight:600;font-size:11px;display:block}
.tl-row .pill{justify-self:end;font-size:8px;font-weight:700;
  padding:3px 6px;border-radius:999px;letter-spacing:0.06em;text-transform:uppercase}
.pill.drive{background:var(--blue-50);color:var(--blue-80)}
.pill.hold{background:var(--coral-50);color:var(--coral-80)}
.pill.arrive{background:var(--green-50);color:var(--green-80)}
.dep{display:grid;grid-template-columns:22px 1fr 50px;align-items:center;
  gap:8px;padding:8px 10px;background:var(--panel);
  border:1px solid var(--border);border-radius:6px;font-size:11px;margin-bottom:2px;}
.dep.winner{border-color:#1f5030}
.dep .rank{text-align:center;font-size:13px;font-weight:600;color:var(--dim)}
.dep.winner .rank{color:var(--green-80)}
.dep .body b{display:block;font-size:11px;font-weight:600}
.dep .body small{display:block;font-size:9px;color:var(--dim);margin-top:2px}
.dep .eta{text-align:right}
.dep .eta b{display:block;font-size:13px;font-weight:600;font-variant-numeric:tabular-nums}
.dep .eta small{font-size:8px;color:var(--dim);text-transform:uppercase;letter-spacing:0.05em}
#sidebar footer{margin-top:16px;padding-top:10px;border-top:1px solid var(--border);
  font-size:9px;color:var(--fade);font-variant-numeric:tabular-nums}
.err{padding:14px;border:1px solid var(--coral-80);border-radius:8px;
  color:var(--coral-80);background:var(--coral-50);font-size:11px}

@media (max-width:900px){
  #stage{right:0;bottom:280px}
  #sidebar{top:auto;left:0;right:0;bottom:0;width:100%;height:280px;
    border-left:none;border-top:1px solid var(--border)}
  #sol-log{top:14px;bottom:auto;left:268px;max-height:132px}
}
</style></head>
<body>

<div id="stage">
  <div id="scene"></div>

  <div id="hud">
    <h1 id="hud-title">Sol-Window Planner</h1>
    <div class="sub" id="hud-sub">Mission view</div>
    <div class="row"><span>Sol</span><b id="s-sol">0.0</b></div>
    <div class="row"><span>τ opacity</span><b id="s-tau">—</b></div>
    <div class="row"><span>Position</span><b id="s-pos">—</b></div>
    <div class="row"><span>Elevation</span><b id="s-elev">— m</b></div>
    <div class="status drive" id="s-status">READY</div>
  </div>

  <div id="sol-log">
    <div class="sol-log-title">Sol log</div>
    <div id="sol-log-lines"></div>
  </div>

  <div id="legend">
    <div><span class="dot" style="background:#ff8a30"></span>Planned route</div>
    <div><span class="dot" style="background:#ffb060"></span>Rover trail</div>
    <div><span class="dot" style="background:#40e0ff"></span>Water deposits</div>
    <div><span class="dot" style="background:#40ff80"></span>Rover start</div>
    <div style="margin-top:5px;color:var(--fade)">drag: orbit · scroll: zoom</div>
  </div>

  <div id="controls">
    <button id="btn-play">▶ Play</button>
    <button id="btn-reset">↻</button>
    <input id="scrub" type="range" min="0" max="1000" value="0">
    <span class="sol-label" id="sol-label">Sol 0.0</span>
    <button id="btn-cam">📷 Fly</button>
  </div>

  <div id="tooltip"></div>
</div>

<aside id="sidebar">
  <header>
    <div>
      <h2 id="side-title">Sol-Window · Live</h2>
      <div class="sub" id="side-sub">Loading…</div>
    </div>
    <span id="pill">● LIVE</span>
  </header>
  <div id="side-content"></div>
  <footer>
    Reads <b>demo/plan.json</b> · re-run <b>python -m sol_window.demo</b> to refresh
  </footer>
</aside>

<script type="importmap">
{"imports":{
  "three":"https://unpkg.com/three@0.160.0/build/three.module.js",
  "three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"
}}
</script>

<script type="module">
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';

const D = __PAYLOAD__;
document.getElementById('hud-title').textContent = D.title;
document.getElementById('hud-sub').textContent =
  `${D.route.length} waypoints · ${D.deposits[0].name}`;

// ============================================================
// ALL TUNABLES — edit here for the live demo
// ============================================================
const CONFIG = {
  colors: {
    marsSky: 0x1a0a05,
    fog: 0x2a1508,
    sun: 0xffd8a0,
    rim: 0x8060ff,
    hemiSky: 0xffa060,
    hemiGround: 0x1a0a05,
    ribbon: 0xff8a30,
    ribbonGlow: 0xffc070,
    trail: 0xffb060,
    hold: 0xff2a18,
    roverBody: 0xd8d0c0,
    roverPanel: 0x1a2a5a,
    panelStrip: 0x4ad0ff,
    wheel: 0x1a1a1a,
    arm: 0x6a6054,
    deposit: 0x40e0ff,
    depositWinner: 0xffb060,
    start: 0x40ff80,
    dust: 0xc08050,
    stars: 0xfff6e8,
  },
  scales: {
    zScale: 0.25,
    roverScale: 1.0,
    ribbonWidth: 1.25,
    ribbonLift: 0.95,
    wheelRadius: 0.52,
    hexRadius: 1.35,
    hexHeight: 9.2,
    beamHeight: 60,
    beamRadius: 0.38,
    ringRadius: 2.35,
    holdHaloRadius: 4.4,
    holdLightDistance: 24,
    normalJitter: 0.16,
  },
  opacities: {
    ribbon: 0.88,
    ribbonEdge: 0.35,
    beam: 0.26,
    ring: 0.78,
    dustMax: 0.55,
    starMax: 0.92,
    holdHalo: 0.38,
  },
  glow: {
    holdLightIntensity: 3.4,
    holdPulseHz: 1.65,
    chaseSpeed: 0.035,
    chaseRadius: 1.15,
    chaseIntensity: 2.15,
    chaseRange: 16,
    panelStripEmissive: 0.9,
  },
  stars: {
    count: 2400,
    radius: 2200,
  },
  sun: {
    intensity: 2.05,
    shadowIntensity: 1.55,
    ambient: 0.22,
    rim: 0.18,
    hemi: 0.28,
  },
  animation: {
    solSeconds: 0.55,
    wheelSpeed: 11,
    ringSpin: 0.42,
  },
  fog: {
    density: 0.004,
    stormBoost: 0.008,
  },
};

const zScale = CONFIG.scales.zScale;

// ============================================================
// SCENE SETUP
// ============================================================
const stage = document.getElementById('scene');
const scene = new THREE.Scene();
scene.background = new THREE.Color(CONFIG.colors.marsSky);
scene.fog = new THREE.FogExp2(CONFIG.colors.fog, CONFIG.fog.density);

function stageSize(){ return {w: stage.clientWidth, h: stage.clientHeight}; }

const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 8000);
camera.position.set(D.w*0.85, D.h*0.85, Math.max(D.w,D.h)*0.55);

const renderer = new THREE.WebGLRenderer({antialias:true, alpha:false});
renderer.setPixelRatio(devicePixelRatio);
renderer.setSize(stageSize().w, stageSize().h);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.12;
stage.appendChild(renderer.domElement);
camera.aspect = stageSize().w/stageSize().h;
camera.updateProjectionMatrix();

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.target.set(D.w/2, D.h/2, 0);
controls.minDistance = 20;
controls.maxDistance = 1200;

// ============================================================
// LIGHTS
// ============================================================
const sun = new THREE.DirectionalLight(CONFIG.colors.sun, CONFIG.sun.intensity);
sun.position.set(D.w*1.4, D.h*1.4, 350);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.camera.left = -D.w; sun.shadow.camera.right = D.w;
sun.shadow.camera.top = D.h; sun.shadow.camera.bottom = -D.h;
sun.shadow.camera.near = 1;
sun.shadow.camera.far = 2200;
sun.shadow.bias = -0.00035;
sun.shadow.normalBias = 0.65;
if ('intensity' in sun.shadow) sun.shadow.intensity = CONFIG.sun.shadowIntensity;
scene.add(sun);
scene.add(new THREE.AmbientLight(0x604030, CONFIG.sun.ambient));

const rim = new THREE.DirectionalLight(CONFIG.colors.rim, CONFIG.sun.rim);
rim.position.set(-D.w, -D.h, 300);
scene.add(rim);

const hemi = new THREE.HemisphereLight(CONFIG.colors.hemiSky, CONFIG.colors.hemiGround, CONFIG.sun.hemi);
scene.add(hemi);

// ============================================================
// TERRAIN
// ============================================================
const geo = new THREE.PlaneGeometry(D.w, D.h, D.w-1, D.h-1);
geo.rotateX(-Math.PI/2);
geo.translate(D.w/2, D.h/2, 0);
const pos = geo.attributes.position;
for (let i=0; i<pos.count; i++){
  const x=i%D.w, z=Math.floor(i/D.w);
  pos.setY(i, (D.elev[z*D.w+x]-D.eMin)*zScale);
}
geo.computeVertexNormals();

// Micro-roughness: perturb normals from elevation-derived noise (not a texture)
{
  const nrm = geo.attributes.normal;
  const na = nrm.array;
  const jitter = CONFIG.scales.normalJitter;
  for (let i=0; i<pos.count; i++){
    const x=i%D.w, z=Math.floor(i/D.w);
    const e0 = D.elev[z*D.w+x];
    const eR = D.elev[z*D.w + Math.min(D.w-1, x+1)];
    const eD = D.elev[Math.min(D.h-1, z+1)*D.w + x];
    const h1 = Math.sin(e0*12.9898 + x*78.233 + z*37.719) * 43758.5453;
    const n1 = h1 - Math.floor(h1);
    const h2 = Math.sin(e0*4.123 + eR*2.17 + x*0.37) * 9187.31;
    const n2 = h2 - Math.floor(h2);
    const ridge = (e0 - eR) + (e0 - eD);
    na[i*3]   += (n1 - 0.5) * jitter + ridge * 0.004;
    na[i*3+1] += (n2 - 0.35) * jitter * 0.15;
    na[i*3+2] += (n2 - 0.5) * jitter + ridge * 0.003;
  }
  for (let i=0; i<pos.count; i++){
    const ix=i*3;
    const lx=na[ix], ly=na[ix+1], lz=na[ix+2];
    const len = Math.hypot(lx, ly, lz) || 1;
    na[ix]=lx/len; na[ix+1]=ly/len; na[ix+2]=lz/len;
  }
  nrm.needsUpdate = true;
}

const colors = new Float32Array(pos.count*3);
const c = new THREE.Color();
for (let i=0; i<pos.count; i++){
  const x=i%D.w, z=Math.floor(i/D.w);
  const eV=D.elev[z*D.w+x], tcl=D.terrainClass[z*D.w+x];
  const norm=(eV-D.eMin)/Math.max(D.eMax-D.eMin,1);
  const hueJitter = ((x*7 + z*13) % 100) / 1000;
  c.setHSL(0.045 + norm*0.03 + hueJitter, 0.58, 0.24 + norm*0.22);
  if (tcl===2) c.setRGB(c.r*1.15, c.g*1.05, c.b*0.65);  // sand
  if (tcl===1) c.setRGB(c.r*0.82, c.g*0.82, c.b*0.85);  // bedrock
  if (tcl===3) c.setRGB(0.14, 0.09, 0.07);              // rock
  colors[i*3]=c.r; colors[i*3+1]=c.g; colors[i*3+2]=c.b;
}
geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

const terrainMat = new THREE.MeshStandardMaterial({
  vertexColors:true, roughness:0.97, metalness:0.02,
});
const terrain = new THREE.Mesh(geo, terrainMat);
terrain.receiveShadow = true;
terrain.castShadow = true;
scene.add(terrain);

const mountains = new THREE.Group();
for (let k=0; k<12; k++){
  const shape = new THREE.Shape();
  const startA = Math.random()*Math.PI*2;
  const cx = D.w/2 + Math.cos(startA)*D.w*1.3;
  const cz = D.h/2 + Math.sin(startA)*D.h*1.3;
  shape.moveTo(-40, 0);
  for (let x=-40; x<=40; x+=4){
    shape.lineTo(x, 20 + 25*Math.sin(x*0.15 + k) + 15*Math.random());
  }
  shape.lineTo(40, 0);
  shape.closePath();
  const mgeo = new THREE.ShapeGeometry(shape);
  const mmat = new THREE.MeshBasicMaterial({
    color: new THREE.Color(0x2a1508).lerp(new THREE.Color(0x1a0a05), Math.random()*0.5),
    side: THREE.DoubleSide, transparent: true, opacity: 0.85,
  });
  const m = new THREE.Mesh(mgeo, mmat);
  m.position.set(cx, 0, cz);
  m.lookAt(D.w/2, 0, D.h/2);
  m.rotateY(Math.PI/2);
  mountains.add(m);
}
scene.add(mountains);

// ============================================================
// HELPERS
// ============================================================
function toWorld(row, col, lift=1){
  const rr=Math.max(0,Math.min(D.h-1,Math.round(row)));
  const cc=Math.max(0,Math.min(D.w-1,Math.round(col)));
  const y=(D.elev[rr*D.w+cc]-D.eMin)*zScale+lift;
  return new THREE.Vector3(col, y, row);
}

function hash01(n){
  const x = Math.sin(n * 127.1) * 43758.5453;
  return x - Math.floor(x);
}

// ============================================================
// ROUTE — raised orange ribbon + slow chase glow
// ============================================================
const routePts = D.route.map(([r,c])=>toWorld(r,c, CONFIG.scales.ribbonLift));

function buildRibbon(pts, width){
  const n = pts.length;
  const positions = [];
  const up = new THREE.Vector3(0,1,0);
  for (let i=0; i<n; i++){
    const p = pts[i];
    const p0 = pts[Math.max(0, i-1)];
    const p1 = pts[Math.min(n-1, i+1)];
    const dir = new THREE.Vector3().subVectors(p1, p0);
    if (dir.lengthSq() < 1e-8) dir.set(0,0,1);
    dir.normalize();
    const side = new THREE.Vector3().crossVectors(up, dir);
    if (side.lengthSq() < 1e-8) side.set(1,0,0);
    side.normalize().multiplyScalar(width * 0.5);
    const L = p.clone().add(side); L.y += 0.05;
    const R = p.clone().sub(side); R.y += 0.05;
    positions.push(L, R);
  }
  const idx = [];
  for (let i=0; i<n-1; i++){
    const a=i*2, b=i*2+1, c=i*2+2, d=i*2+3;
    idx.push(a,b,c, b,d,c);
  }
  const g = new THREE.BufferGeometry();
  const arr = new Float32Array(positions.length * 3);
  positions.forEach((v,i)=>{ arr[i*3]=v.x; arr[i*3+1]=v.y; arr[i*3+2]=v.z; });
  g.setAttribute('position', new THREE.BufferAttribute(arr, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

const ribbonMat = new THREE.MeshStandardMaterial({
  color: CONFIG.colors.ribbon,
  emissive: CONFIG.colors.ribbon,
  emissiveIntensity: 0.35,
  roughness: 0.45,
  metalness: 0.15,
  transparent: true,
  opacity: CONFIG.opacities.ribbon,
  side: THREE.DoubleSide,
});
const ribbon = new THREE.Mesh(buildRibbon(routePts, CONFIG.scales.ribbonWidth), ribbonMat);
ribbon.receiveShadow = true;
scene.add(ribbon);

const chaseGlow = new THREE.Mesh(
  new THREE.SphereGeometry(CONFIG.glow.chaseRadius, 14, 12),
  new THREE.MeshBasicMaterial({
    color: CONFIG.colors.ribbonGlow, transparent: true, opacity: 0.95, fog: false,
  })
);
const chaseLight = new THREE.PointLight(CONFIG.colors.ribbonGlow, CONFIG.glow.chaseIntensity, CONFIG.glow.chaseRange);
chaseGlow.add(chaseLight);
scene.add(chaseGlow);

const drivenGeo = new THREE.BufferGeometry();
drivenGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(routePts.length*3), 3));
drivenGeo.setDrawRange(0, 0);
const drivenLine = new THREE.Line(drivenGeo, new THREE.LineBasicMaterial({
  color: CONFIG.colors.trail, linewidth: 3,
}));
scene.add(drivenLine);

const waypointGroup = new THREE.Group();
D.route.forEach(([r,c], i) => {
  const sol = D.routeSols[i] || 0;
  const tauAtSol = D.tau[Math.min(sol, D.tau.length-1)] || 0.5;
  const color = tauAtSol > 1.0 ? 0xff5040 : (tauAtSol > 0.7 ? 0xffb060 : 0xffd7a8);
  const dot = new THREE.Mesh(
    new THREE.SphereGeometry(0.4, 8, 8),
    new THREE.MeshBasicMaterial({color, transparent:true, opacity:0.6})
  );
  dot.position.copy(toWorld(r, c, 1.2));
  waypointGroup.add(dot);
});
scene.add(waypointGroup);

// ============================================================
// DEPOSITS — hex prism + rotating ring + 60 m fading beam
// ============================================================
const depMeshes = [];
const beamVert = `
  varying float vH;
  void main(){
    vH = position.y;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0);
  }
`;
const beamFrag = `
  uniform vec3 uColor;
  uniform float uOpacity;
  varying float vH;
  void main(){
    float t = clamp(vH / 60.0, 0.0, 1.0);
    float fade = (1.0 - t) * (1.0 - t);
    gl_FragColor = vec4(uColor, uOpacity * fade);
  }
`;

D.deposits.forEach((d, idx) => {
  const g = new THREE.Group();
  const isWinner = idx === 0;
  const col = isWinner ? CONFIG.colors.depositWinner : CONFIG.colors.deposit;

  const hex = new THREE.Mesh(
    new THREE.CylinderGeometry(CONFIG.scales.hexRadius*0.55, CONFIG.scales.hexRadius, CONFIG.scales.hexHeight, 6),
    new THREE.MeshStandardMaterial({
      color: col,
      emissive: col,
      emissiveIntensity: isWinner ? 0.7 : 0.55,
      roughness: 0.28, metalness: 0.55,
    })
  );
  hex.position.y = CONFIG.scales.hexHeight * 0.5;
  hex.castShadow = true;
  g.add(hex);

  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(CONFIG.scales.ringRadius, 0.12, 8, 36),
    new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: CONFIG.opacities.ring })
  );
  ring.rotation.x = Math.PI/2;
  ring.position.y = 1.4;
  g.add(ring);

  const beamGeo = new THREE.CylinderGeometry(
    CONFIG.scales.beamRadius*0.15, CONFIG.scales.beamRadius, CONFIG.scales.beamHeight, 10, 1, true
  );
  beamGeo.translate(0, CONFIG.scales.beamHeight * 0.5, 0);
  const beamMat = new THREE.ShaderMaterial({
    uniforms: {
      uColor: { value: new THREE.Color(col) },
      uOpacity: { value: CONFIG.opacities.beam },
    },
    vertexShader: beamVert,
    fragmentShader: beamFrag,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending,
    fog: false,
  });
  const beam = new THREE.Mesh(beamGeo, beamMat);
  g.add(beam);

  g.position.copy(toWorld(d.row, d.col, 1));
  Object.assign(g.userData, d, { ring, beam, hex });
  scene.add(g);
  depMeshes.push(g);
});

// ============================================================
// START MARKER
// ============================================================
const startGroup = new THREE.Group();
const startCone = new THREE.Mesh(
  new THREE.ConeGeometry(1.6, 5, 8),
  new THREE.MeshStandardMaterial({color:CONFIG.colors.start, emissive:0x109050, emissiveIntensity:0.8})
);
startCone.rotation.x = Math.PI;
startCone.position.y = 4;
startGroup.add(startCone);
const startRing = new THREE.Mesh(
  new THREE.TorusGeometry(2.5, 0.2, 8, 20),
  new THREE.MeshBasicMaterial({color:CONFIG.colors.start, transparent:true, opacity:0.9})
);
startRing.rotation.x = Math.PI/2;
startGroup.add(startRing);
startGroup.position.copy(toWorld(D.start[0], D.start[1], 1));
scene.add(startGroup);

// ============================================================
// 6-WHEEL ROCKER-BOGIE ROVER
// ============================================================
function makeRover(){
  const roverG = new THREE.Group();
  roverG.scale.setScalar(CONFIG.scales.roverScale);
  const bodyMat = new THREE.MeshStandardMaterial({
    color: CONFIG.colors.roverBody, metalness: 0.68, roughness: 0.34,
  });
  const darkMat = new THREE.MeshStandardMaterial({
    color: 0x3a3834, metalness: 0.5, roughness: 0.48,
  });
  const armMat = new THREE.MeshStandardMaterial({
    color: CONFIG.colors.arm, metalness: 0.55, roughness: 0.4,
  });
  const wheelMat = new THREE.MeshStandardMaterial({
    color: CONFIG.colors.wheel, roughness: 0.92, metalness: 0.08,
  });

  const chassis = new THREE.Mesh(new THREE.BoxGeometry(2.35, 0.82, 3.45), bodyMat);
  chassis.position.y = 1.22;
  chassis.castShadow = true;
  roverG.add(chassis);

  const belly = new THREE.Mesh(new THREE.BoxGeometry(1.7, 0.28, 2.6), darkMat);
  belly.position.y = 0.78;
  roverG.add(belly);

  const panel = new THREE.Mesh(
    new THREE.BoxGeometry(3.15, 0.08, 2.95),
    new THREE.MeshStandardMaterial({
      color: CONFIG.colors.roverPanel, metalness: 0.55, roughness: 0.16,
      emissive: CONFIG.colors.roverPanel, emissiveIntensity: 0.18,
    })
  );
  panel.position.set(0, 1.72, -0.12);
  panel.castShadow = true;
  roverG.add(panel);
  for (let i=1; i<4; i++){
    const grid = new THREE.Mesh(
      new THREE.BoxGeometry(3.15, 0.09, 0.04),
      new THREE.MeshBasicMaterial({color:0x40608a})
    );
    grid.position.set(0, 1.73, -1.35 + i*0.7);
    roverG.add(grid);
  }
  const strip = new THREE.Mesh(
    new THREE.BoxGeometry(0.1, 0.045, 2.7),
    new THREE.MeshStandardMaterial({
      color: CONFIG.colors.panelStrip,
      emissive: CONFIG.colors.panelStrip,
      emissiveIntensity: CONFIG.glow.panelStripEmissive,
      roughness: 0.2, metalness: 0.4,
    })
  );
  strip.position.set(1.42, 1.78, -0.12);
  roverG.add(strip);

  const ant = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.05, 2.15, 8), armMat);
  ant.position.set(-0.72, 2.85, 0.85);
  roverG.add(ant);
  const dish = new THREE.Mesh(new THREE.CircleGeometry(0.32, 18), darkMat);
  dish.position.set(-0.72, 3.95, 0.85);
  dish.rotation.x = -0.95;
  roverG.add(dish);

  const armRoot = new THREE.Group();
  armRoot.position.set(1.28, 1.05, 0.55);
  const seg1 = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.16, 1.35), armMat);
  seg1.position.set(0.12, 0.02, 0.35);
  seg1.rotation.y = 0.4;
  armRoot.add(seg1);
  const seg2 = new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.14, 1.05), armMat);
  seg2.position.set(0.42, -0.22, 0.95);
  seg2.rotation.set(0.85, 0.35, 1.15);
  armRoot.add(seg2);
  const scoop = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.1, 0.32), darkMat);
  scoop.position.set(0.62, -0.48, 1.15);
  armRoot.add(scoop);
  roverG.add(armRoot);

  const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.1, 1.75, 8), armMat);
  mast.position.set(0.12, 2.55, 1.32);
  roverG.add(mast);
  const head = new THREE.Mesh(new THREE.BoxGeometry(0.52, 0.38, 0.42), darkMat);
  head.position.set(0.12, 3.48, 1.32);
  roverG.add(head);

  const wr = CONFIG.scales.wheelRadius;
  const wheelGeo = new THREE.CylinderGeometry(wr, wr, 0.36, 16);
  const wheels = [];
  function addWheel(x, y, z){
    const pivot = new THREE.Group();
    pivot.position.set(x, y, z);
    const mesh = new THREE.Mesh(wheelGeo, wheelMat);
    mesh.rotation.z = Math.PI/2;
    mesh.castShadow = true;
    pivot.add(mesh);
    const hub = new THREE.Mesh(new THREE.CylinderGeometry(wr*0.32, wr*0.32, 0.4, 8), darkMat);
    hub.rotation.z = Math.PI/2;
    pivot.add(hub);
    roverG.add(pivot);
    wheels.push(pivot);
    return pivot;
  }
  function armBox(len, thick=0.13){
    const m = new THREE.Mesh(new THREE.BoxGeometry(thick, thick, len), armMat);
    m.castShadow = true;
    return m;
  }
  function knuckle(x, z, h=0.58){
    const k = new THREE.Mesh(new THREE.CylinderGeometry(0.065, 0.065, h, 6), armMat);
    k.position.set(x, wr + h*0.5, z);
    roverG.add(k);
  }

  const track = 1.52;
  const zF = 1.58, zM = 0.02, zR = -1.52;
  addWheel(-track, wr, zF); addWheel(-track, wr, zM); addWheel(-track, wr, zR);
  addWheel( track, wr, zF); addWheel( track, wr, zM); addWheel( track, wr, zR);
  [-1,1].forEach(s => {
    const x = s * track;
    knuckle(x, zF); knuckle(x, zM); knuckle(x, zR);
    const rocker = armBox(3.15, 0.15);
    rocker.position.set(x, 0.98, 0.08);
    rocker.rotation.x = 0.14;
    roverG.add(rocker);
    const drop = armBox(1.55, 0.11);
    drop.position.set(x, 0.82, 0.82);
    drop.rotation.x = -0.58;
    roverG.add(drop);
    const bogie = armBox(1.72, 0.12);
    bogie.position.set(x, 0.72, -0.72);
    bogie.rotation.x = 0.22;
    roverG.add(bogie);
    const link = armBox(1.05, 0.09);
    link.position.set(x, 1.05, -0.15);
    link.rotation.x = 0.55;
    roverG.add(link);
  });
  const diff = new THREE.Mesh(new THREE.BoxGeometry(track*2.05, 0.11, 0.16), armMat);
  diff.position.set(0, 1.32, 0.18);
  roverG.add(diff);

  const beacon = new THREE.Mesh(
    new THREE.SphereGeometry(0.28, 14, 14),
    new THREE.MeshBasicMaterial({color: CONFIG.colors.trail})
  );
  beacon.position.set(0, 1.55, 0);
  roverG.add(beacon);
  const beaconLight = new THREE.PointLight(CONFIG.colors.trail, 1.15, 14);
  beaconLight.position.set(0, 1.7, 0);
  roverG.add(beaconLight);

  const holdHalo = new THREE.Mesh(
    new THREE.SphereGeometry(CONFIG.scales.holdHaloRadius, 24, 16),
    new THREE.MeshBasicMaterial({
      color: CONFIG.colors.hold, transparent: true, opacity: 0,
      depthWrite: false, side: THREE.DoubleSide,
    })
  );
  holdHalo.position.y = 1.1;
  roverG.add(holdHalo);
  const holdLight = new THREE.PointLight(CONFIG.colors.hold, 0, CONFIG.scales.holdLightDistance);
  holdLight.position.set(0, 1.4, 0);
  roverG.add(holdLight);

  return {group: roverG, wheels, beacon, beaconLight, holdHalo, holdLight};
}

const roverParts = makeRover();
const rover = roverParts.group;
const wheels = roverParts.wheels;
rover.position.copy(routePts[0]);
scene.add(rover);

// ============================================================
// DUST PARTICLES
// ============================================================
const dustGeo = new THREE.BufferGeometry();
const N = 4000;
const dustArr = new Float32Array(N*3);
for (let i=0; i<N; i++){
  dustArr[i*3]   = Math.random()*D.w;
  dustArr[i*3+1] = Math.random()*90;
  dustArr[i*3+2] = Math.random()*D.h;
}
dustGeo.setAttribute('position', new THREE.BufferAttribute(dustArr, 3));
const dustMat = new THREE.PointsMaterial({
  color: CONFIG.colors.dust, size:1.0, transparent:true, opacity:0.0, sizeAttenuation:true,
});
const dust = new THREE.Points(dustGeo, dustMat);
scene.add(dust);

// ============================================================
// STARFIELD — fog-exempt backdrop; opacity rises with τ
// ============================================================
const starGeo = new THREE.BufferGeometry();
const N_STAR = CONFIG.stars.count;
const starArr = new Float32Array(N_STAR*3);
const starCol = new Float32Array(N_STAR*3);
const Rstar = CONFIG.stars.radius;
for (let i=0; i<N_STAR; i++){
  const theta = hash01(i*3.1) * Math.PI * 2;
  const phi = hash01(i*7.7) * Math.PI * 0.48 + 0.06;
  starArr[i*3]   = D.w/2 + Rstar*Math.sin(phi)*Math.cos(theta);
  starArr[i*3+1] = Rstar*Math.cos(phi) * 0.72 + 80;
  starArr[i*3+2] = D.h/2 + Rstar*Math.sin(phi)*Math.sin(theta);
  const b = 0.65 + hash01(i*11.3)*0.35;
  starCol[i*3]=b; starCol[i*3+1]=b*0.96; starCol[i*3+2]=b*0.88;
}
starGeo.setAttribute('position', new THREE.BufferAttribute(starArr, 3));
starGeo.setAttribute('color', new THREE.BufferAttribute(starCol, 3));
const starMat = new THREE.PointsMaterial({
  color: CONFIG.colors.stars, size: 1.65, transparent: true, opacity: 0,
  vertexColors: true, sizeAttenuation: true, depthWrite: false, fog: false,
});
scene.add(new THREE.Points(starGeo, starMat));

// ============================================================
// SOL LOG (from D.routeSols + D.tau only)
// ============================================================
function buildSolLog(){
  const n = D.route.length;
  const perSol = {};
  let pathLen = 0;
  for (let i=1; i<n; i++){
    const a=D.route[i-1], b=D.route[i];
    const d = Math.hypot(b[0]-a[0], b[1]-a[1]);
    pathLen += d;
    const sol = D.routeSols[i] ?? D.routeSols[i-1] ?? 0;
    perSol[sol] = (perSol[sol] || 0) + d;
  }
  const kmPer = pathLen > 0 ? D.totalKm / pathLen : 0;
  const maxSol = D.routeSols.length ? Math.max(...D.routeSols) : 0;
  const el = document.getElementById('sol-log-lines');
  const parts = [];
  for (let s=0; s<=maxSol; s++){
    const tv = D.tau[Math.min(s, D.tau.length-1)] ?? 0;
    const hold = tv > 1.0;
    const km = (perSol[s] || 0) * kmPer;
    const text = hold
      ? `Sol ${s} · τ ${tv.toFixed(2)} · HOLD`
      : `Sol ${s} · τ ${tv.toFixed(2)} · DRIVE ${km.toFixed(1)} km`;
    parts.push(`<div class="line${hold?' hold':''}" data-sol="${s}">${text}</div>`);
  }
  el.innerHTML = parts.join('');
}
buildSolLog();

function highlightSolLog(sol){
  const cur = Math.floor(sol);
  document.querySelectorAll('#sol-log .line').forEach(el => {
    el.classList.toggle('now', Number(el.dataset.sol) === cur);
  });
}

// ============================================================
// UI CONTROLS
// ============================================================
let progress = 0, playing = false, flying = false;
const scrub = document.getElementById('scrub');
const btnPlay = document.getElementById('btn-play');
btnPlay.onclick = () => { playing = !playing; btnPlay.textContent = playing?'❚❚ Pause':'▶ Play'; };
document.getElementById('btn-reset').onclick = () => { progress = 0; scrub.value = 0; };
document.getElementById('btn-cam').onclick = e => {
  flying = !flying; e.target.textContent = flying?'📷 Orbit':'📷 Fly';
};
scrub.oninput = () => {
  progress = scrub.value / 1000;
  playing = false; btnPlay.textContent = '▶ Play';
};

const tooltip = document.getElementById('tooltip');
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();
renderer.domElement.addEventListener('mousemove', e => {
  const rect = renderer.domElement.getBoundingClientRect();
  mouse.x = ((e.clientX-rect.left)/rect.width)*2 - 1;
  mouse.y = -((e.clientY-rect.top)/rect.height)*2 + 1;
  raycaster.setFromCamera(mouse, camera);
  const hits = raycaster.intersectObjects(depMeshes, true);
  if (hits.length){
    let g = hits[0].object;
    while (g.parent && !g.userData.name) g = g.parent;
    const d = g.userData;
    tooltip.innerHTML = `<b>${d.name}</b><br>Depth ${d.depth.toFixed(1)} m · Yield ${Math.round(d['yield'])} kg/m²`;
    tooltip.style.left = (e.clientX+12)+'px';
    tooltip.style.top = (e.clientY+12)+'px';
    tooltip.style.display = 'block';
  } else tooltip.style.display = 'none';
});

// ============================================================
// HUD UPDATE
// ============================================================
function updateHUD(sol, roverPos){
  const ti = Math.min(D.tau.length-1, Math.max(0, Math.floor(sol)));
  const tv = D.tau[ti];
  document.getElementById('s-sol').textContent = sol.toFixed(1);
  document.getElementById('s-tau').textContent = tv.toFixed(2);
  document.getElementById('s-pos').textContent = `(${Math.round(roverPos.z)}, ${Math.round(roverPos.x)})`;
  document.getElementById('s-elev').textContent = Math.round(roverPos.y/zScale + D.eMin) + ' m';
  const st = document.getElementById('s-status');
  const holding = progress < 1 && tv > 1.0;
  if (progress >= 1){ st.className = 'status arrive'; st.textContent = 'ARRIVED · SAMPLING ICE'; }
  else if (holding){ st.className = 'status hold'; st.textContent = 'SAFETY HOLD · τ > 1.0'; }
  else { st.className = 'status drive'; st.textContent = 'DRIVING'; }
  document.getElementById('sol-label').textContent = `Sol ${sol.toFixed(1)}`;
  highlightSolLog(sol);

  dustMat.opacity = Math.max(0, Math.min(CONFIG.opacities.dustMax, (tv-0.6)*1.2));
  const dark = Math.max(0, Math.min(1, (tv-0.5)*0.9));
  scene.background = new THREE.Color().setRGB(
    0.10*(1-dark*0.7), 0.04*(1-dark*0.5), 0.02
  );
  sun.intensity = Math.max(0.15, CONFIG.sun.intensity*Math.exp(-1.2*tv));
  starMat.opacity = dark * CONFIG.opacities.starMax;
  scene.fog.density = CONFIG.fog.density + dark*CONFIG.fog.stormBoost;

  const pulse = 0.5 + 0.5 * Math.sin(clock.elapsedTime * CONFIG.glow.holdPulseHz * Math.PI * 2);
  if (holding){
    roverParts.holdLight.intensity = CONFIG.glow.holdLightIntensity * (0.55 + 0.45*pulse);
    roverParts.holdHalo.material.opacity = CONFIG.opacities.holdHalo * (0.4 + 0.6*pulse);
    roverParts.holdHalo.scale.setScalar(0.85 + 0.25*pulse);
  } else {
    roverParts.holdLight.intensity = 0;
    roverParts.holdHalo.material.opacity = 0;
  }
  return { tv, holding };
}

// ============================================================
// SIDEBAR LIVE UPDATE (reads plan.json)
// ============================================================
const pill = document.getElementById('pill');
const sideContent = document.getElementById('side-content');
const sideSub = document.getElementById('side-sub');
let lastJson = null;

async function fetchPlan(){
  try {
    const r = await fetch('plan.json?t=' + Date.now(), {cache:'no-store'});
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return await r.json();
  } catch (e){ return {_err: e.message}; }
}
function fmt(n, d=1){ return n.toFixed(d); }

function renderSidebar(p, currentSol){
  if (p._err){
    sideContent.innerHTML = `<div class="err">Cannot read <b>plan.json</b> yet.<br><small>${p._err}</small><br><br>If running as file://, start the server:<br><code>python serve.py</code></div>`;
    pill.className = 'stale';
    pill.textContent = '● WAITING';
    return;
  }
  pill.className = '';
  pill.textContent = '● LIVE';
  const w = p.winner;
  sideSub.textContent = `Start (${p.start.row}, ${p.start.col}) → ${w.name.split(' ')[0]}`;

  sideContent.innerHTML = `
    <div class="stats">
      <div class="stat"><b>${fmt(w.eta_sols)}</b><small>ETA sols</small></div>
      <div class="stat"><b>${fmt(w.distance_km)}</b><small>km driven</small></div>
      <div class="stat"><b>${w.idle_sols}</b><small>sols idled</small></div>
      <div class="stat"><b>${Math.round(w.yield_kg_m2)}</b><small>kg/m² yield</small></div>
      <div class="stat"><b>${fmt(w.peak_tau, 2)}</b><small>peak τ</small></div>
      <div class="stat"><b>${w.waypoints}</b><small>waypoints</small></div>
    </div>

    <h3>Mission timeline</h3>
    <div class="tl">${p.timeline.map(ev => `
      <div class="tl-row ${ev.status==='hold'?'hl':''} ${Math.floor(currentSol)===ev.sol?'current':''}">
        <span class="d"><b>Sol ${ev.sol}</b><small>τ ${fmt(ev.tau,2)}</small></span>
        <span class="body">
          <b>${ev.status==='hold' ? (ev.tau>1.3?'Storm peak':'Storm hold')
              : ev.status==='arrive' ? 'Arrival · sample ice'
              : ev.sol===0 ? 'Depart' : 'Continue traverse'}</b>
          waypoint (${ev.row}, ${ev.col})
        </span>
        <span class="pill ${ev.status}">${ev.status}</span>
      </div>`).join('')}</div>

    <h3>Ranked deposits</h3>
    ${p.ranked_deposits.map((d,i)=>`
      <div class="dep ${i===0?'winner':''}">
        <span class="rank">${i+1}</span>
        <span class="body"><b>${d.name}</b><small>yield ${Math.round(d.yield_kg_m2)} kg/m² · ${fmt(d.distance_km)} km</small></span>
        <span class="eta"><b>${fmt(d.eta_sols)}</b><small>sols</small></span>
      </div>`).join('')}
  `;
}

async function pollLoop(){
  const p = await fetchPlan();
  lastJson = p;
  renderSidebar(p, currentSol);
  setTimeout(pollLoop, 2000);
}
let currentSol = 0;
pollLoop();

// ============================================================
// ANIMATION LOOP
// ============================================================
const clock = new THREE.Clock();
function animate(){
  const dt = clock.getDelta();
  if (playing){
    progress += dt / (D.tau.length * CONFIG.animation.solSeconds);
    if (progress > 1){ progress = 1; playing = false; btnPlay.textContent = '▶ Play'; }
    scrub.value = progress * 1000;
  }
  const iF = progress * (routePts.length - 1);
  const i0 = Math.floor(iF), i1 = Math.min(routePts.length-1, i0+1), t = iF-i0;
  rover.position.lerpVectors(routePts[i0], routePts[i1], t);
  rover.position.y += 1.0;
  if (i1 > i0){
    const dir = new THREE.Vector3().subVectors(routePts[i1], routePts[i0]);
    rover.rotation.y = Math.atan2(dir.x, dir.z);
  }

  drivenGeo.setDrawRange(0, i0+1);
  const dp = drivenGeo.attributes.position.array;
  for (let k=0; k<=i0; k++){
    dp[k*3] = routePts[k].x;
    dp[k*3+1] = routePts[k].y + 0.2;
    dp[k*3+2] = routePts[k].z;
  }
  drivenGeo.attributes.position.needsUpdate = true;

  const sol = D.routeSols.length
    ? D.routeSols[Math.min(i0, D.routeSols.length-1)] + (i1>i0 ? t*0.25 : 0)
    : progress * D.tau.length;
  currentSol = sol;
  const { tv, holding } = updateHUD(sol, rover.position);

  const driving = playing && progress < 1 && !holding;
  wheels.forEach(w => { if (driving) w.rotation.x += dt * CONFIG.animation.wheelSpeed; });

  const cu = (clock.elapsedTime * CONFIG.glow.chaseSpeed) % 1;
  const cF = cu * (routePts.length - 1);
  const c0 = Math.floor(cF), c1 = Math.min(routePts.length-1, c0+1);
  chaseGlow.position.lerpVectors(routePts[c0], routePts[c1], cF-c0);
  chaseGlow.position.y += 0.35;

  const dparr = dustGeo.attributes.position.array;
  const wind = 8 + dustMat.opacity * 15;
  for (let i=0; i<N; i++){
    dparr[i*3] += dt * wind;
    if (dparr[i*3] > D.w+50) dparr[i*3] = -50;
  }
  dustGeo.attributes.position.needsUpdate = true;

  roverParts.beacon.scale.setScalar(1 + 0.4 * Math.sin(clock.elapsedTime*5));
  roverParts.beaconLight.intensity = 1.2 + 0.5 * Math.sin(clock.elapsedTime*5);

  depMeshes.forEach((g, i) => {
    g.userData.ring.rotation.z += dt * CONFIG.animation.ringSpin;
    g.userData.ring.scale.setScalar(1 + 0.12 * Math.sin(clock.elapsedTime*2 + i));
    g.userData.beam.material.uniforms.uOpacity.value =
      CONFIG.opacities.beam * (0.82 + 0.18 * Math.sin(clock.elapsedTime*1.5 + i));
  });

  if (flying){
    controls.enabled = false;
    const look = rover.position.clone();
    const off = new THREE.Vector3(
      Math.cos(clock.elapsedTime*0.25)*30, 22,
      Math.sin(clock.elapsedTime*0.25)*30,
    );
    camera.position.copy(look.clone().add(off));
    camera.lookAt(look);
  } else {
    controls.enabled = true;
    controls.update();
  }
  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}
animate();

function resize(){
  const {w, h} = stageSize();
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
}
addEventListener('resize', resize);
</script>
</body></html>
"""
