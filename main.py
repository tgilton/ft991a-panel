"""
main.py — FastAPI backend for the FT-991A web control panel

This is the application server. It does three things:
  1. Exposes REST API endpoints for rig commands (frequency, mode, levels, etc.)
  2. Runs a WebSocket server that pushes live rig state to browser clients
  3. Serves the static web UI from the /static directory

Architecture:
  Browser  <—WebSocket—>  main.py  <—TCP—>  rigctld  <—serial—>  FT-991A
  Browser  <—REST POST—>  main.py  <—TCP—>  rigctld
  Browser  <—REST GET—>   main.py  <—HTTPS—> PSKReporter / NOAA

The rig poll loop runs every 1 second and broadcasts state to all
connected WebSocket clients. The propagation loop runs every 3 minutes.

To start the server:
  cd ~/ham-panel
  source venv/bin/activate
  uvicorn main:app --host 0.0.0.0 --port 8000

To add a new rig control:
  1. Add a function to rig.py (get_xxx / set_xxx)
  2. Add a Pydantic model and @app.post("/api/xxx") endpoint here
  3. Add the UI control to static/index.html
  See DEVELOPER.md for a full walkthrough.
"""

import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import rig
import propagation
import advisor

app = FastAPI(title="FT-991A Control Panel")

# ─────────────────────────────────────────────
# Request models (Pydantic validates incoming JSON)
# ─────────────────────────────────────────────

class FreqRequest(BaseModel):
    freq: int           # frequency in Hz

class ModeRequest(BaseModel):
    mode: str           # e.g. "USB", "PKTUSB"
    bandwidth: int = 0  # passband in Hz, 0 = rig default

class LevelRequest(BaseModel):
    level: str          # Hamlib level name e.g. "RFPOWER", "AGC", "METER"
    value: float        # new value

class FuncRequest(BaseModel):
    func: str           # Hamlib function name e.g. "NB", "NR", "ANF"
    value: bool         # True = on, False = off

# ─────────────────────────────────────────────
# REST API endpoints
# ─────────────────────────────────────────────

@app.get("/api/state")
def get_state():
    """Return current rig state as JSON. Useful for debugging."""
    return rig.get_rig_state()

@app.post("/api/freq")
def set_freq(req: FreqRequest):
    """Set VFO A frequency in Hz."""
    ok = rig.set_freq(req.freq)
    return {"ok": ok, "freq": req.freq}

@app.post("/api/mode")
def set_mode(req: ModeRequest):
    """Set operating mode and optional passband."""
    ok = rig.set_mode(req.mode, req.bandwidth)
    return {"ok": ok, "mode": req.mode}

@app.post("/api/level")
def set_level(req: LevelRequest):
    """Set a named Hamlib level (RFPOWER, AF, RF, AGC, METER, etc.)."""
    ok = rig.set_level(req.level, req.value)
    return {"ok": ok}

@app.post("/api/func")
def set_func(req: FuncRequest):
    """Toggle a named Hamlib function (NB, NR, ANF, etc.)."""
    ok = rig.set_func(req.func, req.value)
    return {"ok": ok}

@app.post("/api/preamp/cycle")
def preamp_cycle():
    """Cycle preamp through IPO → AMP1 → AMP2 → IPO."""
    val = rig.cycle_preamp()
    return {"ok": True, "preamp": val, "label": rig.PREAMP_LABELS[val]}

class AdvisorRequest(BaseModel):
    question: str = ""
    clear_history: bool = False

# Conversation history stored server-side per session
# Simple single-user implementation — extend to dict keyed by session ID for multi-user
conversation_history: list = []

@app.post("/api/advisor/stream")
async def stream_advice(req: AdvisorRequest):
    """
    Stream Claude's response using Server-Sent Events.
    Maintains conversation history for multi-turn context.
    """
    global conversation_history

    if req.clear_history:
        conversation_history = []

    rig_state = rig.get_rig_state()
    prop_state = await propagation.get_propagation_state()
    question = req.question.strip() or None

    # Capture the full response to append to history after streaming
    full_response = []

    def generate():
        for chunk in advisor.stream_advice(
            rig_state, prop_state, conversation_history, question
        ):
            full_response.append(chunk)
            # Server-Sent Events format
            yield "data: " + chunk + "\n\n"
        # Signal end of stream
        yield "data: [DONE]\n\n"

        # Append this exchange to conversation history
        context = advisor.format_context(rig_state, prop_state, question)
        conversation_history.append({"role": "user", "content": context})
        conversation_history.append({"role": "assistant", "content": "".join(full_response)})
        # Keep history to last 6 exchanges (3 turns) to manage token costs
        if len(conversation_history) > 6:
            conversation_history[:] = conversation_history[-6:]

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/api/advisor/clear")
async def clear_history():
    """Clear conversation history to start a fresh context."""
    global conversation_history
    conversation_history = []
    return {"ok": True}

@app.get("/api/propagation")
async def get_propagation():
    """
    Return current band activity and solar data.
    Results are cached for 3 minutes — PSKReporter rate-limits heavy queries.
    """
    return await propagation.get_propagation_state()

# ─────────────────────────────────────────────
# WebSocket — live rig state and propagation push
# ─────────────────────────────────────────────

# Set of currently connected browser WebSocket clients
clients: set = set()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint. Each browser tab that opens the panel connects here.
    The server pushes rig state every second and propagation data every 3 min.
    The client doesn't need to send anything — receives only.
    """
    await websocket.accept()
    clients.add(websocket)
    try:
        while True:
            # Keep connection alive — client sends nothing, we just wait
            await websocket.receive_text()
    except WebSocketDisconnect:
        clients.discard(websocket)


async def broadcast(message: str):
    """Send a JSON string to all connected clients, removing dead connections."""
    dead = set()
    for ws in clients:
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    clients.difference_update(dead)


async def poll_rig():
    """
    Background task: poll rig state every second and push to all clients.
    Rig state messages are plain JSON dicts (no 'type' field).
    The browser distinguishes them from propagation messages by absence of type.
    """
    while True:
        try:
            state = rig.get_rig_state()
            await broadcast(json.dumps(state))
        except Exception as e:
            print(f"Poll error: {e}")
        await asyncio.sleep(1.0)


async def push_propagation():
    """Fetch fresh propagation data and push to all connected clients."""
    try:
        state = await propagation.get_propagation_state()
        # Wrap with type tag so browser can distinguish from rig state
        await broadcast(json.dumps({"type": "propagation", "data": state}))
    except Exception as e:
        print(f"Propagation poll error: {e}")


async def poll_propagation():
    """
    Background task: refresh propagation data every 3 minutes.
    PSKReporter asks clients not to query more often than every 5 minutes,
    but 3 minutes works reliably in practice for the senderGrid query.
    """
    await asyncio.sleep(3.0)  # let rig poll establish first
    while True:
        await push_propagation()
        await asyncio.sleep(180.0)


@app.on_event("startup")
async def startup():
    """Launch background polling tasks when the server starts."""
    asyncio.create_task(poll_rig())
    asyncio.create_task(poll_propagation())


# ─────────────────────────────────────────────
# Static file serving — must be last
# ─────────────────────────────────────────────

# Serves static/index.html and any future CSS/JS files
# Must be mounted last so API routes take priority
app.mount("/", StaticFiles(directory="static", html=True), name="static")
