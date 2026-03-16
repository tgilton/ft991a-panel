import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import rig

app = FastAPI()

# --- REST endpoints ---

@app.get("/api/state")
def get_state():
    return rig.get_rig_state()

class FreqRequest(BaseModel):
    freq: int

@app.post("/api/freq")
def set_freq(req: FreqRequest):
    ok = rig.set_freq(req.freq)
    return {"ok": ok, "freq": req.freq}

class ModeRequest(BaseModel):
    mode: str
    bandwidth: int = 0

@app.post("/api/mode")
def set_mode(req: ModeRequest):
    ok = rig.set_mode(req.mode, req.bandwidth)
    return {"ok": ok, "mode": req.mode}

class LevelRequest(BaseModel):
    level: str
    value: float

@app.post("/api/level")
def set_level(req: LevelRequest):
    ok = rig.set_level(req.level, req.value)
    return {"ok": ok}

class FuncRequest(BaseModel):
    func: str
    value: bool

@app.post("/api/func")
def set_func(req: FuncRequest):
    ok = rig.set_func(req.func, req.value)
    return {"ok": ok}

@app.post("/api/preamp/cycle")
def preamp_cycle():
    val = rig.cycle_preamp()
    return {"ok": True, "preamp": val, "label": rig.PREAMP_LABELS[val]}

# --- WebSocket ---

clients = set()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        clients.discard(websocket)

async def poll_rig():
    while True:
        try:
            state = rig.get_rig_state()
            if clients:
                msg = json.dumps(state)
                dead = set()
                for ws in clients:
                    try:
                        await ws.send_text(msg)
                    except Exception:
                        dead.add(ws)
                clients.difference_update(dead)
        except Exception as e:
            print(f"Poll error: {e}")
        await asyncio.sleep(1.0)

@app.on_event("startup")
async def startup():
    asyncio.create_task(poll_rig())

# --- Serve static UI ---
app.mount("/", StaticFiles(directory="static", html=True), name="static")
