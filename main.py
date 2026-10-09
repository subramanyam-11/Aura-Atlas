import asyncio
import json
import os
import urllib.request
import zipfile
import io
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sim.simulator import Simulator
from sim.grid import load_movingai_map, auto_stations

app     = FastAPI(title="Warehouse Swarm Coordinator")
sim     = Simulator()
clients : list[WebSocket] = []
sim_task = None
STATIC_DIR = Path(__file__).resolve().parent / "static"
MAPS_DIR   = Path(__file__).resolve().parent / "maps"
MAPS_DIR.mkdir(parents=True, exist_ok=True)
MAPF_BASE = "https://movingai.com/benchmarks/mapf/"

async def broadcast(state):
    dead = []
    for ws in list(clients):
        try:
            await ws.send_text(json.dumps(state))
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in clients:
            clients.remove(ws)

@app.get("/", response_class=HTMLResponse)
async def root():
    index_file = STATIC_DIR / "index.html"
    return HTMLResponse(index_file.read_text(encoding="utf-8"))

@app.websocket("/ws")
async def ws_ep(ws: WebSocket):
    await ws.accept()
    clients.append(ws)
    s = sim.state_dict()
    s['grid'] = sim.grid.to_dict()
    await ws.send_text(json.dumps(s))
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        if ws in clients:
            clients.remove(ws)
    except Exception:
        if ws in clients:
            clients.remove(ws)

class Cell       (BaseModel): x: int; y: int
class Order      (BaseModel): priority: int = 1; qty: int = 1
class MapSwitch  (BaseModel): map_name: str = "custom"; num_robots: int = 5; robot_capacity: int = 1
class StationPri (BaseModel): priority: int = 1

@app.post("/control/start")
async def start():
    global sim_task
    if not sim.running:
        sim_task = asyncio.create_task(sim.run_loop(broadcast))
    return {"ok": True}

@app.post("/control/pause")
async def pause():
    global sim_task
    sim.running = False
    if sim_task:
        sim_task.cancel()
        sim_task = None
    s = sim.state_dict()
    s['grid'] = sim.grid.to_dict()
    await broadcast(s)
    return {"ok": True}

@app.post("/control/reset")
async def reset():
    global sim, sim_task
    if sim_task:
        sim_task.cancel()
        sim_task = None
    sim = Simulator()
    s = sim.state_dict()
    s['grid'] = sim.grid.to_dict()
    await broadcast(s)
    return {"ok": True}

@app.post("/event/block")
async def block(c: Cell):
    sim.block_cell(c.x, c.y)
    s = sim.state_dict()
    s['grid'] = sim.grid.to_dict()
    await broadcast(s)
    return {"ok": True}

@app.post("/event/fail/{rid}")
async def fail(rid: int):
    sim.fail_robot(rid)
    return {"ok": True}

@app.post("/event/order")
async def order(o: Order):
    sim.add_order(o.priority, o.qty)
    return {"ok": True}

@app.post("/station/{sid}/priority")
async def station_pri(sid: int, b: StationPri):
    sim.set_station_priority(sid, b.priority)
    return {"ok": True}

@app.get("/map/available")
async def avail():
    local = [f.replace(".map", "") for f in os.listdir(MAPS_DIR) if f.endswith(".map")]
    return {"maps": ["custom"] + sorted(local)}

@app.post("/map/download/{name}")
async def dl_map(name: str):
    path = MAPS_DIR / f"{name}.map"
    if path.exists():
        return {"ok": True}
    try:
        # Try MovingAI .map.zip first
        downloaded = False
        try:
            req = urllib.request.Request(MAPF_BASE + name + ".map.zip", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=12) as r:
                z = zipfile.ZipFile(io.BytesIO(r.read()))
                fn = next(n for n in z.namelist() if n.endswith('.map'))
                with open(path, 'wb') as f_out:
                    f_out.write(z.read(fn))
                downloaded = True
        except Exception:
            pass

        if not downloaded:
            # Fallback to direct .map URL if not html menu
            req2 = urllib.request.Request(MAPF_BASE + name + ".map", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req2, timeout=12) as r2:
                content = r2.read()
                if b"<!DOCTYPE" in content or b"<html" in content:
                    return {"ok": False, "error": f"Map {name} returned HTML menu instead of map file."}
                with open(path, 'wb') as f_out:
                    f_out.write(content)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/map/switch")
async def sw_map(req: MapSwitch):
    global sim, sim_task
    if sim_task:
        sim_task.cancel()
        sim_task = None
    if req.map_name == "custom":
        sim = Simulator(num_robots=req.num_robots, robot_capacity=req.robot_capacity)
    else:
        path = MAPS_DIR / f"{req.map_name}.map"
        if not path.exists():
            return {"ok": False, "error": "Map not found. Download first."}
        grid = load_movingai_map(str(path))
        picks, drops = auto_stations(grid, count=max(4, req.num_robots // 3))
        grid.pick_stations = picks
        grid.drop_stations = drops
        sim = Simulator(grid=grid, num_robots=req.num_robots, robot_capacity=req.robot_capacity)
    s = sim.state_dict()
    s['grid'] = sim.grid.to_dict()
    await broadcast(s)
    return {"ok": True}
